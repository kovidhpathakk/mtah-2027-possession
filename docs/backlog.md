# Backlog: every idea, nothing dropped silently

One row per idea we have had. **Check this before choosing the next step.** New ideas are added
the moment they come up. Rows are never deleted: an idea we decide against is marked `dropped`
with the reason.

Status: `done` · `now` · `next` (in order) · `planned` · `parked` (decided to wait) · `dropped`

Last updated: 2026-10-26.

## Model

| # | Idea | Source | Status | Notes |
|---|---|---|---|---|
| M1 | Ball gaps mean stoppages (v1) | gap clips, counts | done | `blackout_v1` |
| M2 | Stoppage rules: ball out, ball still, gaps with slow players / at an edge / long (v2) | Vidal-Codina, practice measurements | done | `v2`, current best |
| M3 | Clean-up: frozen objects, team's 12th+ object | data audit | done | in v2; no score change alone |
| M4 | Flicker tidy-up | bug found testing v2 | done | in v2 |
| M5 | Precise tracking: ball blips, Savitzky-Golay smoothing, broadcast ball fill | Vidal-Codina, audit | done | neutral; `v2_precise` kept as an option |
| M6 | **Better ball-gap rules**: sweep thresholds; new clue "how far the ball moved while missing" | Kovidh's idea | **now** | |
| M7 | **Possession logic**: control vs touch, kick = acceleration jump ≥ 4 m/s², a pass stays with the passer's team, duels don't flip | **Link & Hoernig 2017**, Vidal-Codina (duel zone) | **next 1** | fixes loose timing of team changes (1 s late = 0.65 score) |
| M8 | Precise Smart Tagging: exact restart frame inside each 35 s window, taker's team, trust per tag type | Smart Tagging audit | next 2 | |
| M9 | Imitation clues on the practice matches (fake Smart Tagging and commentary from their event lists, with our sources' measured flaws) | our design | next 3 | so commentary and tagging can be tested fairly |
| M10 | Who restarts: the taker's team gets the ball from the restart frame | Vidal-Codina | next 4 | |
| M11 | Ball Radar-lite: which team has the ball during open-play gaps, from both teams' movement | Kim et al. 2023 (Ball Radar) | next 5 | small model trained on the practice matches |
| M12 | **Decoder** (HMM/Viterbi): the most believable H/A/D sequence, weighing every clue with trust learned on practice | our design | next 6 | |
| M13 | Stop the vote at stoppages | v2 testing | dropped | slightly worse in every scenario |
| M14 | Visible-ball stoppages where the ball is carried, not still | v2 weaknesses | planned | e.g. walking to a throw-in |

## Sources and clues

| # | Idea | Status | Notes |
|---|---|---|---|
| S1 | Commentary transcript (Whisper, local) | done | first run looped; fixed (VAD, no carried context) |
| S2 | Commentary keyword events | done | weak clue: only modestly above chance |
| S3 | **Commentary read by a local LLM**: possession, live/stopped, event per line; reliability vs tracking; general description | **now** (running in background) | qwen3:4b via Ollama |
| S4 | Whistle detector on the tactical audio | planned | |
| S5 | Crowd-noise level (rises on attacks, drops in long stoppages) | planned | |
| S6 | Broadcast replays as a stoppage clue (replays follow stoppages) | planned | replays already detected by `align_broadcast.py` |
| S7 | Smart Tagging team tags as weighted clues | planned | via the decoder (M12) |

## Video (all local models; Claude never sees frames)

| # | Idea | Status | Notes |
|---|---|---|---|
| V1 | Detector audit of the tracking (420 frames) | done | ghost not a person; ball visible in ~2/3 of gap frames |
| V2 | **Detector finds the ball inside tracking gaps** | next (background, after S3) | where the ball is during gaps: restart spot? moving? |
| V3 | Local vision-language model: "is play stopped?" on chosen frames | parked | Kovidh: wait; revisit after the decoder |
| V4 | SoccerNet-style whole-video models | dropped | too heavy for the laptop; trained on TV close-ups |
| V5 | Clips with the tracking drawn on top, for Kovidh to watch and describe in general terms | planned | when a weakness needs understanding |

## Process and deliverables

| # | Idea | Status | Notes |
|---|---|---|---|
| P1 | Practice-match test bench (open data, fault kit, calibration) | done | `scripts/open_test.py` |
| P2 | Organiser questions: issue #14 (saving model outputs; clips → rules), #11 | open | check each session; upstream RULES now allow people to watch the video |
| P3 | Merge the organisers' latest docs (23 Oct) into our branch | planned | offered, not done |
| P4 | Reproducible pipeline: `run.py` regenerates every derived input (alignment, transcript, model outputs) from a clean clone | planned | needed before the final submission |
| P5 | Remove experimental method variants not used in the final model | planned | before the final submission |
| P6 | Technical document | planned | |
| P7 | Final submission, validated and reproduced byte for byte | planned | by ~15 Nov (deadline 17 Nov) |
