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
    python scripts/vision_pilot.py
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
SEED = 0
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


def frame_jpeg(path, frame):
    return subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", "{:.3f}".format(frame / FPS), "-i", path,
         "-frames:v", "1", "-vf", "scale={}:-2".format(WIDTH), "-f", "image2", "-c:v", "mjpeg",
         "-q:v", "3", "-"], capture_output=True, stdin=subprocess.DEVNULL, check=True).stdout


def ask(jpeg):
    body = json.dumps({"model": MODEL, "prompt": PROMPT, "images": [base64.b64encode(jpeg).decode()],
                       "format": SCHEMA, "stream": False,
                       "options": {"temperature": 0, "seed": SEED}}).encode()
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(json.loads(response.read())["response"])


def pick(mask, rng):
    candidates = np.flatnonzero(mask)
    return rng.choice(candidates, size=min(GROUP_SIZE, len(candidates)), replace=False)


if __name__ == '__main__':
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

    video = asset_paths()["video"]
    answers, started = {}, time.time()
    for name, frames in groups.items():
        answers[name] = [ask(frame_jpeg(video, int(f))) for f in frames]
    seconds = (time.time() - started) / sum(len(f) for f in groups.values())
    print("{:.1f} s per frame on this machine\n".format(seconds))
    print("{:<15} {:>14} {:>10} {:>14} {:>12}".format(
        "group", "says stopped", "unclear", "ball visible", "ball in air"))
    for name, rows in answers.items():
        def share(key, value):
            return "{:.0%}".format(np.mean([r[key] == value for r in rows]))
        print("{:<15} {:>14} {:>10} {:>14} {:>12}".format(
            name, share("play_stopped", "yes"), share("play_stopped", "unclear"),
            share("ball_visible", "yes"), share("ball_in_air", "yes")))
    restarts = [r["restart"] for r in answers["dead"]]
    print("\nrestart named in the 'dead' group: " + ", ".join(
        "{} {}".format(k, restarts.count(k)) for k in sorted(set(restarts))))
    print("A useful model says 'stopped' far more often in the first group than the second.")
