# Experiment 004: Tagged restarts

## Mission statement (MS)

Can automatic set-piece tags plus ball motion locate stopped play more reliably than player
speed alone? Add one rule to Experiment 003 and measure its incremental effect.

## Fixed rule

1. Rebuild Experiment 003 exactly, including its long-gap and player-speed rules.
2. Look inside each automatic `SET PIECES` interval, with a two-second margin on each side.
   This includes kickoffs after goals. Do not use the broader `GOALS` phase as an exact goal time.
3. Find the first run of at least five consecutive frames with a detected ball moving at least
   2 m/s, immediately preceded by at least one second of missing or stationary ball (at most
   0.5 m/s). Use the beginning of that moving run as an approximate restart.
4. Require the preceding quiet section to overlap a missing-ball gap of at least ten seconds.
   Mark that quiet section `D`, bounded by the padded tag window and the graded half. Preserve
   Experiment 003 elsewhere, including from the estimated restart onwards.

Two signal sources are recorded with the same rule. The initial attempt used supplied ball
speeds and found no restart evidence. An input audit found these speeds absent in 103,579 of
113,488 detected-ball frames (91.3%). The second attempt estimates speed from consecutive ball
positions, after scaling coordinates to metres. It uses a forward median over five adjacent
position differences, requiring at least three, and never bridges missing positions or halves.
The forward window makes this an offline estimate and adds a few frames of timing uncertainty.
The second signal source was chosen from that coverage audit, without changing thresholds to
fit public labels. Both variants are evaluated and retained in `metrics.json`.

These thresholds are fixed before scoring. Tags do not establish ground truth, their team labels
are not copied into predictions, and absence of a tag does not establish live play. The rule only
adds `D`; it cannot yet rescue live goalkeeper possession that the baseline already calls dead.
It tests stronger stoppage evidence and more localized boundaries, not a complete goalkeeper detector.
It also misses restarts with gradual/noisy ball acceleration or a ball that remains undetected.

## Run

From the repository root:

```bash
.venv/bin/python -m unittest discover -s experiments/004_tagged_restarts -p 'test_*.py'
.venv/bin/python experiments/004_tagged_restarts/run.py
```

The candidate is fixed and passes the official validator before loading public ground truth.
Compare its public score with Experiment 003's 0.3349, plus Smooth50. Full-match possession counts
and dead-ball share are sanity checks; full-match accuracy remains unknown. No public score sweep
or per-window human labels are used. `metrics.json` stores aggregate results and code hashes.

## Review

The run exports changed sections to the [shared clip reviewer](../../docs/clip-reviewer.md).
Nearby changes within two seconds are combined for viewing, with five seconds of context on
each side. This grouping affects only the review list, never the predictions.

- [Local review player](../../data/derived/clip_reviews/004_tagged_restarts/review.html)
- [Timestamp list](../../data/derived/clip_reviews/004_tagged_restarts/timestamps.md)
- [Timestamp CSV](../../data/derived/experiments/004_tagged_restarts/changed_clips.csv)

The HTML is generated when there are changed sections and the tactical video is available.
All match-specific timestamps and labels remain ignored under `data/derived/`; only code,
documentation, and aggregates belong in git. Review general failure patterns without making
an answer key or correcting individual prediction rows.
