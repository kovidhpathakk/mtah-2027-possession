"""Blackout-aware v1: the baseline, plus what the gap clips taught us about the missing ball.

The tracker drops the ball when play stops -- even with the ball plainly visible -- and picks it
up at the restart (docs/experiments.md, 2026-10-24). So a ball blackout is mostly a stoppage
signal, not missing information. The baseline instead calls EVERY missing-ball frame dead, which
also turns live play with the ball merely hidden into D, splitting real possessions.

v1, frame by frame inside the graded halves:
  1. Ball visible: vote for the team of the nearest tracked player, as the baseline does.
  2. Ball missing for at least LONG_GAP: dead ball. Two thirds of all missing-ball time sits in
     gaps over 20 s, and in those the players move at half their live-play speed.
  3. Ball missing for MIN_GAP..LONG_GAP: dead only while the team speed (all tracked players,
     averaged over +/- SPEED_WINDOW) is below SLOW. Otherwise live play with the ball hidden.
  4. Live frames take the majority vote of the nearest-player team over +/- VOTE_WINDOW, as in the
     baseline; where the window holds no vote at all (a long live blackout), the last team holds.

Thresholds come from full-match measurements and the clips, never from the public 5 minutes:
SLOW is the 5th percentile of team speed while the ball is visible (95% of live play is faster);
LONG_GAP is where the clips and the speed drop say gaps are stoppages.
"""

import numpy as np

from possession import baseline

# Params
FPS = 25
VOTE_WINDOW = 50        # +/- 2 s majority vote, the baseline's best
MIN_GAP = 2 * FPS       # shorter blackouts are blinks in live play
LONG_GAP = 20 * FPS     # longer ones are treated as stoppages outright
SLOW = 1.0              # m/s, team mean speed below which play looks stopped
SPEED_WINDOW = 50       # +/- 2 s smoothing of the team speed
HOME, AWAY, NOBODY = 0, 1, -1


def windowed_mean(values, half_width):
    """Centred moving mean over +/- half_width, ignoring NaN. Cumulative sums: O(n)."""
    valid = ~np.isnan(values)
    sums = np.concatenate(([0.0], np.cumsum(np.where(valid, values, 0.0))))
    counts = np.concatenate(([0], np.cumsum(valid)))
    index = np.arange(len(values))
    low = np.maximum(0, index - half_width)
    high = np.minimum(len(values), index + half_width + 1)
    n = counts[high] - counts[low]
    return np.where(n > 0, (sums[high] - sums[low]) / np.maximum(n, 1), np.nan)


def missing_runs(ball):
    """[(start, stop)] half-open runs of frames with no ball position."""
    missing = np.isnan(ball[:, 0]).astype(np.int8)
    edges = np.diff(np.concatenate(([0], missing, [0])))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def dead_mask(tracking):
    """True on frames v1 calls dead ball: long blackouts, and slow stretches of medium ones."""
    team_speed = windowed_mean(np.nanmean(tracking["speed"], axis=1).astype(float), SPEED_WINDOW)
    slow = team_speed < SLOW
    dead = np.zeros(len(team_speed), dtype=bool)
    for start, stop in missing_runs(tracking["ball"]):
        length = stop - start
        if length >= LONG_GAP:
            dead[start:stop] = True
        elif length >= MIN_GAP:
            dead[start:stop] = slow[start:stop]
    return dead


def vote_with_hold(codes, window):
    """Majority vote of HOME/AWAY over +/- window; no votes in range -> hold the last team."""
    home = np.concatenate(([0], np.cumsum(codes == HOME)))
    away = np.concatenate(([0], np.cumsum(codes == AWAY)))
    index = np.arange(len(codes))
    low = np.maximum(0, index - window)
    high = np.minimum(len(codes), index + window + 1)
    h, a = home[high] - home[low], away[high] - away[low]

    team = np.where(h + a > 0, np.where(h >= a, HOME, AWAY), NOBODY).astype(np.int8)
    known = np.flatnonzero(team != NOBODY)
    if not len(known):
        return team
    carry = np.maximum.accumulate(np.where(team != NOBODY, index, -1))
    carry[carry < 0] = known[0]  # before the first vote, take the first team seen
    return team[carry]


def predict(tracking, frames=None):
    codes = baseline.nearest_team(tracking["players"], tracking["ball"], tracking["team"], frames)
    team = vote_with_hold(codes, VOTE_WINDOW)
    labels = np.where(team == HOME, "H", "A").astype("<U1")
    labels[dead_mask(tracking)] = "D"
    return labels
