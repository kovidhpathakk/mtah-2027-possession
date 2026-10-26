"""What is wrong with the tracking? Every suspected fault, measured as whole-match counts.

The ATD is automatic and unreviewed (DATA.md), and each kind of fault breaks a different part of a
possession model: an object on the touchline that is not a player wins "nearest player" votes, an
identity swap fakes a sprint, an invented straight-line path hides an occlusion, a stray ball far
from play hands possession to whoever stands near it. We found one fault by accident (an Athletic
label in Barca's goal); this looks for the others on purpose, before v2 is built on top of them.

Sections:
  1 objects     how many objects each team has per frame
  2 where       objects outside the pitch, and long tracks that live there (staff, assistants)
  3 jumps       one-frame moves no human can make: identity swaps
  4 speed       does the speed column agree with speed computed from positions, and is it late?
  5 invented    frozen frames and perfectly straight 1 s paths: positions the tracker filled in
  6 ball        flicker, balls off the pitch, impossible ball jumps, balls far from everyone
  7 coverage    does the object count drop when play is near one end (camera coverage)?
  8 sides       which way each team attacks per half, and who is deepest in each goal
  9 pairs       same-team objects on top of each other: duplicates

    python scripts/audit_tracking.py                      # tactical, graded halves
    python scripts/audit_tracking.py --source broadcast   # broadcast, frames with play in view
    python scripts/audit_tracking.py --source dfl-J03WMX  # another match, as a control

Run on the clean open-data matches (possession/external.py) it is a control: faults it reports
there are the audit's own false alarms, so the same numbers on our match are not real faults.

Prints aggregates only: counts, shares, percentiles. Never a frame, a row or one object's path.
"""

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES  # noqa: E402

from possession.external import load_source, sources  # noqa: E402
from possession.tracking import PITCH  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
LENGTH, WIDTH = PITCH
HOME, AWAY = 0, 1
TEAM_NAMES = {HOME: "home (Barca)", AWAY: "away (Athletic)"}
MIN_OBJECTS_IN_VIEW = 10     # broadcast: frames with fewer objects are close-ups or crowd shots
OUTSIDE_MARGIN = 0.5         # m beyond a line before an object counts as off the pitch
FAR_OUTSIDE = 2.0            # m; further than this is clearly not a player in play
LONG_TRACK = 10 * FPS        # a track this long that stays off the pitch is not a player
TOUCHLINE_BAND = 3.0         # m either side of a touchline: where assistant referees run
HUMAN_MAX = 12.0             # m/s; faster than any sprinter
JUMP = 3.0                   # m in one frame (75 m/s): a teleport, not a movement
STRAIGHT_TOL = 0.02          # m; a 1 s path closer than this to a straight line was filled in
BOX_DEPTH, BOX_HALF_WIDTH = 16.5, 20.16
FAR_BALL = 40.0              # m from a goal: keepers are alone at the back, nobody else is there
DUPLICATE = 1.0              # m between two same-team objects
X_BINS = np.arange(0, LENGTH + 15, 15.0)


def pct(x):
    return "{:.1%}".format(x) if np.isfinite(x) else "n/a"


def runs(mask):
    """[(start, stop)] half-open runs of True."""
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)


def frame_mask(halves, players):
    """Frames to audit: inside the halves where they are known (graded halves on tactical), else
    frames with play in view (broadcast, which has no halves on its own timeline)."""
    if halves:
        mask = np.zeros(len(players), dtype=bool)
        for _, first, last in halves:
            mask[first:last + 1] = True
        return mask
    return (~np.isnan(players[:, :, 0])).sum(axis=1) >= MIN_OBJECTS_IN_VIEW


def objects(present, team, mask):
    print("\n1 OBJECTS PER FRAME")
    home = present[:, team == HOME].sum(axis=1)[mask]
    away = present[:, team == AWAY].sum(axis=1)[mask]
    total = home + away
    print("  mean home {:.1f}, away {:.1f}, total {:.1f}".format(home.mean(), away.mean(),
                                                                 total.mean()))
    for name, share in [("home > 11", (home > 11).mean()), ("away > 11", (away > 11).mean()),
                        ("total > 22", (total > 22).mean()), ("total < 18", (total < 18).mean()),
                        ("home < 9", (home < 9).mean()), ("away < 9", (away < 9).mean())]:
        print("  frames with {:<11} {:>7}".format(name, pct(share)))


def where(players, present, team, mask):
    print("\n2 OBJECTS OUTSIDE THE PITCH")
    x, y = players[:, :, 0], players[:, :, 1]
    beyond = np.fmax(np.fmax(-x, x - LENGTH), np.fmax(-y, y - WIDTH))  # m past the nearest line
    near_touchline = np.fmin(np.abs(y), np.abs(y - WIDTH)) <= TOUCHLINE_BAND
    for code in (HOME, AWAY):
        cells = present[mask][:, team == code]
        b = beyond[mask][:, team == code][cells]
        print("  {:<16} object-frames off the pitch: >{} m {:>6}, >{} m {:>6}".format(
            TEAM_NAMES[code], OUTSIDE_MARGIN, pct((b > OUTSIDE_MARGIN).mean()),
            FAR_OUTSIDE, pct((b > FAR_OUTSIDE).mean())))

    # Whole tracks: a track that lives off the pitch, or along one touchline, for 10 s or more is
    # a substitute, a coach or an assistant referee, not a player in play.
    graded_seconds = mask.sum() / FPS
    for code in (HOME, AWAY):
        off_n = off_s = line_n = line_s = 0
        for slot in np.flatnonzero(team == code):
            for start, stop in zip(*runs(present[:, slot] & mask)):
                if stop - start < LONG_TRACK:
                    continue
                if (beyond[start:stop, slot] > OUTSIDE_MARGIN).mean() >= 0.8:
                    off_n, off_s = off_n + 1, off_s + (stop - start) / FPS
                elif near_touchline[start:stop, slot].mean() >= 0.8:
                    line_n, line_s = line_n + 1, line_s + (stop - start) / FPS
        print("  {:<16} tracks >= {} s mostly off the pitch: {} ({:.1f} object-min, {} of time)"
              .format(TEAM_NAMES[code], LONG_TRACK // FPS, off_n, off_s / 60,
                      pct(off_s / graded_seconds)))
        print("  {:<16} tracks >= {} s mostly on a touchline:  {} ({:.1f} object-min, {} of time)"
              .format("", LONG_TRACK // FPS, line_n, line_s / 60, pct(line_s / graded_seconds)))


def jumps(players, team, mask):
    print("\n3 ONE-FRAME JUMPS (identity swaps)")
    step = np.linalg.norm(players[1:] - players[:-1], axis=2)  # m per frame; NaN unless both seen
    keep = mask[1:] & mask[:-1]
    for code in (HOME, AWAY):
        s = step[keep][:, team == code]
        s = s[~np.isnan(s)]
        speed = s * FPS
        print("  {:<16} speed p50 {:.1f}, p99 {:.1f}, p99.9 {:.1f} m/s; > {:.0f} m/s {:>6};"
              " jumps > {:.0f} m: {:,} ({:.1f} per min)".format(
                  TEAM_NAMES[code], *np.percentile(speed, [50, 99, 99.9]), HUMAN_MAX,
                  pct((speed > HUMAN_MAX).mean()), JUMP, int((s > JUMP).sum()),
                  (s > JUMP).sum() / (keep.sum() / FPS / 60)))


def centred_speed(xy, half=2):
    """m/s from the move between t-half and t+half. NaN at the edges and where either is missing."""
    out = np.full(xy.shape[:-1], np.nan)
    out[half:-half] = np.linalg.norm(xy[2 * half:] - xy[:-2 * half], axis=-1) * FPS / (2 * half)
    return out


def speed_check(players, speed, ball, ball_speed, mask):
    print("\n4 SPEED COLUMN vs SPEED FROM POSITIONS")
    derived = centred_speed(players)
    both = mask[:, None] & ~np.isnan(derived) & ~np.isnan(speed)
    col, der = speed[both].astype(float), derived[both]
    moving = der > 1.0
    print("  players: column median {:.2f}, from positions {:.2f} m/s; corr {:.3f};"
          " column/positions on moving objects: median {:.2f}".format(
              np.median(col), np.median(der), np.corrcoef(col, der)[0, 1],
              np.median(col[moving] / der[moving])))
    # Is the column late or early? Correlate it with positions shifted by k frames.
    sample = np.flatnonzero(mask)[::7]
    best = []
    for k in range(-15, 16):
        rows = sample[(sample + k >= 0) & (sample + k < len(derived))]
        a, b = speed[rows].astype(float).ravel(), derived[rows + k].ravel()
        ok = ~np.isnan(a) & ~np.isnan(b)
        best.append((np.corrcoef(a[ok], b[ok])[0, 1], k))
    corr, k = max(best)
    print("  best match when the column is compared with positions {} frames {} (corr {:.3f})"
          .format(abs(k), "later" if k > 0 else "earlier" if k < 0 else "same", corr))

    ball_derived = centred_speed(ball)
    seen = mask & ~np.isnan(ball[:, 0])
    filled = seen & ~np.isnan(ball_speed)
    both = filled & ~np.isnan(ball_derived)
    print("  ball: column filled on {} of visible frames".format(pct(filled.sum() / seen.sum())))
    if both.sum() > 100:
        col, der = ball_speed[both].astype(float), ball_derived[both]
        moving = der > 1.0
        print("  ball where filled: column median {:.2f}, from positions {:.2f} m/s; corr {:.3f};"
              " ratio on moving ball {:.2f}".format(np.median(col), np.median(der),
                                                    np.corrcoef(col, der)[0, 1],
                                                    np.median(col[moving] / der[moving])))


def straight_share(xy, mask, min_travel=0.5):
    """Share of moving 1 s windows whose path is a straight line at constant speed, within
    STRAIGHT_TOL. Real people and real balls curve and change pace; a filled-in gap does not."""
    n = (len(xy) - 1) // FPS * FPS
    starts = np.arange(0, n - FPS + 1, FPS)
    starts = starts[mask[starts] & mask[starts + FPS - 1]]
    window = xy[starts[:, None] + np.arange(FPS)]          # (windows, FPS, ..., 2)
    first, last = window[:, :1], window[:, -1:]
    t = (np.arange(FPS) / (FPS - 1)).reshape((1, FPS) + (1,) * (xy.ndim - 1))
    line = first + (last - first) * t
    deviation = np.nanmax(np.linalg.norm(window - line, axis=-1), axis=1)
    travel = np.linalg.norm(last[:, 0] - first[:, 0], axis=-1)
    complete = ~np.isnan(window[..., 0]).any(axis=1)
    moving = complete & (travel > min_travel)
    return (deviation[moving] < STRAIGHT_TOL).mean() if moving.any() else np.nan, moving.sum()


def invented(players, ball, mask):
    print("\n5 FILLED-IN POSITIONS")
    step = np.linalg.norm(players[1:] - players[:-1], axis=2)
    keep = (mask[1:] & mask[:-1])[:, None] & ~np.isnan(step)
    print("  object-frames with no movement at all: {}".format(pct((step[keep] == 0).mean())))
    # Whole frames identical to the previous one: a repeated (frozen) frame, not a still team.
    present = ~np.isnan(step)
    counted = present.sum(axis=1) >= 5
    frozen = counted & np.all((step == 0) | ~present, axis=1)
    rows = mask[1:] & mask[:-1] & counted
    print("  frames where every object is exactly where it was: {}".format(
        pct(frozen[rows].mean())))
    nonzero = np.abs(np.diff(players[:2000, :, 0], axis=0))
    nonzero = nonzero[np.isfinite(nonzero) & (nonzero > 0)]
    if len(nonzero):
        print("  smallest position step: {:.1f} mm".format(1000 * nonzero.min()))
    share, n = straight_share(players, mask)
    print("  players: moving 1 s paths that are perfectly straight: {} of {:,}".format(
        pct(share), n))
    share, n = straight_share(ball, mask)
    print("  ball:    moving 1 s paths that are perfectly straight: {} of {:,}".format(
        pct(share), n))


def ball_check(ball, players, mask):
    print("\n6 BALL")
    seen = ~np.isnan(ball[:, 0])
    starts, stops = runs(seen & mask)
    lengths = stops - starts
    short = lengths < 5
    print("  visible runs: {:,}, median {:.1f} s; runs < 5 frames: {} of runs, {} of visible"
          " frames".format(len(lengths), np.median(lengths) / FPS, pct(short.mean()),
                           pct(lengths[short].sum() / lengths.sum())))
    gap_starts, gap_stops = runs(~seen & mask)
    gaps = (gap_stops - gap_starts) / FPS
    if not len(gaps):
        gaps = np.array([0.0])  # the ball is never missing (clean data)
    print("  missing runs: {:,}; shortest {:.2f} s; p10/p50/p90 {:.1f} / {:.1f} / {:.1f} s".format(
        len(gaps), gaps.min(), *np.percentile(gaps, [10, 50, 90])))
    edges = [0, 1, 2, 5, 10, 20, 60, np.inf]
    counts, _ = np.histogram(gaps, edges)
    print("  missing runs by length: " + " | ".join(
        "{}-{} s: {}".format(a, b if np.isfinite(b) else "", c)
        for a, b, c in zip(edges[:-1], edges[1:], counts)))
    v = seen & mask
    x, y = ball[v, 0], ball[v, 1]
    beyond = np.fmax(np.fmax(-x, x - LENGTH), np.fmax(-y, y - WIDTH))
    print("  visible frames with the ball > {} m off the pitch: {}".format(
        FAR_OUTSIDE, pct((beyond > FAR_OUTSIDE).mean())))
    step = np.linalg.norm(ball[1:] - ball[:-1], axis=1)
    keep = mask[1:] & mask[:-1] & ~np.isnan(step)
    print("  ball moves > 2 m in one frame (50 m/s, faster than a hard shot): {:,} ({} of"
          " visible steps)".format(int((step[keep] > 2).sum()), pct((step[keep] > 2).mean())))
    speed = centred_speed(ball)
    s = speed[v & ~np.isnan(speed)]
    print("  speed from positions p10/p50/p90/p99: {:.1f} / {:.1f} / {:.1f} / {:.1f} m/s".format(
        *np.percentile(s, [10, 50, 90, 99])))
    nearest = np.nanmin(np.linalg.norm(players[v] - ball[v][:, None], axis=2), axis=1)
    slow = speed[v] < 1.0
    for far in (10, 20):
        alone = nearest > far
        print("  ball > {} m from every object: {} of visible frames; of those, slow: {}".format(
            far, pct(alone.mean()), pct((alone & slow).sum() / max(alone.sum(), 1))))


def coverage(players, ball, present, mask):
    print("\n7 OBJECT COUNT BY WHERE PLAY IS (ball x, or the objects' centre when it is missing)")
    focus = np.where(np.isnan(ball[:, 0]), np.nanmean(players[:, :, 0], axis=1), ball[:, 0])
    count = present.sum(axis=1)
    which = np.digitize(focus, X_BINS) - 1
    cells = []
    for b in range(len(X_BINS) - 1):
        rows = mask & (which == b)
        if rows.sum():
            cells.append("{:.0f}-{:.0f} m: {:.1f}".format(X_BINS[b], X_BINS[b + 1],
                                                          count[rows].mean()))
    print("  " + " | ".join(cells))


def sides(players, present, team, ball, halves):
    print("\n8 SIDES AND KEEPERS")
    if not halves:
        print("  skipped: no halves on this timeline")
        return
    for half, first, last in halves:
        rows = slice(first, last + 1)
        p, pr, b = players[rows], present[rows], ball[rows]
        mean_x = {code: np.nanmean(p[:, team == code, 0]) for code in (HOME, AWAY)}
        print("  half {}: mean x home {:.1f} m, away {:.1f} m".format(half, mean_x[HOME],
                                                                     mean_x[AWAY]))
        for code in (HOME, AWAY):
            # Each team defends the end it sits nearer to, relative to the other team: an
            # absolute halfway test fails when one side camps in the other half for a whole half.
            goal_x = 0.0 if mean_x[code] < mean_x[1 - code] else LENGTH
            depth = np.abs(p[:, :, 0] - goal_x)
            in_box = (depth <= BOX_DEPTH) & (np.abs(p[:, :, 1] - WIDTH / 2) <= BOX_HALF_WIDTH) & pr
            ball_far = np.abs(b[:, 0] - goal_x) > FAR_BALL  # NaN ball -> False: not judged
            judged = ball_far & in_box.any(axis=1)
            deepest = np.argmin(np.where(in_box, depth, np.inf), axis=1)
            wrong = judged & (team[deepest] != code)
            own_in_box = (in_box & (team == code)[None, :]).any(axis=1)
            print("    {:<16} ball far from its goal: {:,} frames; deepest object in its box"
                  " labelled the other team: {:,}; no own object in its box: {:,}".format(
                      TEAM_NAMES[code], int(ball_far.sum()), int(wrong.sum()),
                      int((ball_far & ~own_in_box).sum())))


def pairs(players, present, team, mask):
    print("\n9 SAME-TEAM OBJECTS ON TOP OF EACH OTHER")
    rows = np.flatnonzero(mask)[::5]  # every 5th frame is plenty for a share
    for code in (HOME, AWAY):
        p = players[rows][:, team == code]
        d = np.linalg.norm(p[:, :, None] - p[:, None, :], axis=3)
        idx = np.arange(d.shape[1])
        d[:, idx, idx] = np.inf
        close = np.nanmin(np.where(np.isnan(d), np.inf, d), axis=(1, 2)) < DUPLICATE
        print("  {:<16} frames with two objects within {} m: {}".format(
            TEAM_NAMES[code], DUPLICATE, pct(close.mean())))
    p = players[rows]
    home, away = p[:, team == HOME], p[:, team == AWAY]
    d = np.linalg.norm(home[:, :, None] - away[:, None, :], axis=3)
    close = np.nanmin(np.where(np.isnan(d), np.inf, d), axis=(1, 2)) < 0.3
    print("  {:<16} frames with a home and an away object within 0.3 m: {}".format(
        "both", pct(close.mean())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default="tactical", choices=sources())
    args = parser.parse_args()

    t = load_source(args.source)
    LENGTH, WIDTH = t["pitch"]  # the module-level pitch every section uses
    X_BINS = np.arange(0, LENGTH + 15, 15.0)
    scale = np.array(t["pitch"])
    players, ball = t["players"] * scale, t["ball"] * scale  # metres from here on
    present = ~np.isnan(players[:, :, 0])
    halves = t.get("halves")
    mask = frame_mask(halves, players)
    print("{}: {:,} frames audited ({:.1f} min), {} track slots".format(
        args.source, int(mask.sum()), mask.sum() / FPS / 60, len(t["team"])))

    with np.errstate(invalid="ignore", divide="ignore"):
        import warnings
        warnings.simplefilter("ignore", RuntimeWarning)
        objects(present, t["team"], mask)
        where(players, present, t["team"], mask)
        jumps(players, t["team"], mask)
        speed_check(players, t["speed"], ball, t["ball_speed"], mask)
        invented(players, ball, mask)
        ball_check(ball, players, mask)
        coverage(players, ball, present, mask)
        sides(players, present, t["team"], ball, halves)
        pairs(players, present, t["team"], mask)
