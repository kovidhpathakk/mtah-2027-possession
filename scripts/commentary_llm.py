"""A local LLM reads the commentary line by line: who has the ball, is play live, what happened.

Commentators say who has the ball far more often than they name set pieces ("Pedri ... out to
Yamal ... Athletic win it back"). A small LLM running on this machine (Ollama, qwen3:4b, pinned
below) reads the local transcript (scripts/transcribe.py) in batches and records, per line:

  possession   Barcelona / Athletic / unclear -- who has the ball as the line describes it
  state        live / stopped / unclear
  event        one short label (pass, shot, foul, free kick, corner, throw-in, ...) or none

The labels (no text) go to data/derived/commentary_llm.json, local only. Then the script measures
how far to trust them, against the tracking: for commentary delays of 0-10 s, how often the line's
team matches v2's team, and its "stopped" matches v2's dead ball. Finally the LLM writes a short
general description of the commentary -- what it covers and how reliably -- with no times,
scores, quotes or specific incidents. Nothing else from the transcript is printed.

Settings for repeatable output: temperature 0, fixed seed, thinking off, JSON schema.

    ollama serve &                                  # the local server
    python scripts/commentary_llm.py --pilot        # the 3-minute pilot transcript: timing
    python scripts/commentary_llm.py                # the whole match
"""

import argparse
import json
import os
import sys
import time
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from commentary_events import broadcast_to_tactical  # noqa: E402
from games import GAME, GAMES, half_video_blocks  # noqa: E402

from possession.squads import PLAYERS  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
MODEL = "qwen3:4b"
MODEL_DIGEST = "359d7dd4bcda"          # `ollama list` ID of the pulled model
URL = "http://localhost:11434/api/chat"
BATCH = 12                             # lines per request
CONTEXT = 3                            # previous lines shown for context
SEED = 42
DERIVED = os.path.join(ROOT, "data", "derived")
LAGS = range(0, 11)                    # seconds the commentary may trail the play
EVENTS = ["none", "pass", "dribble", "cross", "shot", "save", "tackle", "interception",
          "clearance", "foul", "free kick", "corner", "throw-in", "goal kick", "offside",
          "goal", "penalty", "card", "injury", "substitution", "var", "kickoff", "whistle",
          "other"]
SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {
    "type": "object", "properties": {
        "id": {"type": "integer"},
        "possession": {"type": "string", "enum": ["Barcelona", "Athletic", "unclear"]},
        "state": {"type": "string", "enum": ["live", "stopped", "unclear"]},
        "event": {"type": "string", "enum": EVENTS}},
    "required": ["id", "possession", "state", "event"]}}}, "required": ["lines"]}

SYSTEM = """You label lines of English football commentary from FC Barcelona vs Athletic Club.
Barcelona players: {home}.
Athletic Club players: {away}.
For each numbered CURRENT line, give:
- possession: the team that has the ball as the line describes it (use player names), or
  "unclear" if the line does not say;
- state: "stopped" if the line describes the ball out of play, a foul, a free kick or other
  set piece being taken, an injury, a substitution, a celebration or a break; "live" if it
  describes open play; otherwise "unclear";
- event: the main event the line describes, from the allowed list, or "none".
Lines marked CONTEXT are only there to help; do not label them. Answer only from the text."""


def ask(messages):
    body = json.dumps({"model": MODEL, "messages": messages, "stream": False, "think": False,
                       "format": SCHEMA, "options": {"temperature": 0, "seed": SEED,
                                                    "num_ctx": 4096}}).encode()
    request = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.loads(json.loads(response.read())["message"]["content"])


def label(segments):
    system = SYSTEM.format(home=", ".join(PLAYERS[0]), away=", ".join(PLAYERS[1]))
    out = [None] * len(segments)
    for first in range(0, len(segments), BATCH):
        context = segments[max(0, first - CONTEXT):first]
        batch = segments[first:first + BATCH]
        text = "\n".join("CONTEXT: " + s["text"].strip() for s in context) + "\n" + \
            "\n".join("{}: {}".format(first + i, s["text"].strip()) for i, s in enumerate(batch))
        try:
            answer = ask([{"role": "system", "content": system}, {"role": "user", "content": text}])
            for item in answer.get("lines", []):
                if first <= item["id"] < first + len(batch):
                    out[item["id"]] = item
        except (ValueError, KeyError, OSError):
            pass  # an unparseable batch stays unlabelled; counted below
    return out


def check(segments, labels):
    """Agreement with v2 on our match, for each commentary delay. Aggregates only."""
    from possession.stoppages import predict
    from possession.tracking import load_tracking
    mapping = broadcast_to_tactical(len(np.load(os.path.join(DERIVED, "broadcast_offsets.npz"))
                                        ["offset"]))
    v2 = predict(load_tracking())
    graded = np.zeros(len(v2), dtype=bool)
    for _, a, b in half_video_blocks(GAME):
        graded[a:b + 1] = True
    frames = np.array([mapping[min(int(s["offsets"]["from"] / 1000 * FPS), len(mapping) - 1)]
                       for s in segments])
    team = np.array([(l or {}).get("possession", "missing") for l in labels])
    state = np.array([(l or {}).get("state", "missing") for l in labels])
    print("\nAGREEMENT WITH v2 ON OUR MATCH, by how many seconds the commentary trails the play")
    print("{:>6} {:>22} {:>22}".format("delay", "team matches v2", "'stopped' is v2 dead"))
    best = None
    for lag in LAGS:
        f = frames - lag * FPS
        ok = (f >= 0) & (f < len(v2))
        ok[ok] = graded[f[ok]]
        named = ok & np.isin(team, ["Barcelona", "Athletic"])
        live_v2 = named & np.isin(v2[np.clip(f, 0, len(v2) - 1)], ["H", "A"])
        expected = np.where(team == "Barcelona", "H", "A")
        team_ok = (v2[np.clip(f, 0, len(v2) - 1)] == expected)[live_v2].mean()
        stopped = ok & (state == "stopped")
        dead_ok = (v2[np.clip(f, 0, len(v2) - 1)] == "D")[stopped].mean()
        print("{:>5}s {:>15.0%} of {:>4} {:>15.0%} of {:>4}".format(
            lag, team_ok, int(live_v2.sum()), dead_ok, int(stopped.sum())))
        if best is None or team_ok > best[1]:
            best = (lag, team_ok)
    print("best team agreement at a {} s delay. For scale: v2's own team calls are right about "
          "as often as the practice score allows -- disagreement is not all the commentary's "
          "fault.".format(best[0]))


def describe(labels):
    """A short general description, from the label counts only: no text is sent back."""
    counts = {}
    for key in ("possession", "state", "event"):
        values = [(l or {}).get(key, "missing") for l in labels]
        counts[key] = {v: values.count(v) for v in sorted(set(values))}
    prompt = ("Here are counts of labels a model gave to {} lines of football commentary: {}. "
              "In four sentences, describe in general terms what this commentary is useful for "
              "when deciding which team has the ball and when play is stopped, and its limits. "
              "Do not mention times, scores or specific incidents.").format(
                  len(labels), json.dumps(counts))
    body = json.dumps({"model": MODEL, "prompt": prompt, "stream": False, "think": False,
                       "options": {"temperature": 0, "seed": SEED}}).encode()
    request = urllib.request.Request("http://localhost:11434/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        text = json.loads(response.read())["response"]
    return text.split("</think>")[-1].strip()  # qwen3 may still print its reasoning first


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pilot", action="store_true", help="the 3-minute pilot transcript")
    args = parser.parse_args()
    source = os.path.join(DERIVED, "commentary_pilot.json" if args.pilot else "commentary.json")
    if not os.path.isfile(source):
        sys.exit("no transcript: run scripts/transcribe.py first")
    with open(source) as handle:
        segments = json.load(handle)["transcription"]

    started = time.time()
    labels = label(segments)
    seconds = time.time() - started
    out = os.path.join(DERIVED, "commentary_llm{}.json".format("_pilot" if args.pilot else ""))
    with open(out, "w") as handle:
        json.dump([{"from_ms": s["offsets"]["from"], **(l or {})}
                   for s, l in zip(segments, labels)], handle)

    done = [l for l in labels if l]
    print("{} lines labelled in {:.1f} min ({:.1f} s per line); {} unparseable".format(
        len(done), seconds / 60, seconds / max(len(segments), 1), len(segments) - len(done)))
    for key in ("possession", "state"):
        values = [l[key] for l in done]
        print("  {:<10} ".format(key) + ", ".join("{} {:.0%}".format(v, values.count(v) / len(values))
                                                  for v in sorted(set(values))))
    events = [l["event"] for l in done if l["event"] != "none"]
    print("  events     " + ", ".join("{} {}".format(e, events.count(e)) for e in
                                      sorted(set(events), key=lambda e: -events.count(e))))
    if not args.pilot:
        check(segments, labels)
    print("\nTHE LOCAL MODEL'S GENERAL DESCRIPTION\n" + describe(labels))
