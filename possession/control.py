"""Which team has the ball in live play, by control rather than by proximity.

v1 and v2 give each visible-ball frame to the team of the nearest player and smooth with a +/- 2 s
majority vote. An oracle test on the practice matches showed that this team call is where most
points are lost: with the true team in live play v2 would score 0.72 instead of 0.31. Two faults
of "nearest player": a pass in flight is nearest to an opponent halfway, and the vote moves every
change of possession by up to 2 s (a possession 1 s late scores only 0.65).

The rules here follow two papers:
  Link & Hoernig 2017 ("Individual ball possession in soccer"): possession needs control, not a
    touch; a pass stays with the passer's team until someone else controls the ball.
  Vidal-Codina et al. 2022: a player possesses the ball within ~1 m; if an opponent is also that
    close, it is a duel, not possession.
and CHALLENGE.md: a change of possession happens when the other team gains CONTROLLED possession;
contested or loose balls stay with the last team.

Per frame with the ball in view:
  1. reach      the nearest player of each team, and their distances to the ball
  2. candidate  a team whose nearest player is within REACH m, while the other team's is not
                within DUEL m (otherwise a duel: no candidate)
  3. control    a candidate held for CONTROL_FRAMES consecutive frames is a control event: that
                team has the ball from the first of those frames
  4. hold       between control events the last team keeps the ball -- through passes, loose
                balls, duels and short ball gaps. Before the first control event of a live
                stretch, the nearest-player vote decides (a restart's first touch).
No smoothing window: a change lands on the frame the new team takes control.
"""

import numpy as np

from possession.blackout import vote_with_hold
from possession.tracking import PITCH

# Params, set on the practice matches (never on our match): a sweep of reach 1-3 m, duel 0-2 m and
# 1-15 frames picked reach 1.0 m and duel 1.0 m -- the distances Vidal-Codina et al. use -- and
# 3 frames (practice score 0.377 vs 0.309 for v2's vote).
REACH = 1.0            # m
DUEL = 1.0             # m
CONTROL_FRAMES = 3     # 0.12 s
# Touch rule (deep dive 1), set on the damaged practice matches: dv 3-12, pass-by 4-8, reach
# 1.0/1.5 swept; dv 7, pass-by 6, reach 1.0 best (practice 0.409 vs 0.353 for the 3-frame hold).
TOUCH_DV = 7.0         # m/s change in ball velocity that marks a touch
TOUCH_SPAN = 3         # frames either side over which the change is measured
PASS_BY = 6.0          # m/s: a ball faster than this past a player is not held by him
HOME, AWAY, NOBODY = 0, 1, -1


def team_distances(players, ball, team, pitch):
    """(n, 2): distance in m from the ball to the nearest home and nearest away player."""
    metres = np.array(pitch)
    d = np.linalg.norm(players * metres - (ball * metres)[:, None, :], axis=2)
    out = np.full((len(ball), 2), np.inf)
    for code in (HOME, AWAY):
        mine = d[:, team == code]
        if mine.shape[1]:
            out[:, code] = np.where(np.all(np.isnan(mine), axis=1), np.inf,
                                    np.nanmin(np.where(np.isnan(mine), np.inf, mine), axis=1))
    return out


def control_events(dist, reach=REACH, duel=DUEL, frames=CONTROL_FRAMES):
    """Per frame: the team that takes control there (start of a held candidate run), else NOBODY."""
    home = (dist[:, 0] < reach) & (dist[:, 1] >= duel)
    away = (dist[:, 1] < reach) & (dist[:, 0] >= duel)
    candidate = np.where(home, HOME, np.where(away, AWAY, NOBODY)).astype(np.int8)
    events = np.full(len(candidate), NOBODY, dtype=np.int8)
    change = np.flatnonzero(np.diff(np.concatenate(([NOBODY - 1], candidate))) != 0)
    stops = np.concatenate((change[1:], [len(candidate)]))
    for a, b in zip(change, stops):
        if candidate[a] != NOBODY and b - a >= frames:
            events[a] = candidate[a]
    return events


def ball_velocity(ball_m):
    """(n, 2) m/s from the move between t-2 and t+2; NaN at the edges and around gaps."""
    v = np.full(ball_m.shape, np.nan)
    v[2:-2] = (ball_m[4:] - ball_m[:-4]) * 25 / 4
    return v


def control_events_touch(dist, ball_m, reach=REACH, duel=DUEL, frames=CONTROL_FRAMES,
                         dv=TOUCH_DV, pass_by=PASS_BY, k=TOUCH_SPAN):
    """Control by touch or by hold (deep dive 1, docs/deep-dives/01-ball-travelling.md).

    Deep dive 1 found v3's 3-frame hold misses a third of true changes (a one-touch pass is a
    possession in the answers) and invents changes when a fast pass zips past an opponent (median
    9.6 m/s). Vidal-Codina et al.: a gain of possession needs the ball to change direction or
    speed near the player; Link & Hoernig: a touch is a sudden change in the ball's motion. So:
      touch  the ball's velocity changes by at least dv m/s between t-k and t+k while one team's
             player is within reach and no opponent within duel: control from that frame, even
             if brief
      hold   the candidate team keeps the ball within reach for `frames` frames while it moves
             slower than pass_by m/s (the ball travels with the player, not past him)
    """
    home = (dist[:, 0] < reach) & (dist[:, 1] >= duel)
    away = (dist[:, 1] < reach) & (dist[:, 0] >= duel)
    candidate = np.where(home, HOME, np.where(away, AWAY, NOBODY)).astype(np.int8)
    v = ball_velocity(ball_m)
    speed = np.linalg.norm(v, axis=1)
    change = np.full(len(v), np.nan)
    change[k:-k] = np.linalg.norm(v[2 * k:] - v[:-2 * k], axis=1)
    events = np.full(len(candidate), NOBODY, dtype=np.int8)
    touch = (candidate != NOBODY) & (change >= dv)
    events[touch] = candidate[touch]
    starts = np.flatnonzero(np.diff(np.concatenate(([NOBODY - 1], candidate))) != 0)
    stops = np.concatenate((starts[1:], [len(candidate)]))
    for a, b in zip(starts, stops):
        if candidate[a] != NOBODY and b - a >= frames and np.nanmedian(speed[a:b]) < pass_by:
            events[a] = candidate[a]
    return events


def keep_through_duels(events, dist, keep):
    """Drop a change of team unless the team in possession is clearly away from the ball.

    Deep dive 1's real cases: in tight pressing the holder keeps a slow ball while a challenger
    hovers about 1 m away, and the plain rule flips whenever the challenger is a few centimetres
    closer. The answers keep the ball with the holder ("a duel does not change possession"). So
    an event for the other team counts only if the current team's nearest player is at least
    `keep` m from the ball at that frame."""
    out = events.copy()
    current = NOBODY
    for f in np.flatnonzero(events != NOBODY):
        team = events[f]
        if current != NOBODY and team != current and dist[f, current] < keep:
            out[f] = NOBODY
            continue
        current = team
    return out


def team_by_control(tracking, dead, codes, reach=REACH, duel=DUEL, frames=CONTROL_FRAMES,
                    vote_window=50, touch=False, dv=TOUCH_DV, pass_by=PASS_BY, keep=0.0):
    """HOME/AWAY per frame for live play (dead frames get a placeholder the caller overwrites).
    touch=True uses control_events_touch (control by touch or slow hold) instead of the plain
    3-frame hold; keep > 0 keeps the ball with its holder through duels (keep_through_duels)."""
    pitch = tracking.get("pitch", PITCH)
    dist = team_distances(tracking["players"], tracking["ball"], tracking["team"], pitch)
    if touch:
        events = control_events_touch(dist, tracking["ball"] * np.array(pitch), reach, duel,
                                      frames, dv, pass_by)
    else:
        events = control_events(dist, reach, duel, frames)
    if keep > 0:
        events = keep_through_duels(events, dist, keep)
    fallback = vote_with_hold(codes, vote_window)
    team = fallback.copy()
    edges = np.diff(np.concatenate(([0], (~dead).astype(np.int8), [0])))
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        held = events[a:b].copy()
        known = np.flatnonzero(held != NOBODY)
        if not len(known):
            continue
        index = np.arange(b - a)
        last = np.maximum.accumulate(np.where(held != NOBODY, index, -1))
        team[a:b] = np.where(last >= 0, held[np.maximum(last, 0)], fallback[a:b])
    return team
