"""Transcribe the broadcast commentary locally with Whisper, into data/derived/ (never committed).

The commentary (English) names what the tracking cannot: fouls, free kicks and who gets them,
offsides, injuries, substitutions. It sits on the broadcast soundtrack, whose timeline maps to the
tactical one through data/derived/broadcast_offsets.npz (scripts/align_broadcast.py).

Runs whisper.cpp (Homebrew `whisper-cpp`, Metal on Apple silicon) with the large-v3-turbo model,
pinned by its SHA-256 below. Decoding is greedy with no temperature fallback, so the same audio and
model give the same text on every run. The transcript is an extract of the broadcast: it stays on
this machine and is read only by local code (scripts/commentary_events.py). This script prints
counts only.

    python scripts/transcribe.py --minutes 3       # pilot on the first 3 minutes: timing
    python scripts/transcribe.py                   # the whole broadcast (~110 min of audio)

Fetch the model first (~550 MB, into models/, gitignored):
    curl -L -o models/ggml-large-v3-turbo-q5_0.bin \\
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin
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

    if not os.path.isfile(MODEL) or sha256(MODEL) != MODEL_SHA256:
        sys.exit("model missing or not the pinned file: see the docstring")
    if not os.path.isfile(AUDIO):
        sys.exit("no broadcast audio: run scripts/extract_audio.py first")

    out = OUT + ("_pilot" if args.minutes else "")
    cmd = [whisper_cli(), "-m", MODEL, "-f", AUDIO, "-l", "en", "-t", str(THREADS),
           "-bs", "1", "-bo", "1", "-nf",          # greedy, no temperature fallback: repeatable
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
