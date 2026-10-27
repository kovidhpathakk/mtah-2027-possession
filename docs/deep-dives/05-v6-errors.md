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

## Step 2: the ball in the air (`learned_test.py --air`)

Our tracking is flat. DFL measures the ball's height, so v6 (held-out models, damaged tracking,
true height) was scored by height:

| Ball (DFL, true height) | share of live play | v6 team call right | called dead |
|---|---|---|---|
| on the ground (< 0.5 m) | 71% | 91.8% | 4.8% |
| low, bouncing (0.5-2 m) | 12% | 77.8% | 6.7% |
| high (2 m+) | 17% | 82.4% | 5.6% |
| first 2 s after a high ball comes down | – | 74.1% | – |

About half of all team errors happen with the ball off the ground (29% of live play); the landing
(headers, second balls) is the weakest moment. On our match a 2D ball at 18 m/s+ is high 63% of the
time (DFL), the best stand-in for height we have. Ideas: a "probably in the air" clue trained on
DFL's height (M30); "where will it land and whose players are nearer" (reachability, Link &
Hoernig, M20). Clips of fast long balls for Kovidh: does the tracked ball follow a lofted ball?

## Step 3: why the possession count falls (`learned_test.py --possessions`, `--short`)

| True possession length | how many | v6 finds | v6 predicts | of those, real |
|---|---|---|---|---|
| under 2 s | 3,069 (30%) | 13% | 986 | 38% |
| 2-5 s | 3,087 (30%) | 41% | 2,055 | 60% |
| 5-10 s | 1,902 | 66% | 1,686 | 68% |
| 10-20 s | 1,302 | 79% | 1,449 | 79% |
| 20 s+ | 1,020 | 87% | 1,098 | 85% |

(IoU >= 0.5, same team; damaged practice, seed 0.) v6 finds ~47% of true possessions and ~66% of
its own are real: **recall is the bottleneck**, and it is lost on short possessions.

Inside each short true possession, does the team model favour the right team on average?

| | model favours the right team | v6 finds it |
|---|---|---|
| under 2 s | 48% | 13% |
| 2-5 s | 72% | 41% |
| ... first 3 s after a stoppage (under 2 s / 2-5 s) | 76% / 88% | 39% / 62% |
| ... a duel, under 2 s | 39% | 3% |
| ... ball missing, under 2 s / 2-5 s | 34% / 55% | 2% / 15% |

Two different problems. **2-5 s possessions and restarts: the model sees them, the decoder
smooths half of them away**: one fixed price per change of team is too blunt (a lower price
everywhere trades the gain for invented possessions: v5's sweep, 5 and 10 tie). Fix to try: a
**learned price**, from a model of "a change of possession happens here" (M25). **Under 2 s and
duels: the model does not see them** in tracking like ours; lower priority.
