# Experiment 003: Player speed during ball gaps

## Mission statement (MS)

Does player movement help avoid calling a tracking loss a stoppage? Experiment 002 marked every
ball gap of at least 10 seconds as dead. This experiment requires evidence of slow movement
before making those extra dead-ball assignments.

## Fixed rule

Start with official Smooth50, independently of Experiment 001. For each ball gap of at least
250 frames (10 seconds) within a graded half:

1. A frame supports a stoppage if at least 12 player tracks have usable positions and nonnegative,
   finite speeds, and their median speed is at most 1.5 metres per second.
2. At least 80% of the gap's frames must support a stoppage. Frames with inadequate tracking do
   not count as evidence of slow movement.
3. If the gap qualifies, mark all of it `D`. Otherwise retain Smooth50's predictions.

These thresholds are an initial hypothesis fixed before scoring, not learned from the public
answer key. The whole gap is considered offline; this rule is not suitable for live predictions.

Rejecting a gap only cancels the *extra* `D` assignments from Experiment 002. Smooth50 still calls
the middle of long tracking gaps dead. A successful speed gate would therefore be a narrower
change, not a complete solution for possession during missing-ball periods.

## Run and results

From the repository root:

```bash
.venv/bin/python -m unittest discover -s experiments/003_player_speed -p 'test_*.py'
.venv/bin/python experiments/003_player_speed/run.py
```

`results.md` explains the outcome. `metrics.json` records aggregate measurements, parameters,
code hashes and dependency versions. The candidate CSV is stored only in ignored
`data/derived/experiments/003_player_speed/`. No tracking rows, images or per-frame reports are
printed or saved in this experiment folder.

Compare Smooth50, Experiment 002, and this candidate using the official public scorer plus
whole-match prediction counts. Bootstrap intervals express uncertainty within the public sample;
they cannot establish accuracy on the unlabeled rest of the match. All derived match files stay
local. The existing damage test mentioned in team notes has not been implemented in this checkout.

## Local video review

Experiment 003 exports the rejected gaps to the [shared clip reviewer](../../docs/clip-reviewer.md).
With the tactical video in its configured location, generate the timestamp CSV and local player:

```bash
.venv/bin/python experiments/003_player_speed/review_gaps.py
```

The generator reuses this experiment's gate and checks the rejection count against `metrics.json`.
It prints only counts and output paths. The shared reviewer adds five seconds of context on each
side and saves its files under ignored `data/derived/clip_reviews/003_player_speed/`.

- [Timestamp CSV](../../data/derived/experiments/003_player_speed/rejected_gaps.csv)
- [Timestamp list](../../data/derived/clip_reviews/003_player_speed/timestamps.md)
- [Local review player](../../data/derived/clip_reviews/003_player_speed/review.html)

Open the HTML file in a browser on your computer and choose a gap. It seeks within the original
tactical video and pauses at the end of the review window; it does not export or upload clips.
If the browser cannot play the file, use the timestamp list with your usual video player.
Timestamps are elapsed tactical-video time, not the on-screen match clock, and do not apply to
the unsynchronized broadcast video.

These lists and footage stay local under `data/derived/`. A hosted assistant must not open the
generated player or inspect its interval-level contents. Human review should identify general
football patterns, not produce clip-specific H/A/D annotations or hand-corrected predictions.
