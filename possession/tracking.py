"""Load the tactical ATD into arrays indexed by video frame, once, and cache them locally.

Parsing 199319 text lines of 46 player groups takes about a minute in pure Python, and every
stage and every experiment needs the same arrays, so the first call writes them to
data/derived/ (gitignored, and blocked by the guard) and later calls load that in a second.

Positions stay NORMALISED (0-1) and float64, exactly as parsed. float64 matters more than it
looks: the reference baseline compares squared distances parsed as float64, and rounding to
float32 changes the nearest player on a handful of near-ties, which makes a byte-for-byte
reproduction of the committed baseline files impossible. Multiply by PITCH for metres.

    from possession.tracking import load_tracking
    t = load_tracking()
    t["ball"]      (n_frames, 2)      ball x, y; NaN where the tracker has no ball
    t["players"]   (n_frames, S, 2)   per track slot x, y; NaN where the slot is empty
    t["speed"]     (n_frames, S)      per slot speed in m/s, float32
    t["ball_speed"](n_frames,)        float32
    t["team"]      (S,)               0 home (Barcelona), 1 away, per slot
"""

import os
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES, require, source_frames  # noqa: E402

# Params
DERIVED_DIR = os.path.join(ROOT, "data", "derived")
CACHE_VERSION = 1  # bump when the cached layout changes, so stale caches are rebuilt
PITCH = GAMES[GAME]["pitch"]  # (length, width) in metres
HOME, AWAY = 0, 1


def team_of_each_slot(meta_path):
    """0 for home slots, 1 for away. The first team in the metadata is home, as in baseline.py."""
    root = ET.parse(meta_path).getroot()
    home_id = [team.get("id") for team in root.iter("Team")][0]
    return np.array([HOME if player.get("teamId") == home_id else AWAY
                     for player in root.iter("Player")], dtype=np.int8)


def _parse(raw_path, n_frames, n_slots):
    """Stream the raw file into arrays. Missing groups stay NaN."""
    ball = np.full((n_frames, 2), np.nan)
    ball_speed = np.full(n_frames, np.nan, dtype=np.float32)
    players = np.full((n_frames, n_slots, 2), np.nan)
    speed = np.full((n_frames, n_slots), np.nan, dtype=np.float32)

    with open(raw_path) as handle:
        for line in handle:
            frame_part, player_part, ball_part = line.rstrip("\n").split(":")
            row = int(frame_part) - 1  # frame_id counts from 1, video frames from 0
            for slot, group in enumerate(player_part.split(";")):
                if group[0] != "N":
                    x, y, s = group.split(",")
                    players[row, slot] = (float(x), float(y))
                    speed[row, slot] = float(s)
            if ball_part[0] != "N":
                x, y, s = ball_part.split(",")
                ball[row] = (float(x), float(y))
                ball_speed[row] = float(s)
    return ball, ball_speed, players, speed


def load_tracking(source="tactical", refresh=False):
    """The ATD as arrays, from the local cache when it is there and current."""
    meta_path, raw_path = require(["atd_meta", "atd_raw"], source=source)
    cache = os.path.join(DERIVED_DIR, "tracking_{}_v{}.npz".format(source, CACHE_VERSION))

    if not refresh and os.path.isfile(cache) \
            and os.path.getmtime(cache) >= os.path.getmtime(raw_path):
        with np.load(cache) as stored:
            return {key: stored[key] for key in stored.files}

    team = team_of_each_slot(meta_path)
    ball, ball_speed, players, speed = _parse(raw_path, source_frames(source), len(team))
    arrays = {"ball": ball, "ball_speed": ball_speed, "players": players, "speed": speed,
              "team": team}
    os.makedirs(DERIVED_DIR, exist_ok=True)
    np.savez(cache, **arrays)
    return arrays
