"""Track T pilot 2: the ball detector on the BROADCAST video, where the ball is several times larger.

On the wide tactical view the Roboflow ball detector found the ball within 2 m only half the time
(scripts/ball_pilot.py): the ball is a few pixels across, and the model was trained on broadcast-
style footage. The broadcast camera is zoomed in, so the same model may do far better there. The
broadcast frames map to tactical frames through data/derived/broadcast_offsets.npz (live pictures
only) and to the pitch through the broadcast homography. Same three tests as pilot 1:

  A accuracy  live broadcast frames whose tactical frame has a provided ball: a detection within
              MATCH m of it? the most confident detection that ball?
  B gaps      live broadcast frames whose tactical frame is live play with no provided ball: a ball
              found? how far from where it was last seen?
  C smoothing runs of consecutive broadcast frames around v4's control moments: sharp velocity
              changes of the detected ball vs the provided one

    .venv-video/bin/python scripts/ball_pilot_broadcast.py

Local only; prints counts.
"""

import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from ball_pilot import (CONF, GROUP, IMGSZ, MATCH, MODEL, MODEL_SHA256, RUN_LENGTH, RUNS,  # noqa
                        SEED, frames_bgr, sha256, velocity_changes)
from games import GAME, asset_paths, half_video_blocks  # noqa: E402

from possession import control  # noqa: E402
from possession.methods import METHODS  # noqa: E402
from possession.tracking import PITCH, load_tracking  # noqa: E402

OFFSETS = os.path.join(ROOT, "data", "derived", "broadcast_offsets.npz")


def detect_broadcast(model, image, H):
    result = model.predict(image, imgsz=IMGSZ, conf=CONF, device="cpu", verbose=False)[0]
    inverse = np.linalg.inv(H)
    out = []
    for conf, box in zip(result.boxes.conf.numpy(), result.boxes.xyxy.numpy()):
        p = inverse @ np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2, 1.0])
        out.append((float(conf), p[0] / p[2] * PITCH[0], p[1] / p[2] * PITCH[1]))
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
    offset = np.load(OFFSETS)["offset"]
    hb = pd.read_csv(asset_paths(source="broadcast")["homography"]).set_index("frame")
    Hb = hb[["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]].to_numpy()
    valid = hb["valid"].to_numpy() == 1
    b_frames = np.flatnonzero((offset >= 0) & valid[:len(offset)])
    t_frames = b_frames + offset[b_frames]
    keep = t_frames < len(v4)
    b_frames, t_frames = b_frames[keep], t_frames[keep]
    video = asset_paths(source="broadcast")["video"]
    rng = np.random.default_rng(SEED)
    started = time.time()

    pick = np.flatnonzero(live[t_frames] & seen[t_frames])
    sel = rng.choice(pick, GROUP, replace=False)
    found, best, nearest = 0, 0, []
    for k in sel:
        bf, tf = int(b_frames[k]), int(t_frames[k])
        dets = detect_broadcast(model, frames_bgr(video, bf, 1)[0], Hb[bf].reshape(3, 3))
        if dets:
            d = [np.hypot(x - ball[tf, 0], y - ball[tf, 1]) for _, x, y in dets]
            nearest.append(min(d))
            found += min(d) < MATCH
            best += d[int(np.argmax([c for c, _, _ in dets]))] < MATCH
    print("speed: {:.1f} s per frame\n".format((time.time() - started) / GROUP))
    print("A. {} live broadcast frames whose tactical frame has a provided ball".format(GROUP))
    print("  a detection within {} m of the provided ball: {:.0%}   (tactical view: 50%)".format(
        MATCH, found / GROUP))
    print("  the most confident detection is that ball:    {:.0%}   (tactical view: 32%)".format(
        best / GROUP))
    if nearest:
        print("  nearest detection: median {:.1f} m, p90 {:.1f} m".format(
            np.median(nearest), np.percentile(nearest, 90)))

    last = np.maximum.accumulate(np.where(seen, np.arange(len(seen)), 0))
    pick = np.flatnonzero(live[t_frames] & ~seen[t_frames])
    print("\nB. live tactical frames with no provided ball that the broadcast shows live: {:,}".format(
        len(pick)))
    sel = rng.choice(pick, min(GROUP, len(pick)), replace=False)
    with_ball, confident, far = 0, 0, []
    for k in sel:
        bf, tf = int(b_frames[k]), int(t_frames[k])
        dets = detect_broadcast(model, frames_bgr(video, bf, 1)[0], Hb[bf].reshape(3, 3))
        on = [(c, x, y) for c, x, y in dets if -1 <= x <= PITCH[0] + 1 and -1 <= y <= PITCH[1] + 1]
        if on:
            with_ball += 1
            c, x, y = max(on)
            confident += c >= 0.5
            far.append(np.hypot(x - ball[last[tf], 0], y - ball[last[tf], 1]))
    print("  a ball detected on the pitch: {:.0%} (confidence >= 0.5: {:.0%})".format(
        with_ball / len(sel), confident / len(sel)))
    if far:
        print("  distance from where the provided ball was last seen: median {:.1f} m, p90 {:.1f} m"
              .format(np.median(far), np.percentile(far, 90)))

    dist = control.team_distances(t["players"], t["ball"], t["team"], PITCH)
    events = np.flatnonzero(control.control_events_touch(dist, ball) != -1)
    t_to_b = np.full(len(v4), -1, dtype=np.int64)
    t_to_b[t_frames] = b_frames
    half = RUN_LENGTH // 2
    ok = [e for e in events if e - half >= 0 and e + half < len(v4) and live[e - half:e + half].all()
          and seen[e - half:e + half].all() and (t_to_b[e - half:e + half] >= 0).all()
          and np.all(np.diff(t_to_b[e - half:e + half]) == 1)]
    print("\nC. control moments with {} consecutive live broadcast frames: {}".format(
        RUN_LENGTH, len(ok)))
    if len(ok) >= RUNS:
        starts = rng.choice(ok, RUNS, replace=False) - half
        det_changes, prov_changes, coverage = [], [], []
        for s in starts:
            bs = int(t_to_b[s])
            images = frames_bgr(video, bs, RUN_LENGTH)
            path = np.full((RUN_LENGTH, 2), np.nan)
            for k, image in enumerate(images):
                dets = detect_broadcast(model, image, Hb[bs + k].reshape(3, 3))
                if dets:
                    d = [np.hypot(x - ball[s + k, 0], y - ball[s + k, 1]) for _, x, y in dets]
                    j = int(np.argmin(d))
                    if d[j] < 5.0:
                        path[k] = dets[j][1:]
            coverage.append(np.mean(~np.isnan(path[:, 0])))
            det_changes.append(velocity_changes(path))
            prov_changes.append(velocity_changes(ball[int(s):int(s) + RUN_LENGTH]))
        dc, pc = np.concatenate(det_changes), np.concatenate(prov_changes)
        both = ~np.isnan(dc) & ~np.isnan(pc)
        print("  ball detected on {:.0%} of these frames".format(np.mean(coverage)))
        if both.any():
            print("  velocity change >= 7 m/s in 0.24 s: detected {:.0%}, provided {:.0%}".format(
                np.mean(dc[both] >= 7), np.mean(pc[both] >= 7)))
            print("  90th percentile of change: detected {:.1f} m/s, provided {:.1f} m/s".format(
                np.percentile(dc[both], 90), np.percentile(pc[both], 90)))
