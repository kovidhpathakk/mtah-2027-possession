"""Score a method on the public 5 minutes after damaging the ball tracking to look like the match.

The public window is the only place we have answers, and it is unrepresentatively easy: the ball
is missing on about 12% of its frames against 41% across the graded match, and the full-match
gaps are long (median ~11 s). Any method looks better there than it will be.

So, for each run:
  1. copy the tracking and, inside the public window only, delete the ball in blocks whose lengths
     are drawn from the REAL full-match gap lengths, until the window's missing share reaches the
     full match's (~41%)
  2. run the method, apply the match rules, score against the public ground truth
Repeat with different random seeds and report the mean and the 5-95% spread.

    python scripts/damage_test.py                          # all methods, 100 runs each
    python scripts/damage_test.py --methods baseline --runs 200

CALIBRATION. The four published baselines have known full-match scores (EVALUATION.md). The
report prints them beside the damage-test means: if the test is honest, its means sit near the
full-match numbers and rank the baselines the same way -- which the raw public window does not
(it picks smooth125). Check this before trusting the test on anything new.

Known limits: random gap placement is kinder than reality, where gaps cluster in crowded,
contested moments; and only the ball is damaged, not the players. Expect it to stay a little
optimistic.

Prints scores and counts only; no data leaves the machine.
"""

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402
from games import GAME, half_video_blocks  # noqa: E402

from possession.methods import METHODS  # noqa: E402
from possession.polish import apply_match_rules  # noqa: E402
from possession.tracking import load_tracking  # noqa: E402

# Params
GT_PATH = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
DEFAULT_RUNS = 100
SPREAD = (5, 95)
CONTEXT = 250  # frames either side of the window handed to the method, for smoothing context
# Full-match scores of the published baselines, from EVALUATION.md -- the calibration targets.
FULL_MATCH = {"baseline_raw": 0.0486, "baseline_smooth25": 0.1996,
              "baseline": 0.2433, "baseline_smooth125": 0.2242}


def graded_ball_gaps(ball):
    """Lengths, in frames, of every run of missing ball inside the graded halves."""
    lengths = []
    for _, first, last in half_video_blocks(GAME):
        missing = np.isnan(ball[first:last + 1, 0]).astype(np.int8)
        edges = np.diff(np.concatenate(([0], missing, [0])))
        lengths.extend(np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1))
    return np.array(lengths)


def damage(ball, window, gap_lengths, target, rng):
    """A copy of `ball` with real-length gaps cut into `window` until `target` of it is missing."""
    first, last = window
    damaged = ball.copy()
    inside = damaged[first:last + 1, 0]  # a view: writes through to `damaged`
    while np.isnan(inside).mean() < target:
        length = int(rng.choice(gap_lengths))
        start = int(rng.integers(first - length + 1, last + 1))  # may overhang either edge
        damaged[max(start, first):min(start + length, last + 1)] = np.nan
    return damaged


def score(method, tracking, frames, gt_codes):
    labels = apply_match_rules(method(tracking, frames))
    result = pm.evaluate(gt_codes, pm.label_codes(labels))
    return result["spell_f1_mean"], result["macro_f1"], result["n_pred_spells"]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--methods", nargs="+", default=sorted(METHODS), choices=sorted(METHODS))
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    gt_codes = pm.label_codes(pm.read_label_csv(GT_PATH))
    graded = np.flatnonzero(gt_codes != pm.X)
    window = (int(graded[0]), int(graded[-1]))
    frames = np.arange(window[0] - CONTEXT, window[1] + CONTEXT + 1)

    tracking = load_tracking()
    gaps = graded_ball_gaps(tracking["ball"])
    match_missing = float(np.isnan(tracking["ball"][
        np.concatenate([np.arange(f, l + 1) for _, f, l in half_video_blocks(GAME)]), 0]).mean())
    window_missing = float(np.isnan(tracking["ball"][window[0]:window[1] + 1, 0]).mean())

    print("public window {}..{}: ball missing {:.0%} as delivered; damaging to the match's {:.0%}"
          .format(window[0], window[1], window_missing, match_missing))
    print("gap lengths drawn from {} real gaps, median {:.1f} s; {} runs per method, seed {}\n"
          .format(len(gaps), np.median(gaps) / 25, args.runs, args.seed))

    header = "{:<20} {:>9} {:>17} {:>15} {:>7} {:>11}".format(
        "method", "public", "damaged mean", "5-95%", "poss", "full match")
    print(header + "\n" + "-" * len(header))
    for name in args.methods:
        method = METHODS[name]
        public = score(method, tracking, frames, gt_codes)[0]

        rng = np.random.default_rng(args.seed)  # same damage for every method: a fair comparison
        spell, possessions = [], []
        for _ in range(args.runs):
            damaged = dict(tracking)
            damaged["ball"] = damage(tracking["ball"], window, gaps, match_missing, rng)
            s, _, n = score(method, damaged, frames, gt_codes)
            spell.append(s)
            possessions.append(n)

        low, high = np.percentile(spell, SPREAD)
        full = FULL_MATCH.get(name)
        print("{:<20} {:>9.4f} {:>17.4f} {:>15} {:>7.1f} {:>11}".format(
            name, public, np.mean(spell), "{:.3f}-{:.3f}".format(low, high),
            np.mean(possessions), "{:.4f}".format(full) if full is not None else "-"))

    print("\npublic = undamaged 5 minutes; poss = mean predicted possessions in the window "
          "(truth: 17); full match = published score, where known")
