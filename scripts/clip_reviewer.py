"""Build a local video reviewer from an experiment's timestamp CSV.

The source CSV and generated pages contain match-specific intervals. Keep them in ignored
data/derived/; this script prints only the number of clips and the output directory.
"""

import argparse
import csv
import json
import math
import os
import re
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "data" / "derived" / "clip_reviews"
TEMPLATE = Path(__file__).with_name("clip_reviewer_template.html")


def format_timestamp(seconds):
    """Format elapsed video seconds to milliseconds."""
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("Timestamp must be finite and nonnegative")
    total_ms = round(seconds * 1000)
    hours, rest = divmod(total_ms, 3600000)
    minutes, rest = divmod(rest, 60000)
    whole_seconds, milliseconds = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Clip timestamps must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError("Clip timestamps must be finite")
    return result


def read_clips(path, fps=None, expected_duration_seconds=None):
    """Read half-open intervals in seconds or frames; never print their contents."""
    if fps is not None and (not math.isfinite(fps) or fps <= 0):
        raise ValueError("FPS must be positive and finite")
    if expected_duration_seconds is not None and (
        not math.isfinite(expected_duration_seconds) or expected_duration_seconds <= 0
    ):
        raise ValueError("Expected video duration must be positive and finite")

    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        in_seconds = {"start_seconds", "end_seconds"}.issubset(fields)
        in_frames = {"start_frame", "end_frame"}.issubset(fields)
        if in_seconds == in_frames:
            raise ValueError("CSV needs exactly one start/end pair: seconds or frames")
        if in_frames and fps is None:
            raise ValueError("Frame timestamps require --fps")

        clips = []
        try:
            for row in reader:
                if None in row:
                    raise ValueError("CSV has an unexpected extra field")
                if in_seconds:
                    start = _number(row["start_seconds"])
                    end = _number(row["end_seconds"])
                else:
                    start_frame = _number(row["start_frame"])
                    end_frame = _number(row["end_frame"])
                    if not start_frame.is_integer() or not end_frame.is_integer():
                        raise ValueError("Frame timestamps must be whole numbers")
                    start, end = start_frame / fps, end_frame / fps
                if start < 0 or end <= start:
                    raise ValueError("Clip intervals must have 0 <= start < end")
                if expected_duration_seconds is not None and end > expected_duration_seconds:
                    raise ValueError("A clip extends beyond the expected video duration")
                clips.append({
                    "number": len(clips) + 1,
                    "name": (row.get("name") or "").strip() or f"Clip {len(clips) + 1:02d}",
                    "detail": (row.get("detail") or "").strip(),
                    "start_seconds": start,
                    "end_seconds": end,
                })
        except csv.Error as exc:
            raise ValueError("Could not read the clip CSV") from exc
    if not clips:
        raise ValueError("The clip CSV is empty")
    return clips


def with_context(clips, context_seconds, expected_duration_seconds=None):
    """Add bounded viewing windows while preserving the supplied clip intervals."""
    if not math.isfinite(context_seconds) or context_seconds < 0:
        raise ValueError("Context seconds must be finite and nonnegative")
    entries = []
    for clip in clips:
        start, end = clip["start_seconds"], clip["end_seconds"]
        review_start = max(0.0, start - context_seconds)
        review_end = end + context_seconds
        if expected_duration_seconds is not None:
            review_end = min(expected_duration_seconds, review_end)
        entries.append({
            **clip,
            "start": format_timestamp(start),
            "end": format_timestamp(end),
            "duration_seconds": end - start,
            "review_start": format_timestamp(review_start),
            "review_end": format_timestamp(review_end),
            "review_start_seconds": review_start,
            "review_end_seconds": review_end,
        })
    return entries


def _markdown_text(value):
    return value.replace("\r", " ").replace("\n", " ").replace("|", "\\|")


def render_timestamps(entries, title, context_seconds):
    lines = [
        f"# {_markdown_text(title)}",
        "",
        "Times are elapsed time in the selected video, not the match clock. They do not apply",
        "to a different camera unless its timeline is synchronized.",
        "",
        f"Each review window includes up to {context_seconds:g} seconds of context on each side.",
        "End times are exclusive. Keep this generated list local under data/derived/.",
        "",
        "[Open the local clip reviewer](review.html)",
        "",
        "| Clip | Starts | Ends | Review from | Review through | Detail |",
        "|---|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| {} | {} | {} | {} | {} | {} |".format(
                _markdown_text(entry["name"]), entry["start"], entry["end"],
                entry["review_start"], entry["review_end"], _markdown_text(entry["detail"])
            )
        )
    return "\n".join(lines) + "\n"


def create_review(video, clips_csv, name, context_seconds=5,
                  expected_duration_seconds=None, fps=None, title=None):
    """Generate one self-contained local player plus a timestamp list."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError("Review name must contain only letters, numbers, _ or -")
    video = Path(video).resolve()
    if not video.is_file():
        raise ValueError("Video file is missing")
    clips = read_clips(clips_csv, fps=fps, expected_duration_seconds=expected_duration_seconds)
    entries = with_context(clips, context_seconds, expected_duration_seconds)
    output = OUTPUT_ROOT / name
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "clips": entries,
        "title": title or name.replace("_", " "),
        "video": quote(os.path.relpath(video, output).replace(os.sep, "/"), safe="/"),
        "expectedDuration": expected_duration_seconds,
    }
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count("__REVIEW_PAYLOAD__") != 1:
        raise ValueError("Review template must contain one data placeholder")
    embedded_json = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    for char, escape in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                         ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        embedded_json = embedded_json.replace(char, escape)
    (output / "review.html").write_text(
        template.replace("__REVIEW_PAYLOAD__", embedded_json), encoding="utf-8"
    )
    (output / "timestamps.md").write_text(
        render_timestamps(entries, payload["title"], context_seconds), encoding="utf-8"
    )
    return output, len(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clips", type=Path, required=True, help="CSV with start/end timestamps")
    parser.add_argument("--video", type=Path, required=True, help="Local video file")
    parser.add_argument("--name", required=True, help="Output folder name under data/derived/clip_reviews/")
    parser.add_argument("--title", help="Title shown in the player")
    parser.add_argument("--fps", type=float, help="Required if the CSV uses frame numbers")
    parser.add_argument("--context-seconds", type=float, default=5)
    parser.add_argument("--expected-duration-seconds", type=float)
    args = parser.parse_args()
    try:
        output, count = create_review(
            args.video, args.clips, args.name, args.context_seconds,
            args.expected_duration_seconds, args.fps, args.title
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Created {count} local review windows under {output.relative_to(ROOT)}/")
    print("The interval list was not printed; no video frames were viewed.")


if __name__ == "__main__":
    main()
