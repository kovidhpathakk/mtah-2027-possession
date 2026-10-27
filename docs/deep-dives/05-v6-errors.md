# Deep dive 5: v6's remaining errors

v5 and v6 each came from one round of build, test and check. This dive goes back over them the
slow way: anatomy of the errors, real cases, the realism of what the models learned from, one fix
at a time. Started 2026-10-26.

## Step 1: is the practice data's stoppage realistic? No: the dead ball was frozen

**Why we looked.** v6's stoppage model is right 94% of the time even where ball gaps tell nothing,
and in the public window it calls 10% of frames dead against the truth's 20% (not tuned on, but a
warning). The realism report had no stoppage measures, so we added some (no answers needed).

**What we found** (`scripts/realism_report.py`, plus one-off counts):

| Measure | Our match | Practice, clean | Practice, damaged (before) |
|---|---|---|---|
| visible ball still for 2 s+, share of graded frames | 1.5% | 38% | 3.8% |
| walking phases (players under half pace) with the ball in view: ball still | 17% | 87% | ~40% |
| same: ball speed median | 1.7 m/s | 0.9 m/s | – |
| same: a player within 1.5 m of the ball | 44% | 14% | – |

- **DFL freezes the ball where play stopped**: in all 698 DFL stoppages of 2 s+, the mid-stoppage
  ball sits within 1 m of the last live position and never moves; at the restart it jumps a median
  6.3 m to the restart spot. 96-97% of DFL dead frames have a perfectly still ball. A data
  convention, not football. Metrica has no ball at all in stoppages.
- **Ours moves**: in walking phases with the ball in view it is still only 17% of the time, moves
  at 0.7-4.1 m/s (quartiles), is near a player 44% of the time, in short visible runs (median
  1.6 s), often near a line: carried to a throw-in, rolled to a free kick.
- So v6 had never seen a stoppage with a moving ball. A stoppage our tracker shows with the ball
  moving looks like live play to it.

**A bonus: which ball-gap scenario is ours?** With the ball missing, our players move at 53% of
their typical pace. Damaged practice: "gaps at stoppages" 52%, "mixed" 73%, "random" 108%. Our
tracker's gaps behave like the stoppage scenario. Until now the kit treated gap placement as
unknowable without answers.

**Fix** (`possession/damage.py`, "dead ball"): in each practice stoppage the ball goes from where
play stopped to the nearest player (within 1 s), moves with that player for 30-90% of the stoppage,
travels to the restart spot at 3-10 m/s, and lies there until the restart. Drawn after every other
fault, so the rest of the damage is unchanged. Realism after the fix:

| Measure | Ours | Practice, damaged (after) |
|---|---|---|
| visible ball still for 2 s+ | 1.5% | 1.4% |
| walking phases, ball in view: still / speed median / player within 1.5 m | 17% / 1.72 m/s / 44% | 22% / 1.51 m/s / 52% |

(A first version with 20-70% carried gave 27% still; lengthened once, on our tracking's own
statistics, never on answers.)

**Result on practice** (`open_test.py`, seeds 0-1, models retrained on the corrected kit):

| Method | practice before the fix | after |
|---|---|---|
| v6 | 0.555 | 0.538 |
| v5 | 0.430 | 0.422 |
| v4 | 0.286 | 0.280 |
| organisers' baseline (real match 0.243) | 0.229 | 0.237 |

Practice got slightly harder, as it should, and the baseline now sits within 0.006 of its real
score: the practice test predicts reality better than before.

**On our match** (v6 retrained on the corrected kit; nothing tuned on our match):

| | v6 before | v6 after | public 5 min truth |
|---|---|---|---|
| dead-ball share in the public window | 10% | 15% | 20% |
| Smart Tagging agreement, attacking / defending | 76% / 84% | 79% / 86% | – |
| dead-ball share, whole match | 43% | 47% | – |
| possessions per minute | 2.66 | 2.46 | 3.40 (5 min) |

The public window moved towards its truth without being looked at during the fix, which supports
the diagnosis. The falling possession count is now the main open weakness (step 2).
