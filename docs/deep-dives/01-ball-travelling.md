# Deep dive 1: the team call while the ball is travelling

Status: in progress (started 2026-10-26). Practice matches only (open data); nothing here uses
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

Next: a sweep on the **damaged** practice matches (tracking noise can fake velocity changes),
then fresh seeds, then our match's sanity checks.
