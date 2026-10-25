"""Test automatic restart cues on top of Experiment 003, with local-only match processing."""

import csv
import importlib.util
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

# Import by path because each experiment intentionally has its own run.py.
spec = importlib.util.spec_from_file_location(
    "experiment_003", ROOT / "experiments" / "003_player_speed" / "run.py")
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)

from games import GAME, GAMES, asset_paths, half_video_blocks, require  # noqa: E402
from scripts.clip_reviewer import create_review  # noqa: E402
from starter import baseline, load_smart_tagging  # noqa: E402

pm = previous.pm

CONFIG = {
    "position_speed_window_frames": 5,
    "position_speed_minimum_differences": 3,
    "tag_margin_frames": 50,
    "minimum_quiet_frames": 25,
    "maximum_stationary_ball_speed_mps": 0.5,
    "minimum_moving_ball_speed_mps": 2.0,
    "minimum_moving_frames": 5,
    "review_merge_gap_frames": 50,
    "review_context_seconds": 5,
}


def read_ball_signals(raw_path, n_frames):
    """Read ball positions and provided speeds locally; never expose record contents."""
    positions = np.full((n_frames, 2), np.nan)
    speeds = np.full(n_frames, np.nan)
    records = 0
    with open(raw_path) as handle:
        for index, line in enumerate(handle):
            try:
                parts = line.strip().split(":")
                if index >= n_frames or len(parts) != 3 or int(parts[0]) != index + 1:
                    raise ValueError
                x, y, speed = map(float, parts[2].split(","))
                if np.isfinite(x) and np.isfinite(y):
                    positions[index] = (x, y)
                    if np.isfinite(speed) and speed >= 0:
                        speeds[index] = speed
            except (ValueError, IndexError, OverflowError):
                raise ValueError("Ball tracking structure or alignment is invalid") from None
            records += 1
    if records != n_frames:
        raise ValueError("Ball tracking record count differs from the video")
    return positions, speeds


def position_speeds(positions, pitch, fps, blocks, config=CONFIG):
    """Estimate outgoing motion from consecutive positions within visible runs only.

    A forward median reduces coordinate jitter and lets the first detected frame after a gap
    have a motion estimate. It is an offline cue, with a few frames of timing uncertainty.
    Never interpolate across a missing position or a half boundary.
    """
    speeds = np.full(len(positions), np.nan)
    visible = np.all(np.isfinite(positions), axis=1)
    for first, stop in blocks:
        for local_start, local_end in previous.true_runs(visible[first:stop]):
            start, end = first + int(local_start), first + int(local_end)
            if end - start <= config["position_speed_minimum_differences"]:
                continue
            metres = positions[start:end] * np.asarray(pitch)
            differences = np.linalg.norm(np.diff(metres, axis=0), axis=1) * fps
            smoothed = pd.Series(differences[::-1]).rolling(
                config["position_speed_window_frames"],
                min_periods=config["position_speed_minimum_differences"]).median().to_numpy()[::-1]
            speeds[start:end - 1] = smoothed
    return speeds


def apply_restart_rule(reference, missing, speeds, long_gaps, events, blocks, config=CONFIG):
    """Add D only to quiet sections supported by both a long gap and a tagged restart.

    A restart estimate is the start of a sustained moving-ball run after a quiet run. Both
    runs must lie within the tag window plus a fixed margin and within one graded half.
    Tag intervals and team tags are never copied directly into output labels.
    """
    candidate = reference.copy()
    supported = np.zeros(len(reference), dtype=bool)
    quiet = missing | (np.isfinite(speeds) & (speeds <= config["maximum_stationary_ball_speed_mps"]))
    moving = ~missing & np.isfinite(speeds) & (speeds >= config["minimum_moving_ball_speed_mps"])
    tagged = [event for event in events
              if (event["code"] or "").strip().casefold() == "set pieces"]
    detected_restarts = set()
    supported_tags = 0
    overlapping_tags = moving_tags = quiet_then_moving_tags = 0
    for event in sorted(tagged, key=lambda item: (item["start_frame"], item["end_frame"])):
        if event["end_frame"] <= event["start_frame"]:
            continue
        used = False
        overlap = has_moving = has_quiet_then_moving = False
        for first, stop in blocks:
            low = max(first, event["start_frame"] - config["tag_margin_frames"])
            high = min(stop, event["end_frame"] + config["tag_margin_frames"])
            if low >= high:
                continue
            overlap |= bool(np.any(long_gaps[low:high]))
            for local_start, local_end in previous.true_runs(moving[low:high]):
                if local_end - local_start < config["minimum_moving_frames"]:
                    continue
                has_moving = True
                restart = low + int(local_start)
                start = restart
                while start > low and quiet[start - 1]:
                    start -= 1
                if restart - start < config["minimum_quiet_frames"]:
                    continue
                has_quiet_then_moving = True
                if not np.any(long_gaps[start:restart]):
                    continue
                candidate[start:restart] = "D"
                supported[start:restart] = True
                detected_restarts.add(restart)
                used = True
                break
        supported_tags += int(used)
        overlapping_tags += int(overlap)
        moving_tags += int(has_moving)
        quiet_then_moving_tags += int(has_quiet_then_moving)
    return candidate, supported, {
        "set_piece_tags": len(tagged),
        "tags_with_restart_evidence": supported_tags,
        "distinct_restart_estimates": len(detected_restarts),
        "supported_dead_frames": int(np.sum(supported)),
        "tags_overlapping_long_gaps": overlapping_tags,
        "tags_with_sustained_moving_ball": moving_tags,
        "tags_with_quiet_then_moving_ball": quiet_then_moving_tags,
    }


def review_intervals(changed, blocks, merge_gap):
    """Group nearby changes for viewing, without combining the two halves."""
    intervals = []
    for first, stop in blocks:
        runs = [(first + int(start), first + int(end))
                for start, end in previous.true_runs(changed[first:stop])]
        merged = []
        for start, end in runs:
            if merged and start - merged[-1][1] <= merge_gap:
                merged[-1] = (merged[-1][0], end)
            else:
                merged.append((start, end))
        intervals.extend(merged)
    return intervals


def main():
    fps, n_frames = GAMES[GAME]["fps"], GAMES[GAME]["n_video_frames"]
    blocks = [(first, last + 1) for _, first, last in half_video_blocks(GAME)]
    graded = np.zeros(n_frames, dtype=bool)
    for first, stop in blocks:
        graded[first:stop] = True

    raw_path = require(["atd_raw", "smart_tagging"])[0]
    missing, player_count, median_speed = previous.read_motion(raw_path, n_frames)
    positions, provided_speeds = read_ball_signals(raw_path, n_frames)
    speeds = position_speeds(positions, GAMES[GAME]["pitch"], fps, blocks)
    events = load_smart_tagging.load()
    slow = ((player_count >= previous.CONFIG["minimum_valid_players"]) &
            (median_speed <= previous.CONFIG["maximum_median_speed_mps"]))
    reference = baseline.smooth(baseline.build(), previous.CONFIG["smoothing_half_window"])
    reference[~graded] = "X"
    _, prior, long_gaps, accepted, gap_counts = previous.apply_gap_rules(
        reference, missing, slow, blocks, previous.CONFIG["minimum_gap_frames"],
        previous.CONFIG["minimum_slow_fraction"])
    provided_candidate, _, provided_diagnostics = apply_restart_rule(
        prior, missing, provided_speeds, long_gaps, events, blocks)
    candidate, supported, diagnostics = apply_restart_rule(
        prior, missing, speeds, long_gaps, events, blocks)
    changed = candidate != prior
    if np.any(changed & (~graded | (candidate != "D"))):
        raise AssertionError("Restart rule changed a frame outside its D-only scope")

    output_dir = ROOT / "data" / "derived" / "experiments" / "004_tagged_restarts"
    output_file = output_dir / "tagged_restarts.csv"
    for filename, labels in ((output_file, candidate),
                             (output_dir / "provided_speed_attempt.csv", provided_candidate)):
        baseline.write_submission(str(filename), labels)
        subprocess.run([sys.executable, str(ROOT / "evaluation" / "validate_submission.py"),
                        str(filename)], check=True, capture_output=True)

    # Predictions are fixed before the public answer key is read.
    gt = pm.label_codes(pm.read_label_csv(str(ROOT / "evaluation" / "gt" /
                                            "BAR-ATH_possession_gt_public.csv")))
    versions = {"smooth50": reference, "experiment_003": prior,
                "provided_speed": provided_candidate, "position_speed": candidate}
    results = {name: previous.summarize(labels, gt, graded, blocks)
               for name, labels in versions.items()}
    public = gt != pm.X
    gt_labels = np.array(pm.LABELS)[gt]
    prior_correct = prior == gt_labels
    intervals = review_intervals(changed, blocks, CONFIG["review_merge_gap_frames"])
    manifest = output_dir / "changed_clips.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("start_frame", "end_frame", "name", "detail"))
        for number, (start, end) in enumerate(intervals, 1):
            writer.writerow((start, end, f"Change {number:02d}",
                             f"{int(np.sum(changed[start:end]))} frames changed from Experiment 003"))
    video = Path(asset_paths()["video"])
    review_created = False
    if intervals and video.is_file():
        _, count = create_review(
            video, manifest, name="004_tagged_restarts", title="Experiment 004: changed sections",
            fps=fps, context_seconds=CONFIG["review_context_seconds"],
            expected_duration_seconds=n_frames / fps)
        if count != len(intervals):
            raise AssertionError("Review count differs from the changed sections")
        review_created = True

    diagnostics.update({
        "provided_speed_attempt": provided_diagnostics,
        "ball_detected_frames_all_video": int(np.sum(~missing)),
        "ball_frames_with_provided_speed_all_video": int(np.sum(np.isfinite(provided_speeds))),
        "ball_detected_frames_graded": int(np.sum(~missing & graded)),
        "ball_frames_with_provided_speed_graded": int(np.sum(np.isfinite(provided_speeds) & graded)),
        "ball_frames_with_position_speed_graded": int(np.sum(np.isfinite(speeds) & graded)),
        "long_gaps": gap_counts["long_gaps"],
        "long_gaps_with_restart_support": sum(
            bool(np.any(supported[start:end])) for start, end in previous.true_runs(long_gaps)),
        "speed_rejected_gaps_with_restart_support": sum(
            bool(np.any(supported[start:end]))
            for start, end in previous.true_runs(long_gaps & ~accepted)),
        "frames_changed_from_experiment_003": int(np.sum(changed)),
        "changed_frames_ball_missing": int(np.sum(changed & missing)),
        "public_changed_frames": int(np.sum(changed & public)),
        "public_errors_corrected": int(np.sum(changed & public & ~prior_correct & (candidate == gt_labels))),
        "public_errors_introduced": int(np.sum(changed & public & prior_correct & (candidate != gt_labels))),
        "review_windows": len(intervals),
        "review_created": review_created,
    })
    source_paths = [Path(__file__).resolve(), ROOT / "experiments/003_player_speed/run.py",
                    ROOT / "starter/baseline.py", ROOT / "starter/load_smart_tagging.py",
                    ROOT / "evaluation/possession_metrics.py", ROOT / "scripts/clip_reviewer.py"]
    report = {
        "config": CONFIG, "base_experiment_config": previous.CONFIG,
        "provenance": {
            "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "source_sha256": {str(path.relative_to(ROOT)): previous.file_hash(path) for path in source_paths},
        },
        "results": results, "diagnostics": diagnostics,
        "candidate_sha256": previous.file_hash(output_file),
    }
    (HERE / "metrics.json").write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print("version          spellF1  macroF1  D precision  D recall   full poss  D share")
    for name, values in results.items():
        print("{:<16} {:>7.4f}  {:>7.4f}  {:>11.3f}  {:>8.3f}  {:>10}  {:>6.1f}%".format(
            name, values["public_spell_f1"], values["public_macro_f1"],
            values["public_dead_precision"], values["public_dead_recall"],
            values["full_possessions"], 100 * values["full_dead_share"]))
    print("Aggregate diagnostics: " + json.dumps(diagnostics, sort_keys=True))
    print("Official validation passed; aggregate metrics saved to experiments/004_tagged_restarts/metrics.json")
    if review_created:
        print("Local reviewer saved under data/derived/clip_reviews/004_tagged_restarts/")


if __name__ == "__main__":
    main()
