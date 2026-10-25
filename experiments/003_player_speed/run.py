"""Gate Experiment 002's added dead-ball labels using sustained slow player movement.

Raw tracking stays local. Only aggregate metrics are reported; generated labels remain in data/.
"""

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

from games import GAME, GAMES, half_video_blocks, require  # noqa: E402
from starter import baseline  # noqa: E402
import possession_metrics as pm  # noqa: E402

CONFIG = {
    "smoothing_half_window": 50,
    "minimum_gap_frames": 250,
    "minimum_valid_players": 12,
    "maximum_median_speed_mps": 1.5,
    "minimum_slow_fraction": 0.8,
    "bootstrap_draws": 1000,
}


def true_runs(mask):
    """Half-open intervals of true values, including gaps touching an endpoint."""
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


def read_motion(raw_path, n_frames):
    """Return ball availability and frame summaries without retaining player coordinates."""
    missing = np.zeros(n_frames, dtype=bool)
    player_count = np.zeros(n_frames, dtype=np.int16)
    median_speed = np.full(n_frames, np.nan)
    records = 0
    with open(raw_path) as handle:
        for index, line in enumerate(handle):
            # Suppress malformed input contents in errors: never echo a data record.
            try:
                parts = line.strip().split(":")
                if index >= n_frames or len(parts) != 3 or int(parts[0]) != index + 1:
                    raise ValueError
                missing[index] = parts[2].startswith("NaN")
                speeds = []
                for group in parts[1].split(";"):
                    x, y, speed = map(float, group.split(","))
                    if np.isfinite(x) and np.isfinite(y) and np.isfinite(speed) and speed >= 0:
                        speeds.append(speed)
                player_count[index] = len(speeds)
                if speeds:
                    median_speed[index] = float(np.median(speeds))
            except (ValueError, IndexError, OverflowError):
                raise ValueError("Tracking structure or frame alignment is invalid") from None
            records += 1
    if records != n_frames:
        raise ValueError("Tracking record count does not match the tactical video")
    return missing, player_count, median_speed


def apply_gap_rules(reference, missing, slow_frames, blocks, minimum_frames, slow_fraction):
    """Return the ungated and gated predictions; never merge across half boundaries."""
    ungated = reference.copy()
    gated = reference.copy()
    long_gaps = np.zeros(len(reference), dtype=bool)
    accepted = np.zeros(len(reference), dtype=bool)
    counts = {"long_gaps": 0, "accepted_gaps": 0}
    for first, stop in blocks:
        for start, end in true_runs(missing[first:stop]):
            if end - start < minimum_frames:
                continue
            region = slice(first + start, first + end)
            counts["long_gaps"] += 1
            long_gaps[region] = True
            ungated[region] = "D"
            if float(np.mean(slow_frames[region])) >= slow_fraction:
                counts["accepted_gaps"] += 1
                accepted[region] = True
                gated[region] = "D"
    return ungated, gated, long_gaps, accepted, counts


def summarize(labels, gt, graded, blocks):
    codes = pm.label_codes(labels)
    public = pm.evaluate(gt, codes, bootstrap_n=CONFIG["bootstrap_draws"])
    spells = pm.possession_spells(codes, blocks)
    alive_frames = int(np.sum(graded & ((codes == pm.H) | (codes == pm.A))))
    transitions = public["transitions"][25]
    return {
        "public_spell_f1": public["spell_f1_mean"],
        "public_macro_f1": public["macro_f1"],
        "public_spell_bootstrap_5_95": [public["spell_bootstrap_low"],
                                          public["spell_bootstrap_high"]],
        "public_dead_precision": public["per_class"]["D"]["precision"],
        "public_dead_recall": public["per_class"]["D"]["recall"],
        "public_possessions": public["n_pred_spells"],
        "public_spurious_transitions": transitions["n_spurious"],
        "public_missed_transitions": transitions["n_missed"],
        "full_possessions": len(spells),
        "full_mean_possession_seconds": alive_frames / GAMES[GAME]["fps"] / len(spells)
            if spells else 0.0,
        "full_dead_share": float(np.mean(codes[graded] == pm.D)),
    }


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    n_frames = GAMES[GAME]["n_video_frames"]
    blocks = [(first, last + 1) for _, first, last in half_video_blocks(GAME)]
    graded = np.zeros(n_frames, dtype=bool)
    for first, stop in blocks:
        graded[first:stop] = True

    raw_path = require(["atd_raw"])[0]
    missing, player_count, median_speed = read_motion(raw_path, n_frames)
    usable = player_count >= CONFIG["minimum_valid_players"]
    slow = usable & (median_speed <= CONFIG["maximum_median_speed_mps"])
    if not np.any(graded & usable & (median_speed > 0)):
        raise ValueError("Usable player speeds are absent or all zero; motion rule cannot be tested")

    reference = baseline.smooth(baseline.build(), CONFIG["smoothing_half_window"])
    reference[~graded] = "X"
    ungated, candidate, long_gaps, accepted, gap_counts = apply_gap_rules(
        reference, missing, slow, blocks,
        CONFIG["minimum_gap_frames"], CONFIG["minimum_slow_fraction"])

    output_dir = ROOT / "data" / "derived" / "experiments" / "003_player_speed"
    output_file = output_dir / "speed_gated_dead.csv"
    baseline.write_submission(str(output_file), candidate)
    subprocess.run([sys.executable, str(ROOT / "evaluation" / "validate_submission.py"),
                    str(output_file)], check=True, capture_output=True)
    if np.any(candidate[~graded] != "X") or np.any(candidate[graded] == "X"):
        raise AssertionError("Labels violate the graded-half output contract")

    # Ground truth is first loaded after the candidate is fixed and validated.
    gt = pm.label_codes(pm.read_label_csv(str(ROOT / "evaluation" / "gt" /
                                            "BAR-ATH_possession_gt_public.csv")))
    versions = {"smooth50": reference, "experiment_002": ungated, "experiment_003": candidate}
    results = {name: summarize(labels, gt, graded, blocks) for name, labels in versions.items()}
    public = gt != pm.X
    gt_labels = np.array(pm.LABELS)[gt]
    baseline_correct = reference == gt_labels
    changed = candidate != reference
    diagnostics = {
        **gap_counts,
        "rejected_gaps": gap_counts["long_gaps"] - gap_counts["accepted_gaps"],
        "graded_frames_with_usable_speeds_fraction": float(np.mean(usable[graded])),
        "graded_frame_median_speed_p10_p50_p90": np.percentile(
            median_speed[graded & usable], [10, 50, 90]).tolist(),
        "long_gap_frames": int(np.sum(long_gaps)),
        "accepted_gap_frames": int(np.sum(accepted)),
        "new_dead_frames_experiment_002": int(np.sum(ungated != reference)),
        "new_dead_frames_experiment_003": int(np.sum(changed)),
        "public_changed_frames": int(np.sum(changed & public)),
        "public_errors_corrected": int(np.sum(changed & public & ~baseline_correct &
                                                (candidate == gt_labels))),
        "public_errors_introduced": int(np.sum(changed & public & baseline_correct &
                                                 (candidate != gt_labels))),
        "public_frames_different_from_experiment_002": int(np.sum(public & (candidate != ungated))),
    }
    report = {
        "config": CONFIG,
        "provenance": {
            "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "run_py_sha256": file_hash(Path(__file__).resolve()),
            "baseline_py_sha256": file_hash(ROOT / "starter" / "baseline.py"),
            "metrics_py_sha256": file_hash(ROOT / "evaluation" / "possession_metrics.py"),
        },
        "results": results,
        "diagnostics": diagnostics,
        "candidate_sha256": file_hash(output_file),
    }
    (HERE / "metrics.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print("version          spellF1  macroF1  D precision  D recall   full poss  D share")
    for name, values in results.items():
        print("{:<16} {:>7.4f}  {:>7.4f}  {:>11.3f}  {:>8.3f}  {:>10}  {:>6.1f}%".format(
            name, values["public_spell_f1"], values["public_macro_f1"],
            values["public_dead_precision"], values["public_dead_recall"],
            values["full_possessions"], 100 * values["full_dead_share"]))
    print("Aggregate diagnostics: " + json.dumps(diagnostics, sort_keys=True))
    print("Official format validation passed; aggregate report saved to experiments/003_player_speed/metrics.json")


if __name__ == "__main__":
    main()
