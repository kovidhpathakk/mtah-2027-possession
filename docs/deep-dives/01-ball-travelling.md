# Deep dive 1: the team call while the ball is travelling

Status: in progress (started 2026-10-26). **v4 adopted** after steps 1-5; case review, Smart Tagging and clips for Kovidh still to do. Practice matches only (open data); nothing here uses
our match's answers.

## The problem

With the true team in live play, v3 would score 0.735 on the practice matches instead of 0.352
(oracle test). The team call is the biggest lever. Breaking v3's wrong team calls down by
situation (damaged practice matches):

| Situation | Share of live play | v3 wrong |
|---|---|---|
| ball visible, nobody within 1 m (passes, loose balls) | 59% | 16% |
| ball visible, someone within 1 m | 34% | 8% |
| ball missing | 7% | 28% |
| first 3 s after a stoppage | 9% | 23% |

## Step 1: anatomy (clean DFL, 7 matches)

At the 2,351 true live changes of possession:

| | |
|---|---|
| v3 makes the change within 5 s | 77% |
| v3 misses it | 23% (544) |
| v3 changes when nothing changed | 852 |
| matched changes within 3 frames / 0.5 s | 37% / 57% |
| matched changes > 1 s late / > 1 s early | 18% / 14% |
| the new team's nearest player at the true change: within 1 m / 1–2 m | 84% / 15% |

So the answers' definition is "a player of the new team gets the ball within about 1 m": v3's
rule is the right shape.

**Why v3 misses changes:** the new team touches the ball for under 3 frames (33%: a one-touch
pass counts as possession in the answers), never comes within 1 m (18%), a duel blocks it (11%),
other, mostly v3 calling a stoppage around the moment (38%). A third of missed possessions last
over 3 s.

**Why v3 invents changes:** a fast pass zips past an opponent within 1 m for 3 frames (ball speed
median 9.6 m/s at the false change). Two thirds of the invented possessions last over a second.

## Step 2: what the papers say

- Vidal-Codina et al. 2022: a gain of possession needs the ball to **change direction or speed**
  near the player; control sequences with neither are discarded.
- Link & Hoernig 2017: a **touch** is a sudden change in the ball's motion (an acceleration peak);
  possession ends when the player cannot reach the ball's predicted position.

## Step 2b: looking at real cases (`scripts/case_viewer.py`)

The practice matches have no video, so their tracking is the only view of the play.
`case_viewer.py` draws top-down snapshots (−2 s to +1 s) around a moment, zoomed on the ball
with a 1 m circle and each team's nearest distance; it refuses our match. Four random cases from
one clean DFL match:

| Case | What happens | Earlier guess right? |
|---|---|---|
| missed | a duel by the touchline: both teams on the ball, the away side wins it | no (guessed: one-touch pass) |
| missed | a quick interception: an away player meets a 9.5 m/s ball for a split second at 0.9 m | yes |
| invented | tight pressing: the home side keeps a slow ball while an away player hovers ~1 m away; v3 flips whenever he is a few cm closer | no (guessed: fast pass) |
| invented | a long pass (13–19 m/s) flies past an away player and v3 gives it to him | yes |

Three patterns, not two: (1) a fast pass flying past an opponent, (2) a quick one-touch
interception, (3) duels and tight pressing. The touch rule targets (1) and (2). (3) needs the
team in possession to keep the ball until the challenger is clearly on it **and** the holder
clearly away (e.g. over 2 m): "a duel does not change possession" applied firmly.

**Lesson for every dive: averages got two of four cases wrong; look at real cases before fixing.**

## Step 3: fix under test

`control_events_touch` in `possession/control.py`: control is gained by a **touch** (the ball's
velocity changes by ≥ dv m/s across ±3 frames right by one team's player, no opponent within
1 m), however brief, or by a **slow hold** (3+ frames within reach while the ball moves slower
than pass_by m/s). A ball passing by at unchanged speed never counts.

First look, 2 clean DFL matches:

| Setting | missed | invented | spellF1 |
|---|---|---|---|
| v3 (hold 3 frames) | 24% | 216 | 0.556 |
| touch dv 3, pass-by 8 | 15% | 260 | 0.623 |
| **touch dv 5, pass-by 6** | **17%** | **199** | **0.646** |

## Step 5: the damaged practice matches

Sweep (seed 0, all 8 matches × 3 damage scenarios; dv 3/5/7, pass-by 4/6/8, reach 1.0/1.5):

| Setting | practice | stoppage / mixed / random |
|---|---|---|
| v3 (hold 3 frames) | 0.353 | 0.430 / 0.340 / 0.287 |
| **touch dv 7, pass-by 6, reach 1.0** | **0.409** | **0.504 / 0.393 / 0.329** |
| next five settings | 0.399–0.406 | all above v3 in every scenario |

The gain survives tracking noise (+0.056) and is stable across neighbouring settings. Reach
1.5 m is worse than 1.0 m everywhere. The best dv sits at the edge of the grid, so the next sweep
tries 7/9/12, together with the duel rule for pattern 3 (`keep_through_duels`: a change counts only
if the holder's nearest player is at least `keep` m from the ball; keep 0/1.5/2/3).

Second sweep (pass-by 6, reach 1.0):

| dv | keep 0 (off) | keep 1.5 | keep 2.0 |
|---|---|---|---|
| 7 | **0.409** | 0.394 | 0.373 |
| 9 | 0.407 | 0.390 | 0.372 |
| 12 | 0.397 | 0.381 | 0.362 |

dv 7 stays best. **The duel rule hurts at every setting**: requiring the holder to be clearly away
also blocks real tackles, where the holder is still beside the ball when he loses it. One pressing
case did not represent the pattern. It stays off; pressing errors go back to the case review.
Candidate v4 = v3 + touch rule (dv 7, pass-by 6, reach 1.0).

## Step 6: fresh seeds and our match → v4

Fresh seeds 5 and 6, all 8 matches × 3 scenarios: **v4 better than v3 in 48/48 runs**, mean
0.352 → 0.410 (per match +0.026 to +0.089).

On our match (checks only, never tuned on): 365 possessions, 3.45 per minute against 3.40 in the
public truth (v3: 4.41); Smart Tagging team agreement 74/78% (v3 70/74%); quiz 0.431 (v3 0.357,
within the quiz's ~0.33 noise band but at the top of the public board). Valid and byte-identical
on rerun. **v4 is the new best model and this week's frozen submission candidate.**

Still to do in this dive: a larger case review of the remaining errors (including pressing), the
Smart Tagging test, and overlay clips of our match for Kovidh.

## Step 7: Smart Tagging where v4 is stale: no gain

**Why here.** v4's team errors grow with the time since it last saw a player gain control
(damaged practice, live frames):

| since last control | share of live play | v4 wrong |
|---|---|---|
| < 1 s | 52% | 9% |
| 1-2 s | 21% | 10% |
| 2-4 s | 14% | 16% |
| 4-8 s | 6% | 26% |
| 8-15 s | 3% | 36% |
| > 15 s | 4% | ~40% |

About a third of its team errors sit in stretches of 4 s or more without a control event, where
it only repeats its last call.

**Smart Tagging on our match** (counts only): attacking-phase tags cover 81% of v4's live frames;
phases last 12-30 s; v4 agrees with build-up 87%, progression 83%, long ball 71%, final third 70%,
box / chances / transitions 60-66%.

**Test.** `possession/tagging.py` builds imitation tags for the practice matches with the real
ones' shape (coverage, phase length, accuracy by zone, estimated from v4's agreement allowing for
v4's own error). Rule under test: where v4 has seen no control event for `stale` seconds and a tag
of a trusted kind covers the frame, the tag's team is used. Sweep: stale 2/4/8 s × kinds open /
open+final / all.

**Result.**

| Rule | practice |
|---|---|
| v4 | 0.409 |
| tags (open play) after 8 s | 0.409 |
| tags after 4 s | 0.400-0.407 |
| tags after 2 s | 0.347-0.386 |

No gain: a phase tag names one team for 12-30 s, so where it overrules v4 it also overwrites the
other team's short possessions inside the phase. Not adopted; re-test after step 8.

## Step 8: our tracker's ball is smoothed: the touch rule's gain was an artefact

Checking whether practice balls move like ours showed they do not: our ball's velocity changes by
>= 7 m/s within 0.24 s on 1.9% of graded live frames against 9-13% in clean DFL. Our tracker
smooths the ball over roughly 0.9 s, so kicks look gradual and the touch rule tuned at 7 m/s
fires 4-5× less often on our match. The fault kit now applies a 23-frame moving average (matching
our ball on three measures). Running: the practice test recalibrated against the published
baselines, and the touch rule re-tuned (dv 2-7 m/s, span 3/6/10 frames, pass-by 6/8).

**Result (realistic kit).** baseline 0.238 (real 0.243), v1 0.259, v2 0.271, **v3 0.291, v4 0.288**;
best re-tuned touch rule 0.297 (noise vs v3). The touch rule's gain came from practice balls being
sharper than ours. v4 stays the candidate on the strength of our match's checks (possession rate,
Smart Tagging agreement), with that caveat.

**What this changes for the dive.** On a ball smoothed over ~0.9 s, short-window rules cannot see
touches. Next, in order: (1) the anatomy and case review redone on the realistic kit; (2) models
trained on the practice matches (control classifier, possession model), which can use longer
context and player movement; (3) longer-window trajectory rules (did the ball's direction change
over ~1 s?) and receiver cues (the receiver slows and turns); (4) Link & Hoernig's
end-of-possession rule.

## Step 9: where points are lost now (realistic kit, v4)

| What-if | practice |
|---|---|
| v4 | 0.288 |
| v4 with the true stoppages | 0.380 (+0.09) |
| v4 with the true team in live play | 0.709 (+0.42) |

| Situation (live in truth and in v4) | share of live play | v4 wrong | share of team errors |
|---|---|---|---|
| ball travelling, nobody within 1 m | 66% | 21.2% | ~75% |
| ball at a player's feet | 27% | 9.9% | ~15% |
| ball missing | 7% | 29.6% | ~10% |
| first 3 s after a stoppage (overlaps) | 9% | 24.4% | – |

Stoppage frames: v4 misses 25.5% of true dead frames and calls 23.5% of true live frames dead
(frame shares, damaged practice).

The team call while the ball travels is three quarters of the team errors, and the team call is
worth four times the stoppages. This dive stays the priority; it now turns to trained models and
longer-window cues.
