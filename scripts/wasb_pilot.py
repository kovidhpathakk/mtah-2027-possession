"""Track T pilot 3: WASB, a ball tracker built for small fast balls, on the tactical video.

WASB (Tarashima et al., BMVC 2023, arXiv 2311.05237; code MIT, github.com/nttcom/WASB-SBDT) reads
three consecutive frames at once, so a blurred kick does not lose the ball, and outputs one heatmap
per frame. Its soccer weights were trained on the ISSIA-CNR soccer dataset: fixed wide cameras,
each covering half a pitch -- close to our tactical view, and not our match. The weights
(models/wasb_soccer_best.pth.tar, SHA-256 below, downloaded with Kovidh's approval) hold tensors
only and load with weights_only=True. The architecture comes from the cloned repository
(third_party/WASB-SBDT, read before use: models/hrnet.py imports only os, logging and torch).

Preprocessing as the repository's: each frame scaled to 512x288, ImageNet mean/std, three frames
stacked as 9 channels; output logits -> sigmoid -> blobs above 0.5 -> weighted centre. Two modes:
  full  the whole 1920x1080 frame (the ball shrinks to ~1-2 pixels)
  crop  a 960x540 window around where the ball is expected (the provided ball, or where it was
        last seen), about the scale of the half-pitch training cameras
Same tests as scripts/ball_pilot.py (A accuracy, B gaps, C smoothing).

    .venv-video/bin/python scripts/wasb_pilot.py
"""

import hashlib
import importlib.util
import os
import sys
import time

import cv2
import numpy as np
import pandas as pd
import torch
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from ball_pilot import GROUP, MATCH, RUN_LENGTH, RUNS, SEED, frames_bgr, velocity_changes  # noqa
from games import GAME, asset_paths, half_video_blocks  # noqa: E402

from possession import control  # noqa: E402
from possession.methods import METHODS  # noqa: E402
from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
WEIGHTS = os.path.join(ROOT, "models", "wasb_soccer_best.pth.tar")
WEIGHTS_SHA256 = "d0369572807c2baf751880d6cdf3cce9fc6283fa8d153f18af6baf4e64d2646c"
REPO = os.path.join(ROOT, "third_party", "WASB-SBDT", "src")
IN_W, IN_H = 512, 288
CROP_W, CROP_H = 960, 540
THRESHOLD = 0.5
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def load_model():
    digest = hashlib.sha256(open(WEIGHTS, "rb").read()).hexdigest()
    if digest != WEIGHTS_SHA256:
        sys.exit("WASB weights missing or not the pinned file")
    spec = importlib.util.spec_from_file_location("wasb_hrnet", os.path.join(REPO, "models", "hrnet.py"))
    hrnet = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hrnet)
    cfg = yaml.safe_load(open(os.path.join(REPO, "configs", "model", "wasb.yaml")))
    model = hrnet.HRNet(cfg)
    state = torch.load(WEIGHTS, map_location="cpu", weights_only=True)["model_state_dict"]
    state = {k.replace("module.", "", 1): v for k, v in state.items()}
    model.load_state_dict(state)
    return model.eval()


def window(H, point, mode):
    """(x0, y0, w, h) of the pixel window for a pitch point (normalised), or the whole frame."""
    if mode == "full" or np.isnan(point[0]):
        return 0, 0, 1920, 1080
    p = H @ np.array([point[0], point[1], 1.0])
    u, v = p[0] / p[2], p[1] / p[2]
    x0 = int(np.clip(u - CROP_W / 2, 0, 1920 - CROP_W))
    y0 = int(np.clip(v - CROP_H / 2, 0, 1080 - CROP_H))
    return x0, y0, CROP_W, CROP_H


def detect3(model, images_bgr, H_list, win):
    """Balls in each of three consecutive frames: [[(score, x_m, y_m), ...] x3]."""
    x0, y0, w, h = win
    stack = []
    for img in images_bgr:
        rgb = cv2.cvtColor(img[y0:y0 + h, x0:x0 + w], cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (IN_W, IN_H), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
        stack.append(((rgb - MEAN) / STD).transpose(2, 0, 1))
    with torch.no_grad():
        heat = torch.sigmoid(model(torch.from_numpy(np.concatenate(stack)[None]))[0])[0].numpy()
    out = []
    for k in range(3):
        hm = heat[k]
        found = []
        if hm.max() > THRESHOLD:
            n, labels = cv2.connectedComponents((hm > THRESHOLD).astype(np.uint8))
            inverse = np.linalg.inv(H_list[k])
            for m in range(1, n):
                ys, xs = np.where(labels == m)
                ws = hm[ys, xs]
                px = x0 + (np.sum(xs * ws) / ws.sum()) * w / IN_W
                py = y0 + (np.sum(ys * ws) / ws.sum()) * h / IN_H
                q = inverse @ np.array([px, py, 1.0])
                found.append((float(ws.sum()), q[0] / q[2] * PITCH[0], q[1] / q[2] * PITCH[1]))
        out.append(found)
    return out


if __name__ == '__main__':
    torch.set_num_threads(8)
    model = load_model()
    t = load_tracking()
    ball_n = t["ball"]
    ball = ball_n * np.array(PITCH)
    v4 = METHODS["v4"](t)
    graded = np.zeros(len(v4), dtype=bool)
    for _, a, b in half_video_blocks(GAME):
        graded[a:b + 1] = True
    live = graded & np.isin(v4, ["H", "A"])
    seen = ~np.isnan(ball[:, 0])
    last = np.maximum.accumulate(np.where(seen, np.arange(len(seen)), 0))
    H = pd.read_csv(asset_paths()["homography"]).set_index("frame")[
        ["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]].to_numpy().reshape(-1, 3, 3)
    video = asset_paths()["video"]
    rng = np.random.default_rng(SEED)
    a_frames = rng.choice(np.flatnonzero(live & seen), GROUP, replace=False)
    b_frames = rng.choice(np.flatnonzero(live & ~seen), GROUP, replace=False)

    for mode in ("full", "crop"):
        started = time.time()
        found, best, nearest = 0, 0, []
        for f in a_frames:
            dets = detect3(model, frames_bgr(video, int(f) - 1, 3), H[f - 1:f + 2],
                           window(H[f], ball_n[f], mode))[1]
            if dets:
                d = [np.hypot(x - ball[f, 0], y - ball[f, 1]) for _, x, y in dets]
                nearest.append(min(d))
                found += min(d) < MATCH
                best += d[int(np.argmax([s for s, _, _ in dets]))] < MATCH
        speed = (time.time() - started) / GROUP
        with_ball, far = 0, []
        for f in b_frames:
            dets = detect3(model, frames_bgr(video, int(f) - 1, 3), H[f - 1:f + 2],
                           window(H[f], ball_n[last[f]], mode))[1]
            on = [(s, x, y) for s, x, y in dets if -1 <= x <= PITCH[0] + 1 and -1 <= y <= PITCH[1] + 1]
            if on:
                with_ball += 1
                s, x, y = max(on)
                far.append(np.hypot(x - ball[last[f], 0], y - ball[last[f], 1]))
        print("MODE {} ({:.2f} s per 3-frame step)".format(mode, speed))
        print("  A. with a provided ball: within {} m {:.0%}; most confident is it {:.0%}; nearest "
              "median {:.1f} m".format(MATCH, found / GROUP, best / GROUP,
                                       np.median(nearest) if nearest else np.nan))
        print("  B. live gaps: ball found {:.0%}; median {:.1f} m from where last seen".format(
            with_ball / GROUP, np.median(far) if far else np.nan))

    # C: smoothing, crop mode, consecutive frames around v4's control moments
    dist = control.team_distances(t["players"], t["ball"], t["team"], PITCH)
    events = np.flatnonzero(control.control_events_touch(dist, ball) != -1)
    half = RUN_LENGTH // 2
    ok = [e for e in events if live[e - half:e + half].all() and seen[e - half:e + half].all()]
    starts = rng.choice(ok, RUNS, replace=False) - half
    det_changes, prov_changes, coverage = [], [], []
    for s in starts:
        images = frames_bgr(video, int(s), RUN_LENGTH + 2)
        path = np.full((RUN_LENGTH, 2), np.nan)
        for k in range(0, RUN_LENGTH - 2, 3):
            f = int(s) + k
            triple = detect3(model, images[k:k + 3], H[f:f + 3], window(H[f + 1], ball_n[f + 1], "crop"))
            for j in range(3):
                dets = triple[j]
                if dets:
                    d = [np.hypot(x - ball[f + j, 0], y - ball[f + j, 1]) for _, x, y in dets]
                    if min(d) < 5.0:
                        path[k + j] = dets[int(np.argmin(d))][1:]
        coverage.append(np.mean(~np.isnan(path[:, 0])))
        det_changes.append(velocity_changes(path))
        prov_changes.append(velocity_changes(ball[int(s):int(s) + RUN_LENGTH]))
    dc, pc = np.concatenate(det_changes), np.concatenate(prov_changes)
    both = ~np.isnan(dc) & ~np.isnan(pc)
    print("C. {} runs of {} frames (crop): ball detected on {:.0%}".format(RUNS, RUN_LENGTH, np.mean(coverage)))
    if both.any():
        print("  velocity change >= 7 m/s in 0.24 s: detected {:.0%}, provided {:.0%}; p90 {:.1f} vs {:.1f} m/s"
              .format(np.mean(dc[both] >= 7), np.mean(pc[both] >= 7), np.percentile(dc[both], 90),
                      np.percentile(pc[both], 90)))
    print("\n(Roboflow detector, tactical full frame: A within 2 m 50%, most confident 32%)")
