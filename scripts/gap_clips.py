"""Cut video clips around the longest ball blackouts, so we can see WHY the ball goes missing.

The ball is missing on 41% of graded frames, in long gaps (median ~11 s). Whether those gaps are
stoppages, crowded scrambles, balls in the air or plain tracker failures decides how we handle
them -- and whether building our own ball detector is worth it. Only watching tells us.

    python scripts/gap_clips.py                # the 15 longest gaps
    python scripts/gap_clips.py --top 25

Each clip runs from LEAD seconds before the ball disappears to LEAD seconds after it returns. A
red bar across the top of the picture marks the frames where the tracker has no ball. Clips and
an index (clip name, half, match clock, length) go to data/derived/clips/ -- local only: they are
gitignored, the guard blocks video files, and they must never be shared publicly.

HOW TO USE WHAT YOU SEE. Write general patterns in docs/football-notes.md ("long gaps where
players walk are stoppages"), and we turn patterns into rules. Never encode a specific gap of this
match as a label -- that is hand labelling, which the rules forbid.

Needs ffmpeg (brew install ffmpeg). Prints counts only.
"""

import argparse
import csv
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES, asset_paths, half_video_blocks  # noqa: E402

from possession.polish import SECOND_HALF_KICKOFF  # noqa: E402
from possession.tracking import DERIVED_DIR, load_tracking  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
LEAD = 3  # seconds of context either side of the gap
OUT_DIR = os.path.join(DERIVED_DIR, "clips")
WIDTH = 1280  # downscaled from 1920 to keep the clips small
BAR = "drawbox=x=0:y=0:w=iw:h=ih/14:color=red@0.85:t=fill:enable='between(n,{},{})'"
# Match clock zero of each half: the kickoffs (FAQ.md), so the clock reads like the broadcast's.
CLOCK_ZERO = {1: half_video_blocks(GAME)[0][1], 2: SECOND_HALF_KICKOFF}
CLOCK_OFFSET_MIN = {1: 0, 2: 45}


def ball_gaps(ball):
    """[(half, first_frame, last_frame)] of every missing-ball run inside the graded halves."""
    gaps = []
    for half, first, last in half_video_blocks(GAME):
        missing = np.isnan(ball[first:last + 1, 0]).astype(np.int8)
        edges = np.diff(np.concatenate(([0], missing, [0])))
        for start, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            gaps.append((half, first + int(start), first + int(stop) - 1))
    return gaps


def match_clock(half, frame):
    seconds = (frame - CLOCK_ZERO[half]) / FPS
    minutes = CLOCK_OFFSET_MIN[half] + int(seconds // 60)
    return "{}'{:02d}".format(minutes, int(seconds % 60)) if seconds >= 0 else "pre-kickoff"


def cut(video, out_path, first, last, gap_first, gap_last):
    """Re-encode [first, last] with the red bar over the gap frames (frame numbers in the clip)."""
    bar = BAR.format(gap_first - first, gap_last - first)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", "{:.2f}".format(first / FPS), "-i", video,
         "-frames:v", str(last - first + 1), "-an",
         "-vf", "scale={}:-2,{}".format(WIDTH, bar),
         "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", out_path],
        check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--top", type=int, default=15, help="how many of the longest gaps")
    args = parser.parse_args()

    video = asset_paths()["video"]
    if not os.path.isfile(video):
        sys.exit("no video at {} -- see SETUP.md".format(video))

    gaps = sorted(ball_gaps(load_tracking()["ball"]), key=lambda g: g[1] - g[2])[:args.top]
    os.makedirs(OUT_DIR, exist_ok=True)
    blocks = dict((half, (first, last)) for half, first, last in half_video_blocks(GAME))

    rows = []
    for rank, (half, gap_first, gap_last) in enumerate(gaps, 1):
        first = max(gap_first - LEAD * FPS, blocks[half][0])
        last = min(gap_last + LEAD * FPS, blocks[half][1])
        name = "gap{:02d}.mp4".format(rank)
        cut(video, os.path.join(OUT_DIR, name), first, last, gap_first, gap_last)
        rows.append({"clip": name, "half": half, "ball lost at": match_clock(half, gap_first),
                     "missing for (s)": round((gap_last - gap_first + 1) / FPS, 1),
                     "cause (stoppage / crowd / air / off-camera / visible)": ""})
        print("  cut {} of {}".format(rank, len(gaps)))

    with open(os.path.join(OUT_DIR, "index.csv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    total = sum(r["missing for (s)"] for r in rows)
    print("\n{} clips in {}, covering {:.0f} s of missing ball. Index: index.csv".format(
        len(rows), os.path.relpath(OUT_DIR, ROOT), total))
