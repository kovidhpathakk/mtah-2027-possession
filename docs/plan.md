# Plan: what's next, every idea with its status

One row per idea we have had. **Check this before choosing the next step.** New ideas are added
the moment they come up. Rows are never deleted: an idea we decide against is marked `dropped`
with the reason.

Status: `done` · `now` · `next` (in order) · `planned` · `parked` (decided to wait) · `dropped`

Last updated: 2026-10-26.

## Data use: every asset, how it is used, what is untried

Kept so no source is quietly forgotten (Smart Tagging went unused until 2026-10-26).

| Asset | Used in the model today (v6) | Used elsewhere | Untried |
|---|---|---|---|
| Tactical tracking | ✅ the only input: 59 team clues + 35 stoppage clues | audits; realism report | per-player clues (receiver's speed and turn); 20-80 s windows (Lang 2022) |
| Tactical homography | ❌ | video audit and ball pilots (pitch ↔ pixels) | mapping video detections into the model |
| **Smart Tagging** | ❌ not in the model | audited; checks (agreement 76/84%, set-piece windows with D 95%); team-tag override tested: no gain | **clues for both models** (team phases; set-piece windows → stoppages and restarts), tested with imitation tags (M8c, M9) |
| Tactical video | ❌ | detector audit; three ball-detector pilots (50-60% within 2 m: not enough for our own ball track) | ball fusion where a detector is confident (T12); player re-detection and shirt colours (T10) |
| Tactical audio | ❌ | alignment test only | **whistles** (S4), crowd noise (S5) |
| Broadcast tracking | ❌ (ball fill tested, neutral) | alignment, audits, second witness | its ball in live-play gaps as a clue (dive 3) |
| Broadcast homography | ❌ | broadcast ball pilot | – |
| Broadcast video | ❌ (re-downloaded, 164,487 frames, aligned to tactical) | ball pilot (T6) | **camera behaviour as a stoppage clue**: close-ups, crowd shots and replays come when play stops (S6, S8) |
| Broadcast audio / commentary | ❌ | transcript; keyword events; LLM labels (weak) | rare long stoppages (S3c); event-focused pass (S3e) |
| Public 5-minute answers | sanity check only (never tuned on) | – | – |
| Open data (DFL ×7, Metrica Game 3) | ✅ training and testing both models (leave one match out) | realism report; case drawings | – |
| More open data | – | – | **Metrica Games 1-2 as a sealed exam** (E1); SkillCorner's 9 broadcast-tracking matches with per-frame ball owner (E2) |

## Roadmap (rewritten 2026-10-26)

**Principles.** Make the practice test honest first (everything is judged on it). One problem at
a time, ordered by points at stake: perfect team calls in live play are worth up to +0.36 on
practice, perfect stoppages +0.08. In each deep dive, try **every** relevant source and
technique (tracking rules, the papers, models trained on the 8 practice matches, Smart Tagging,
tactical and broadcast video, audio, commentary), look at real cases before fixing, test on fresh
seeds, then check on our match. One heavy job at a time. A weekly freeze keeps a validated
submission of the best model.

**Each deep dive:** (1) anatomy of the errors, (2) real cases (practice: top-down drawings;
our match: overlay clips Kovidh watches), (3) the research, (4) fixes from every source below,
(5) practice test with fresh seeds, then our match's checks, (6) write-up in `docs/deep-dives/`.

### Track T: improve the tracking data itself (from 2026-10-26)

RULES.md: "Improving that data, or replacing it with your own, is entirely legitimate." The touch
rule worked on a sharp ball (+0.06 on practice) and failed only because the provided ball path is
smoothed; a ball track of our own from the video could be sharp, and could fill gaps.

| Step | Experiment | Rows | Status |
|---|---|---|---|
| T0 | **Realism report**: our match vs damaged practice on every measure, flagging gaps | P1d | ✅ 17 of 18 measures within 1.5× after copying missing-player episodes |
| T1 | Football-trained detector pilot | V9, T1, V17 | ✅ done: **not good enough** on the wide view (ball within 2 m on 50% of frames; 55% with a zoomed crop); smoothing check inconclusive |
| T2 | **Confirm the smoothing from the video**: detector on runs of consecutive frames around kicks; compare the real ball's speed changes with the recorded ones | V17 | with T1 |
| T3 | Our own ball track from the video | T3 | **parked**: three off-the-shelf detectors reach 50-60% within 2 m (T1 Roboflow tactical, T6 Roboflow broadcast, T9 WASB); ~90% is needed. Reopens only if T14/T15 produce a much better detector |
| T4 | v4's touch rule and the trained models on our own ball track | T4 | after T3 |
| T5 | Player re-detection (missing players), team labels from shirt colours | V8, V15 | later |
| T6 | Broadcast pilot: the same ball detector on the zoomed-in broadcast video, mapped to tactical time | T6 | ✅ done: best guess right 51% (tactical 32%); a ball in 80% of tactical gaps shown live (57% confident); detected ball sharper than the provided one (9% vs 4%). Still ~50% within 2 m: not reliable enough alone |
| T7 | Fine-tune a ball detector on **public wide-angle football footage** with labelled balls (e.g. fixed-camera research datasets), possibly on a free cloud GPU since only public data goes there. **Never on our match's video with the provided tracking as labels**: the organisers refused exactly that (issue #2) | T7 | planned, if T6 is not enough |
| T8 | A vision-language model (Qwen-VL) for tracking | – | dropped: good at describing scenes, imprecise at positions and far too slow for 25 frames a second; detectors are the right tool |
| T9 | WASB ball tracker (BMVC 2023; soccer weights from fixed wide cameras) | T9 | ✅ done: best 60% within 2 m (640×360 window, threshold 0.15); whole frame 0%. Better than Roboflow (50-55%), not enough for our own track (~90% needed) |
| T10 | Player detection + multi-object tracker (ByteTrack / BoT-SORT) + teams from shirt colours (Roboflow "sports" pipeline): fill missing players, check team labels | T10 | planned (player model already downloaded) |
| T11 | SAM 2 video tracking seeded with the provided ball positions, to bridge short gaps | T11 | planned, low priority (heavy on CPU) |
| T12 | **Ball fusion** (best remaining track T route): combine the provided tactical ball, the broadcast tracker's ball and video detections in one filter with a ball-flight model (Kalman-type): keeps the most consistent path, rejects false detections, fills gaps where a confident detection exists | T12 | planned (after T9) — improves what we have even if no detector is good enough alone |
| T13 | Other soccer models in WASB's model zoo (TrackNetV2, MonoTrack, DeepBall, BallSeg) as a second opinion / ensemble | T13 | low priority: in WASB's own paper WASB beat all of them on soccer, and WASB reaches 60% here |
| T14 | Fine-tune a ball tracker on public wide-angle football datasets (e.g. ISSIA-CNR, SoccerTrack/TeamTrack) on a cloud GPU with public data only | T14 | planned if T9 falls short |
| T15 | Self-training: fine-tune on our own video with labels produced by the tracker itself (pseudo-labels, no person involved). RULES.md now allows "pseudo-labels produced by an algorithm", but issue #2 forbade the provided tracking as labels | T15 | **ask the organisers first** |
| T16 | Ball height: tracking is flat, so a lofted ball is placed wrongly; the tactical and broadcast views together could estimate height | T16 | planned, low priority (complex) |

### Deep dive 5: v6's remaining errors (next, from 2026-10-26)

v5 and v6 each came from one round of build-test-check. Before adding anything, the deep-dive
steps they skipped:

| Step | What | Rows |
|---|---|---|
| Sealed exam | fetch Metrica Sample Games 1-2 (same repository as Game 3, hash-pinned); score only milestone versions, never choose anything on them | E1 |
| Anatomy | ✅ realism of stoppages (fixed: dead ball moves); ✅ ball in the air (half of team errors off the ground; landings 74%); ✅ possessions by length (recall is the bottleneck: under-5 s possessions; 2-5 s ones seen by the model but smoothed away by the decoder). Still to do: oracle on top of v6, stoppage edges | M25, M7d |
| Practice cases | top-down drawings of the largest error types (`scripts/case_viewer.py`) | M7d |
| Our match | **review clips for Kovidh** (`scripts/review_clips.py`): 37 clips of 7 kinds picked by algorithm (moving ball in walking phases, fast long balls, v6 vs v4, unsure stoppages, v6 vs Smart Tagging, long possessions, tracker losing players), with the tracked ball and v6's answer drawn on. **Cut 2026-10-26, waiting for Kovidh's notes** (general patterns only; never labels) | V16 |
| Fixes | one at a time from what the cases show; research ideas below; each tested leave-one-out and on fresh seeds | M26-M29 |

### Deep dive 1: the team call while the ball travels (passes, loose balls): v5 done, follow-ups open

| Track | Experiment | Rows | Status |
|---|---|---|---|
| Tracking + papers | touch rule (Vidal-Codina, Link & Hoernig) → **v4** | M7b | ✅ done |
| Tracking + papers | duel rule ("holder keeps the ball") | M7c | ✅ dropped (blocks real tackles) |
| Data check | our ball is smoothed: copy into practice, re-tune the touch rule | P1c, M7e | ✅ done: **touch rule's gain was an artefact** (realistic kit: v3 0.291, v4 0.288, best re-tune 0.297) |
| Tracking | anatomy and case review redone on the realistic kit | M7d | next |
| Tracking | longer-window cues: ball direction change over ~1 s; the receiver slows and turns | M24 | partly covered by v5's before/after clues; retry as extra v5 clues |
| Papers | Link & Hoernig's end-of-possession rule: possession ends when no teammate can reach the ball's predicted position within 1 s | M20 | next |
| **Trained on DFL** | **control classifier** (Link & Hoernig's features) trained on DFL's true possession changes | M19 | folded into M15: v3/v4's control events are clues of the learned team call |
| **Trained on practice** | **learned team call** (Borghesi 2023 idea: a model over tracking clues) giving P(home) per frame, Viterbi decoding | M15 | ✅ done → **v5**: practice 0.279 → 0.430 (fresh seeds, 48/48 runs); team right 89.5% vs 81.0%; team shape is the strongest clue |
| Smart Tagging | team tags overriding v4 when stale | M8b | ✅ no gain |
| Smart Tagging | team tags as **weighted evidence** in the decoder, and a phase-level check (v4 contradicting a whole high-trust phase) | M8c, M8d | planned (decoder) |
| Video (tactical) | detector + shirt colours to check team labels in the boxes | V8 | planned |
| Video (tactical) | vision model on crops: "is the ball in the air?" (a nearby opponent does not have it) | V7 | planned (overnight) |
| Our match | larger case review; overlay clips for Kovidh | M7d, V16 | next |

### Deep dive 2: the first seconds after a stoppage (who restarts)

| Track | Experiment | Rows |
|---|---|---|
| Tracking + papers | **restart detector from player positions** (Vidal-Codina): throw-in taker beyond the touchline, corner taker at the flag, keeper in the goal area for a goal kick, kickoff formation; the taker's team gets the ball | M23, M10 |
| Smart Tagging | **precise set pieces**: snap each 35 s window to the restart frame; type; taker's team; imitation tags to test | M8, M9 |
| Commentary | event-focused pass: "free kick to Athletic", "corner for Barcelona" (keywords find candidates, a local LLM judges each) | S3e |
| Video (tactical) | detector finds the ball at the restart moment: which spot (touchline, corner flag, goal area, centre) | V14 |
| Trained on DFL | restart team from the configuration of both teams at the restart | M23 |

### Deep dive 3: ball missing in live play (5.3 min of our match; v4 wrong ~28% there, v5 ~16% on practice)

| Track | Experiment | Rows |
|---|---|---|
| Tracking | **broadcast tracker's ball** where tactical has none (tested as a fill: neutral; retest inside this dive) | M5 |
| Papers + trained on DFL | **Ball Radar-lite** (Kim 2023): which team has the ball from player movement, trained on DFL with the ball hidden | M11 |
| Papers | **PathCRF** (2026): possession without the ball, via the most probable player-to-player path | M16 |
| Trained on DFL | **team-shape clue**: the team advancing in an open shape vs the team retreating compactly | M21 |
| Video (tactical) | **football-trained detector** finds the ball in those frames (it was visible in ~2/3 of gap frames) | V2, V6, V9 |
| Video (broadcast) | close-up camera often still shows the ball when the wide view loses it (needs re-download) | V10 |

### Deep dive 4: stoppage edges (when play stops and restarts): first round done → v6 (learned stoppages, joint decoder); the clues below are still open

| Track | Experiment | Rows |
|---|---|---|
| Audio (tactical) | **whistle detector**: signal processing (3-4.5 kHz tone, duration) plus a pretrained audio classifier; marks fouls, offsides, half ends | S4 |
| Audio | crowd-noise level: rises on attacks and shots, drops in long breaks | S5 |
| Broadcast (no video needed) | **camera behaviour as a stoppage clue**: close-ups, crowd shots and replays happen when play stops; already flagged per broadcast frame by the alignment | S6, S8 |
| Commentary | rare long stoppages (goals, cards, injuries, VAR, substitutions) | S3c, S3e |
| Video (tactical) | vision model on crops and frame sequences: "is play stopped?" (overnight, apps closed) | V12, V13 |
| Trained on DFL | **learned stoppage classifier** (gap length, ball position at loss/return, team speed, still ball, restart shapes) vs v2's hand rules | M18 |
| Smart Tagging | goal tags: long stoppages after goals | M8 |

### Then: the decoder, combining everything

| Experiment | Rows |
|---|---|
| HMM/Viterbi over H/A/D: per-frame evidence from every clue above, weights learned on the practice matches (with imitation clues for Smart Tagging, commentary, whistles), transition and duration statistics learned from DFL | M12, M22 |

### Finally

| Step | Rows |
|---|---|
| Merge the organisers' latest docs; reproducible pipeline (`run.py` regenerates every derived input); remove unused variants; technical document (from `model.md`, `data.md`, `sources.md`, `deep-dives/`); validated final submission by ~15 Nov | P3-P7 |

## Model

| # | Idea | Source | Status | Notes |
|---|---|---|---|---|
| M1 | Ball gaps mean stoppages (v1) | gap clips, counts | done | `blackout_v1` |
| M2 | Stoppage rules: ball out, ball still, gaps with slow players / at an edge / long (v2) | Vidal-Codina, practice measurements | done | `v2`, current best |
| M3 | Clean-up: frozen objects, team's 12th+ object | data audit | done | in v2; no score change alone |
| M4 | Flicker tidy-up | bug found testing v2 | done | in v2 |
| M5 | Precise tracking: ball blips, Savitzky-Golay smoothing, broadcast ball fill | Vidal-Codina, audit | done | neutral; `v2_precise` kept as an option |
| M6 | Better ball-gap rules: sweep thresholds; new clue "how far the ball moved while missing" | Kovidh's idea | done | gaps classified 83% right (was 74%) but score unchanged; `v2_return` kept as an option. **Oracle test: the team call in live play costs ~4× more than stoppages** |
| M7 | Possession logic: control (within 1 m for 3 frames), duels don't flip, a pass stays with the passer's team | Link & Hoernig 2017, Vidal-Codina 2022 | done | **v3**: practice 0.311 → 0.377, better in 48/48 runs |
| M7b | Possession logic, part 2: control by touch (ball velocity change near a player) or slow hold; no credit for a ball passing by | Link & Hoernig 2017, Vidal-Codina 2022 | **now (deep dive 1)** | damaged practice 0.353 → 0.409 (dv 7, pass-by 6); candidate v4 |
| M7c | Duel rule: keep the ball with its holder until he is clearly away (`keep_through_duels`) | deep dive 1 real cases | dropped | worse at every setting (0.394 at 1.5 m, 0.373 at 2 m): it also blocks real tackles |
| M7d | Pressing errors: understand from a larger case review, then retry | deep dive 1 | planned | |
| M7e | Touch rule re-tuned on the smoothed practice ball | data check 2026-10-26 | done | best 0.297 vs v3 0.290: no real gain; v4's earlier gain was an artefact of sharp practice balls |
| M24 | Longer-window team-call cues for a smoothed ball: change of ball direction over ~1 s; receiver decelerates and turns | deep dive 1 | next | |
| M8b | Smart Tagging team tags where v4 is stale | deep dive 1 | done: no gain | 0.409 vs 0.409; tags overwrite short possessions; re-test after M7e |
| M8 | Precise Smart Tagging: exact restart frame inside each 35 s window, taker's team, trust per tag type | Smart Tagging audit | next 2 | |
| M9 | Imitation clues on the practice matches (fake Smart Tagging and commentary from their event lists, with our sources' measured flaws) | our design | next 3 | so commentary and tagging can be tested fairly |
| M10 | Who restarts: the taker's team gets the ball from the restart frame | Vidal-Codina | next 4 | |
| M11 | Ball Radar-lite: which team has the ball during open-play gaps, from both teams' movement | Kim et al. 2023 (Ball Radar) | next 5 | small model trained on the practice matches |
| M12 | **Decoder** (HMM/Viterbi): the most believable H/A/D sequence, weighing every clue with trust learned on practice | our design | next 6 | |
| M13 | Stop the vote at stoppages | v2 testing | dropped | slightly worse in every scenario |
| M14 | Visible-ball stoppages where the ball is carried, not still | v2 weaknesses | planned | e.g. walking to a throw-in |
| M15 | **Learned team call**: gradient-boosted trees over 59 tracking clues trained on the damaged practice matches' per-frame possession (idea from Borghesi et al. 2023), both teams' views, Viterbi decoding | research 2026-10-26 | **done → v5** | practice 0.430 vs v4 0.279 (fresh seeds); `scripts/learned_test.py`; model.md step 4 |
| M16 | **Ball-free possession and events** with a CRF/Viterbi over player-to-player paths, as in PathCRF (arXiv 2602.12080, KDD'26) | research 2026-10-26 | planned | targets live play with the ball missing, and fits the decoder (M12) |
| M18 | **Learned stoppage model** (35 clues: v2's rules, ball still/gap, where the ball vanished and returned, player speed and walking, objects tracked, layout) + one Viterbi decoder for H/A/D | deep dive 4 | **done → v6** | practice 0.430 → 0.558 (fresh seeds, 48/48 runs); dead frames missed/false 24%/23% → 5%/4%; leans on player speed (as Lang et al. 2022) |
| M19 | **Learned control classifier** trained on DFL's true possession changes, with Link & Hoernig's features (duration, ball speed and acceleration, opponents within 0.5-5 m) | Link & Hoernig 2017 | folded into M15 | the control events and distance windows are v5 clues |
| M20 | End-of-possession rule: possession ends when no teammate can reach the ball's predicted position within 1 s | Link & Hoernig 2017 | next (dive 1) | |
| M21 | Team-shape clue for who has the ball (advancing open shape vs retreating compact shape; share goal-side of the ball), learned on DFL | tactics literature | done inside M15 | the strongest v5 clue: shuffling it costs 17 points of accuracy |
| M22 | Decoder statistics learned from DFL: possession and stoppage length distributions, switch rates | our design | planned (decoder) | |
| M23 | **Restart detector from player positions** (throw-in taker beyond the touchline, corner taker at the flag, keeper in the goal area, kickoff formation); taker's team gets the ball | Vidal-Codina 2022 | next (dive 2) | |
| M25 | **Possession count / learned change price**: v6 finds 13% of true possessions under 2 s and 41% of 2-5 s ones (deep dive 5, step 3); for 2-5 s ones the model favours the right team 72% of the time, so the decoder smooths them away. Try a third model, "a change of possession happens here", whose probability sets the decoder's price per frame instead of one fixed price | deep dive 5 | **next** | lowering the fixed price everywhere trades the gain for invented possessions |
| M26 | **v5 model upgrades**: more damaged copies per match, hyperparameters, per-player clues (the receiver's speed and turn), a sequence model (TCN, Borghesi 2023) over the clues | v5 results 2026-10-26 | planned | practice matches only; leave-one-match-out |
| M27 | **Long windows** for the stoppage model: player movement 20, 40 and 80 s before and after (Lang et al. 2022, *Scientific Reports*: 92% in-play accuracy from players alone, all time shifts contributed) | research 2026-10-26 | planned (dive 5) | |
| M28 | **Sequence models** over the clues: TranSPORTmer (Capellera et al., ACCV 2024: per-frame pass / possession / uncontrolled / out of play, plus ball imputation) and multi-modal masked pre-training (arXiv 2512.19528, Dec 2025: +7.6 points state accuracy over TranSPORTmer) | research 2026-10-26 | planned | check code availability and CPU cost first (8 GB machine) |
| M29 | Restart clues for the team model: who is nearest when the ball starts moving after a stoppage; where (touchline, corner, goal area, centre); which team is set up to attack | deep dive 2 | planned | |
| P8 | Model cache keeps one copy per code version (~250 MB each): delete stale versions automatically | disk 2026-10-26 | next code change | cleaned by hand to 244 MB |
| M30 | **Ball in the air**: a "probably in the air" clue trained on DFL's ball height from 2D movement (on DFL a 2D ball at 18 m/s+ is high 63% of the time), plus landing-point reachability (M20); half of v6's team errors happen with the ball off the ground | deep dive 5, step 2 | planned | |
| M8c | Smart Tagging team tags as weighted evidence in the decoder (not a hard override) | deep dive 1 | planned | |
| M8d | Phase-level check: v4 contradicting an entire high-trust Smart Tagging phase | deep dive 1 | planned | |
| M17 | Wider research pass: MLSA/ECML sports-analytics workshops, SoccerNet game-state, 2024-26 possession and event-detection papers | Kovidh, 2026-10-26 | started | first pass 2026-10-26: Lang 2022 (→ M27), TranSPORTmer and masked pre-training (→ M28), SkillCorner (→ E2), Metrica Games 1-2 (→ E1); more to do |

## Sources and clues

| # | Idea | Status | Notes |
|---|---|---|---|
| E1 | **Sealed exam**: Metrica Sample Games 1-2 (anonymised, 25 fps, tracking + events; labels derived from events as for Game 3) | next (dive 5) | github.com/metrica-sports/sample-data; acknowledge Metrica when used publicly |
| E2 | SkillCorner open data: 9 matches of broadcast tracking (10 fps) with the ball owner per frame (their own algorithm, so a weaker answer key) | planned | another kind of imperfect tracking; possible extra practice or test |
| S1 | Commentary transcript (Whisper, local) | done | first run looped; fixed (VAD, no carried context) |
| S2 | Commentary keyword events | done | weak clue: only modestly above chance |
| S3 | Commentary read by a local LLM: possession, live/stopped, event per line | done | **at chance for possession** (55% vs ~57% "always Barça"); "stopped" weak (55% vs 40% base) |
| S3b | Commentary player names → team, without the LLM | done | 55–58% vs 52–54% chance: commentators don't narrate who has the ball; Barça named 3× as often as Athletic |
| S3c | Commentary as a clue for rare long stoppages (goals, injuries, VAR, subs) | planned (low weight, in the decoder) | |
| S3d | A bigger local LLM on the commentary | folded into S3e | |
| S3e | **Event-focused commentary pass**: keywords find every candidate line (they found 21 corners; the LLM found 3), then a larger local LLM judges each candidate with context: happening now or replay/chat, which team gets the ball (for a foul, the *other* team), confidence | planned (step 8) | Kovidh 2026-10-26: the specific events the LLM did spot were often right (offsides 5/5 near a stoppage, chance 41%), but it missed most |
| S4 | Whistle detector on the tactical audio | planned (step 8) | never started: the commentary work came first; marks stoppage starts |
| S5 | Crowd-noise level (rises on attacks, drops in long stoppages) | planned | |
| S6 | Broadcast replays as a stoppage clue (replays follow stoppages) | planned | replays already detected by `align_broadcast.py` |
| S7 | Smart Tagging team tags as weighted clues | planned | via the decoder (M12) |
| S8 | **Broadcast camera behaviour as a stoppage clue**: close-ups, crowd shots and replays (no live pitch in view), mapped to tactical time; needs only the broadcast tracking and homography we already have | planned (dive 4) | already flagged per frame by `align_broadcast.py` |
| S9 | Snap events (Smart Tagging, commentary) to the exact tracking moment with trajectory-based event/tracking synchronisation (ELASTIC, arXiv 2608.30227) | planned (dives 2, 4) | |
| S10 | Ball-strike sounds in the audio (kick onsets) | planned, low priority | probably drowned by crowd noise |

## Video (all local models; Claude never sees frames)

| # | Idea | Status | Notes |
|---|---|---|---|
| V1 | Detector audit of the tracking (420 frames) | done | ghost not a person; ball visible in ~2/3 of gap frames |
| V2 | **Detector finds the ball inside tracking gaps** | next (background, after S3) | where the ball is during gaps: restart spot? moving? |
| V3 | Local vision-language model: "is play stopped?" on chosen frames | done (pilot); model removed to free disk | **failed**: qwen2.5vl:3b says "stopped" on 100% of frames in every group; 26 s per frame. The wide view is illegible to it |
| V12 | Vision pilot 2: crops around the action (tracking + homography), 2-3 frames a second apart, Qwen3-VL 4B | parked until deep dives 3-4 | blocked twice: first by memory (4.1 GB model with apps open), then the disk filled with swap (324 MB free) and macOS ran out of memory. Run it alone, overnight, apps closed |
| V13 | Qwen3-VL 2B pilot with crops and sequences | planned | fits in memory; weaker |
| V14 | Detector finds the ball at restart moments: which spot (touchline, corner flag, goal area, centre) | planned (dive 2) | |
| V15 | Detector counts people on the pitch to measure missing players | planned, low priority | |
| V17 | Confirm from the video that the provided ball path is smoothed | done: inconclusive | the detector loses the ball in kicks (motion blur); A3 stays unconfirmed |
| T1 | Football-trained detector pilot on our video | done | ball within 2 m on 50% of frames (55% zoomed); not enough for our own track |
| T3 | Our own ball track from the video for every graded frame | parked | off-the-shelf detector finds the ball ~50% of the time on the wide view; broadcast route needs disk space |
| T4 | Methods re-run on our own ball track | planned (after T3) | |
| V16 | **Overlay clips of our match for Kovidh** (tracking drawn on the tactical video) for each dive's error types | next (dive 1) | Kovidh watches and describes in general terms |
| V9 | **Best vision models that fit the laptop**: Qwen3-VL 4B (8B needs ~12 GB); football-trained detectors (YOLOv11 "soccana": players/ball/referees; RF-DETR ball) | planned (after the pilot) | check licences and that none was trained on our match |
| V10 | **Re-download the broadcast video** and run vision models on its close-ups (mapped to tactical time by the alignment) | planned, Kovidh to download | players and ball are far larger than in the wide tactical view |
| V11 | Cloud GPU for bigger vision models | needs the organisers' OK | the FAQ forbids giving the video to third-party hosted or cloud LLMs; a self-run model on a rented GPU is unclear: ask before trying |
| V4 | SoccerNet-style whole-video models | dropped | too heavy for the laptop; trained on TV close-ups |
| V5 | Clips with the tracking drawn on top, for Kovidh to watch and describe in general terms | planned | when a weakness needs understanding |
| V6 | **Video for the team call**: in live-play gaps, the detector finds the ball and the player nearest it | planned (after M7) | targets the biggest lever; Kovidh's idea |
| V7 | Video sees the ball **in the air**, so a nearby opponent doesn't have it | planned (after M7) | tracking is flat; a vision model can tell |
| V8 | Shirt colours check players' team labels (~5% wrong in the boxes) | planned (after M7) | |

## Process and deliverables

| # | Idea | Status | Notes |
|---|---|---|---|
| P1 | Practice-match test bench (open data, fault kit, calibration) | done | `scripts/open_test.py` |
| P1c | Fault kit: smooth the practice ball like our tracker's (23-frame moving average) | done | practice balls now match ours on 3 measures |
| P1d | **Realism report**: our match vs the practice matches on every measure, flagging big differences; re-run whenever the kit changes | done | 17/18 within 1.5×; it caught the missing-player gap (9.4% vs 0.6%), now fixed |
| P1b | Fault kit, missing faults: wrong team labels (1.8% of objects, 4× likelier in the boxes) and large ball errors (5-15 m on ~3.5% of frames) | done | practice baseline 0.248 vs real 0.243; v3 0.352 vs v2 0.284 |
| P2 | Organiser questions: issue #14 (saving model outputs; clips → rules), #11 | open | check each session; upstream RULES now allow people to watch the video |
| P3 | Merge the organisers' latest docs (23 Oct) into our branch | planned | offered, not done |
| P4 | Reproducible pipeline: `run.py` regenerates every derived input (alignment, transcript, model outputs) from a clean clone | planned | needed before the final submission |
| P5 | Remove experimental method variants not used in the final model | planned | before the final submission |
| P6 | Technical document | planned | |
| P7 | Final submission, validated and reproduced byte for byte | planned | by ~15 Nov (deadline 17 Nov) |

## Decisions (Kovidh, 2026-10-25)

1. Open data: DFL (7 matches, per-frame alive/possession) first, Metrica Game 3 second; damaged
   to look like our tracker; used to set thresholds, as a bigger damage test, and for training.
2. Audit the data before building v2 (done for tracking, tagging, broadcast).
3. v2 = clean-up + restart detector + possession logic, thresholds from open data; then decoder.
4. Broadcast re-downloaded; keep audio + tracking.
5. Models: Whisper + whistle classifier first, then a vision-model timing pilot; Ball Radar later.
6. Questions to organisers: posted as
   [issue #14](https://github.com/metrica-sports/more-than-a-hack-2027/issues/14).

## Open questions

- **Organisers:** issue #14 (saving model outputs for reproducibility; turning what we saw in
  clips into general rules), and #11 (another team's: is byte-identical required across
  hardware?). Check both at the start of each session.
- How `main` is used and who merges.
- Is a ball gap ending in the penalty box a keeper holding the ball (live) or a goal kick (dead)?
  Needs the restart detector and DFL to answer.
