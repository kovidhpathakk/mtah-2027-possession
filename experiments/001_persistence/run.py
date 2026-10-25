"""Experiment 001: collapse short team reversals in the official smooth25 baseline.

Only aggregate numbers are printed. Candidate frame-level files stay under ignored data/derived/.
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from games import GAME, GAMES, half_video_blocks  # noqa: E402
from starter import baseline  # noqa: E402
import possession_metrics as pm  # noqa: E402

OUTPUT = ROOT / "data" / "derived" / "experiments" / "001_persistence"
GT = ROOT / "evaluation" / "gt" / "BAR-ATH_possession_gt_public.csv"


def graded_labels(labels):
    """Keep the official baseline's labels in the graded halves and X elsewhere."""
    output = np.full(len(labels), "X", dtype="<U1")
    for _, first, last in half_video_blocks(GAME):
        output[first:last + 1] = labels[first:last + 1]
    return output


def collapse_reversals(labels, minimum_frames):
    """Remove an H/A run shorter than minimum_frames only when both neighbors agree.

    A run adjoining D, a half boundary, or a different next team remains untouched. This
    deliberately tests a narrow anti-flicker rule rather than guessing about dead balls.
    """
    output = labels.copy()
    for _, first, last in half_video_blocks(GAME):
        block = labels[first:last + 1]
        starts = np.r_[0, np.flatnonzero(block[1:] != block[:-1]) + 1]
        ends = np.r_[starts[1:], len(block)]
        for index in range(1, len(starts) - 1):
            left = block[starts[index - 1]]
            middle = block[starts[index]]
            right = block[starts[index + 1]]
            if (middle in ("H", "A") and left == right and left in ("H", "A")
                    and left != middle and ends[index] - starts[index] < minimum_frames):
                output[first + starts[index]:first + ends[index]] = left
    return output


def summarize(name, labels, gt):
    prediction = pm.label_codes(labels)
    public = pm.evaluate(gt, prediction)
    runs = pm.valid_runs(prediction)
    spells = pm.possession_spells(prediction, runs)
    graded = sum(last - first + 1 for _, first, last in half_video_blocks(GAME))
    dead = sum(int(np.sum(prediction[first:last + 1] == pm.D))
               for _, first, last in half_video_blocks(GAME))
    print("{:<16} {:>7.4f} {:>7.4f} {:>5} {:>7} {:>7} {:>7.1f}%".format(
        name, public["spell_f1_mean"], public["macro_f1"],
        public["n_pred_spells"], public["transitions"][25]["n_spurious"],
        len(spells), 100.0 * dead / graded))


def main():
    gt = pm.label_codes(pm.read_label_csv(str(GT)))
    codes = baseline.build()
    smooth25 = graded_labels(baseline.smooth(codes, 25))
    smooth50 = graded_labels(baseline.smooth(codes, 50))

    print("version           spellF1 macroF1  poss spurious    full   D share")
    summarize("smooth25", smooth25, gt)
    for minimum_frames in (10, 25):
        candidate = collapse_reversals(smooth25, minimum_frames)
        name = "persistence_{}".format(minimum_frames)
        output_path = OUTPUT / (name + ".csv")
        baseline.write_submission(str(output_path), candidate)
        parsed = pm.read_label_csv(str(output_path))
        error = pm.validate_submission(parsed, GAMES[GAME]["n_video_frames"])
        if error:
            raise ValueError("{}: {}".format(name, error))
        summarize(name, candidate, gt)
    summarize("smooth50", smooth50, gt)
    print("Candidate CSVs saved locally under data/derived/experiments/001_persistence/")


if __name__ == "__main__":
    main()
