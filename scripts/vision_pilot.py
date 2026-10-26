"""Pilot: can a small local vision model tell, from one frame, whether play is stopped?

A vision-language model running on this machine (Ollama, qwen2.5vl:3b) looks at sampled frames of
the tactical video and answers fixed questions in JSON. The frames go only to the local model.
This prints timing and agreement counts only.

Frames, GROUP_SIZE per group, from v3's own calls on our match (away from any boundary):
  dead          v3 calls a stoppage
  live, at feet v3 calls live play and a player is within 1 m of the ball
  live, missing v3 calls live play and the ball is missing
Agreement with v3 is not accuracy -- v3 is wrong sometimes too -- but a model that cannot separate
the first two groups is no use, and the third group shows what it says where we know least.

    ollama serve &
    python scripts/vision_pilot.py                                     # pilot 1: whole frame
    python scripts/vision_pilot.py --model qwen3-vl:4b --crop --sequence   # pilot 2

Pilot 1 (qwen2.5vl:3b, whole frame) called every frame "stopped": in the wide tactical view the
players are a few pixels tall, and one still frame shows no movement. Pilot 2 options:
  --crop       a CROP_W x CROP_H pixel window around the ball -- or its last known position when
               it is missing -- located with the frame's homography, scaled up for the model
  --sequence   three frames, SEQUENCE_STEP apart, so the model can see whether play moves
"""

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES, asset_paths, half_video_blocks  # noqa: E402

from possession import control  # noqa: E402
from possession.methods import METHODS  # noqa: E402
from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
MODEL = "qwen2.5vl:3b"
URL = "http://localhost:11434/api/generate"
GROUP_SIZE = 10
MARGIN = 2 * FPS          # frames away from any change of v3's label
WIDTH = 1280              # frames are scaled down to this width before the model sees them
CROP_W, CROP_H = 640, 360 # pixels of the 1920x1080 frame around the action
CROP_SCALE = 960          # width the crop is scaled to
SEQUENCE_STEP = FPS       # frames between the images of a sequence
SEED = 0
TIMEOUT = 300             # s per question before giving up
PROMPT = """This is a wide camera view of a professional football match.
Answer only from what the image shows.
- play_stopped: "yes" if the ball is out of play or play is clearly paused (players waiting for a
  restart, a celebration, an injury, a substitution), "no" if play is live, else "unclear".
- restart: the restart being prepared or taken, if any.
- ball_visible: whether you can see the ball.
- ball_in_air: whether the ball is in the air rather than on the ground."""
SCHEMA = {"type": "object", "properties": {
    "play_stopped": {"type": "string", "enum": ["yes", "no", "unclear"]},
    "restart": {"type": "string", "enum": ["none", "throw-in", "corner", "free kick", "goal kick",
                                           "kickoff", "penalty", "unclear"]},
    "ball_visible": {"type": "string", "enum": ["yes", "no"]},
    "ball_in_air": {"type": "string", "enum": ["yes", "no", "unclear"]}},
    "required": ["play_stopped", "restart", "ball_visible", "ball_in_air"]}


def frame_jpeg(path, frame, window=None):
    """One frame as JPEG: scaled whole, or the pixel window (x, y) cropped and scaled up."""
    if window is None:
        vf = "scale={}:-2".format(WIDTH)
    else:
        vf = "crop={}:{}:{}:{},scale={}:-2".format(CROP_W, CROP_H, window[0], window[1], CROP_SCALE)
    return subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", "{:.3f}".format(frame / FPS), "-i", path,
         "-frames:v", "1", "-vf", vf, "-f", "image2", "-c:v", "mjpeg",
         "-q:v", "3", "-"], capture_output=True, stdin=subprocess.DEVNULL, check=True).stdout


def crop_window(homography, point):
    """Top-left pixel of a CROP_W x CROP_H window centred on a pitch point (normalised x, y)."""
    p = homography @ np.array([point[0], point[1], 1.0])
    u, v = p[0] / p[2], p[1] / p[2]
    x = int(np.clip(u - CROP_W / 2, 0, 1920 - CROP_W))
    y = int(np.clip(v - CROP_H / 2, 0, 1080 - CROP_H))
    return x, y


def ask(jpegs, model, prompt):
    """The model's JSON answer, or None if it fails or takes longer than TIMEOUT. Thinking is off
    and the context small: on an 8 GB machine a 4B vision model with thinking on did not answer
    one cropped image within 10 minutes, swapping heavily."""
    body = json.dumps({"model": model, "prompt": prompt,
                       "images": [base64.b64encode(j).decode() for j in jpegs],
                       "format": SCHEMA, "stream": False, "think": False,
                       "options": {"temperature": 0, "seed": SEED, "num_ctx": 2048}}).encode()
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(json.loads(response.read())["response"])
    except (OSError, ValueError, KeyError):
        return None


def pick(mask, rng):
    candidates = np.flatnonzero(mask)
    return rng.choice(candidates, size=min(GROUP_SIZE, len(candidates)), replace=False)


SEQUENCE_NOTE = """You are shown three images of the same area, one second apart (oldest first).
Use the change between them: players walking or standing and the ball not moving suggests play is
stopped; players running and the ball moving suggests play is live.
"""

if __name__ == '__main__':
    import argparse
    import pandas as pd
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--crop", action="store_true")
    parser.add_argument("--sequence", action="store_true")
    args = parser.parse_args()
    prompt = (SEQUENCE_NOTE if args.sequence else "") + PROMPT
    if args.crop:
        homography = pd.read_csv(asset_paths()["homography"]).set_index("frame")[
            ["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]].to_numpy()

    tracking = load_tracking()
    v3 = METHODS["v3"](tracking)
    graded = np.zeros(len(v3), dtype=bool)
    for _, a, b in half_video_blocks(GAME):
        graded[a:b + 1] = True
    # Away from boundaries: the label is the same MARGIN frames either side.
    steady = graded.copy()
    steady[MARGIN:-MARGIN] &= (v3[:-2 * MARGIN] == v3[2 * MARGIN:])
    dist = control.team_distances(tracking["players"], tracking["ball"], tracking["team"], PITCH)
    at_feet = np.nanmin(dist, axis=1) < 1.0
    missing = np.isnan(tracking["ball"][:, 0])
    live = np.isin(v3, ["H", "A"])
    rng = np.random.default_rng(SEED)
    groups = {"dead": pick(steady & (v3 == "D"), rng),
              "live, at feet": pick(steady & live & at_feet & ~missing, rng),
              "live, missing": pick(steady & live & missing, rng)}

    # Where the action is: the ball, or its last known position while it is missing.
    seen = ~np.isnan(tracking["ball"][:, 0])
    last = np.maximum.accumulate(np.where(seen, np.arange(len(seen)), 0))
    focus = tracking["ball"][last]

    video = asset_paths()["video"]
    answers, started = {}, time.time()
    for name, frames in groups.items():
        answers[name] = []
        for f in frames:
            f = int(f)
            shots = [f - SEQUENCE_STEP, f, f + SEQUENCE_STEP] if args.sequence else [f]
            window = crop_window(homography[f].reshape(3, 3), focus[f]) if args.crop else None
            answers[name].append(ask([frame_jpeg(video, g, window) for g in shots],
                                     args.model, prompt))
    seconds = (time.time() - started) / sum(len(f) for f in groups.values())
    print("model {}, crop {}, sequence {}: {:.1f} s per moment on this machine\n".format(
        args.model, args.crop, args.sequence, seconds))
    print("{:<15} {:>14} {:>10} {:>14} {:>12}".format(
        "group", "says stopped", "unclear", "ball visible", "ball in air"))
    for name, rows in answers.items():
        failed = sum(r is None for r in rows)
        rows = [r for r in rows if r]
        if failed:
            print("  ({}: {} of {} questions failed or timed out)".format(name, failed, failed + len(rows)))
        if not rows:
            continue

        def share(key, value):
            return "{:.0%}".format(np.mean([r[key] == value for r in rows]))
        print("{:<15} {:>14} {:>10} {:>14} {:>12}".format(
            name, share("play_stopped", "yes"), share("play_stopped", "unclear"),
            share("ball_visible", "yes"), share("ball_in_air", "yes")))
    restarts = [r["restart"] for r in answers["dead"] if r]
    print("\nrestart named in the 'dead' group: " + ", ".join(
        "{} {}".format(k, restarts.count(k)) for k in sorted(set(restarts))))
    print("A useful model says 'stopped' far more often in the first group than the second.")
