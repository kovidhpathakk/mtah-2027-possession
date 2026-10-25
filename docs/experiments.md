# Experiment log

One row per experiment, newest first. Public scores describe the five-minute sample; whole-match
counts are sanity checks, not accuracy measurements. Use bootstrap intervals when interpreting
public differences: the roughly 0.04 noise band quoted for a full match does not apply here.
The planned damage test is not implemented yet, so its results remain blank.

| Date | Who | Branch | What changed | Public spellF1 / macroF1 | Damage-test spellF1 (mean ± spread) | Possessions (full match) | Mean length (s) | D share | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-24 | — | test-v1 | [004: tagged restarts plus ball motion](../experiments/004_tagged_restarts/README.md) | 0.3349 / 0.6522 | — | 547 | 7.46 | 35.8% | 500 frames changed outside public sample; ten review windows. Full-match improvement unknown. [Results](../experiments/004_tagged_restarts/results.md) |
| 2026-10-24 | — | test-v1 | [003: speed check for long gaps](../experiments/003_player_speed/README.md) | 0.3349 / 0.6522 | — | 555 | 7.39 | 35.5% | Same public predictions as 002; accepts 50 of 79 gaps. [Results](../experiments/003_player_speed/results.md) |
| 2026-10-24 | — | test-v1 | [002: gaps of at least 10 seconds become D](../experiments/002_long_ball_gaps/README.md) | 0.3349 / 0.6522 | — | 532 | 7.49 | 37.3% | Small public gain; full-match accuracy unknown. [Results](../experiments/002_long_ball_gaps/results.md) |
| 2026-10-24 | — | test-v1 | [001: remove team reversals under 10 frames](../experiments/001_persistence/README.md) | 0.2868 / 0.6200 | — | 700 | — | 36.5% | Built on Smooth25; no public score change. [Results](../experiments/001_persistence/results.md) |
| 2026-10-23 | — | main | Baseline smooth50, unchanged | 0.3256 / 0.6207 | — | 594 | 7.24 | 32.3% | Reference. Full-match spellF1 0.2433 per EVALUATION.md; counts verified in 003. |
