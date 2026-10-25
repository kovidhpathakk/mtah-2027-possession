"""Send Experiment 003's rejected-gap timestamps to the shared clip reviewer.

Tracking is processed locally. The timestamp CSV and generated player stay in ignored
data/derived/. Only an aggregate clip count and output paths are printed.
"""

import csv
import json
from pathlib import Path

import numpy as np

from run import (CONFIG, GAME, GAMES, HERE, ROOT, apply_gap_rules,
                 half_video_blocks, read_motion, require, true_runs)
from games import asset_paths
from scripts.clip_reviewer import create_review


def build_entries(rejected, usable, slow, halves, fps):
    """Return exact rejected intervals within each half, with diagnostic context."""
    entries = []
    for half, first, last in halves:
        for local_start, local_stop in true_runs(rejected[first:last + 1]):
            start, stop = first + int(local_start), first + int(local_stop)
            entries.append({
                "start_seconds": start / fps,
                "end_seconds": stop / fps,
                "name": f"Gap {len(entries) + 1:02d}",
                "detail": (
                    f"Half {half}; slow-player evidence: {100 * float(np.mean(slow[start:stop])):.1f}% "
                    f"of gap frames; usable player speeds: "
                    f"{100 * float(np.mean(usable[start:stop])):.1f}%"
                ),
            })
    return entries


def main():
    fps = GAMES[GAME]["fps"]
    n_frames = GAMES[GAME]["n_video_frames"]
    video = Path(asset_paths()["video"])
    if not video.is_file():
        raise SystemExit("Tactical video is missing from the configured data location")
    metrics = json.loads((HERE / "metrics.json").read_text())
    if metrics["config"] != CONFIG:
        raise SystemExit("Experiment settings changed; rerun Experiment 003 before making its review list")

    missing, player_count, median_speed = read_motion(require(["atd_raw"])[0], n_frames)
    usable = player_count >= CONFIG["minimum_valid_players"]
    slow = usable & (median_speed <= CONFIG["maximum_median_speed_mps"])
    halves = half_video_blocks(GAME)
    blocks = [(first, last + 1) for _, first, last in halves]
    # Reuse the actual experiment's gate. The placeholder labels do not affect gap selection.
    _, _, long_gaps, accepted, counts = apply_gap_rules(
        np.full(n_frames, "X"), missing, slow, blocks,
        CONFIG["minimum_gap_frames"], CONFIG["minimum_slow_fraction"])
    entries = build_entries(long_gaps & ~accepted, usable, slow, halves, fps)
    expected = metrics["diagnostics"]["rejected_gaps"]
    if len(entries) != expected or len(entries) != counts["long_gaps"] - counts["accepted_gaps"]:
        raise SystemExit("Gap count differs from the saved experiment; rerun Experiment 003 first")

    manifest = ROOT / "data" / "derived" / "experiments" / "003_player_speed" / "rejected_gaps.csv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("start_seconds", "end_seconds", "name", "detail"))
        writer.writeheader()
        writer.writerows(entries)

    output, count = create_review(
        video, manifest, name="003_player_speed", title="Experiment 003: rejected gaps",
        context_seconds=5, expected_duration_seconds=n_frames / fps,
    )
    if count != expected:
        raise AssertionError("Shared reviewer clip count differs from the experiment")
    print(f"Created {count} local review windows with up to 5 seconds of context on both sides.")
    print("Saved timestamp CSV under data/derived/experiments/003_player_speed/.")
    print(f"Saved shared clip reviewer under {output.relative_to(ROOT)}/")
    print("The generated interval list was not printed; no video frames were viewed.")


if __name__ == "__main__":
    main()
