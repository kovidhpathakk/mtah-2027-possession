# Experiment 001 results

Status: first run complete, October 24, 2026.

| Version | Public spellF1 | Public macroF1 | Public possessions | Spurious transitions | Full-match possessions | Dead-ball share |
|---|---:|---:|---:|---:|---:|---:|
| Official smooth25 | 0.2868 | 0.6200 | 36 | 33 | 746 | 36.5% |
| Persistence 10 frames | 0.2868 | 0.6200 | 36 | 33 | 700 | 36.5% |
| Persistence 25 frames | 0.2824 | 0.6184 | 34 | 32 | 642 | 36.5% |
| Official smooth50 anchor | 0.3256 | 0.6207 | 26 | 27 | 594 | 32.3% |

The 10-frame rule removed 46 short possession runs over the two graded halves without changing
the public score. The 25-frame rule removed 104 runs, but the public score moved slightly lower.
Neither version beats the official smooth50 anchor on this public sample. The hidden full-match
score is unknown, so no improvement is established. Dead-ball share is unchanged because this
experiment only edits short team reversals.

Next question: are the remaining false switches caused by short `H/A` blips, or by the baseline's
handling of dead balls and missing ball tracking? The current public diagnostics suggest the
second issue may matter more.
