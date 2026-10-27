"""Pull the soundtrack out of a video into data/derived/, as 16 kHz mono WAV.

16 kHz mono is what Whisper (speech to text) expects, it keeps everything up to 8 kHz -- the
referee whistle sits at 3-4.5 kHz -- and it is about 250 MB for the whole recording instead of
the 5-14 GB video. Once the broadcast audio is out, the broadcast video is no longer needed for
anything we plan, which frees 14 GB.

Both videos' audio starts at the same instant as their picture (ffprobe start_time 0), so audio
second s is video frame s * 25 with no correction.

    python scripts/extract_audio.py                      # tactical and broadcast
    python scripts/extract_audio.py --source broadcast

Writes data/derived/<source>_audio_16k.wav (gitignored). Prints nothing from the audio itself.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import asset_paths  # noqa: E402

# Params
DERIVED_DIR = os.path.join(ROOT, "data", "derived")
RATE = 16000


def audio_path(source):
    return os.path.join(DERIVED_DIR, "{}_audio_16k.wav".format(source))


def extract(source):
    video = asset_paths(source=source)["video"]
    if not os.path.isfile(video):
        print("{}: no video at {}, skipped".format(source, os.path.relpath(video, ROOT)))
        return
    out = audio_path(source)
    os.makedirs(DERIVED_DIR, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1",
                    "-ar", str(RATE), "-c:a", "pcm_s16le", out], check=True)
    print("{}: wrote {} ({:.0f} MB)".format(source, os.path.relpath(out, ROOT),
                                            os.path.getsize(out) / 1e6))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=("tactical", "broadcast"))
    args = parser.parse_args()
    if shutil.which("ffmpeg") is None:
        sys.exit("ffmpeg not installed (brew install ffmpeg)")
    for source in [args.source] if args.source else ["tactical", "broadcast"]:
        extract(source)
