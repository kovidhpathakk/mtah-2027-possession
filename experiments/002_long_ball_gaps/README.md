# Experiment 002: Long ball tracking gaps

## Mission statement (MS)

Test the team's observation that long periods without a tracked ball often occur while play is
stopped. Start with the official `smooth50` baseline and change one thing: label an entire
ball-missing interval `D` when it lasts at least 250 frames (10 seconds) within a graded half.

The 10-second threshold was chosen before looking at this experiment's score. The rule uses
tracking availability only; it does not use manual labels from video clips.

## What we will check

- On the public five minutes: dead-ball precision and recall, possession score, and transitions.
- Across both halves: how much missing-ball time the rule covers, how many labels change, and
  whether it creates an implausible number of possessions.
- The public window has unusually good ball coverage, so its score is a limited diagnostic.

## Run

From the repository root:

```bash
.venv/bin/python experiments/002_long_ball_gaps/run.py
```

The script prints aggregates only. Its candidate CSV stays in ignored
`data/derived/experiments/002_long_ball_gaps/`. Record the result and conclusion in `results.md`.
