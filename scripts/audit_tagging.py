"""How far can we trust Smart Tagging? Checked against the tracking, over the whole match.

Smart Tagging is automatic (DATA.md): it has false positives, misses, and phases that do not line
up with possessions. We cannot check it against the full-match truth, which is private, and must
not tune against the public 5 minutes. What we can do is check it against a second, independent
automatic source -- the tracking -- on all 106 minutes. Where two independent sources agree, both
are probably right; where they disagree, at least one is wrong, and the pattern says which.

Sections:
  1 coverage    how much of the match the phases cover, and how often Team is N/A
  2 team        does the tagged team have the ball? Measured on clean frames only: ball within
                CONTROL m of one object and no opponent within PRESSURE m (Vidal-Codina's
                possession zone), so the tracking side of the comparison is trustworthy
  3 set pieces  per type: does the tag start where the ball reappears after a blackout, and is the
                ball where that restart happens (a touchline for a throw-in, a corner flag...)?
  4 misses      blackouts of 5 s or more: how many end with a set-piece tag nearby, and where the
                ball reappears for the ones that do not (restarts the tagging missed?)
  5 goals       is every goal tag followed by a long stoppage and a kickoff from the centre?

    python scripts/audit_tagging.py

Prints aggregates only.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "starter"))
import load_smart_tagging  # noqa: E402
from games import GAME, GAMES, half_video_blocks  # noqa: E402

from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
LENGTH, WIDTH = PITCH
HOME, AWAY, NOBODY = 0, 1, -1
TEAM_CODE = {"barcelona": HOME, "atletic club": AWAY}
SET_PIECES = "set pieces"
CONTROL = 1.5            # m, ball to the nearest object: that object has it
PRESSURE = 3.0           # m, no opponent this close, so it is not a duel
MIN_GAP = 5 * FPS        # the tactical tracker fills shorter blackouts itself (audit_tracking)
MATCH_WINDOW = 10 * FPS  # a tag "belongs" to a blackout whose end is within this of its start
EDGE = 3.0               # m from a line or a spot that still counts as "at" it


def restart_spot(ball):
    """Where on the pitch a ball position is, in restart terms. One name per position."""
    x, y = ball
    if np.isnan(x):
        return "unknown"
    near_end = min(x, LENGTH - x)
    off_centre = abs(y - WIDTH / 2)
    if near_end < EDGE + 2 and min(y, WIDTH - y) < EDGE + 2:
        return "corner"
    if near_end < 5.5 + EDGE and off_centre < 9.16 + EDGE:
        return "goal area"
    if min(y, WIDTH - y) < EDGE:
        return "touchline"
    if np.hypot(x - LENGTH / 2, off_centre) < EDGE:
        return "centre spot"
    if near_end < 16.5 and off_centre < 20.16:
        return "penalty box"
    return "open field"


EXPECTED_SPOT = {"throw-in": "touchline", "corner kick": "corner", "goal kick": "goal area",
                 "kick off (start)": "centre spot", "kick off (after goal)": "centre spot"}


def runs(mask):
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)


def controller(players, ball, team):
    """Per frame: team of the object in clear control of the ball, NOBODY otherwise."""
    out = np.full(len(ball), NOBODY, dtype=np.int8)
    seen = np.flatnonzero(~np.isnan(ball[:, 0]))
    d = np.linalg.norm(players[seen] - ball[seen][:, None], axis=2)
    d = np.where(np.isnan(d), np.inf, d)
    nearest = np.argmin(d, axis=1)
    near_team = team[nearest]
    opponent = np.where((team[None, :] != near_team[:, None]), d, np.inf).min(axis=1)
    clean = (d[np.arange(len(seen)), nearest] < CONTROL) & (opponent > PRESSURE)
    out[seen[clean]] = near_team[clean]
    return out


def team_check(events, owner, graded):
    print("\n2 DOES THE TAGGED TEAM HAVE THE BALL? (clean-control frames only)")
    print("  clean-control frames: {:.1%} of graded frames; home share of them {:.1%}".format(
        (owner[graded] != NOBODY).mean(), (owner[graded] == HOME).mean()
        / max((owner[graded] != NOBODY).mean(), 1e-9)))
    by_code = {}
    for event in events:
        code = (event["code"] or "").strip().lower()
        team = TEAM_CODE.get((event["tags"].get("Team") or "").strip().lower())
        if code == SET_PIECES or team is None:
            continue
        o = owner[event["start_frame"]:event["end_frame"]]
        o = o[o != NOBODY]
        agree, total = by_code.get(code, (0, 0))
        by_code[code] = (agree + int((o == team).sum()), total + len(o))
    for code, (agree, total) in sorted(by_code.items(), key=lambda kv: -kv[1][1]):
        print("  {:<30} tagged team in control on {:>6.1%} of {:>6,} clean frames".format(
            code, agree / max(total, 1), total))
    print("  (defending phases: a LOW share means the tag is right -- the other team has it)")


def set_piece_check(events, ball, owner, gap_ends):
    print("\n3 SET PIECES vs THE TRACKING")
    print("  {:<22} {:>3} {:>9} {:>13} {:>14} {:>13}".format(
        "type", "n", "dur med", "gap end near", "start-gap end", "ball at spot"))
    rows = {}
    for event in events:
        if (event["code"] or "").strip().lower() != SET_PIECES:
            continue
        kind = (event["tags"].get("Type") or "?").strip().lower()
        start = event["start_frame"]
        near = gap_ends[np.abs(gap_ends - start) <= MATCH_WINDOW] if len(gap_ends) else []
        offset = (start - near[np.argmin(np.abs(near - start))]) / FPS if len(near) else np.nan
        # Where the ball is when play restarts: the reappearance if there is one, else the start.
        frame = near[np.argmin(np.abs(near - start))] if len(near) else start
        spot = restart_spot(ball[min(frame, len(ball) - 1)])
        team = TEAM_CODE.get((event["tags"].get("Team") or "").strip().lower())
        after = owner[frame:frame + 3 * FPS]
        after = after[after != NOBODY]
        taker = after[0] if len(after) else NOBODY
        rows.setdefault(kind, []).append((event["end_frame"] - start, offset, spot, team, taker))
    for kind, items in sorted(rows.items(), key=lambda kv: -len(kv[1])):
        durations = np.array([i[0] for i in items]) / FPS
        offsets = np.array([i[1] for i in items])
        matched = ~np.isnan(offsets)
        expected = EXPECTED_SPOT.get(kind)
        at_spot = np.mean([i[2] == expected for i in items]) if expected else np.nan
        print("  {:<22} {:>3} {:>8.1f}s {:>13.0%} {:>13} {:>13}".format(
            kind, len(items), np.median(durations), matched.mean(),
            "{:+.1f}s".format(np.median(offsets[matched])) if matched.any() else "-",
            "{:.0%}".format(at_spot) if expected else "-"))
        spots = {}
        for i in items:
            spots[i[2]] = spots.get(i[2], 0) + 1
        print("  {:<22} ball spots: {}".format("", ", ".join(
            "{} {}".format(k, v) for k, v in sorted(spots.items(), key=lambda kv: -kv[1]))))
        judged = [(team, taker) for _, _, _, team, taker in items
                  if team is not None and taker != NOBODY]
        if judged:
            print("  {:<22} tagged team = first team in clean control within 3 s: {}/{}".format(
                "", sum(a == b for a, b in judged), len(judged)))


def miss_check(events, ball, gaps):
    print("\n4 BLACKOUTS >= 5 s: DOES A SET-PIECE TAG EXPLAIN THEM?")
    starts = np.array([e["start_frame"] for e in events
                       if (e["code"] or "").strip().lower() == SET_PIECES])
    edges = [5, 10, 20, 60, np.inf]
    for low, high in zip(edges[:-1], edges[1:]):
        chosen = [(a, b) for a, b in gaps if low * FPS <= b - a < high * FPS]
        tagged = [abs(starts - b).min() <= MATCH_WINDOW for a, b in chosen] if len(starts) else []
        print("  {:>2}-{:<3} s: {:>3} blackouts, {:>3} with a set-piece tag within {} s of the"
              " ball's return".format(low, high if np.isfinite(high) else "", len(chosen),
                                      int(np.sum(tagged)), MATCH_WINDOW // FPS))
    spots_tagged, spots_untagged = {}, {}
    for a, b in gaps:
        spot = restart_spot(ball[min(b, len(ball) - 1)])
        target = spots_tagged if len(starts) and abs(starts - b).min() <= MATCH_WINDOW \
            else spots_untagged
        target[spot] = target.get(spot, 0) + 1
    for name, spots in (("tagged", spots_tagged), ("untagged", spots_untagged)):
        print("  where the ball reappears, {:<8}: {}".format(name, ", ".join(
            "{} {}".format(k, v) for k, v in sorted(spots.items(), key=lambda kv: -kv[1]))))


def goal_check(events, ball, gaps):
    print("\n5 GOAL TAGS")
    for event in events:
        if (event["code"] or "").strip().lower() != "goals":
            continue
        end = event["end_frame"]
        after = [(a, b) for a, b in gaps if end - 10 * FPS <= a <= end + 60 * FPS]
        long_gap = max((b - a for a, b in after), default=0) / FPS
        reappear = [restart_spot(ball[min(b, len(ball) - 1)]) for a, b in after
                    if b - a >= 20 * FPS]
        print("  goal tag: longest blackout starting near it {:.0f} s; ball reappears at: {}"
              .format(long_gap, ", ".join(reappear) or "-"))


if __name__ == '__main__':
    import warnings
    warnings.simplefilter("ignore", RuntimeWarning)

    t = load_tracking()
    scale = np.array(PITCH)
    players, ball = t["players"] * scale, t["ball"] * scale
    graded = np.zeros(len(ball), dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        graded[first:last + 1] = True
    events = load_smart_tagging.load()

    print("1 COVERAGE")
    phases = np.zeros(len(ball), dtype=bool)
    na = {}
    for event in events:
        code = (event["code"] or "").strip().lower()
        if code != SET_PIECES:
            phases[event["start_frame"]:event["end_frame"]] = True
        if (event["tags"].get("Team") or "").strip().lower() not in TEAM_CODE:
            na[code] = na.get(code, 0) + 1
    print("  graded frames inside some phase tag: {:.1%}".format(phases[graded].mean()))
    print("  tags with Team N/A: {}".format(", ".join("{} {}".format(k, v)
                                                     for k, v in sorted(na.items()))))
    check = load_smart_tagging.check_time_base(events)
    print("  kickoff tags contain the real kickoffs: {}".format(check["agrees"]))

    owner = controller(players, ball, t["team"])
    team_check(events, owner, graded)

    seen = ~np.isnan(ball[:, 0])
    starts, stops = runs(~seen & graded)
    gaps = [(a, b) for a, b in zip(starts, stops) if b - a >= MIN_GAP]
    gap_ends = np.array([b for a, b in gaps])
    set_piece_check(events, ball, owner, gap_ends)
    miss_check(events, ball, gaps)
    goal_check(events, ball, gaps)
