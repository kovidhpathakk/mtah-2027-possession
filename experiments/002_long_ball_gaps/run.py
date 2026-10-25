"""Experiment 002: mark long ball-missing intervals dead, starting from smooth50.

Prints aggregates only. The generated frame-level candidate stays in ignored data/derived/.
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from games import GAME, GAMES, half_video_blocks, require  # noqa: E402
from starter import baseline  # noqa: E402
import possession_metrics as pm  # noqa: E402

MIN_GAP_FRAMES = 250  # 10 seconds at 25 fps; fixed before scoring.
OUTPUT = ROOT / "data" / "derived" / "experiments" / "002_long_ball_gaps"
GT = ROOT / "evaluation" / "gt" / "BAR-ATH_possession_gt_public.csv"


def ball_missing_mask(raw_path, n_frames):
    """Read only ball availability; never print or retain tracking coordinates."""
    missing = np.zeros(n_frames, dtype=bool)
    records = 0
    with open(raw_path) as handle:
        for row_number, line in enumerate(handle):
            if row_number >= n_frames:
                raise ValueError("more ATD records than tactical frames")
            ball_group = line.rsplit(":", 1)[-1]
            missing[row_number] = ball_group.startswith("NaN")
            records += 1
    if records != n_frames:
        raise ValueError("ATD record count does not match tactical frames")
    return missing


def graded_labels(labels):
    output = np.full(len(labels), "X", dtype="<U1")
    for _, first, last in half_video_blocks(GAME):
        output[first:last + 1] = labels[first:last + 1]
    return output


def mark_long_gaps_dead(labels, missing, minimum_frames):
    """Replace full qualifying gaps with D, separately within each graded half."""
    output = labels.copy()
    eligible = np.zeros(len(labels), dtype=bool)
    gap_count = 0
    for _, first, last in half_video_blocks(GAME):
        block = missing[first:last + 1]
        edges = np.diff(np.r_[False, block, False].astype(np.int8))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        for start, end in zip(starts, ends):
            if end - start >= minimum_frames:
                eligible[first + start:first + end] = True
                output[first + start:first + end] = "D"
                gap_count += 1
    return output, eligible, gap_count


def summarize(name, labels, gt):
    prediction = pm.label_codes(labels)
    scored = pm.evaluate(gt, prediction)
    runs = pm.valid_runs(prediction)
    full_possessions = len(pm.possession_spells(prediction, runs))
    graded_frames = sum(last - first + 1 for _, first, last in half_video_blocks(GAME))
    dead_frames = sum(int(np.sum(prediction[first:last + 1] == pm.D))
                      for _, first, last in half_video_blocks(GAME))
    dead = scored["per_class"]["D"]
    transitions = scored["transitions"][25]
    print("{:<14} {:>7.4f} {:>7.4f} {:>7.3f} {:>7.3f} {:>6} {:>6} {:>6.1f}% {:>5}/{:<5}".format(
        name, scored["spell_f1_mean"], scored["macro_f1"], dead["precision"],
        dead["recall"], scored["n_pred_spells"], full_possessions,
        100.0 * dead_frames / graded_frames,
        transitions["n_spurious"], transitions["n_missed"]))


def main():
    n_frames = GAMES[GAME]["n_video_frames"]
    raw_path = require(["atd_raw"])[0]
    missing = ball_missing_mask(raw_path, n_frames)
    codes = baseline.build()
    reference = graded_labels(baseline.smooth(codes, 50))
    candidate, eligible, gap_count = mark_long_gaps_dead(reference, missing, MIN_GAP_FRAMES)

    output_path = OUTPUT / "long_gaps_to_D.csv"
    baseline.write_submission(str(output_path), candidate)
    reason = pm.validate_submission(pm.read_label_csv(str(output_path)), n_frames)
    if reason:
        raise ValueError("candidate failed official format checks: " + reason)

    gt = pm.label_codes(pm.read_label_csv(str(GT)))
    print("version        spellF1 macroF1  D prec   D rec public   full  D share spur/miss")
    summarize("smooth50", reference, gt)
    summarize("long_gap_D", candidate, gt)

    graded = np.zeros(n_frames, dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        graded[first:last + 1] = True
    public = gt != pm.X
    changed = int(np.sum((reference != candidate) & graded))
    eligible_frames = int(np.sum(eligible))
    missing_graded = int(np.sum(missing & graded))
    public_eligible = eligible & public
    public_dead = int(np.sum(public_eligible & (gt == pm.D)))
    print("Qualifying gaps: {} totaling {} frames ({:.1f}% of graded missing-ball time)".format(
        gap_count, eligible_frames, 100.0 * eligible_frames / missing_graded))
    print("Changed to D: {} frames; public qualifying frames: {} ({} truly D)".format(
        changed, int(np.sum(public_eligible)), public_dead))
    print("Candidate CSV saved locally under data/derived/experiments/002_long_ball_gaps/")


if __name__ == "__main__":
    main()
