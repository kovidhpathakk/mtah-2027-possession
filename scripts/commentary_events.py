"""Turn the local commentary transcript into timed events on the tactical timeline. Counts only.

The transcript (scripts/transcribe.py) stays on this machine; this reads it locally and writes
data/derived/commentary_events.npz: per event its tactical frame, type and the team the line
names (or none). Nothing from the transcript is printed -- only counts, and checks of how each
event type lines up with what the tracking shows, which tell us how far to trust it.

Events are found with plain keyword rules first (transparent, repeatable). A local LLM can come
later for what keywords miss.

Timing: Whisper gives broadcast-audio times. broadcast frame = ms / 40; the broadcast-to-tactical
offset comes from scripts/align_broadcast.py, carried through replays and close-ups from the
nearest live frame (commentary keeps real time while the picture shows a replay). Commentators
speak a few seconds after the event; the checks below measure by how much.

    python scripts/commentary_events.py
"""

import json
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES, half_video_blocks  # noqa: E402

from possession.squads import teams_mentioned  # noqa: E402
from possession.stoppages import dead_mask  # noqa: E402
from possession.tracking import load_tracking  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
TRANSCRIPT = os.path.join(ROOT, "data", "derived", "commentary.json")
OFFSETS = os.path.join(ROOT, "data", "derived", "broadcast_offsets.npz")
OUT = os.path.join(ROOT, "data", "derived", "commentary_events.npz")
NEAR = 20 * FPS            # an event "lines up" with a stoppage starting within this before it

# Stoppage events, then live-play events. Order matters: the first type that matches a phrase
# takes it, so "free kick" is not also counted as a "kick".
EVENT_PATTERNS = [
    ("goal", r"\b(he scores|scores|goa+l!|it's in|back of the net|they lead|equalis|equaliz)"),
    ("penalty", r"\b(penalty|spot kick|spot-kick)\b"),
    ("free kick", r"\bfree[ -]?kick"),
    ("corner", r"\bcorner\b"),
    ("throw-in", r"\bthrow[ -]?in\b|\bthrow\b"),
    ("goal kick", r"\bgoal[ -]?kick"),
    ("offside", r"\boffside|flag (is|goes) up"),
    ("foul", r"\bfoul|brought down|tripped|clipped|hauled down|bundled over"),
    ("card", r"\b(yellow|red) card|\bbooked|\bbooking|\bcaution"),
    ("injury", r"\binjur|\btreatment|\bphysio|\bstretcher|\bstays down|\bgoes down"),
    ("substitution", r"\bsubstitut|comes on|coming on|comes off|makes way|replaced by"),
    ("var", r"\bvar\b|video assistant|\bon review|being checked"),
    ("kickoff", r"\bkick[ -]?off|\bkicks off|\bunderway|\bunder way"),
    ("whistle", r"\bhalf[ -]?time|\bfull[ -]?time|\bfinal whistle|\bblows (his|the) whistle"),
    ("shot", r"\bshot\b|\bshoots|\bstrike\b|\bheader\b|\bheads (it|wide|over)|\bsave[sd]?\b|"
             r"\bover the bar|\bwide\b|\bblocked"),
]
STOPPAGE_TYPES = {"goal", "penalty", "free kick", "corner", "throw-in", "goal kick", "offside",
                  "foul", "card", "injury", "substitution", "var", "kickoff", "whistle"}
COMPILED = [(name, re.compile(pattern)) for name, pattern in EVENT_PATTERNS]


def broadcast_to_tactical(n_broadcast):
    """Tactical frame for every broadcast frame. Where the broadcast shows no live play (replays,
    close-ups) the offset of the nearest live frame is used: commentary keeps real time. Never
    interpolated, so nothing is invented across the halftime splice."""
    offset = np.load(OFFSETS)["offset"]
    index = np.arange(len(offset))
    known = index[offset >= 0]
    right = np.clip(np.searchsorted(known, index), 0, len(known) - 1)
    left = np.clip(right - 1, 0, len(known) - 1)
    nearest = np.where(np.abs(known[left] - index) <= np.abs(known[right] - index),
                       known[left], known[right])
    return (index + offset[nearest]).astype(np.int64)[:n_broadcast]


if __name__ == '__main__':
    if not os.path.isfile(TRANSCRIPT):
        sys.exit("no transcript: run scripts/transcribe.py first")
    with open(TRANSCRIPT) as handle:
        segments = json.load(handle)["transcription"]
    mapping = broadcast_to_tactical(len(np.load(OFFSETS)["offset"]))

    graded = np.zeros(GAMES[GAME]["n_video_frames"], dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        graded[first:last + 1] = True

    frames, types, teams = [], [], []
    for segment in segments:
        text = segment["text"].lower()
        b_frame = int(segment["offsets"]["from"] / 1000 * FPS)
        if b_frame >= len(mapping):
            continue
        t_frame = int(mapping[b_frame])
        counts = teams_mentioned(segment["text"])
        team = 0 if counts[0] > counts[1] else 1 if counts[1] > counts[0] else -1
        for name, pattern in COMPILED:
            if pattern.search(text):
                frames.append(t_frame)
                types.append(name)
                teams.append(team)
    frames, types, teams = np.array(frames), np.array(types), np.array(teams, dtype=np.int8)
    np.savez(OUT, frame=frames, type=types, team=teams)

    inside = (frames >= 0) & (frames < len(graded))
    inside[inside] = graded[frames[inside]]
    tracking = load_tracking()
    dead = dead_mask(tracking)
    starts = np.flatnonzero(np.diff(np.concatenate(([0], dead.astype(np.int8)))) == 1)
    lines_with_team = sum(1 for s in segments if max(teams_mentioned(s["text"]).values()) > 0)
    print("{:,} transcript lines; {:.0%} name a team or a one-team player".format(
        len(segments), lines_with_team / len(segments)))
    print("{:,} events found, {:,} inside the graded halves\n".format(len(frames), inside.sum()))
    print("{:<13} {:>6} {:>10} {:>11} {:>22}".format(
        "type", "events", "team named", "home/away", "v2 stoppage began"))
    print("{:<13} {:>6} {:>10} {:>11} {:>22}".format(
        "", "", "", "", "0-20 s before (median)"))
    for name, _ in EVENT_PATTERNS:
        sel = inside & (types == name)
        if not sel.any():
            continue
        lags = []
        for f in frames[sel]:
            before = starts[(starts <= f) & (starts >= f - NEAR)]
            lags.append((f - before[-1]) / FPS if len(before) else np.nan)
        lags = np.array(lags)
        named = teams[sel] >= 0
        print("{:<13} {:>6} {:>10.0%} {:>5}/{:<5} {:>12.0%} ({:>4.1f} s)".format(
            name, int(sel.sum()), named.mean(), int((teams[sel] == 0).sum()),
            int((teams[sel] == 1).sum()), np.mean(~np.isnan(lags)),
            np.nanmedian(lags) if (~np.isnan(lags)).any() else np.nan))
    print("\nlast column: share of events with a v2 stoppage starting up to 20 s before the line,"
          "\nand the median delay. Stoppage words should score high; 'shot' is live play.")
