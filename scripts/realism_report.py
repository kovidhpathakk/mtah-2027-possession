"""Does the damaged practice data look like our match? Every measure we can think of, side by side.

We test every method on practice matches damaged to look like our tracking (possession/damage.py).
If the damage misses a property of our data, a method can look good in practice and do nothing on
our match: the touch rule did exactly that, because practice balls moved more sharply than ours
until 2026-10-26. This report compares our match with the practice matches (clean and damaged) on
a broad list of measures and flags every large difference, so a gap shows up before a method
depends on it. Re-run it whenever the fault kit or the methods change.

Measures are taken on graded frames; "live" means the frame is live in the method's own labels
(v4 on every source, so the definition is the same everywhere).

    python scripts/realism_report.py

Prints aggregates only.
"""

import os
import sys
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from possession import cleanup, control  # noqa: E402
from possession.damage import damage, our_profile  # noqa: E402
from possession.external import load_source, sources  # noqa: E402
from possession.methods import METHODS  # noqa: E402

# Params
FPS = 25
FLAG = 1.5          # flag a measure when practice differs from ours by more than this factor
SCENARIO = "mixed"


def measures(t, graded):
    """name -> value for one match."""
    pitch = np.array(t["pitch"])
    clean = cleanup.clean(t)
    ball = clean["ball"] * pitch
    players = clean["players"] * pitch
    seen = graded & ~np.isnan(ball[:, 0])
    labels = METHODS["v4"](t)
    live = graded & np.isin(labels, ["H", "A"])
    out = {}

    # ball presence and gaps
    out["ball visible, share of graded frames"] = seen.sum() / graded.sum()
    gaps = []
    edges = np.diff(np.concatenate(([0], (graded & ~seen).astype(np.int8), [0])))
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        gaps.append((b - a) / FPS)
    gaps = np.array(gaps) if gaps else np.array([0.0])
    hours = graded.sum() / FPS / 3600
    out["ball gaps of 1-5 s, per hour"] = ((gaps >= 1) & (gaps < 5)).sum() / hours
    out["ball gaps of 5 s+, per hour"] = (gaps >= 5).sum() / hours

    # ball motion in live play with the ball in view
    v = control.ball_velocity(ball)
    speed = np.linalg.norm(v, axis=1)
    k = control.TOUCH_SPAN
    dv = np.full(len(v), np.nan)
    dv[k:-k] = np.linalg.norm(v[2 * k:] - v[:-2 * k], axis=1)
    m = live & seen & ~np.isnan(dv)
    out["ball speed median, live (m/s)"] = np.median(speed[m])
    out["ball speed p90, live (m/s)"] = np.percentile(speed[m], 90)
    out["ball velocity change >= 3 m/s in 0.24 s, live"] = np.mean(dv[m] >= 3)
    out["ball velocity change >= 7 m/s in 0.24 s, live"] = np.mean(dv[m] >= 7)
    heading = np.arctan2(v[:, 1], v[:, 0])
    turn = np.full(len(v), np.nan)
    turn[12:-12] = np.abs(np.angle(np.exp(1j * (heading[24:] - heading[:-24]))))
    moving = m & (speed > 3) & ~np.isnan(turn)
    out["ball turns > 45 deg within 1 s, moving ball"] = np.mean(turn[moving] > np.pi / 4)

    # players
    pv = np.full(players.shape, np.nan)
    pv[2:-2] = (players[4:] - players[:-4]) * FPS / 4
    pspeed = np.linalg.norm(pv, axis=2)[live]
    pspeed = pspeed[~np.isnan(pspeed)]
    out["player speed median, live (m/s)"] = np.median(pspeed)
    out["player speed p90, live (m/s)"] = np.percentile(pspeed, 90)
    present = ~np.isnan(players[:, :, 0])
    count = present.sum(axis=1)[graded]
    out["tracked objects per frame"] = count.mean()
    out["frames with fewer than 18 objects"] = np.mean(count < 18)

    # the ball and the players around it
    dist = control.team_distances(clean["players"], clean["ball"], clean["team"], tuple(pitch))
    nearest = np.nanmin(dist, axis=1)
    mm = live & seen & np.isfinite(nearest)
    out["nearest player to ball, median, live (m)"] = np.median(nearest[mm])
    out["live frames with a player within 1 m of the ball"] = np.mean(nearest[mm] < 1.0)
    out["live frames with both teams within 1 m (duel)"] = np.mean((dist[mm] < 1.0).all(axis=1))

    # what the method sees
    events = control.control_events_touch(dist, ball)
    minutes = live.sum() / FPS / 60
    out["control events per live minute (v4)"] = (events[live] != -1).sum() / minutes
    switches = np.flatnonzero((labels[1:] != labels[:-1]) & np.isin(labels[1:], ["H", "A"])
                              & np.isin(labels[:-1], ["H", "A"]) & graded[1:])
    out["live team changes per live minute (v4)"] = len(switches) / minutes
    out["dead-ball share of graded frames (v4)"] = np.mean(labels[graded] == "D")
    return out


if __name__ == '__main__':
    warnings.simplefilter("ignore")
    ours_t = load_source("tactical")
    graded = np.zeros(len(ours_t["ball"]), dtype=bool)
    for _, a, b in ours_t["halves"]:
        graded[a:b + 1] = True
    ours = measures(ours_t, graded)
    del ours_t

    profile = our_profile()
    clean_rows, damaged_rows = [], []
    for name in [s for s in sources() if s not in ("tactical", "broadcast")]:
        t = load_source(name)
        g = t["labels"] != "X"
        clean_rows.append(measures(t, g))
        damaged_rows.append(measures(damage(t, SCENARIO, np.random.default_rng(0), profile), g))
        del t

    print("{:<48} {:>9} {:>11} {:>16}   {}".format("measure", "ours", "practice", "practice", "flag"))
    print("{:<48} {:>9} {:>11} {:>16}".format("", "", "clean", "damaged (range)"))
    flagged = 0
    for key, value in ours.items():
        c = np.mean([r[key] for r in clean_rows])
        d = [r[key] for r in damaged_rows]
        dm = np.mean(d)
        ratio = (dm / value) if value else np.inf
        flag = ratio > FLAG or ratio < 1 / FLAG
        flagged += flag
        print("{:<48} {:>9.3g} {:>11.3g} {:>7.3g} ({:.3g}-{:.3g})   {}".format(
            key, value, c, dm, min(d), max(d), "<-- differs {:.1f}x".format(ratio) if flag else ""))
    print("\n{} of {} measures differ by more than {}x between our match and the damaged practice"
          " matches.".format(flagged, len(ours), FLAG))
