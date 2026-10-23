"""Check that your copy of the match data is complete and lined up. Run it once after unpacking.

Every teammate runs this on their own machine and should get the same PASS lines. It prints counts
and percentages only -- never a row of the data -- so its output is safe to paste into a team chat
or an AI assistant. The data itself must not leave your machine (see CLAUDE.md).

    python scripts/check_data.py                 # data checks, a few seconds
    python scripts/check_data.py --baseline      # also rebuilds the baseline, a minute or two

What it checks, against the figures DATA.md publishes:

  tracking      record counts, frame ids contiguous from 1, slots per line, ball present on 56.9%
                of all frames and 59.3% of graded ones, 20.5 tracked objects per graded frame
  homography    one row per frame, valid on 100% (tactical) and 65.8% (broadcast)
  smart tagging 638 instances
  video         199,319 frames, if the video is there and ffprobe is installed (optional)
  --baseline    starter/baseline.py, run on your data, reproduces the four committed baseline
                files byte for byte. The strongest single check: it can only pass if every
                tracking file and the frame alignment are exactly right.

The broadcast assets and both videos are optional. A missing optional file is reported as SKIP,
not FAIL.
"""

import argparse
import filecmp
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, asset_paths, half_video_blocks, source_frames  # noqa: E402

# Params
# Published figures, from DATA.md. Percentages are compared after rounding to one decimal place,
# which is how DATA.md states them.
EXPECTED = {
    "tactical": {"slots": 46, "ball_all": 56.9, "ball_graded": 59.3, "objects_graded": 20.5,
                 "homography_valid": 100.0},
    "broadcast": {"slots": 51, "ball_all": 50.5, "homography_valid": 65.8},
}
N_SMART_TAGGING = 638
MISSING = "N"  # first character of "NaN"
BASELINES = ("baseline_raw", "baseline_smooth25", "baseline_smooth50", "baseline_smooth125")

failures = []


def report(ok, what, got, expected=None):
    """One PASS/FAIL line. Failures are collected so the exit code can say so."""
    status = "PASS" if ok else "FAIL"
    if not ok:
        failures.append(what)
    detail = "{}".format(got) if expected is None else "{} (expected {})".format(got, expected)
    print("  {}  {:<34} {}".format(status, what, detail))


def skip(what, why):
    print("  SKIP  {:<34} {}".format(what, why))


def graded_mask():
    """Boolean over tactical video frames: True inside the two graded halves."""
    mask = np.zeros(source_frames("tactical"), dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        mask[first:last + 1] = True
    return mask


def check_tracking(source, paths):
    """Stream the raw ATD once and compare its shape and ball coverage with DATA.md."""
    expected = EXPECTED[source]
    n_frames = source_frames(source)

    slots = list(ET.parse(paths["atd_meta"]).getroot().iter("Player"))
    report(len(slots) == expected["slots"], "track slots", len(slots), expected["slots"])

    ids, ball, objects = [], [], []
    with open(paths["atd_raw"]) as handle:
        for line in handle:
            parts = line.rstrip("\n").split(":")
            ids.append(int(parts[0]))
            objects.append(sum(group[:1] != MISSING for group in parts[1].split(";")))
            ball.append(parts[2][:1] != MISSING)
    ids, ball, objects = np.array(ids), np.array(ball), np.array(objects)

    contiguous = bool(len(ids)) and ids[0] == 1 and bool(np.all(np.diff(ids) == 1))
    report(len(ids) == n_frames and contiguous, "records, ids 1..n contiguous",
           len(ids), n_frames)

    share = round(100.0 * ball.mean(), 1)
    report(share == expected["ball_all"], "ball present, all frames",
           "{}%".format(share), "{}%".format(expected["ball_all"]))

    if source == "tactical":
        graded = graded_mask()
        share = round(100.0 * ball[graded].mean(), 1)
        report(share == expected["ball_graded"], "ball present, graded frames",
               "{}%".format(share), "{}%".format(expected["ball_graded"]))
        mean_objects = round(float(objects[graded].mean()), 1)
        report(mean_objects == expected["objects_graded"], "tracked objects per graded frame",
               mean_objects, expected["objects_graded"])


def check_homography(source, path):
    table = pd.read_csv(path, usecols=["frame", "valid"])
    n_frames = source_frames(source)
    in_order = bool(np.array_equal(table["frame"].values, np.arange(n_frames)))
    report(len(table) == n_frames and in_order, "homography rows, frames 0..n-1",
           len(table), n_frames)
    share = round(100.0 * (table["valid"] == 1).mean(), 1)
    expected = EXPECTED[source]["homography_valid"]
    report(share == expected, "homography valid", "{}%".format(share), "{}%".format(expected))


def check_smart_tagging(path):
    count = sum(1 for _ in ET.parse(path).getroot().iter("instance"))
    report(count == N_SMART_TAGGING, "smart tagging instances", count, N_SMART_TAGGING)


def check_video(source, path):
    """Exact frame count via ffprobe. Decoding headers only, so it takes about a minute."""
    if shutil.which("ffprobe") is None:
        skip("video frames", "ffprobe not installed (brew install ffmpeg)")
        return
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
         "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True).stdout.strip()
    n_frames = source_frames(source)
    report(out == str(n_frames), "video frames", out, n_frames)


def check_baseline():
    """Rebuild the four baselines into a temp folder and compare them with the committed ones."""
    out_dir = tempfile.mkdtemp(prefix="mtah_baseline_")
    try:
        subprocess.run([sys.executable, os.path.join(ROOT, "starter", "baseline.py"),
                        "--out", out_dir], check=True, capture_output=True)
        for name in BASELINES:
            committed = os.path.join(ROOT, "evaluation", "results", name + ".csv")
            rebuilt = os.path.join(out_dir, name + ".csv")
            same = filecmp.cmp(committed, rebuilt, shallow=False)
            report(same, "rebuilt " + name, "identical" if same else "differs", "identical")
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", action="store_true",
                        help="also rebuild the baseline and compare it byte for byte")
    args = parser.parse_args()

    for source in ("tactical", "broadcast"):
        paths = asset_paths(source=source)
        print("\n{}".format(source))
        if os.path.isfile(paths["atd_raw"]) and os.path.isfile(paths["atd_meta"]):
            check_tracking(source, paths)
        elif source == "tactical":
            report(False, "tracking files", "missing: " + paths["atd_raw"])
        else:
            skip("tracking", "not unpacked (optional)")

        if os.path.isfile(paths["homography"]):
            check_homography(source, paths["homography"])
        else:
            skip("homography", "not unpacked")

        if source == "tactical":
            if os.path.isfile(paths["smart_tagging"]):
                check_smart_tagging(paths["smart_tagging"])
            else:
                report(False, "smart tagging", "missing: " + paths["smart_tagging"])

        if os.path.isfile(paths["video"]):
            check_video(source, paths["video"])
        else:
            skip("video", "not downloaded (optional)")

    if args.baseline:
        print("\nbaseline")
        check_baseline()

    print("\n{}".format("ALL CHECKS PASSED" if not failures else
                        "{} CHECK(S) FAILED: {}".format(len(failures), ", ".join(failures))))
    sys.exit(1 if failures else 0)
