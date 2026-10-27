"""Clips of our match for Kovidh to watch, at the moments v6 is most likely to be wrong.

Claude may not see the video (CLAUDE.md), and numbers only go so far: deep dive 5 needs someone to
look at what actually happens where the model is doubtful. This script picks those moments by
algorithm -- never from the public answers -- and cuts short clips with three things drawn on them:

  top bar      v6's answer on that frame: blue = Barca (H), red = Athletic (A), grey = dead (D)
  second bar   (only for the "v6 vs v4" kind) v4's answer, same colours
  yellow strip the tracker has no ball on that frame
  ring         where the tracker puts the ball (mapped into the picture by the homography)
  white strip  at the bottom: the stretch the clip is about

Kinds of moment (KINDS), up to PER_KIND each, spread over the match:
  moving_dead     players at walking pace while the ball is visible and moving: is play stopped,
                  and what is the ball doing? (checks the damage kit's new dead ball)
  long_ball       the ball moving at 18 m/s+ for 0.6 s+ over 20 m+: probably in the air. Does the
                  ring follow the real ball, and who ends up with it?
  v6_vs_v4        v6 and v4 name different teams for 3 s+ of live play
  unsure_dead     v6's stoppage model unsure (P(dead) 0.3-0.7) for 2 s+
  tags_disagree   v6 names the other team inside a Smart Tagging open-play phase for 5 s+
  long_possession v6 possessions of 45 s+: was it really one team throughout?
  few_players     the tracker follows fewer than 14 people during v6's live play for 2 s+

Clips and index.csv go to data/derived/clips/review/ (local only: gitignored, the guard blocks
video). The index lists each clip's kind, match clock, where the white strip starts, a question,
and an empty notes column. HOW TO USE IT: watch, then tell Claude the GENERAL PATTERN per kind
("most moving_dead clips are throw-ins being carried to the line"). Never turn a clip into a label
for this match: that is hand labelling, which the rules forbid. Claude does not read index.csv:
it holds v6's answers at specific moments of our match.

    .venv/bin/python scripts/review_clips.py [--per-kind 6]

Needs ffmpeg. Prints counts only.
"""

import argparse
import csv
import os
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from gap_clips import match_clock  # noqa: E402
from games import GAME, asset_paths, half_video_blocks  # noqa: E402

from possession import cleanup, learned, stoppages, tagging  # noqa: E402
from possession.blackout import windowed_mean  # noqa: E402
from possession.methods import METHODS  # noqa: E402
from possession.tracking import DERIVED_DIR, PITCH, load_tracking  # noqa: E402

# Params
FPS = 25
OUT_DIR = os.path.join(DERIVED_DIR, "clips", "review")
PER_KIND = 6
LEAD = 3 * FPS                 # frames shown before and after the stretch
MAX_FOCUS = 60 * FPS           # longest stretch shown
SEED = 0
W, H = 1920, 1080
COLOURS = {"H": (200, 80, 0), "A": (30, 30, 210), "D": (128, 128, 128), "X": (0, 0, 0)}  # BGR
YELLOW, WHITE, RING = (0, 220, 255), (255, 255, 255), (255, 0, 255)
QUESTIONS = {
    "moving_dead": "Is play stopped during the white strip? What is the ball doing (carried, thrown, rolled, kicked about)?",
    "long_ball": "Is the ball in the air? Does the ring follow it? Who ends up with it, and does the top bar change at the right moment?",
    "v6_vs_v4": "Which team really has the ball during the white strip: top bar (v6) or second bar (v4)? What is going on?",
    "unsure_dead": "Is play stopped during the white strip? What gives it away (whistle, ball out, injury, players walking)?",
    "tags_disagree": "Which team is in control during the white strip? Does v6 (top bar) look right?",
    "long_possession": "Does the ball really stay with one team throughout, or do changes get missed?",
    "few_players": "What is on screen while the tracker loses people (replay, camera move, crowd, players off the pitch)?",
}


def runs(mask, min_length):
    return [(a, b) for a, b in stoppages.runs(mask) if b - a >= min_length]


def pick(candidates, n, rng):
    """Up to n stretches spread over the match: a random sample, in match order."""
    if len(candidates) <= n:
        return candidates
    index = np.sort(rng.choice(len(candidates), n, replace=False))
    return [candidates[i] for i in index]


def moments(per_kind):
    """{kind: [(first, stop)]} and the per-frame arrays the overlay needs."""
    t = load_tracking()
    n = len(t["ball"])
    graded = np.zeros(n, dtype=bool)
    for _, a, b in half_video_blocks(GAME):
        graded[a:b + 1] = True
    v6 = np.asarray(METHODS["v6"](t), dtype="<U1")
    v4 = np.asarray(METHODS["v4"](t), dtype="<U1")
    p_dead, _ = learned.probabilities(t)
    clean = cleanup.clean(t)
    ball = clean["ball"] * np.array(PITCH)
    seen = ~np.isnan(ball[:, 0])
    on = ~np.isnan(clean["players"][:, :, 0])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mean_speed = np.nanmean(np.where(on, clean["speed"], np.nan), axis=1)
    walking = windowed_mean(mean_speed / np.nanmedian(mean_speed[seen & graded]), 75) < 0.5
    speed = stoppages.ball_speed(ball)
    live6 = np.isin(v6, ("H", "A"))
    tagged = tagging.tag_team(n, tagging.real_tags(), ("open",))
    tag_letter = np.where(tagged == 0, "H", np.where(tagged == 1, "A", ""))

    found = {}
    found["moving_dead"] = runs(graded & seen & walking & (speed >= stoppages.STILL), FPS)
    fast = []
    for a, b in runs(graded & seen & (speed >= 18.0), 15):
        if np.linalg.norm(ball[b - 1] - ball[a]) >= 20.0:
            fast.append((a, b))
    found["long_ball"] = fast
    found["v6_vs_v4"] = runs(graded & live6 & np.isin(v4, ("H", "A")) & (v6 != v4), 3 * FPS)
    found["unsure_dead"] = runs(graded & (p_dead > 0.3) & (p_dead < 0.7), 2 * FPS)
    found["tags_disagree"] = runs(graded & live6 & (tag_letter != "") & (tag_letter != v6), 5 * FPS)
    starts = np.flatnonzero(np.r_[True, v6[1:] != v6[:-1]])
    stops = np.r_[starts[1:], n]
    found["long_possession"] = [(a, b) for a, b in zip(starts, stops)
                                if v6[a] in ("H", "A") and graded[a] and b - a >= 45 * FPS]
    count = on.sum(axis=1)
    found["few_players"] = runs(graded & live6 & (count < 14), 2 * FPS)

    rng = np.random.default_rng(SEED)
    chosen = {kind: pick(found[kind], per_kind, rng) for kind in QUESTIONS}
    return chosen, found, {"v6": v6, "v4": v4, "seen": seen, "ball": t["ball"]}


def homographies():
    hb = pd.read_csv(asset_paths()["homography"]).set_index("frame")
    return hb[["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]].to_numpy().reshape(-1, 3, 3)


def draw(img, f, focus, layers, Hs, with_v4):
    img[0:36] = COLOURS[layers["v6"][f]]
    y = 36
    if with_v4:
        img[y:y + 22] = COLOURS[layers["v4"][f]]
        y += 22
    if not layers["seen"][f]:
        img[y:y + 14] = YELLOW
    if focus[0] <= f < focus[1]:
        img[H - 16:H] = WHITE
    x, yb = layers["ball"][f]
    if not np.isnan(x) and f < len(Hs):
        p = Hs[f] @ np.array([x, yb, 1.0])
        cx, cy = int(p[0] / p[2]), int(p[1] / p[2])
        r, width = 16, 4
        x0, x1 = max(0, cx - r - width), min(W, cx + r + width + 1)
        y0, y1 = max(0, cy - r - width), min(H, cy + r + width + 1)
        if x0 < x1 and y0 < y1:
            yy, xx = np.ogrid[y0:y1, x0:x1]
            d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            img[y0:y1, x0:x1][(d >= r) & (d <= r + width)] = RING


def cut(video, out_path, first, last, focus, layers, Hs, with_v4):
    """Decode [first, last), draw the overlay on every frame, encode at 1280 px."""
    reader = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", "{:.3f}".format(first / FPS), "-i", video,
         "-frames:v", str(last - first), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    writer = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s",
         "{}x{}".format(W, H), "-r", str(FPS), "-i", "-", "-vf", "scale=1280:-2", "-c:v",
         "libx264", "-crf", "28", "-preset", "veryfast", "-pix_fmt", "yuv420p", out_path],
        stdin=subprocess.PIPE)
    size = W * H * 3
    for f in range(first, last):
        raw = reader.stdout.read(size)
        if len(raw) < size:
            break
        img = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 3).copy()
        draw(img, f, focus, layers, Hs, with_v4)
        writer.stdin.write(img.tobytes())
    reader.stdout.close()
    reader.wait()
    writer.stdin.close()
    writer.wait()


def half_of(frame):
    for half, a, b in half_video_blocks(GAME):
        if a <= frame <= b:
            return half
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--per-kind", type=int, default=PER_KIND)
    parser.add_argument("--out", default=OUT_DIR)
    args = parser.parse_args()
    out_dir = os.path.expanduser(args.out)
    video = asset_paths()["video"]
    if not os.path.isfile(video):
        sys.exit("no video at {} -- see SETUP.md".format(video))
    index = os.path.join(out_dir, "index.csv")
    if os.path.isfile(index):
        sys.exit("{} exists (it may hold notes): move it away first".format(index))

    chosen, found, layers = moments(args.per_kind)
    Hs = homographies()
    os.makedirs(out_dir, exist_ok=True)
    blocks = {half: (a, b) for half, a, b in half_video_blocks(GAME)}
    rows = []
    for kind, stretches in chosen.items():
        for k, (a, b) in enumerate(stretches, 1):
            half = half_of(a)
            b = min(b, a + MAX_FOCUS)
            first = max(a - LEAD, blocks[half][0])
            last = min(b + LEAD, blocks[half][1] + 1)
            name = "{}_{:02d}.mp4".format(kind, k)
            cut(video, os.path.join(out_dir, name), first, last, (a, b), layers, Hs,
                kind == "v6_vs_v4")
            rows.append({"clip": name, "kind": kind, "half": half,
                         "clip starts at": match_clock(half, first),
                         "white strip from (s into clip)": round((a - first) / FPS, 1),
                         "white strip lasts (s)": round((b - a) / FPS, 1),
                         "question": QUESTIONS[kind], "your notes": ""})
        print("  {:<16} {:>3} cut of {:>5} found".format(kind, len(stretches), len(found[kind])))
    with open(index, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print("\n{} clips and index.csv in {}".format(len(rows), out_dir))
