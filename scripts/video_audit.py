"""Check the tracking against the video itself, with a pre-trained detector run on this machine.

The audits so far compared the tracking with itself, with the broadcast tracker and with clean
matches. Some questions only the picture can answer: is the motionless "ghost" in front of
Barca's goal a person at all? Are the extra objects people? Is the ball visible while the tracker
has lost it? When the two trackers' balls disagree, which one is right?

A COCO-trained Faster R-CNN (torchvision; trained on everyday photos, never on this match, which
issue #2 allows) finds people and balls in sampled frames of the tactical video. The homography
maps each person's feet and each ball to the pitch, where they are compared with the tracking:

  people   share of tracked objects with a detected person within MATCH m, by kind of object
           (ordinary, the box ghost, extra objects on 12+ frames, touchline tracks); and detected
           people on the pitch with no tracked object near them (missed players)
  ball     how often the detector finds the ball where the tracker has one (its own hit rate),
           how often it finds a ball while the tracker has none, and, where the two trackers
           disagree by > 5 m, which one it agrees with

Everything runs locally and prints counts only; per-frame results go to data/derived/ (gitignored).
Needs the separate video environment (requirements-video.txt):

    .venv-video/bin/python scripts/video_audit.py --limit 40        # pilot: timing and hit rates
    .venv-video/bin/python scripts/video_audit.py --every 2          # one frame every 2 s

Read the "ordinary objects confirmed" line first: it is the detector's own hit rate, and every
other share means something only relative to it.
"""

import argparse
import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES, asset_paths, half_video_blocks  # noqa: E402

from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
WIDTH_PX, HEIGHT_PX = 1920, 1080
TILES = (2, 2)               # the frame is cut into tiles so small, distant players are found
OVERLAP = 64                 # px of overlap between tiles
PERSON, BALL = 1, 37         # COCO classes
PERSON_SCORE, BALL_SCORE = 0.5, 0.3
MATCH = 2.0                  # m: a tracked object and a detection this close are the same thing
BALL_MATCH = 3.0             # m
BOX_DEPTH, BOX_HALF_WIDTH = 16.5, 20.16
TOUCHLINE_BAND = 3.0
OFFSETS = os.path.join(ROOT, "data", "derived", "broadcast_offsets.npz")
OUT = os.path.join(ROOT, "data", "derived", "video_audit.npz")
HOME, AWAY = 0, 1


def sampled_frames(every_s):
    frames = []
    for _, first, last in half_video_blocks(GAME):
        frames.extend(range(first, last + 1, int(every_s * FPS)))
    return np.array(frames)


def read_frames(path, frames):
    """Yield (frame, RGB array) for the requested frames, decoding the video once, in order."""
    wanted = "+".join("eq(n,{})".format(f) for f in frames) if len(frames) < 200 else \
        "+".join("between(n,{},{})*not(mod(n-{},{}))".format(a, b, a, frames[1] - frames[0])
                 for a, b in _blocks(frames))
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-hwaccel", "videotoolbox", "-i", path,
           "-vf", "select='{}'".format(wanted), "-fps_mode", "passthrough",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    size = WIDTH_PX * HEIGHT_PX * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    try:
        for f in frames:
            raw = proc.stdout.read(size)
            if len(raw) < size:
                break
            yield f, np.frombuffer(raw, dtype=np.uint8).reshape(HEIGHT_PX, WIDTH_PX, 3)
    finally:
        proc.kill()


def _blocks(frames):
    """Contiguous evenly spaced stretches of the sample, one per half."""
    step = frames[1] - frames[0]
    breaks = np.flatnonzero(np.diff(frames) != step)
    starts = np.concatenate(([0], breaks + 1))
    stops = np.concatenate((breaks, [len(frames) - 1]))
    return [(frames[a], frames[b]) for a, b in zip(starts, stops)]


def detector():
    import torch
    import torchvision
    weights = torchvision.models.detection.FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn_v2(weights=weights).eval()
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)

    def detect(image):
        """[(class, score, x0, y0, x1, y1)] in full-frame pixels, over all tiles."""
        cols, rows = TILES
        tw, th = WIDTH_PX // cols, HEIGHT_PX // rows
        tiles, origins = [], []
        for r in range(rows):
            for c in range(cols):
                x0, y0 = max(0, c * tw - OVERLAP), max(0, r * th - OVERLAP)
                x1, y1 = min(WIDTH_PX, (c + 1) * tw + OVERLAP), min(HEIGHT_PX, (r + 1) * th + OVERLAP)
                tile = torch.from_numpy(image[y0:y1, x0:x1].copy()).permute(2, 0, 1).float() / 255
                tiles.append(tile.to(device))
                origins.append((x0, y0))
        with torch.no_grad():
            outputs = model(tiles)
        found = []
        for (ox, oy), out in zip(origins, outputs):
            for label, score, box in zip(out["labels"].cpu().numpy(), out["scores"].cpu().numpy(),
                                         out["boxes"].cpu().numpy()):
                keep = (label == PERSON and score >= PERSON_SCORE) or \
                       (label == BALL and score >= BALL_SCORE)
                if keep:
                    found.append((int(label), float(score), box[0] + ox, box[1] + oy,
                                  box[2] + ox, box[3] + oy))
        return dedupe(found)

    return detect, device


def dedupe(found):
    """Drop a detection that mostly overlaps a higher-scoring one of the same class (tile seams)."""
    found = sorted(found, key=lambda d: -d[1])
    kept = []
    for d in found:
        if all(d[0] != k[0] or iou(d[2:], k[2:]) < 0.5 for k in kept):
            kept.append(d)
    return kept


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def to_pitch(H, u, v):
    """Pixel -> metres on the pitch, through the inverse of the frame's homography."""
    p = np.linalg.inv(H) @ np.array([u, v, 1.0])
    return np.array([p[0] / p[2], p[1] / p[2]]) * np.array(PITCH)


def object_kinds(players, team, ball, frame, home_goal):
    """Per tracked slot at one frame: 'ghost', 'extra', 'touchline' or 'ordinary' (NaN slots
    excluded by the caller). Same rules as the audits."""
    kinds = np.array(["ordinary"] * len(team), dtype=object)
    y = players[:, 1]
    kinds[np.fmin(np.abs(y), np.abs(y - PITCH[1])) <= TOUCHLINE_BAND] = "touchline"
    present = ~np.isnan(players[:, 0])
    for code in (HOME, AWAY):
        if (present & (team == code)).sum() > 11:
            kinds[(team == code) & (kinds == "ordinary")] = "extra"
    depth = np.abs(players[:, 0] - home_goal)
    in_box = present & (depth <= BOX_DEPTH) & (np.abs(y - PITCH[1] / 2) <= BOX_HALF_WIDTH)
    if in_box.any() and not np.isnan(ball[0]) and abs(ball[0] - home_goal) > 40:
        deepest = np.flatnonzero(in_box)[np.argmin(depth[in_box])]
        if team[deepest] != HOME:
            kinds[deepest] = "ghost"
    return kinds


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--every", type=float, default=2.0, help="seconds between sampled frames")
    parser.add_argument("--limit", type=int, default=0, help="stop after this many frames (pilot)")
    args = parser.parse_args()

    scale = np.array(PITCH)
    t = load_tracking()
    players, ball, team = t["players"] * scale, t["ball"] * scale, t["team"]
    homography = pd.read_csv(asset_paths()["homography"]).set_index("frame")
    matrix = homography[["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]].to_numpy()
    ball_b = None
    if os.path.isfile(OFFSETS):
        broadcast = load_tracking("broadcast")
        offset = np.load(OFFSETS)["offset"]
        t_to_b = np.full(len(ball), -1, dtype=np.int64)
        live = np.flatnonzero(offset >= 0)
        target = live + offset[live]
        ok = target < len(ball)
        t_to_b[target[ok]] = live[ok]
        ball_b = broadcast["ball"] * scale
    home_goal = {}
    for half, first, last in half_video_blocks(GAME):
        rows = slice(first, last + 1)
        home_goal[half] = 0.0 if np.nanmean(players[rows][:, team == HOME, 0]) \
            < np.nanmean(players[rows][:, team == AWAY, 0]) else PITCH[0]

    frames = sampled_frames(args.every)
    if args.limit:
        frames = frames[np.linspace(0, len(frames) - 1, args.limit).astype(int)]
    detect, device = detector()
    print("{} frames sampled, detector on {}".format(len(frames), device))

    confirmed = {k: [0, 0] for k in ("ordinary", "ghost", "extra", "touchline")}
    missed, people_on_pitch, few_frames, few_missed = 0, 0, 0, 0
    ball_hit = [0, 0]          # tracker has a ball: detector finds one within BALL_MATCH
    ball_in_gap = [0, 0]       # tracker has no ball: detector finds one on the pitch
    disagree = {"tactical": 0, "broadcast": 0, "neither": 0}
    records = []
    started = time.time()
    for done, (f, image) in enumerate(read_frames(asset_paths()["video"], frames), 1):
        H = matrix[f].reshape(3, 3)
        found = detect(image)
        people = np.array([to_pitch(H, (d[2] + d[4]) / 2, d[5]) for d in found if d[0] == PERSON])
        balls = np.array([to_pitch(H, (d[2] + d[4]) / 2, (d[3] + d[5]) / 2)
                          for d in found if d[0] == BALL])
        on_pitch = people[(people[:, 0] > -1) & (people[:, 0] < PITCH[0] + 1)
                          & (people[:, 1] > -1) & (people[:, 1] < PITCH[1] + 1)] \
            if len(people) else np.zeros((0, 2))
        present = ~np.isnan(players[f, :, 0])
        half = 1 if f <= half_video_blocks(GAME)[0][2] else 2
        kinds = object_kinds(players[f], team, ball[f], f, home_goal[half])
        for slot in np.flatnonzero(present):
            near = np.min(np.linalg.norm(people - players[f, slot], axis=1)) if len(people) \
                else np.inf
            confirmed[kinds[slot]][0] += near < MATCH
            confirmed[kinds[slot]][1] += 1
        tracked = players[f, present]
        for p in on_pitch:
            covered = np.min(np.linalg.norm(tracked - p, axis=1)) < MATCH if len(tracked) else False
            people_on_pitch += 1
            missed += not covered
            if present.sum() < 18:
                few_missed += not covered
        few_frames += present.sum() < 18
        has_ball = not np.isnan(ball[f, 0])
        ball_on_pitch = balls[(balls[:, 0] > 0) & (balls[:, 0] < PITCH[0])
                              & (balls[:, 1] > 0) & (balls[:, 1] < PITCH[1])] \
            if len(balls) else np.zeros((0, 2))
        if has_ball:
            ball_hit[1] += 1
            ball_hit[0] += bool(len(balls)) and \
                np.min(np.linalg.norm(balls - ball[f], axis=1)) < BALL_MATCH
        else:
            ball_in_gap[1] += 1
            ball_in_gap[0] += bool(len(ball_on_pitch))
        if ball_b is not None and t_to_b[f] >= 0 and has_ball and len(balls):
            bb = ball_b[t_to_b[f]]
            if not np.isnan(bb[0]) and np.linalg.norm(bb - ball[f]) > 5:
                d_t = np.min(np.linalg.norm(balls - ball[f], axis=1))
                d_b = np.min(np.linalg.norm(balls - bb, axis=1))
                disagree["tactical" if d_t < min(d_b, BALL_MATCH) else
                         "broadcast" if d_b < min(d_t, BALL_MATCH) else "neither"] += 1
        records.append((f, len(people), len(on_pitch), len(balls), int(present.sum())))
        if done in (1, 10) or done % 200 == 0:
            rate = (time.time() - started) / done
            print("  {} frames, {:.1f} s per frame, ~{:.0f} min left".format(
                done, rate, rate * (len(frames) - done) / 60))

    if not records:
        sys.exit("no frames decoded: check the ffmpeg command above")
    np.savez(OUT, frame_stats=np.array(records))

    def share(pair):
        return "{:.0%} of {:,}".format(pair[0] / pair[1], pair[1]) if pair[1] else "n/a"

    print("\nTRACKED OBJECTS WITH A DETECTED PERSON WITHIN {} m".format(MATCH))
    print("  ordinary objects confirmed: {}   <- the detector's own hit rate".format(
        share(confirmed["ordinary"])))
    for kind in ("ghost", "extra", "touchline"):
        print("  {:<9} objects confirmed: {}".format(kind, share(confirmed[kind])))
    print("\nDETECTED PEOPLE ON THE PITCH WITH NO TRACKED OBJECT WITHIN {} m: {}".format(
        MATCH, share([missed, people_on_pitch])))
    print("  on frames with fewer than 18 tracked objects ({} frames): {} missed people".format(
        few_frames, few_missed))
    print("\nBALL")
    print("  tracker has a ball; detector finds one within {} m: {}   <- its own hit rate".format(
        BALL_MATCH, share(ball_hit)))
    print("  tracker has no ball; detector finds one on the pitch: {}".format(share(ball_in_gap)))
    print("  trackers > 5 m apart and the detector sees a ball: closer to tactical {}, to"
          " broadcast {}, to neither {}".format(disagree["tactical"], disagree["broadcast"],
                                                disagree["neither"]))
