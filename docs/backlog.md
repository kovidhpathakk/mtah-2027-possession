# Backlog: every idea, nothing dropped silently

One row per idea we have had. **Check this before choosing the next step.** New ideas are added
the moment they come up. Rows are never deleted: an idea we decide against is marked `dropped`
with the reason.

Status: `done` · `now` · `next` (in order) · `planned` · `parked` (decided to wait) · `dropped`

Last updated: 2026-10-26.

## Data use: every asset, how it is used, what is untried

Kept so no source is quietly forgotten (Smart Tagging went unused until 2026-10-26).

| Asset | Used in the model today | Used elsewhere | Untried |
|---|---|---|---|
| Tactical tracking | ✅ everything (v3) | audits | – |
| Tactical homography | ❌ | video audit (pitch ↔ pixels) | mapping video detections into the model |
| **Smart Tagging** | ❌ **not used** | audited: team tags ~88% right in open play, ~60% near the box; set pieces vague, 2 of 3 restarts missing | **team clue where control is unclear; set-piece windows → restarts** (M8, M9) |
| Tactical video | ❌ | detector audit (420 frames); vision pilot | football-trained detectors, Qwen3-VL, ball in gaps, ball in the air, shirt colours (V2-V8) |
| Tactical audio | ❌ | alignment test only | **whistles** (S4), crowd noise (S5) |
| Broadcast tracking | ❌ (fill tested, neutral) | alignment, audits, second witness | its ball when tactical's is wrong; replays as a stoppage clue (S6) |
| Broadcast homography | ❌ | – | mapping broadcast-video detections |
| Broadcast video | ❌ (deleted to save disk) | audio extracted | **close-up views for vision models**: players and ball are far bigger than in the wide tactical view; replays follow key events. Needs a re-download (14 GB) |
| Broadcast audio / commentary | ❌ | transcript; keyword events; LLM labels (weak) | **event-focused LLM pass with a larger model** (S3e) |
| Public 5-minute answers | sanity check only (never tuned on) | – | – |
| Open data (DFL, Metrica) | practice test; settings for v2/v3 | control audit | **training a learned model** (M15); imitation clues (M9) |

## Order of work (reordered 2026-10-26)

The logic: **make the test honest first** (everything is measured on it), **research before
building** the biggest lever, **team-call work before stoppage work** (perfect team calls are worth
+0.36 on practice, perfect stoppages +0.08), **clues before the decoder** that combines them, and
long jobs in the background whenever the machine is free.

| Step | Backlog rows | Why here |
|---|---|---|
| 1 | P1b: missing faults in the practice damage | ✅ done. Practice baseline now 0.248 vs its real 0.243 |
| 2 | V3: vision-model pilot (30 frames) | running in the background; decides whether V3 is worth a full run |
| 3 | M17: focused research pass (Borghesi TCN, PathCRF, how DFL defines possession, pass/reception detection, whistle detection) | shapes steps 4-5 and 8 before we build them |
| 4 | M7b: possession part 2, for passes and loose balls (59% of live play, 16% wrong) | the largest pile of team errors |
| 5 | M15: learned possession model trained on DFL | may beat or absorb step 4; compared on practice |
| 6 | M10: who restarts (first 3 s after a stoppage: 23% wrong) | second-largest team error |
| 7 | V2 / V6: detector finds the ball in live-play gaps (5.3 min of our match), overnight | ball missing in live play: 28% wrong |
| 8 | Stoppage clues: S4 whistles, M8 precise Smart Tagging, M9 imitation clues, S3c commentary for rare stoppages, V3 if the pilot works | each one tested on practice through the imitation clues |
| 9 | M12 decoder (with M16 PathCRF ideas, M11 Ball Radar-lite) | combines every clue above |
| 10 | P3-P7: merge organiser docs, reproducible pipeline, clean-up, technical document, submit by ~15 Nov | |

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
| M7b | Possession logic, part 2: kick detection (ball acceleration ≥ 4 m/s²) and ball-speed checks for real control, to sharpen when control starts | Link & Hoernig 2017 | next 1 | the team call can still gain up to 0.72 |
| M8 | Precise Smart Tagging: exact restart frame inside each 35 s window, taker's team, trust per tag type | Smart Tagging audit | next 2 | |
| M9 | Imitation clues on the practice matches (fake Smart Tagging and commentary from their event lists, with our sources' measured flaws) | our design | next 3 | so commentary and tagging can be tested fairly |
| M10 | Who restarts: the taker's team gets the ball from the restart frame | Vidal-Codina | next 4 | |
| M11 | Ball Radar-lite: which team has the ball during open-play gaps, from both teams' movement | Kim et al. 2023 (Ball Radar) | next 5 | small model trained on the practice matches |
| M12 | **Decoder** (HMM/Viterbi): the most believable H/A/D sequence, weighing every clue with trust learned on practice | our design | next 6 | |
| M13 | Stop the vote at stoppages | v2 testing | dropped | slightly worse in every scenario |
| M14 | Visible-ball stoppages where the ball is carried, not still | v2 weaknesses | planned | e.g. walking to a throw-in |
| M15 | **Learned possession model**: a sequence model trained on the DFL matches' per-frame possession, as in Borghesi et al. 2023 (Temporal Convolutional Networks on tracking data, *Expert Systems with Applications*) | research 2026-10-26 | planned | DFL gives ~1.4 million labelled frames; leave-one-match-out testing |
| M16 | **Ball-free possession and events** with a CRF/Viterbi over player-to-player paths, as in PathCRF (arXiv 2602.12080, KDD'26) | research 2026-10-26 | planned | targets live play with the ball missing, and fits the decoder (M12) |
| M17 | Wider research pass: MLSA/ECML sports-analytics workshops, SoccerNet game-state, 2024-26 possession and event-detection papers | Kovidh, 2026-10-26 | planned | |

## Sources and clues

| # | Idea | Status | Notes |
|---|---|---|---|
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

## Video (all local models; Claude never sees frames)

| # | Idea | Status | Notes |
|---|---|---|---|
| V1 | Detector audit of the tracking (420 frames) | done | ghost not a person; ball visible in ~2/3 of gap frames |
| V2 | **Detector finds the ball inside tracking gaps** | next (background, after S3) | where the ball is during gaps: restart spot? moving? |
| V3 | Local vision-language model: "is play stopped?" on chosen frames | done (pilot) | **failed**: qwen2.5vl:3b says "stopped" on 100% of frames in every group; 26 s per frame. The wide view is illegible to it |
| V12 | **Vision pilot 2**: crops around the action (tracking + homography), 2-3 frames a second apart, Qwen3-VL 4B | blocked by memory | 4.1 GB model on an 8 GB laptop with apps open: heavy swapping, no answer in 10 min. Retry with every other app closed, or with Qwen3-VL 2B |
| V13 | Qwen3-VL 2B pilot with crops and sequences | planned | fits in memory; weaker |
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
| P1b | Fault kit, missing faults: wrong team labels (1.8% of objects, 4× likelier in the boxes) and large ball errors (5-15 m on ~3.5% of frames) | done | practice baseline 0.248 vs real 0.243; v3 0.352 vs v2 0.284 |
| P2 | Organiser questions: issue #14 (saving model outputs; clips → rules), #11 | open | check each session; upstream RULES now allow people to watch the video |
| P3 | Merge the organisers' latest docs (23 Oct) into our branch | planned | offered, not done |
| P4 | Reproducible pipeline: `run.py` regenerates every derived input (alignment, transcript, model outputs) from a clean clone | planned | needed before the final submission |
| P5 | Remove experimental method variants not used in the final model | planned | before the final submission |
| P6 | Technical document | planned | |
| P7 | Final submission, validated and reproduced byte for byte | planned | by ~15 Nov (deadline 17 Nov) |
