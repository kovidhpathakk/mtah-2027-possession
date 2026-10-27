"""Transcribe the broadcast commentary locally with Whisper, into data/derived/ (never committed).

The commentary (English) names what the tracking cannot: fouls, free kicks and who gets them,
offsides, injuries, substitutions. It sits on the broadcast soundtrack, whose timeline maps to the
tactical one through data/derived/broadcast_offsets.npz (scripts/align_broadcast.py).

Runs whisper.cpp (Homebrew `whisper-cpp`, Metal on Apple silicon) with the large-v3-turbo model,
pinned by its SHA-256 below. Decoding is greedy with no temperature fallback, so the same audio and
model give the same text on every run. That alone sent Whisper into a loop on this long, noisy
audio (5 repeated lines made up 86% of the first transcript): the temperature fallback is what
normally breaks loops. So, keeping it greedy:
  - voice-activity detection (Silero VAD, pinned) transcribes only stretches with speech, so
    crowd noise is never fed to the model;
  - max context 0: each stretch is decoded without the previous text, which sustains a loop;
  - non-speech tokens suppressed.
A 10-minute test after the fix: 250 distinct lines, ~8 words each, 26% naming a team or a player,
language auto-detected as English.

The transcript is an extract of the broadcast: it stays on
this machine and is read only by local code (scripts/commentary_events.py). This script prints
counts only.

    python scripts/transcribe.py --minutes 3       # pilot on the first 3 minutes: timing
    python scripts/transcribe.py                   # the whole broadcast (~110 min of audio)

Fetch the model first (~550 MB, into models/, gitignored):
    curl -L -o models/ggml-large-v3-turbo-q5_0.bin \\
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin
    curl -L -o models/ggml-silero-v6.2.0.bin \\
        https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Params
MODEL = os.path.join(ROOT, "models", "ggml-large-v3-turbo-q5_0.bin")
MODEL_SHA256 = "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2"
VAD_MODEL = os.path.join(ROOT, "models", "ggml-silero-v6.2.0.bin")
VAD_SHA256 = "2aa269b785eeb53a82983a20501ddf7c1d9c48e33ab63a41391ac6c9f7fb6987"
AUDIO = os.path.join(ROOT, "data", "derived", "broadcast_audio_16k.wav")
OUT = os.path.join(ROOT, "data", "derived", "commentary")   # whisper adds .json
THREADS = 8


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def whisper_cli():
    for name in ("whisper-cli", "/opt/homebrew/bin/whisper-cli"):
        found = shutil.which(name)
        if found:
            return found
    sys.exit("whisper-cli not found: brew install whisper-cpp")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--minutes", type=float, default=0, help="only the first N minutes")
    args = parser.parse_args()

    for path, digest in ((MODEL, MODEL_SHA256), (VAD_MODEL, VAD_SHA256)):
        if not os.path.isfile(path) or sha256(path) != digest:
            sys.exit("{} missing or not the pinned file: see the docstring".format(path))
    if not os.path.isfile(AUDIO):
        sys.exit("no broadcast audio: run scripts/extract_audio.py first")

    out = OUT + ("_pilot" if args.minutes else "")
    cmd = [whisper_cli(), "-m", MODEL, "-f", AUDIO, "-l", "en", "-t", str(THREADS),
           "-bs", "1", "-bo", "1", "-nf",          # greedy, no temperature fallback: repeatable
           "-mc", "0", "-sns",                     # no carried-over text, no non-speech tokens
           "--vad", "-vm", VAD_MODEL,              # speech stretches only
           "-ojf", "-of", out, "-np"]              # full JSON (segments and tokens), no live text
    if args.minutes:
        cmd += ["-d", str(int(args.minutes * 60 * 1000))]
    started = time.time()
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    seconds = time.time() - started

    with open(out + ".json") as handle:
        segments = json.load(handle)["transcription"]
    words = sum(len(s["text"].split()) for s in segments)
    spoken = sum((s["offsets"]["to"] - s["offsets"]["from"]) / 1000 for s in segments)
    audio = args.minutes * 60 if args.minutes else segments[-1]["offsets"]["to"] / 1000
    print("transcribed {:.1f} min of audio in {:.1f} min ({:.1f}x real time)".format(
        audio / 60, seconds / 60, audio / seconds))
    print("{:,} segments, {:,} words, speech covers {:.0%} of the audio".format(
        len(segments), words, spoken / audio))
    print("written to {} (local only)".format(os.path.relpath(out + ".json", ROOT)))
