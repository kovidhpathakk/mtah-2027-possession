"""Track T pilot: can a football-trained ball detector give us our own, sharper ball track?

The provided ball track is missing on 41% of graded frames and looks heavily smoothed (assumption
A3 in docs/data.md: sharp velocity changes on 1.9% of live frames against 9-13% in other tracking).
A ball track of our own from the video could be sharp and could fill gaps. This pilot runs the
Roboflow "sports" ball detector (YOLOv8x trained on DFL Bundesliga Data Shootout footage, not our
match; models/football-ball-detection.pt, SHA-256 below) on the CPU -- the Apple GPU path hangs --
and maps each detection to the pitch through the frame's homography. Three tests:

  A accuracy  random live frames where the provided track has a ball: is a detection within
              MATCH m of it? Is the most confident detection that one?
  B gaps      random live frames where the provided track has no ball: how often is a ball found
              on the pitch, and how far from where the ball was last seen?
  C smoothing runs of RUN_LENGTH consecutive frames around moments v4 thinks a player gained the
              ball: velocity changes of the detected ball against the provided one on the same
              frames. A much higher rate of sharp changes on the detected ball confirms A3.

Everything runs locally; results go to data/derived/ball_pilot.npz; this prints counts only.

    .venv-video/bin/python scripts/ball_pilot.py
"""

import hashlib
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, asset_paths, half_video_blocks  # noqa: E402

from possession import control  # noqa: E402
from possession.methods import METHODS  # noqa: E402
from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
FPS = 25
MODEL = os.path.join(ROOT, "models", "football-ball-detection.pt")
MODEL_SHA256 = "678fbad05134f19c5094cb8d273812ec9c6691228180d46832551ecf99ed2912"
IMGSZ = 1280
CONF = 0.1
MATCH = 2.0            # m: a detection this close to the provided ball is the same ball
GROUP = 80             # frames in tests A and B
RUNS, RUN_LENGTH = 6, 50
SEED = 0
OUT = os.path.join(ROOT, "data", "derived", "ball_pilot.npz")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def frames_bgr(video, first, count):
    """`count` consecutive frames from `first`, as BGR arrays, in one ffmpeg call."""
    raw = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", "{:.3f}".format(first / FPS), "-i", video,
         "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True, stdin=subprocess.DEVNULL, check=True).stdout
    size = 1080 * 1920 * 3
    return [np.frombuffer(raw[k * size:(k + 1) * size], dtype=np.uint8).reshape(1080, 1920, 3)
            for k in range(len(raw) // size)]


def detect(model, image, H):
    """[(confidence, x_m, y_m)] for every ball detection, mapped to the pitch in metres."""
    result = model.predict(image, imgsz=IMGSZ, conf=CONF, device="cpu", verbose=False)[0]
    inverse = np.linalg.inv(H)
    out = []
    for conf, box in zip(result.boxes.conf.numpy(), result.boxes.xyxy.numpy()):
        u, v = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        p = inverse @ np.array([u, v, 1.0])
        out.append((float(conf), p[0] / p[2] * PITCH[0], p[1] / p[2] * PITCH[1]))
    return out


def velocity_changes(path_m):
    """|v(t+3) - v(t-3)| in m/s, velocities from +/- 2 frames; NaN where undefined."""
    v = control.ball_velocity(path_m)
    k = control.TOUCH_SPAN
    out = np.full(len(v), np.nan)
    out[k:-k] = np.linalg.norm(v[2 * k:] - v[:-2 * k], axis=1)
    return out


if __name__ == '__main__':
    if sha256(MODEL) != MODEL_SHA256:
        sys.exit("ball model missing or not the pinned file")
    from ultralytics import YOLO
    model = YOLO(MODEL)
    t = load_tracking()
    ball = t["ball"] * np.array(PITCH)
    v4 = METHODS["v4"](t)
    graded = np.zeros(len(v4), dtype=bool)
    for _, a, b in half_video_blocks(GAME):
        graded[a:b + 1] = True
    live = graded & np.isin(v4, ["H", "A"])
    seen = ~np.isnan(ball[:, 0])
    H = pd.read_csv(asset_paths()["homography"]).set_index("frame")[
        ["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]].to_numpy()
    video = asset_paths()["video"]
    rng = np.random.default_rng(SEED)
    started = time.time()

    # A: accuracy where the provided track has a ball
    a_frames = rng.choice(np.flatnonzero(live & seen), GROUP, replace=False)
    found, best_is_it, nearest = 0, 0, []
    for f in a_frames:
        dets = detect(model, frames_bgr(video, int(f), 1)[0], H[f].reshape(3, 3))
        if dets:
            d = [np.hypot(x - ball[f, 0], y - ball[f, 1]) for _, x, y in dets]
            nearest.append(min(d))
            found += min(d) < MATCH
            best_is_it += d[int(np.argmax([c for c, _, _ in dets]))] < MATCH
    seconds_per_frame = (time.time() - started) / GROUP
    print("speed: {:.1f} s per frame on the CPU\n".format(seconds_per_frame))
    print("A. {} live frames WITH a provided ball".format(GROUP))
    print("  a detection within {} m of the provided ball: {:.0%}".format(MATCH, found / GROUP))
    print("  the most confident detection is that ball:    {:.0%}".format(best_is_it / GROUP))
    if nearest:
        print("  nearest detection to the provided ball: median {:.1f} m, p90 {:.1f} m".format(
            np.median(nearest), np.percentile(nearest, 90)))

    # B: gaps
    last = np.maximum.accumulate(np.where(seen, np.arange(len(seen)), 0))
    b_frames = rng.choice(np.flatnonzero(live & ~seen), GROUP, replace=False)
    with_ball, confident, far = 0, 0, []
    for f in b_frames:
        dets = detect(model, frames_bgr(video, int(f), 1)[0], H[f].reshape(3, 3))
        on = [(c, x, y) for c, x, y in dets if -1 <= x <= PITCH[0] + 1 and -1 <= y <= PITCH[1] + 1]
        if on:
            with_ball += 1
            c, x, y = max(on)
            confident += c >= 0.5
            far.append(np.hypot(x - ball[last[f], 0], y - ball[last[f], 1]))
    print("\nB. {} live frames WITHOUT a provided ball".format(GROUP))
    print("  a ball detected on the pitch: {:.0%} (confidence >= 0.5: {:.0%})".format(
        with_ball / GROUP, confident / GROUP))
    if far:
        print("  distance from where the provided ball was last seen: median {:.1f} m, p90 {:.1f} m"
              .format(np.median(far), np.percentile(far, 90)))

    # C: smoothing, on consecutive frames around v4's control events
    dist = control.team_distances(t["players"], t["ball"], t["team"], PITCH)
    events = np.flatnonzero(control.control_events_touch(dist, ball) != -1)
    half = RUN_LENGTH // 2
    ok = [e for e in events if live[e - half:e + half].all() and seen[e - half:e + half].all()]
    starts = rng.choice(ok, RUNS, replace=False) - half
    det_changes, prov_changes, coverage = [], [], []
    for s in starts:
        images = frames_bgr(video, int(s), RUN_LENGTH)
        path = np.full((RUN_LENGTH, 2), np.nan)
        for k, image in enumerate(images):
            f = int(s) + k
            dets = detect(model, image, H[f].reshape(3, 3))
            if dets:
                d = [np.hypot(x - ball[f, 0], y - ball[f, 1]) for _, x, y in dets]
                j = int(np.argmin(d))
                if d[j] < 5.0:  # the detection that is our ball, not another ball-like object
                    path[k] = dets[j][1:]
        coverage.append(np.mean(~np.isnan(path[:, 0])))
        det_changes.append(velocity_changes(path))
        prov_changes.append(velocity_changes(ball[int(s):int(s) + RUN_LENGTH]))
    dc = np.concatenate(det_changes)
    pc = np.concatenate(prov_changes)
    both = ~np.isnan(dc) & ~np.isnan(pc)
    print("\nC. {} runs of {} consecutive frames around control moments".format(RUNS, RUN_LENGTH))
    print("  ball detected on {:.0%} of these frames".format(np.mean(coverage)))
    print("  velocity change >= 7 m/s within 0.24 s: detected ball {:.0%}, provided ball {:.0%}"
          .format(np.mean(dc[both] >= 7), np.mean(pc[both] >= 7)))
    print("  velocity change, 90th percentile:       detected {:.1f} m/s, provided {:.1f} m/s".format(
        np.percentile(dc[both], 90), np.percentile(pc[both], 90)))
    print("  (a much sharper detected ball confirms the provided track is smoothed; detector")
    print("   jitter also adds sharpness, so compare with care)")
    np.savez(OUT, a_frames=a_frames, b_frames=b_frames, run_starts=starts)
