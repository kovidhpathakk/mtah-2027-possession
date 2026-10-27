"""v2: find stoppages from where the ball is and how play moves, then vote within live play.

v1 calls ~35% of a match dead against ~43% in reality (open-data test). It misses stoppages the
tracker keeps the ball through, and it decides ball gaps frame by frame on player speed alone.
Every rule below was measured on the open-data matches (DFL, Metrica; never on our match's answers)
and follows Vidal-Codina et al. 2022: a missing ball and restart positions mark dead ball.

Dead ball, frame by frame inside the halves:
  1. out          the ball is visible more than OUT_MARGIN m beyond a line. (99% of such frames
                  are dead in DFL.)
  2. still        the ball is visible and has not moved (under STILL m/s) for STILL_FOR or more:
                  a ball placed for a restart. (Catches 96% of dead frames in DFL with the ball in
                  view, at 0.6% false alarms in live play.)
  3. gaps         a ball gap of MIN_GAP or more is dead as a whole when any of these holds:
                    - the players are slow during it: mean team speed under SLOW_SHARE of the
                      match's typical live-play speed (gaps like this are 98-99% dead)
                    - the ball went missing beyond a line, at a corner or by a touchline, or came
                      back beyond a line or at a corner (79-100% dead)
                    - it lasts LONG_GAP or more (our gap clips: long gaps were stoppages)
                  otherwise it is live play with the ball hidden, and the team holds.

Tidy-up: a ball lying near a line flickers in and out with a few centimetres of tracking noise,
and each "in" frame would become a one-frame possession (2,000 fake possessions in one damaged DFL
match). So a live stretch shorter than MIN_LIVE between two dead ones becomes dead, then a dead
blip shorter than MIN_DEAD becomes live.

Team in live play: the nearest tracked player's team, majority vote over +/- VOTE_WINDOW, as in
v1. (Stopping the vote at stoppages, so the restarting team is not outvoted by the team before
it, scored slightly worse on the open-data test in every scenario; it stays as an option.)
The tracking is cleaned first (possession.cleanup).
"""

import numpy as np

from possession import baseline, cleanup, control, precise as precise_module
from possession.blackout import missing_runs, vote_with_hold, windowed_mean
from possession.tracking import PITCH

# Params
FPS = 25
VOTE_WINDOW = 50          # +/- 2 s, as v1
OUT_MARGIN = 1.0          # m beyond a line
STILL = 0.5               # m/s, ball speed below which it is not moving
STILL_FOR = 2 * FPS       # frames
BALL_SMOOTH = 12          # +/- frames for the ball speed
MIN_GAP = FPS             # 1 s
LONG_GAP = 20 * FPS       # as v1
NEAR_RETURN = 5.0         # m: a gap whose ball comes back this close to where it vanished ...
NEAR_RETURN_MIN = 3 * FPS # ... and lasts this long is a stoppage (98% of 0-3 m returns are dead)
SLOW_SHARE = 0.65         # of the median team speed while the ball is in view
SPEED_WINDOW = 50         # +/- 2 s smoothing of the team speed
CORNER, TOUCHLINE = 5.0, 3.0   # m
MIN_LIVE = 2 * FPS        # shorter live islands inside a stoppage are flicker
MIN_DEAD = FPS // 2       # shorter dead blips inside live play are flicker
HOME, AWAY, NOBODY = 0, 1, -1


def ball_speed(ball_m):
    """m/s from positions, smoothed: the tracker's own ball-speed column is unusable."""
    speed = np.full(len(ball_m), np.nan)
    speed[2:-2] = np.linalg.norm(ball_m[4:] - ball_m[:-4], axis=1) * FPS / 4
    return windowed_mean(speed, BALL_SMOOTH)


def beyond_line(ball_m, pitch):
    length, width = pitch
    return np.fmax(np.fmax(-ball_m[:, 0], ball_m[:, 0] - length),
                   np.fmax(-ball_m[:, 1], ball_m[:, 1] - width))


def at_edge(xy, pitch):
    """True if a ball position is beyond a line, at a corner or by a touchline: a restart spot."""
    length, width = pitch
    x, y = xy
    if np.isnan(x):
        return False
    if x < -OUT_MARGIN or x > length + OUT_MARGIN or y < -OUT_MARGIN or y > width + OUT_MARGIN:
        return True
    near_end, near_side = min(x, length - x), min(y, width - y)
    return (near_end < CORNER and near_side < CORNER) or near_side < TOUCHLINE


def runs(mask):
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


RULES = ("out", "still", "gaps")


def dead_mask(tracking, rules=RULES, slow_share=SLOW_SHARE, long_gap=LONG_GAP, near_return=0.0):
    pitch = np.array(tracking.get("pitch", PITCH))
    ball = tracking["ball"] * pitch
    n = len(ball)
    seen = ~np.isnan(ball[:, 0])
    dead = np.zeros(n, dtype=bool)

    if "out" in rules:
        dead |= seen & (beyond_line(ball, pitch) > OUT_MARGIN)

    if "still" in rules:
        still = seen & (ball_speed(ball) < STILL)
        for a, b in runs(still):
            if b - a >= STILL_FOR:
                dead[a:b] = True

    if "gaps" not in rules:
        return dead
    team_speed = windowed_mean(np.nanmean(tracking["speed"], axis=1).astype(float), SPEED_WINDOW)
    slow = slow_share * np.nanmedian(team_speed[seen])
    for a, b in missing_runs(tracking["ball"]):
        if b - a < MIN_GAP:
            continue
        edge = (a > 0 and at_edge(ball[a - 1], pitch)) or (b < n and at_edge(ball[b], pitch))
        returned = near_return > 0 and a > 0 and b < n and b - a >= NEAR_RETURN_MIN and \
            np.linalg.norm(ball[b] - ball[a - 1]) < near_return
        if b - a >= long_gap or edge or returned or np.nanmean(team_speed[a:b]) < slow:
            dead[a:b] = True
    return dead


def tidy(dead):
    """Close short live islands, then open short dead blips (see the module docstring)."""
    dead = dead.copy()
    for a, b in runs(~dead):
        if b - a < MIN_LIVE and a > 0 and b < len(dead):
            dead[a:b] = True
    for a, b in runs(dead):
        if b - a < MIN_DEAD:
            dead[a:b] = False
    return dead


def vote_within_live(codes, dead, window):
    """vote_with_hold, run separately on each live stretch, so no vote crosses a stoppage."""
    team = np.full(len(codes), NOBODY, dtype=np.int8)
    for a, b in runs(~dead):
        team[a:b] = vote_with_hold(codes[a:b], window)
    # A live stretch with no ball at all takes the last team seen before it.
    known = np.flatnonzero(team != NOBODY)
    if len(known):
        carry = np.maximum.accumulate(np.where(team != NOBODY, np.arange(len(team)), -1))
        carry[carry < 0] = known[0]
        team = team[carry]
    return team


def predict(tracking, frames=None, rules=RULES, clean=True, live_vote=False, precise=False,
            team_by="vote", control_options=None, **gap_options):
    """H/A/D per frame. rules / clean / live_vote / precise switch parts on and off, to measure
    what each adds. precise=True runs possession.precise (which includes the clean-up)."""
    if precise:
        tracking = precise_module.precise(tracking)
    elif clean:
        tracking = cleanup.clean(tracking)
    codes = baseline.nearest_team(tracking["players"], tracking["ball"], tracking["team"], frames)
    dead = tidy(dead_mask(tracking, rules, **gap_options))
    if team_by == "control":
        team = control.team_by_control(tracking, dead, codes, **(control_options or {}))
    elif live_vote:
        team = vote_within_live(codes, dead, VOTE_WINDOW)
    else:
        team = vote_with_hold(codes, VOTE_WINDOW)
    labels = np.where(team == HOME, "H", "A").astype("<U1")
    labels[dead] = "D"
    return labels
