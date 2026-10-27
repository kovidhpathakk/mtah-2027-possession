"""The organisers' baseline, on our arrays: nearest tracked player to the ball, then a majority vote.

Same algorithm as starter/baseline.py and byte-identical output (run.py --check-baseline proves
it), but working on the cached arrays from possession.tracking instead of re-reading the text
file. That is what makes it cheap enough to run hundreds of times inside the damage test, where
the ball is deleted in different places on every run.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "starter"))
from baseline import NOBODY, smooth  # noqa: E402  (the organisers' smoothing, reused as is)

from possession.tracking import PITCH  # noqa: E402

# Params
DEFAULT_WINDOW = 50  # +/- 2 s, the published floor


def nearest_team(players, ball, team, frames=None):
    """Per frame: team code of the tracked player nearest the ball, NOBODY where no answer.

    Distances in metres, computed in the same order of float64 operations as starter/baseline.py
    so near-ties break the same way. `frames` restricts the work to a slice (the damage test
    only needs the public window); everything outside it is NOBODY.
    """
    length, width = PITCH
    n_frames = len(ball)
    selected = np.arange(n_frames) if frames is None else np.asarray(frames)
    out = np.full(n_frames, NOBODY, dtype=np.int8)

    sub_ball = ball[selected]
    seen = ~np.isnan(sub_ball[:, 0])
    rows = selected[seen]
    if not len(rows):
        return out

    dx = players[rows, :, 0] * length - (ball[rows, 0] * length)[:, None]
    dy = players[rows, :, 1] * width - (ball[rows, 1] * width)[:, None]
    distance = dx * dx + dy * dy
    has_player = ~np.all(np.isnan(distance), axis=1)
    distance = np.where(np.isnan(distance), np.inf, distance)
    nearest = np.argmin(distance, axis=1)  # first minimum, like the strict < in the reference

    codes = team[nearest].astype(np.int8)
    codes[~has_player] = NOBODY
    out[rows] = codes
    return out


def predict(tracking, window=DEFAULT_WINDOW, frames=None):
    """H/A/D labels for every frame, as a numpy array of one-letter strings."""
    codes = nearest_team(tracking["players"], tracking["ball"], tracking["team"], frames)
    return smooth(codes, window)
