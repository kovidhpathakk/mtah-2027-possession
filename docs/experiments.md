# Experiment log

One row per experiment, newest first. Judge on the damage test and the sanity report, never on
the public 5 minutes alone, and treat spellF1 gaps under ~0.04 as noise.

| Date | Who | Branch | What changed | Public spellF1 / macroF1 | Damage-test spellF1 (mean ± spread) | Possessions (full match) | Mean length (s) | D share | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-26 | Claude | phase1-tools | **v5** = v4's stoppages + **learned team call** (`possession/learned.py`, M15): 59 clues per frame (near, before/after, control events, ball, team shape), gradient-boosted trees trained on the 8 damaged practice matches (both teams' views), Viterbi decoding with switch cost 10 | 0.6065 / 0.7074 | 0.440 (0.282–0.556), v4 0.329 (0.222–0.432), 30 runs | 299 | 12.7 | 40% | Practice (realistic kit, fresh seeds) **0.430 vs v4 0.279**; better in 48/48 paired runs (sweep seeds). Team right on live frames 89.5% vs 81.0%. Our match: Smart Tagging agreement 76/82% (v4 74/78%), possessions <1 s 3% (v4 11%), 2.82 possessions/min (v4 3.45; public truth 3.40); model as confident as on practice (0.90). Valid; byte-identical on rerun and after retraining from nothing |
| 2026-10-26 | Claude | phase1-tools | **v4** = v3 + touch rule (deep dive 1): control gained by a touch (ball velocity changes ≥ 7 m/s by one team's player, no opponent within 1 m) or a slow hold (3+ frames within 1 m, ball under 6 m/s); a ball passing by never counts | 0.4308 / 0.6652 | – | 365 | 10.4 | 40% | Practice (harder kit) 0.410 vs v3 0.352; better in 48/48 runs on fresh seeds. Our match: 3.45 possessions/min (public truth 3.40), Smart Tagging agreement 74/78%. Quiz 0.431 (top of the public board; noise band ~0.33). Valid, byte-identical on rerun |
| 2026-10-26 | Claude | phase1-tools | **v3** = v2 stoppages + team by **control** (`possession/control.py`, Link & Hoernig 2017, Vidal-Codina 2022): a team gains the ball when its player holds it within 1 m for 3 frames with no opponent within 1 m; held through passes, loose balls and duels; no smoothing | 0.3565 / 0.6465 | – | 467 | 8.1 | 40% | Practice 0.377 vs v2 0.311; better in 48/48 match × scenario × seed runs on fresh seeds. Our match: fewer short possessions (10% vs 14%), Smart Tagging agreement 70/74% (truth 70/75%), quiz transF1 0.31 vs 0.21; quiz spellF1 0.357 vs 0.371 is within its noise |
| 2026-10-25 | Claude | phase1-tools | **v2** (`possession/stoppages.py`): clean-up; dead if ball > 1 m out, ball still ≥ 2 s, or a gap ≥ 1 s with slow players / at an edge / ≥ 20 s; tidy flicker; plain ±2 s vote | 0.3714 / 0.6602 | 0.277 (0.193–0.358) | 496 | 7.6 | 40% | Open-data test 0.388 / 0.298 / 0.250 vs v1 0.349 / 0.272 / 0.233; D share 42% vs truth 43%. Byte-identical on rerun |
| 2026-10-24 | Claude | phase1-tools | blackout_v1: long blackout = D, medium blackout D only if players slow (<1.0 m/s), otherwise hold the last team | 0.3619 / 0.5236 | 0.277 (0.190–0.354) | 510 | 8.4 | 32% | Better spellF1 on both tests, but predicts no D at all in the public window (truth 20%): its stoppages there are short or have the ball visible. macroF1 drops. Next: detect stoppages with the ball visible |
| 2026-10-23 | Claude | phase1-tools | Insurance: baseline smooth50 + match rules (X outside halves, D before 2nd-half kickoff) | 0.3256 / 0.6207 | 0.226 (0.148–0.316) | 584 | 7.2 | 34% | Uploaded as our safety entry |
| 2026-10-23 | — | main | Baseline smooth50, unchanged | 0.3256 / 0.6207 | 0.226 (0.148–0.316) | 594 | 7.2 | 32% | Reference. Full-match spellF1 0.2433 per EVALUATION.md |

## Findings

### 2026-10-26 · v5: the team call learned from the practice matches (deep dive 1, M15)

`possession/learned.py`, `scripts/learned_test.py`. Stoppages stay v4's; the team in live play is
learned. Training: the 8 practice matches, each damaged under the three ball-gap scenarios (damage
seed 100), every 5th frame live in v4 and in the answers, both teams' views: ~620,000 rows.
scikit-learn HistGradientBoostingClassifier (200 trees, 31 leaves, learning rate 0.1, L2 1.0, no
early stopping, random_state 0). Leave one match out: each practice match is labelled by the model
trained on the other seven.

**Sweep** (test seeds 0-1; v4 0.286 on the same copies):

| Decoding | practice | stoppage | mixed | random | beats v4 |
|---|---|---|---|---|---|
| per-frame likelier team (no decoding) | 0.279 | 0.343 | 0.270 | 0.224 | 21/48 |
| Viterbi, switch cost 5 | 0.431 | 0.533 | 0.418 | 0.344 | 48/48 |
| switch cost 10 | 0.430 | 0.531 | 0.417 | 0.341 | 48/48 |
| switch cost 20 | 0.419 | 0.523 | 0.406 | 0.329 | 48/48 |
| switch cost 40 | 0.386 | 0.482 | 0.372 | 0.304 | 48/48 |
| switch cost 80 | 0.336 | 0.420 | 0.324 | 0.263 | 45/48 |

Without decoding the better frame accuracy is wasted on flicker; switch cost 10 picked (5 ties).

**Fresh seeds 2-3** (`open_test.py --first-seed 2`): v5 0.430, v5_switch5 0.431, v5_switch20 0.415,
v4 0.279, v3 0.279, baseline 0.229 (real 0.243). Clean (undamaged) tracking: v5 0.668 vs v4 0.658,
so the gain is in coping with our tracker's faults.

**Team right on live frames** (live in the answers and v4):

| Situation | share | v4 | v5 |
|---|---|---|---|
| ball travelling, nobody within 1 m | 66% | 78.4% | 88.5% |
| ball at a player's feet | 26% | 90.5% | 93.5% |
| ball missing | 7% | 71.1% | 84.2% |
| all | | 81.0% | 89.5% |

**What the model leans on** (`--importance`: shuffle one family, accuracy drop): team shape 17.1
points, ball 5.4, before/after 2.4, control events 2.1, near 0.3. The arrangement of the two teams
(who pushes up and spreads, who drops goal-side of the ball) is the strongest clue; it survives a
smoothed or missing ball.

**Possession counts.** Practice: truth 4.53 per minute, v4 3.54, v5 3.37 (switch 5: 3.76; 3: 4.06).
Our match: v5 2.82 vs v4 3.45; damage test window 10.8 vs truth 17 (v4 15.0). v5 merges some short
possessions; on practice that costs less than v4's flicker. Next to study.

**The quiz.** Public 5 minutes 0.607 (v4 0.431), but `run_evaluation.py --bootstrap 1000` puts the
noise band for 17 possessions at ~0.37, and the window is easy: ball missing 12% as delivered vs 41%
over the match. With the ball deleted to the match's rate (damage test) v5 averages 0.440.

**Transfer to our match.** Mean confidence max(p, 1-p) on our match's live frames 0.904, unsure
(0.3-0.7) 11%: the same as on practice (0.88-0.91, 11-16%).

**Where the points are now** (`--oracle`, damage seed 2):

| What-if | practice | possessions/min |
|---|---|---|
| v5 | 0.429 | 3.37 |
| v5 + true stoppages (team decoded within the true live stretches) | 0.601 (+0.17) | 3.15 |
| v5's stoppages + true team in live play | 0.719 (+0.29) | 4.57 |
| truth | 1.000 | 4.53 |

With v4's team call, perfect stoppages were worth +0.09; on top of v5 they are worth +0.17. The
missing possessions are a team-call matter (true team gives 4.57 a minute, true stoppages 3.15).

**Reproducible.** Two fits on the same rows give identical probabilities; `run.py --method v5`
from an empty cache (rows and model retrained, 1 min 50 s) gives the same bytes as from the cache.


### 2026-10-26 · Track T pilot 3: WASB ball tracker on the tactical video

`scripts/wasb_pilot.py`: WASB (BMVC 2023) soccer weights (trained on ISSIA-CNR fixed wide cameras),
three frames at a time, ~1.1 s per three-frame step on the CPU.

| Setting | A: ball within 2 m of the provided one | B: ball found in live gaps |
|---|---|---|
| whole frame (512×288) | 0% | 1% |
| 960×540 window, threshold 0.5 | 28% | 9% |
| 640×360 window, threshold 0.5 / 0.3 / 0.15 (40 frames) | 40% / 50% / **60%** | – |
| 1280×720 window, threshold 0.15 | 20% | – |
| (Roboflow YOLOv8, whole frame / 480×270 window) | 50% / 55% | 72% (mostly doubtful) |

Zooming in and lowering the threshold help; the best setting finds the ball within 2 m about 60% of
the time (lower thresholds also add false detections, not counted here). Smoothing check (crop,
threshold 0.5): ball detected on only 26% of consecutive frames; inconclusive.

**Track T verdict so far:** off-the-shelf ball models reach 50-60% on our wide camera; a ball track
of our own needs ~90%. Parked as a main route. Still open: fusion of all ball sources where a
detector is confident (T12), fine-tuning on public wide-camera data (T14), self-training with
algorithm-made labels on our video (T15, organisers' answer needed).


### 2026-10-26 · Track T pilot 2: the same ball detector on the broadcast video

`scripts/ball_pilot_broadcast.py`, broadcast frames showing live play, mapped to tactical frames
(alignment) and to the pitch (broadcast homography), 1.7 s per frame:

| Test | Broadcast | Tactical (pilot 1) |
|---|---|---|
| A. a detection within 2 m of the provided ball / most confident detection is it | 51% / **51%** | 50% / 32% |
| B. tactical live gaps shown live on the broadcast | 4,084 frames (~half of the 8,011) | – |
| B. a ball detected there / with confidence ≥ 0.5 | **80% / 57%** (median 13.6 m from last seen) | 72% / 31% |
| C. sharp velocity changes (≥ 7 m/s in 0.24 s), detected vs provided ball, around control moments | **9% vs 4%**; p90 6.4 vs 3.9 m/s | 7% vs 11% |

The broadcast's larger ball makes the detector's best guess right more often and finds a ball in
most tactical gaps, and the detected ball is sharper than the provided one around control moments
(weak support for A3: detector jitter also adds sharpness). But within 2 m it still matches the
provided ball only half the time (the broadcast homography is less exact for a zoomed, moving
camera). Not yet reliable enough for our own track; WASB (plan T9) is the next candidate.


### 2026-10-26 · Track T pilot: an off-the-shelf ball detector cannot rebuild the ball track

Roboflow "sports" ball detector (YOLOv8x, trained on DFL Bundesliga Data Shootout footage; approved
by Kovidh, scanned before loading), CPU, 1.6 s per frame (`scripts/ball_pilot.py`):

| Test | Result |
|---|---|
| A. 80 live frames with a provided ball: a detection within 2 m / the most confident detection is the ball | 50% / 32% |
| A with a 480×270 crop around the expected ball, enlarged (40 frames) | 55% / 50% |
| A with a 320×180 crop | 18% / 15% |
| B. 80 live frames without a provided ball: something detected on the pitch / with confidence ≥ 0.5 | 72% / 31%, median 14 m from where the ball was last seen |
| C. 6 runs of 50 consecutive frames around control moments: sharp velocity changes, detected vs provided | 7% vs 11% (detected on 72% of frames) |

On the wide tactical view the ball is a few pixels across and the model (trained on broadcast-style
footage) finds it about half the time. Not enough to build our own track. Test C cannot settle
whether the provided ball is smoothed: kicks blur the ball, which is when detection fails; A3 stays
unconfirmed (the realistic kit is justified by the realism report either way). Track T parked; the
broadcast video (ball several times larger) remains an option if disk space allows a re-download.


### 2026-10-26 · Realism report: practice data now matches ours on 17 of 18 measures

`scripts/realism_report.py` compares our match with the 8 practice matches (clean and damaged,
mixed scenario) on 18 measures. First run flagged frames with fewer than 18 tracked people: ours
9.4%, damaged practice 0.6%. In our match these are 56 episodes per match (median 2 s, some over
30 s; median 14 people tracked, sometimes 4), 86% of them while the ball is missing (88% in v4's
stoppages): celebrations, substitutions, players leaving the camera. The kit now copies these
episodes; damaged practice gives 7.7%. Remaining flag: ball gaps of 1-5 s per hour (ours 0.6,
practice 1.1; one gap in our whole match). Also visible: the ball is a little further from the
nearest player in damaged practice (median 2.4 m vs 1.8 m; within 1 m 23% vs 29%).

Practice scores after the fix (stable within 0.002): baseline 0.237 (real 0.243), smooth25 0.219,
smooth125 0.186, raw 0.086, v1 0.257, v2 0.271, v3 0.290, v4 0.286.


### 2026-10-26 · Realistic (smoothed) practice ball: the touch rule's gain disappears

Practice test with the fault kit's 23-frame ball smoothing (mean over 8 matches × 3 scenarios):

| Method | old kit (ball too sharp) | **realistic kit** | real full match |
|---|---|---|---|
| baseline | 0.248 | **0.238** | 0.243 |
| baseline_smooth25 | 0.233 | 0.219 | 0.200 |
| baseline_smooth125 | 0.190 | 0.187 | 0.224 |
| baseline_raw | 0.082 | 0.086 | 0.049 |
| blackout_v1 | 0.269 | 0.259 | – |
| v2 | 0.284 | 0.271 | – |
| v3 | 0.352 | **0.291** | – |
| v4 | 0.410 | **0.288** | – |

Touch rule re-tuned on the realistic kit (dv 2-7 m/s × span 3/6/10 × pass-by 6/8): best 0.297
(dv 7, span 3, pass-by 8) vs v3 0.290: noise. **v4's practice gain was mostly an artefact of
practice balls that were sharper than ours.** On a ball smoothed like ours a kick looks gradual
and short-window touch detection has little to find. v3 and v4 are level on practice; v4 is
better on our match's checks (3.45 possessions/min vs truth 3.40, v3 4.41; Smart Tagging 74/78%
vs 70/74%; quiz 0.431 vs 0.357), so v4 stays the frozen candidate. The baseline's practice score
(0.238) is now within 0.005 of its real score: this is the most trustworthy test so far, and it
puts our realistic expectation at ~0.29.


### 2026-10-26 · Our tracker's ball is heavily smoothed; the fault kit now copies it

In graded live play our ball's velocity changes by >= 7 m/s within 0.24 s on 1.9% of frames
(clean DFL 9-13%, damaged practice 8-11%), by >= 3 m/s on 23%, 90th percentile 4.3 m/s. A
23-frame moving average makes damaged practice balls match (2.3-2.4%, 21-25%, 4.3-4.4 m/s; 19 too
rough, 27 too smooth). Consequence: the touch rule tuned at 7 m/s fires 4-5× less often on our
match than on practice data. The kit now smooths; practice recalibration and a touch-rule re-tune
are running. (A first measurement over all 199,319 frames gave 8.7%: warm-up and half-time, when
balls are knocked about, inflated it; graded frames only from now on.)

### 2026-10-26 · Smart Tagging as a team clue where v4 is stale: no gain

Imitation tags on the damaged practice matches (coverage 81%, phases 12-30 s, accuracy by zone
estimated from v4's agreement with the real tags): deferring to a tag after 8 s without a control
event 0.409 (v4 0.409); after 4 s 0.400-0.407; after 2 s 0.347-0.386. Tags span several
possessions, so where they overrule v4 they also overwrite the other team's short possessions.
Not adopted; to re-test once the touch rule is re-tuned on the smoothed kit.


### 2026-10-26 · Vision pilot 2 could not run: the laptop's 8 GB is the limit

Qwen3-VL 4B (3.3 GB on disk, 4.1 GB loaded) fitted only 71% on the GPU with the usual apps open;
the machine swapped (3.9 GB swap, 56 MB free) and one cropped image got no answer within 10
minutes. Thinking was also left on. Options: Qwen3-VL 2B (~1.9 GB), the 4B with every other app
closed, smaller images and context, football-trained detectors (far lighter than a vision-language
model), or a rented GPU (needs the organisers' OK). The pilot script now turns thinking off,
uses a small context and counts timeouts instead of crashing.


### 2026-10-26 · Vision pilot: a small model cannot read the wide tactical view

`scripts/vision_pilot.py`, qwen2.5vl:3b via Ollama, 30 frames (10 per group), 26 s per frame:

| v3's call | model says "stopped" | sees the ball | ball in the air |
|---|---|---|---|
| dead | 100% | 20% | 0% |
| live, ball at feet | 100% | 70% | 0% |
| live, ball missing | 100% | 0% | 0% |

It calls every frame stopped. In the wide tactical view players are a few pixels tall; one still
frame cannot show movement. Next pilot: crops around the action (tracking + homography give where),
2-3 frames about a second apart, Qwen3-VL 4B; broadcast close-ups if re-downloaded.


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

Full numbers in docs/data.md (Data audit). The ones that change what we build:

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

**Update after web research (docs/sources.md, published football facts):** ball-in-play in LaLiga is ~54–56 min, so
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
