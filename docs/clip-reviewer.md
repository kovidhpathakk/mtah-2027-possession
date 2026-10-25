# Local clip reviewer

Use the same player for timestamp lists from any experiment. An experiment writes a CSV with
elapsed times from **one chosen video**. The reviewer adds context, then creates a local HTML
player and a readable timestamp list. It does not decode, copy, or upload the video.

Put match-specific CSVs under ignored `data/derived/`. The minimal format is:

```csv
start_seconds,end_seconds,name,detail
10,14,Example 1,Optional note
30.5,38,Example 2,Optional note
```

`name` and `detail` are optional columns. End times are exclusive. For frame-based experiments,
use `start_frame,end_frame` instead, and pass `--fps 25` (or the actual video frame rate). Frame
numbers are zero-based; the end frame is exclusive. Use the tactical video for tactical frame
numbers. The broadcast recording has a different, unsynchronized timeline.

Run from the repository root:

```bash
.venv/bin/python scripts/clip_reviewer.py \
  --clips data/derived/experiments/my_experiment/clips.csv \
  --video data/tactical/BAR-ATH_tactical.mp4 \
  --name my_experiment
```

Open `data/derived/clip_reviews/my_experiment/review.html` in your browser. The same directory
contains `timestamps.md` for an ordinary video player. By default, each review window has five
seconds of context on both sides. Use `--context-seconds 2` to change it. If the video is stored
elsewhere, pass its local path to `--video`. If you know its duration, pass
`--expected-duration-seconds` to clamp review windows and warn if the browser loads a different
recording.

Experiment 003 generates its own CSV and calls this reviewer with:

```bash
.venv/bin/python experiments/003_player_speed/review_gaps.py
```

The timestamps, generated HTML, and video all stay local. Do not commit them or use manual
observations to assign possession labels for the competition match.
