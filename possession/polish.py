"""Match-level rules that hold for any model: they need no tracking and cost nothing to apply.

  1. X on every frame outside the two graded halves. Those frames are never scored, so nothing
     we write there matters -- X just makes that explicit.
  2. D from the start of the graded second half to the frame before its kickoff. The half is
     graded from 110808 but kicks off at 113742 (FAQ.md); the 2934 frames between are graded and
     are all dead ball. Leaving them to a model invites a spurious possession, and leaving them X
     is worse: the scorer back-fills X at the head of a half with our first real label.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, half_video_blocks  # noqa: E402

# Params
SECOND_HALF_KICKOFF = 113742  # first live frame of the 2nd half, per FAQ.md


def graded_mask(n_frames):
    mask = np.zeros(n_frames, dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        mask[first:last + 1] = True
    return mask


def apply_match_rules(labels):
    """A copy of `labels` with the two rules above applied."""
    labels = np.array(labels, dtype="<U1")
    labels[~graded_mask(len(labels))] = "X"
    second_half_start = half_video_blocks(GAME)[1][1]
    labels[second_half_start:SECOND_HALF_KICKOFF] = "D"
    return labels
