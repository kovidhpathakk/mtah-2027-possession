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

    .venv-video/bin/python scripts/video_audit.py --per-group 3     # pilot: timing
    .venv-video/bin/python scripts/video_audit.py                   # 60 frames per question

The detector needs ~20 s per frame on the M1's CPU (its GPU path hangs inside PyTorch's Metal
backend on this model), so frames are not sampled evenly but per question, PER_GROUP each: ball
gaps of 5-20 s and of 20 s or more, the box ghost, frames with 12+ or fewer than 18 objects,
frames where the two trackers' balls are > 5 m apart, and ordinary frames as the yardstick.

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
PER_GROUP = 60
SEED = 0
HOME, AWAY = 0, 1


def question_groups(players, ball, team, t_to_b, ball_b, home_goal):
    """Boolean mask over frames for each question, inside the graded halves."""
    n = len(ball)
    graded = np.zeros(n, dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        graded[first:last + 1] = True
    missing = np.isnan(ball[:, 0])
    gap_len = np.zeros(n, dtype=np.int64)
    edges = np.diff(np.concatenate(([0], missing.astype(np.int8), [0])))
    for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        gap_len[a:b] = b - a
    present = ~np.isnan(players[:, :, 0])
    home_n, away_n = present[:, team == HOME].sum(1), present[:, team == AWAY].sum(1)
    ghost = np.zeros(n, dtype=bool)
    for half, first, last in half_video_blocks(GAME):
        rows = np.arange(first, last + 1)
        depth = np.abs(players[rows, :, 0] - home_goal[half])
        in_box = present[rows] & (depth <= BOX_DEPTH) \
            & (np.abs(players[rows, :, 1] - PITCH[1] / 2) <= BOX_HALF_WIDTH)
        deepest = np.argmin(np.where(in_box, depth, np.inf), axis=1)
        far = np.abs(ball[rows, 0] - home_goal[half]) > 40
        ghost[rows] = in_box.any(axis=1) & far & (team[deepest] != HOME)
    disagree = np.zeros(n, dtype=bool)
    if ball_b is not None:
        mapped = np.flatnonzero(t_to_b >= 0)
        d = np.linalg.norm(ball[mapped] - ball_b[t_to_b[mapped]], axis=1)
        disagree[mapped[d > 5]] = True
    groups = {
        "ball gap 5-20 s": missing & (gap_len >= 5 * FPS) & (gap_len < 20 * FPS),
        "ball gap 20 s+": missing & (gap_len >= 20 * FPS),
        "box ghost": ghost,
        "12+ in a team": (home_n > 11) | (away_n > 11),
        "fewer than 18": (home_n + away_n) < 18,
        "balls > 5 m apart": disagree,
    }
    special = np.any(np.stack(list(groups.values())), axis=0)
    groups["ordinary"] = ~missing & ~special
    return {name: mask & graded for name, mask in groups.items()}


def read_frames(path, frames):
    """Yield (frame, RGB array) for each requested frame, jumping straight to it (~0.1 s each).

    One ffmpeg call per frame. Seeking with -ss before -i is frame-accurate in current ffmpeg,
    and the video's clock starts at 0 (ffprobe start_time), so frame f sits at f / FPS seconds.
    """
    size = WIDTH_PX * HEIGHT_PX * 3
    for f in frames:
        raw = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "error", "-ss", "{:.3f}".format(f / FPS), "-i", path,
             "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, stdin=subprocess.DEVNULL, check=True).stdout
        if len(raw) != size:
            continue
        yield f, np.frombuffer(raw, dtype=np.uint8).reshape(HEIGHT_PX, WIDTH_PX, 3)


def detector(device="auto"):
    """The detector, and the device it runs on. One tile at a time, with the GPU's memory released
    after each frame: the M1's GPU shares the 8 GB with everything else, and a batch of four tiles
    pushed the machine into swap until the run stalled."""
    import torch
    import torchvision
    weights = torchvision.models.detection.FasterRCNN_ResNet50_FPN_V2_Weights.DEFAULT
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn_v2(weights=weights).eval()
    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    model.to(device)

    def detect(image):
        """[(class, score, x0, y0, x1, y1)] in full-frame pixels, over all tiles."""
        cols, rows = TILES
        tw, th = WIDTH_PX // cols, HEIGHT_PX // rows
        found = []
        for r in range(rows):
            for c in range(cols):
                x0, y0 = max(0, c * tw - OVERLAP), max(0, r * th - OVERLAP)
                x1, y1 = min(WIDTH_PX, (c + 1) * tw + OVERLAP), min(HEIGHT_PX, (r + 1) * th + OVERLAP)
                tile = torch.from_numpy(image[y0:y1, x0:x1].copy()).permute(2, 0, 1).float() / 255
                with torch.no_grad():
                    out = model([tile.to(device)])[0]
                labels = out["labels"].cpu().numpy()
                scores = out["scores"].cpu().numpy()
                boxes = out["boxes"].cpu().numpy()
                del out
                for label, score, box in zip(labels, scores, boxes):
                    keep = (label == PERSON and score >= PERSON_SCORE) or \
                           (label == BALL and score >= BALL_SCORE)
                    if keep:
                        found.append((int(label), float(score), box[0] + x0, box[1] + y0,
                                      box[2] + x0, box[3] + y0))
        if device == "mps":
            torch.mps.empty_cache()
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
    parser.add_argument("--per-group", type=int, default=PER_GROUP, help="frames per question")
    parser.add_argument("--device", default="cpu", choices=("cpu", "mps"),
                        help="mps hangs on this model with torch 2.5.1; cpu is the safe default")
    args = parser.parse_args()

    scale = np.array(PITCH)
    t = load_tracking()
    players, ball, team = t["players"] * scale, t["ball"] * scale, t["team"]
    homography = pd.read_csv(asset_paths()["homography"]).set_index("frame")
    matrix = homography[["h00", "h01", "h02", "h10", "h11", "h12", "h20", "h21", "h22"]].to_numpy()
    ball_b, t_to_b = None, np.full(len(ball), -1, dtype=np.int64)
    if os.path.isfile(OFFSETS):
        broadcast = load_tracking("broadcast")
        offset = np.load(OFFSETS)["offset"]
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

    groups = question_groups(players, ball, team, t_to_b, ball_b, home_goal)
    rng = np.random.default_rng(SEED)
    group_of = {}
    for name, mask in groups.items():
        candidates = np.flatnonzero(mask)
        chosen = rng.choice(candidates, size=min(args.per_group, len(candidates)), replace=False) \
            if len(candidates) else []
        for f in chosen:
            group_of.setdefault(int(f), []).append(name)
    frames = np.array(sorted(group_of))
    detect, device = detector(args.device)
    print("{} frames ({} per question), detector on {}".format(len(frames), args.per_group, device))
    for name, mask in groups.items():
        print("  {:<18} {:>7,} frames in the match".format(name, int(mask.sum())))

    confirmed = {k: [0, 0] for k in ("ordinary", "ghost", "extra", "touchline")}
    per_group = {name: {"frames": 0, "ball_seen": 0, "tracker_ball": 0, "tracker_ball_hit": 0,
                        "people": 0, "missed": 0, "objects": 0, "objects_confirmed": 0}
                 for name in groups}
    disagree = {"tactical": 0, "broadcast": 0, "neither": 0}
    records = []
    started = time.time()
    for done, (f, image) in enumerate(read_frames(asset_paths()["video"], frames), 1):
        H = matrix[f].reshape(3, 3)
        found = detect(image)
        people = np.array([to_pitch(H, (d[2] + d[4]) / 2, d[5]) for d in found if d[0] == PERSON])
        balls = np.array([to_pitch(H, (d[2] + d[4]) / 2, (d[3] + d[5]) / 2)
                          for d in found if d[0] == BALL])
        inside = lambda xy, m: xy[(xy[:, 0] > -m) & (xy[:, 0] < PITCH[0] + m)  # noqa: E731
                                  & (xy[:, 1] > -m) & (xy[:, 1] < PITCH[1] + m)] \
            if len(xy) else np.zeros((0, 2))
        on_pitch, ball_on_pitch = inside(people, 1.0), inside(balls, 0.0)
        present = ~np.isnan(players[f, :, 0])
        half = 1 if f <= half_video_blocks(GAME)[0][2] else 2
        kinds = object_kinds(players[f], team, ball[f], f, home_goal[half])
        n_confirmed = 0
        for slot in np.flatnonzero(present):
            near = np.min(np.linalg.norm(people - players[f, slot], axis=1)) if len(people) \
                else np.inf
            confirmed[kinds[slot]][0] += near < MATCH
            confirmed[kinds[slot]][1] += 1
            n_confirmed += near < MATCH
        tracked = players[f, present]
        n_missed = sum(not (len(tracked) and np.min(np.linalg.norm(tracked - p, axis=1)) < MATCH)
                       for p in on_pitch)
        has_ball = not np.isnan(ball[f, 0])
        hit = has_ball and bool(len(balls)) and \
            np.min(np.linalg.norm(balls - ball[f], axis=1)) < BALL_MATCH
        for name in group_of[f]:
            g = per_group[name]
            g["frames"] += 1
            g["ball_seen"] += bool(len(ball_on_pitch))
            g["tracker_ball"] += has_ball
            g["tracker_ball_hit"] += hit
            g["people"] += len(on_pitch)
            g["missed"] += n_missed
            g["objects"] += int(present.sum())
            g["objects_confirmed"] += n_confirmed
        if ball_b is not None and t_to_b[f] >= 0 and has_ball and len(balls):
            bb = ball_b[t_to_b[f]]
            if not np.isnan(bb[0]) and np.linalg.norm(bb - ball[f]) > 5:
                d_t = np.min(np.linalg.norm(balls - ball[f], axis=1))
                d_b = np.min(np.linalg.norm(balls - bb, axis=1))
                disagree["tactical" if d_t < min(d_b, BALL_MATCH) else
                         "broadcast" if d_b < min(d_t, BALL_MATCH) else "neither"] += 1
        records.append((f, len(people), len(on_pitch), len(balls), int(present.sum())))
        if done in (1, 5) or done % 25 == 0:
            rate = (time.time() - started) / done
            print("  {} frames, {:.1f} s per frame, ~{:.0f} min left".format(
                done, rate, rate * (len(frames) - done) / 60))

    if not records:
        sys.exit("no frames decoded: check the ffmpeg command above")
    np.savez(OUT, frame_stats=np.array(records))

    def share(a, b):
        return "{:.0%}".format(a / b) if b else "n/a"

    print("\nTRACKED OBJECTS WITH A DETECTED PERSON WITHIN {} m".format(MATCH))
    print("  ordinary objects confirmed: {} of {:,}   <- the detector's own hit rate".format(
        share(*confirmed["ordinary"]), confirmed["ordinary"][1]))
    for kind in ("ghost", "extra", "touchline"):
        print("  {:<9} objects confirmed: {} of {:,}".format(kind, share(*confirmed[kind]),
                                                             confirmed[kind][1]))
    print("\nPER QUESTION")
    print("  {:<18} {:>6} {:>12} {:>15} {:>14} {:>16}".format(
        "group", "frames", "ball seen", "tracker ball", "objects", "missed people"))
    print("  {:<18} {:>6} {:>12} {:>15} {:>14} {:>16}".format(
        "", "", "on pitch", "confirmed", "confirmed", "per frame"))
    for name, g in per_group.items():
        print("  {:<18} {:>6} {:>12} {:>15} {:>14} {:>16}".format(
            name, g["frames"], share(g["ball_seen"], g["frames"]),
            share(g["tracker_ball_hit"], g["tracker_ball"]),
            share(g["objects_confirmed"], g["objects"]),
            "{:.1f}".format(g["missed"] / g["frames"]) if g["frames"] else "n/a"))
    print("\n  trackers > 5 m apart and the detector sees a ball: closer to tactical {}, to"
          " broadcast {}, to neither {}".format(disagree["tactical"], disagree["broadcast"],
                                                disagree["neither"]))
