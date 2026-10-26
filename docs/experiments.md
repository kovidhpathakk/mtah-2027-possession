# Experiment log

One row per experiment, newest first. Judge on the damage test and the sanity report, never on
the public 5 minutes alone, and treat spellF1 gaps under ~0.04 as noise.

| Date | Who | Branch | What changed | Public spellF1 / macroF1 | Damage-test spellF1 (mean ± spread) | Possessions (full match) | Mean length (s) | D share | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-26 | Claude | phase1-tools | **v3** = v2 stoppages + team by **control** (`possession/control.py`, Link & Hoernig 2017, Vidal-Codina 2022): a team gains the ball when its player holds it within 1 m for 3 frames with no opponent within 1 m; held through passes, loose balls and duels; no smoothing | 0.3565 / 0.6465 | – | 467 | 8.1 | 40% | Practice 0.377 vs v2 0.311; better in 48/48 match × scenario × seed runs on fresh seeds. Our match: fewer short possessions (10% vs 14%), Smart Tagging agreement 70/74% (truth 70/75%), quiz transF1 0.31 vs 0.21; quiz spellF1 0.357 vs 0.371 is within its noise |
| 2026-10-25 | Claude | phase1-tools | **v2** (`possession/stoppages.py`): clean-up; dead if ball > 1 m out, ball still ≥ 2 s, or a gap ≥ 1 s with slow players / at an edge / ≥ 20 s; tidy flicker; plain ±2 s vote | 0.3714 / 0.6602 | 0.277 (0.193–0.358) | 496 | 7.6 | 40% | Open-data test 0.388 / 0.298 / 0.250 vs v1 0.349 / 0.272 / 0.233; D share 42% vs truth 43%. Byte-identical on rerun |
| 2026-10-24 | Claude | phase1-tools | blackout_v1: long blackout = D, medium blackout D only if players slow (<1.0 m/s), otherwise hold the last team | 0.3619 / 0.5236 | 0.277 (0.190–0.354) | 510 | 8.4 | 32% | Better spellF1 on both tests, but predicts no D at all in the public window (truth 20%): its stoppages there are short or have the ball visible. macroF1 drops. Next: detect stoppages with the ball visible |
| 2026-10-23 | Claude | phase1-tools | Insurance: baseline smooth50 + match rules (X outside halves, D before 2nd-half kickoff) | 0.3256 / 0.6207 | 0.226 (0.148–0.316) | 584 | 7.2 | 34% | Uploaded as our safety entry |
| 2026-10-23 | — | main | Baseline smooth50, unchanged | 0.3256 / 0.6207 | 0.226 (0.148–0.316) | 594 | 7.2 | 32% | Reference. Full-match spellF1 0.2433 per EVALUATION.md |

## Findings

### 2026-10-26 · Harder, more honest practice damage

Added the two faults the kit lacked, at our match's measured rates: team-label swaps on 1.8% of
object-frames (4× likelier in a box) and the ball 5–15 m off on ~3.5% of visible frames.
Practice score (mean of stoppage / mixed / random):

| Method | practice | real full match |
|---|---|---|
| baseline | 0.248 | 0.243 |
| baseline_smooth25 | 0.233 | 0.200 |
| baseline_smooth125 | 0.190 | 0.224 |
| baseline_raw | 0.082 | 0.049 |
| blackout_v1 | 0.269 | – |
| v2 | 0.284 | – |
| **v3** | **0.352** | – |

The practice score of the published floor now sits within 0.005 of its real full-match score.


### 2026-10-26 · Commentary does not track possession

Transcript: 2,389 lines after the loop fix (98% distinct, 26% name a team or a one-team player).

- **Local LLM** (qwen3:4b, 2,112 lines labelled, 277 in failed batches): possession Barcelona
  35%, Athletic 4%, unclear 60%. Its team matches v2's team 48–55% across 0–10 s delays, against
  ~57% for always answering "Barcelona": chance. Its "stopped" matches v2's dead ball 55% vs a
  ~40% base rate: weak.
- **Player names alone** (no LLM): 605 lines name one side more (Barça 464, Athletic 141). Agreement
  with v3's team 55–58% at −4…+10 s, against a 52–54% chance level.
- Keyword events: stoppage words line up with v2 stoppages 57–69% vs 37% for "shot" (chance).

Conclusion: commentators do not describe who has the ball moment by moment, and talk about Barça
three times as often as Athletic. Commentary is parked as a possession clue; it may still mark
rare long stoppages (goals, injuries, VAR, substitutions) as a low-weight clue in the decoder.


### 2026-10-26 · v3: possession by control (Link & Hoernig, Vidal-Codina)

Sweep on the damaged practice matches (seed 0; 4 reach × 3 duel × 4 hold settings): best reach
1.0 m, duel 1.0 m, 3 frames = 0.377 (v2's vote 0.309); the next seven settings 0.350–0.370; the
worst 0.124. The winning distances are the papers' own. Check on fresh seeds 5 and 6:

| Match | v2 | v3 |
|---|---|---|
| metrica3 | 0.344 | 0.397 |
| dfl-J03WMX | 0.287 | 0.381 |
| dfl-J03WN1 | 0.300 | 0.374 |
| dfl-J03WOH | 0.321 | 0.392 |
| dfl-J03WOY | 0.286 | 0.378 |
| dfl-J03WPY | 0.330 | 0.371 |
| dfl-J03WQQ | 0.323 | 0.366 |
| dfl-J03WR9 | 0.300 | 0.360 |
| **mean** | **0.311** | **0.377** |

v3 is better in all 48 runs. The oracle ceiling for the team call is 0.72, so there is more to
gain here (ball in flight, the first touch after a restart, gaps).


### 2026-10-26 · Ball-gap rules, and where v2 loses its points

**Gap clues on the practice matches** (2,252 gaps, 3 damage scenarios): a gap whose ball comes
back within 3 m of where it vanished is 98% dead (3–8 m: 80%; 30 m+: 25%); team speed below 65%
of the match's typical speed is 98% dead, above 100% only 16%. v2's gap rule is right on 74% of
gaps (catches 91% of stoppages, keeps only 49% of live gaps live); adding "came back within 5 m
after 3 s+ → dead" and dropping the 20 s rule: 83% right (91% / 71%).

**But the practice score barely moves:** v2 0.312, v2_return 0.313, v2_return_nolong 0.311
(dead share falls to 38%). Gap calls are not where the points are.

**Where the points are** (oracle swaps, damaged practice matches, practice score):

| | score |
|---|---|
| v2 | 0.309 |
| v2 with the true stoppages | 0.396 |
| v2 with the true team in live play | **0.722** |
| both true | 1.000 |

The team call in live play (nearest player + ±2 s vote) costs about four times what the stoppage
calls cost. Next: possession logic from Link & Hoernig 2017 (backlog M7). v2 stays unchanged;
`near_return` stays as an option (`v2_return`).


### 2026-10-25 · v2: stoppages from ball position and play speed

Clues measured on the open-data matches first (`possession/stoppages.py` docstring has the
numbers): ball visible and still ≥ 2 s catches 96% of dead frames at 0.6% false alarms; ball
> 1 m beyond a line is 99% dead; a ball gap with slow players is 98–99% dead; a gap that starts
or ends at an edge is 79–100% dead.

| Method | clean | stoppage | mixed | random | D share |
|---|---|---|---|---|---|
| blackout_v1 | 0.320 | 0.349 | 0.272 | 0.233 | 35% |
| v2_gaps_only | 0.327 | 0.380 | 0.285 | 0.234 | 40% |
| **v2** | **0.451** | **0.388** | **0.298** | **0.250** | **42%** |
| v2_live_vote | 0.435 | 0.385 | 0.295 | 0.247 | 42% |

- The "out" rule first created ~2,000 fake sub-second possessions per match: a ball lying near
  a line flickers in and out. A tidy-up (live islands < 2 s inside a stoppage become dead; dead
  blips < 0.5 s become live) fixed it.
- The fault kit's ball noise was per-frame jitter, which made a still ball look like it moves at
  ~4 m/s. It now drifts smoothly (same 0.3 m size); calibration against the published baselines
  is unchanged. The "still" rule still adds nothing on damaged data, only on clean data (0.346 →
  0.451): our tracker removes most dead balls, so its value on our match is uncertain.
- Stopping the vote at stoppages scored slightly worse everywhere; v2 uses the plain vote.
- On our match: D 40% (v1 32%), possessions 496, 92% of tagged set pieces contain D (v1 71%),
  public 0.371 (v1 0.362), macroF1 0.660 (v1 0.524).


### 2026-10-25 · Video audit (detector run locally, 420 frames)

- Detector confirms 94% of ordinary tracked objects, 6% of the box ghost (not a person), 99% of
  touchline tracks (real people). On "fewer than 18" frames it sees ~3.6 more untracked people.
- A ball is visible on the pitch in ~2/3 of the tracker's ball-gap frames: the tracker drops a
  visible ball, so gaps are mostly stoppages, not occlusions.
- Tracker disagreements: tactical's ball is right about twice as often as broadcast's.


### 2026-10-25 · The ghost explained; clean-up does not move the score

- The ghost in Barça's box is the Athletic keeper's track **frozen** (position unchanged to the
  millimetre) for 9.7 minutes across half-time, at the spot he stood in the 1st half; after the
  teams swap ends that spot is in front of Barça's goal. Our match has only 4 frozen stretches of
  10 s or more, all leftovers like this.
- `possession/cleanup.py` drops frozen objects and a team's extras (duplicates, touchline);
  12+ frames fall from 8.1%/4.7% to 4.1%/2.5%. The rest are neither duplicates nor touchline.
- `blackout_v1_clean` vs `blackout_v1` on the open-data test: 0.345 vs 0.347 (stoppage),
  0.274 vs 0.276 (mixed), 0.224 vs 0.225 (random): no change. These objects rarely stand next
  to the ball. Keep the clean-up (it is correct and cheap), but the score is in dead-ball calls.


### 2026-10-25 · The open-data test (8 matches, our tracker's faults added)

`python scripts/open_test.py`. spellF1, mean over 8 matches × 3 seeds:

| Method | clean | stoppage | mixed | random | D share | real match |
|---|---|---|---|---|---|---|
| baseline | 0.316 | 0.316 | 0.251 | 0.212 | 36% | 0.243 |
| baseline_smooth25 | 0.301 | 0.311 | 0.245 | 0.204 | 39% | 0.200 |
| baseline_smooth125 | 0.228 | 0.217 | 0.190 | 0.174 | 27% | 0.224 |
| baseline_raw | 0.097 | 0.062 | 0.050 | 0.041 | 43% | 0.049 |
| blackout_v1 | 0.320 | 0.347 | 0.276 | 0.225 | 35% | – |
| truth | | | | | 43% | |

- **Calibration:** every scenario picks the right best baseline (the old 5-minute test picked
  smooth125). "Mixed" and "random" sit closest to the real full-match scores; "stoppage" is too
  kind. None reproduces smooth125 > smooth25 exactly. Judge new methods on all three.
- blackout_v1 beats the baseline in every scenario, by 0.01–0.03: real but small.
- Every method calls too little dead ball (27–39% vs 43%).
- This replaces the public-window damage test for choosing between methods.


### 2026-10-25 · Open data loaded; control audit on 8 clean matches

- DFL (7) and Metrica Game 3 load into our arrays with an H/A/D label per frame. DFL's dead-ball
  share is 41–52%: our v1 (32%) and the baselines likely call too little D.
- Run on clean data, the audit confirms our extra objects, missing players, touchline tracks,
  box ghost and speed-column lag as real, and shows the "filled-in player paths" finding was
  mostly the test's own false-alarm rate.


### 2026-10-25 · Confirmation with the broadcast tracker as a second witness

- **Corrected:** the "keeper mix-up" is a motionless ghost reusing the Athletic keeper's track
  ID, not Barça's keeper labelled Athletic. Both keepers are labelled correctly. Fix: drop
  motionless objects, do not relabel the deepest object.
- Touchline tracks never end up nearest the ball; the referee is not tracked as a player.
- The two trackers agree on team labels 98% (95% in boxes) and on clear control 97%: the
  yardstick behind the Smart Tagging numbers holds.
- New: their balls are > 5 m apart on 10.5% of frames where both have one.
- Still open: why no 1–5 s ball gaps; half of the "12+ objects" frames.


### 2026-10-25 · Data audit: tracking, Smart Tagging, broadcast alignment

Full numbers in docs/research.md §7. The ones that change what we build:

- The tactical tracker fills in ball gaps under ~5 s itself (only 1 gap of 1–5 s, against 119 on
  the broadcast tracker). Every surviving gap is ≥ 5 s, and there are 132 of them: roughly a
  match's worth of restarts. v1's "medium gap is dead only if players are slow" is probably too
  strict; the restart detector should decide instead.
- Ball speed column: unusable. Player speed column: correct but 7 frames late.
- Keeper mix-up in Barça's box: ~3,400 frames, mostly 2nd half. Touchline tracks labelled as
  players: 33 of 10 s or more.
- Smart Tagging covers only 42 of the 132 long gaps with a set-piece tag, and its set-piece
  windows are a fixed 35 s. Team tags are reliable in open play (87–89%), weak near the box (~60%).
- Broadcast aligned to tactical from the tracking alone (ball and players agree to a frame).
  Audio cross-correlation is too weak to align with.


### 2026-10-23 · Is the damage test honest? Calibrated against the four published baselines

| Baseline | Public 5 min | Damage test (100 runs) | Real full match |
|---|---|---|---|
| raw | 0.038 | 0.037 | 0.049 |
| smooth25 (±1 s) | 0.287 | 0.201 | 0.200 |
| smooth50 (±2 s) | 0.326 | 0.226 | 0.243 |
| smooth125 (±5 s) | 0.424 | 0.302 | 0.224 |

Much closer to reality than the raw window for three of four, but it still over-rewards heavy
smoothing (smooth125). Likely cause: the public 5 minutes have long, calm possessions, which suit
sluggish models, and damaging the ball cannot change the football in them. **Use the damage test
for robustness to ball blackouts. Do not use it to choose how stable or sluggish a model is**;
check that on the full match with the sanity report. Spreads are wide (±0.08): small gaps mean
nothing.

### 2026-10-23 · Sanity report on the baselines

- The truth agrees with Smart Tagging only ~70% (attacking phases) / 75% (defending). That is the
  realistic ceiling for this check, not 100%.
- Baselines call 32–41% D over the full match against ~20% in the public truth, because they
  write D on every missing-ball frame. **Corrected 2026-10-24:** the 20% comes from 5 calm
  minutes; the full match has goals, a hydration break and the end of the 1st half, so its real
  D share is probably higher. The baselines' D share is not necessarily too high; the problem is
  *which* frames they call D (see the gap findings below).
- In the public window, during ball gaps the truth is ~56% D, ~44% A, ~1% H (small sample).

### 2026-10-23 · Gap clips

The 15 longest blackouts cover 1,007 s, 39% of all missing-ball time. Watching them (~17 min)
tells us what a large share of the problem is.

### 2026-10-24 · What the ball blackouts are

Watching the longest clips showed one dominant pattern: **the tracker drops the ball when play
stops, even when the ball is plainly visible** (on the spot, in a player's hands), and picks it
up again when play restarts. The long blackouts were stoppages: goals and the wait for kickoff,
fouls and free kicks, a penalty, a drinks break, the end of a half, goal kicks, corners. A few
were real occlusions in live play, and some long ones contain live play inside them (a corner
delivered and fought over before the ball reappears).

Checked against data we are allowed to measure:

| | |
|---|---|
| Gaps > 20 s | 44 gaps, 67% of all missing-ball time |
| Mean player speed: ball visible / gaps > 20 s / gaps ≤ 20 s | 2.16 / 0.99 / 1.53 m/s |
| Gaps ending within 5 s of a tagged set piece: > 20 s vs shorter | 25% vs 5–9% |
| Public truth inside the 4 gaps of 5–15 s | 2 fully live (A), 1 mostly D, 1 fully D |

**Update after web research (docs/football-notes.md):** ball-in-play in LaLiga is ~54–56 min, so
dead ball is probably ~40–45% of graded frames, not ~20%. The baselines' and v1's 32–34% D is
likely too LOW. Restarts take ~12–27 s on average, so many medium blackouts are probably
restarts; v1's "medium blackout is dead only if players are slow" is likely too strict.

**Ball speed (2026-10-24):** the tracker's ball-speed field is filled on only 8.7% of visible
frames, so compute it from position changes. On visible-ball frames of the public window: live
ball median 6.2 m/s, team 2.32 m/s; dead ball 2.7 m/s, team 1.22 m/s. "Ball < 2 m/s and team
< 1.3 m/s" catches ~22% of visible dead frames at 0.2% false alarms. A real signal but not
enough on its own; combine it with ball position and tags.

Working rule for Phase 2: **long blackout + slow players ≈ stoppage**; medium blackouts are
mixed and need player movement to decide; short ones are usually live play. Edges matter: a
blackout often starts at the moment play stops and ends at the restart, but sometimes ends while
the restart is still being prepared, and long ones can hide live play.
