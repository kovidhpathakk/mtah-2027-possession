"""Make the tracking as precise as the data allows, before any method reads it.

What the audits (docs/research.md section 7) showed can be repaired by code, in this order:

  1. objects    frozen leftover tracks and a team's 12th+ object go (possession.cleanup)
  2. blips      a visible ball that jumps more than JUMP m from where it was and comes back within
                BLIP frames is a false detection: those frames lose their ball. (A real ball
                cannot travel 2 m in 1/25 s: 50 m/s is faster than the hardest shot.)
  3. smoothing  the ball is smoothed with a Savitzky-Golay filter, 7 frames, quadratic -- the
                filter Vidal-Codina et al. 2022 use before detecting possession -- inside each
                visible run only, so nothing is invented across a gap
  4. broadcast  OUR MATCH ONLY: where the tactical ball is missing and the aligned broadcast frame
                shows live play with a ball (scripts/align_broadcast.py), take the broadcast
                ball. Tactical stays first wherever it has one: the video audit found it right
                about twice as often when the two disagree.

    from possession.precise import precise
    tracking = precise(tracking)
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES  # noqa: E402

from possession import cleanup  # noqa: E402
from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
JUMP = 2.0                     # m in one frame
BLIP = 3                       # frames: a jump away and back within this is a false detection
SAVGOL_7_QUADRATIC = np.array([-2, 3, 6, 7, 6, 3, -2]) / 21.0
OFFSETS = os.path.join(ROOT, "data", "derived", "broadcast_offsets.npz")
OUR_FRAMES = GAMES[GAME]["n_video_frames"]


def drop_blips(ball, pitch):
    """NaN the frames of a ball that leaves by more than JUMP m and returns within BLIP frames."""
    ball = ball.copy()
    metres = ball * np.array(pitch)
    step = np.linalg.norm(metres[1:] - metres[:-1], axis=1)
    for t in np.flatnonzero(step > JUMP):
        back = t + 1 + np.arange(1, BLIP + 1)
        back = back[back < len(ball)]
        returns = np.linalg.norm(metres[back] - metres[t], axis=1) < JUMP
        if returns.any():
            ball[t + 1:back[np.argmax(returns)]] = np.nan
    return ball


def smooth(ball):
    """Savitzky-Golay (7, quadratic) inside each visible run of at least 7 frames."""
    out = ball.copy()
    seen = ~np.isnan(ball[:, 0])
    edges = np.diff(np.concatenate(([0], seen.astype(np.int8), [0])))
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if b - a < len(SAVGOL_7_QUADRATIC):
            continue
        for k in range(2):
            out[a + 3:b - 3, k] = np.convolve(ball[a:b, k], SAVGOL_7_QUADRATIC[::-1], "valid")
    return out


def broadcast_ball(n_frames):
    """The broadcast ball on the tactical timeline (NaN where unmapped), or None if not ours."""
    if n_frames != OUR_FRAMES or not os.path.isfile(OFFSETS):
        return None
    offset = np.load(OFFSETS)["offset"]
    ball_b = load_tracking("broadcast")["ball"]
    out = np.full((n_frames, 2), np.nan)
    live = np.flatnonzero(offset >= 0)
    target = live + offset[live]
    ok = target < n_frames
    out[target[ok]] = ball_b[live[ok]]
    return out


def precise(tracking, use_broadcast=True):
    """A copy of `tracking` with steps 1-4 of the module docstring applied."""
    out = cleanup.clean(tracking)
    pitch = tracking.get("pitch", PITCH)
    ball = smooth(drop_blips(tracking["ball"], pitch))
    if use_broadcast:
        other = broadcast_ball(len(ball))
        if other is not None:
            fill = np.isnan(ball[:, 0]) & ~np.isnan(other[:, 0])
            ball[fill] = other[fill]
    out["ball"] = ball
    return out
