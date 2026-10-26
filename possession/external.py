"""Other matches, in the same arrays as ours, with an H/A/D label on every frame.

We may not tune anything on our own match (RULES.md; issue #10), so every threshold is set on
other matches instead. This module loads them into exactly the layout possession.tracking gives
for BAR-ATH -- normalised 0-1 positions, NaN where missing, team 0 = home -- so every method and
audit runs on them unchanged, plus three extras: `labels` (one H/A/D/X per frame), `halves`
[(half, first_row, last_row)] and `pitch` (length, width) in metres.

Fetch the files first: python scripts/fetch_open_data.py

  dfl-<match>  DFL / Bassek et al. 2025, 7 Bundesliga matches (CC BY 4.0). Labels come straight
               from the per-frame BallStatus (0 dead) and BallPossession (1 home, 2 away). Our
               ground truth is made the same way -- from a tracking provider's "ball dead" and
               "owning team" fields (CHALLENGE.md) -- which is why DFL is the closest match.
               Referees are left out: our tracker does not track them (audit_confirm.py).
               DFL speeds are in km/h (audit_tracking.py finds them exactly 3.6x the speed
               from positions) and are converted to m/s like ours.
  metrica3     Metrica Sports sample Game 3. Labels are derived from its event list:
                 dead   from a BALL OUT's end, a FAULT RECEIVED, or a shot that goes in or out,
                        until the next restart (SET PIECE, or a pass marked GOAL KICK); and from
                        the start of each half until its kickoff
                 team   the team of the latest on-ball event (pass, carry, shot, recovery, set
                        piece). Duels (CHALLENGE) do not change it: a contested ball stays with
                        the last team, as in CHALLENGE.md.
               It has no speed column, so speed is computed from positions.

Parsed arrays are cached in data/derived/external/ (gitignored).

    from possession.external import load_source, sources
    t = load_source("dfl-J03WMX")
"""

import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, half_video_blocks  # noqa: E402

from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
EXTERNAL_DIR = os.path.join(ROOT, "data", "external")
CACHE_DIR = os.path.join(ROOT, "data", "derived", "external")
CACHE_VERSION = 2  # 2: DFL speeds converted from km/h
FPS = 25
HOME, AWAY = 0, 1
RESTART_WAIT = 90 * FPS   # a stoppage with no restart event within this ends at the next event
KMH = 3.6                 # DFL speed unit -> m/s
ATTR = re.compile(r'(\w+)="([^"]*)"')
POSSESSION_EVENTS = {"PASS", "CARRY", "SHOT", "RECOVERY", "SET PIECE", "BALL LOST"}


def sources():
    """Every source name load_source accepts, ours first."""
    dfl = sorted(re.search(r"(J03\w+)\.xml$", p).group(1)
                 for p in glob.glob(os.path.join(EXTERNAL_DIR, "dfl", "*positions*.xml")))
    metrica = ["metrica3"] if os.path.isfile(
        os.path.join(EXTERNAL_DIR, "metrica", "Sample_Game_3_tracking.txt")) else []
    return ["tactical", "broadcast"] + metrica + ["dfl-" + m for m in dfl]


def load_source(name, refresh=False):
    """Our tracking (with halves and pitch added) or an external match (with labels too)."""
    if name in ("tactical", "broadcast"):
        t = dict(load_tracking(name))
        t["pitch"] = PITCH
        if name == "tactical":
            t["halves"] = list(half_video_blocks(GAME))
        return t
    cache = os.path.join(CACHE_DIR, "{}_v{}.npz".format(name, CACHE_VERSION))
    if not refresh and os.path.isfile(cache):
        with np.load(cache) as stored:
            t = {key: stored[key] for key in stored.files}
    else:
        t = load_dfl(name[4:]) if name.startswith("dfl-") else load_metrica3()
        os.makedirs(CACHE_DIR, exist_ok=True)
        np.savez(cache, **t)
    t["halves"] = [tuple(int(v) for v in row) for row in t["halves"]]
    t["pitch"] = tuple(float(v) for v in t["pitch"])
    return t


def speed_from_positions(players, pitch, half=2):
    """m/s from the move between t-half and t+half, for sources without a speed column."""
    metres = players * np.array(pitch)
    out = np.full(players.shape[:2], np.nan, dtype=np.float32)
    out[half:-half] = np.linalg.norm(metres[2 * half:] - metres[:-2 * half], axis=-1) \
        * FPS / (2 * half)
    return out


# --- DFL --------------------------------------------------------------------------------------

def load_dfl(match):
    folder = os.path.join(EXTERNAL_DIR, "dfl")
    info_path = glob.glob(os.path.join(folder, "*matchinformation*{}.xml".format(match)))[0]
    general = ET.parse(info_path).getroot().find(".//General")
    environment = ET.parse(info_path).getroot().find(".//Environment")
    home_id = general.get("HomeTeamId")
    pitch = (float(environment.get("PitchX")), float(environment.get("PitchY")))

    # The positions file holds one <Frame> per line, grouped in a <FrameSet> per person and half.
    sets = []
    path = glob.glob(os.path.join(folder, "*positions*{}.xml".format(match)))[0]
    with open(path) as handle:
        current = None
        for line in handle:
            line = line.lstrip()
            if line.startswith("<Frame "):
                a = dict(ATTR.findall(line))
                current["rows"].append((int(a["N"]), float(a["X"]), float(a["Y"]),
                                        float(a.get("S", "nan")), float(a.get("Z", "nan")),
                                        int(a.get("BallStatus", -1)),
                                        int(a.get("BallPossession", -1))))
            elif line.startswith("<FrameSet "):
                a = dict(ATTR.findall(line))
                current = {"section": a["GameSection"], "team": a["TeamId"],
                           "person": a["PersonId"], "rows": []}
                sets.append(current)

    # Rows: each half's ball frames, end to end. The ball is present on every frame in DFL.
    sections = []
    for s in sets:
        if s["team"] == "BALL" and s["section"] not in sections:
            sections.append(s["section"])
    first_n, offset, halves = {}, {}, []
    row = 0
    for k, section in enumerate(sections):
        n = np.array([r[0] for s in sets if s["team"] == "BALL" and s["section"] == section
                      for r in s["rows"]])
        first_n[section], offset[section] = n.min(), row
        halves.append((k + 1, row, row + n.max() - n.min()))
        row += n.max() - n.min() + 1
    n_frames = row

    people = sorted({s["person"] for s in sets if s["team"] not in ("BALL", "referee")})
    slot_of = {p: i for i, p in enumerate(people)}
    team = np.zeros(len(people), dtype=np.int8)
    ball = np.full((n_frames, 2), np.nan)
    ball_z = np.full(n_frames, np.nan, dtype=np.float32)
    ball_speed = np.full(n_frames, np.nan, dtype=np.float32)
    labels = np.full(n_frames, "X", dtype="<U1")
    players = np.full((n_frames, len(people), 2), np.nan)
    speed = np.full((n_frames, len(people)), np.nan, dtype=np.float32)
    length, width = pitch
    for s in sets:
        if s["team"] == "referee" or not s["rows"]:
            continue
        r = np.array(s["rows"])
        idx = (r[:, 0] - first_n[s["section"]] + offset[s["section"]]).astype(int)
        xy = np.stack([(r[:, 1] + length / 2) / length, (r[:, 2] + width / 2) / width], axis=1)
        if s["team"] == "BALL":
            ball[idx], ball_z[idx], ball_speed[idx] = xy, r[:, 4], r[:, 3] / KMH
            labels[idx] = np.where(r[:, 5] == 0, "D", np.where(r[:, 6] == 1, "H", "A"))
        else:
            slot = slot_of[s["person"]]
            team[slot] = HOME if s["team"] == home_id else AWAY
            players[idx, slot], speed[idx, slot] = xy, r[:, 3] / KMH
    return {"ball": ball, "ball_z": ball_z, "ball_speed": ball_speed, "players": players,
            "speed": speed, "team": team, "labels": labels, "halves": np.array(halves),
            "pitch": np.array(pitch)}


# --- Metrica Game 3 ---------------------------------------------------------------------------

def load_metrica3():
    folder = os.path.join(EXTERNAL_DIR, "metrica")
    root = ET.parse(os.path.join(folder, "Sample_Game_3_metadata.xml")).getroot()
    params = {p.findtext("Name"): p.findtext("Value") for p in root.iter("ProviderParameter")}
    field = root.find(".//FieldSize")
    pitch = (float(field.findtext("Width")), float(field.findtext("Height")))
    home_id = [t.get("id") for t in root.iter("Team")][0]
    team_of_player = {p.get("id"): (HOME if p.get("teamId") == home_id else AWAY)
                      for p in root.iter("Player")}
    player_of_channel = {c.get("id"): c.get("playerId") for c in root.iter("PlayerChannel")}
    people = sorted(team_of_player)
    slot_of = {p: i for i, p in enumerate(people)}
    team = np.array([team_of_player[p] for p in people], dtype=np.int8)

    # Substitutions change which players a line lists, so each frame range has its own order.
    layouts = []
    for spec in root.iter("DataFormatSpecification"):
        channels = [c.get("playerChannelId") for c in spec.iter("PlayerChannelRef")]
        slots = [slot_of[player_of_channel[c]] for c in channels if c.endswith("_x")]
        layouts.append((int(spec.get("startFrame")), int(spec.get("endFrame")), slots))

    halves_frames = [(1, int(params["first_half_start"]), int(params["first_half_end"])),
                     (2, int(params["second_half_start"]), int(params["second_half_end"]))]
    n_frames = halves_frames[-1][2]  # frames count from 1; row = frame - 1
    ball = np.full((n_frames, 2), np.nan)
    players = np.full((n_frames, len(people), 2), np.nan)
    with open(os.path.join(folder, "Sample_Game_3_tracking.txt")) as handle:
        for line in handle:
            frame_part, player_part, ball_part = line.rstrip("\n").split(":")
            frame = int(frame_part)
            slots = next(s for a, b, s in layouts if a <= frame <= b)
            for slot, group in zip(slots, player_part.split(";")):
                x, y = group.split(",")
                players[frame - 1, slot] = (float(x), float(y))
            x, y = ball_part.split(",")
            ball[frame - 1] = (float(x), float(y))

    events = json.load(open(os.path.join(folder, "Sample_Game_3_events.json")))["data"]
    labels = metrica_labels(events, n_frames, home_id, halves_frames)
    halves = np.array([(h, a - 1, b - 1) for h, a, b in halves_frames])
    return {"ball": ball, "ball_speed": np.full(n_frames, np.nan, dtype=np.float32),
            "players": players, "speed": speed_from_positions(players, pitch), "team": team,
            "labels": labels, "halves": halves, "pitch": np.array(pitch)}


def _subtypes(event):
    s = event.get("subtypes")
    if isinstance(s, dict):
        s = [s]
    return {x["name"] for x in s} if s else set()


def metrica_labels(events, n_frames, home_id, halves_frames):
    """H/A/D per row from Metrica's event list, by the rules in the module docstring."""
    labels = np.full(n_frames, "X", dtype="<U1")
    restarts = np.array(sorted(e["start"]["frame"] for e in events
                               if e["type"]["name"] == "SET PIECE"
                               or "GOAL KICK" in _subtypes(e)))
    starts = np.array([e["start"]["frame"] for e in events])

    def restart_after(frame):
        later = restarts[restarts >= frame]
        if len(later) and later[0] - frame <= RESTART_WAIT:
            return later[0]
        nxt = starts[starts > frame]
        return nxt[0] if len(nxt) else frame

    # Live team: the latest on-ball event's team, carried forward.
    team_at = np.full(n_frames + 2, -1, dtype=np.int8)
    for e in events:
        if e["type"]["name"] in POSSESSION_EVENTS:
            team_at[e["start"]["frame"]] = HOME if e["team"]["id"] == home_id else AWAY
    for _, first, last in halves_frames:
        seen = -1
        for f in range(first, last + 1):
            if team_at[f] >= 0:
                seen = team_at[f]
            team_at[f] = seen
    for _, first, last in halves_frames:
        part = team_at[first:last + 1]
        labels[first - 1:last] = np.where(part == HOME, "H", np.where(part == AWAY, "A", "D"))

    # Dead stretches.
    dead = np.zeros(n_frames + 2, dtype=bool)
    for e in events:
        name, sub = e["type"]["name"], _subtypes(e)
        if name == "BALL OUT" or (name == "SHOT" and sub & {"GOAL", "OUT"}):
            begin = e["end"]["frame"]
        elif name == "FAULT RECEIVED":
            begin = e["start"]["frame"]
        else:
            continue
        dead[begin:restart_after(begin + 1)] = True
    for _, first, last in halves_frames:
        kickoff = restarts[(restarts >= first) & (restarts <= last)]
        if len(kickoff):
            dead[first:kickoff[0]] = True
    labels[dead[1:n_frames + 1]] = "D"
    return labels
