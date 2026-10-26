# Plan: what's next, every idea with its status

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
| **Smart Tagging** | ❌ not in the model | audited; team-tag override where v4 is stale tested: no gain | **set pieces → restarts** (dive 2), goal tags (dive 4), team tags as weighted decoder evidence (M8c), phase-level check (M8d) |
| Tactical video | ❌ | detector audit (420 frames); vision pilot | football-trained detectors, Qwen3-VL, ball in gaps, ball in the air, shirt colours (V2-V8) |
| Tactical audio | ❌ | alignment test only | **whistles** (S4), crowd noise (S5) |
| Broadcast tracking | ❌ (fill tested, neutral) | alignment, audits, second witness | its ball in live-play gaps (dive 3); **camera behaviour (close-ups, crowd shots, replays) as a stoppage clue** (S8, dive 4) |
| Broadcast homography | ❌ | – | mapping broadcast-video detections |
| Broadcast video | ❌ (deleted to save disk) | audio extracted | **close-up views for vision models**: players and ball are far bigger than in the wide tactical view; replays follow key events. Needs a re-download (14 GB) |
| Broadcast audio / commentary | ❌ | transcript; keyword events; LLM labels (weak) | **event-focused LLM pass with a larger model** (S3e) |
| Public 5-minute answers | sanity check only (never tuned on) | – | – |
| Open data (DFL, Metrica) | practice test; every setting of v2-v4 | control audit; case drawings | **trained models**: control classifier (M19), possession model (M15), Ball Radar-lite (M11), stoppage classifier (M18), team shape (M21), decoder statistics (M22); imitation clues (M9) |

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
| T3 | Our own ball track from the video | T3 | **parked**: needs a detector that finds the ball reliably; route left: the broadcast video (ball several times larger), if disk space allows a 14 GB re-download |
| T4 | v4's touch rule and the trained models on our own ball track | T4 | after T3 |
| T5 | Player re-detection (missing players), team labels from shirt colours | V8, V15 | later |
| T6 | **Broadcast pilot**: the same ball detector on the zoomed-in broadcast video (ball several times larger), mapped to tactical time | T6 | ⏳ running (`scripts/ball_pilot_broadcast.py`) |
| T7 | Fine-tune a ball detector on **public wide-angle football footage** with labelled balls (e.g. fixed-camera research datasets), possibly on a free cloud GPU since only public data goes there. **Never on our match's video with the provided tracking as labels**: the organisers refused exactly that (issue #2) | T7 | planned, if T6 is not enough |
| T8 | A vision-language model (Qwen-VL) for tracking | – | dropped: good at describing scenes, imprecise at positions and far too slow for 25 frames a second; detectors are the right tool |

### Deep dive 1: the team call while the ball travels (passes, loose balls): in progress

| Track | Experiment | Rows | Status |
|---|---|---|---|
| Tracking + papers | touch rule (Vidal-Codina, Link & Hoernig) → **v4** | M7b | ✅ done |
| Tracking + papers | duel rule ("holder keeps the ball") | M7c | ✅ dropped (blocks real tackles) |
| Data check | our ball is smoothed: copy into practice, re-tune the touch rule | P1c, M7e | ✅ done: **touch rule's gain was an artefact** (realistic kit: v3 0.291, v4 0.288, best re-tune 0.297) |
| Tracking | anatomy and case review redone on the realistic kit | M7d | next |
| Tracking | longer-window cues: ball direction change over ~1 s; the receiver slows and turns | M24 | next |
| Papers | Link & Hoernig's end-of-possession rule: possession ends when no teammate can reach the ball's predicted position within 1 s | M20 | next |
| **Trained on DFL** | **control classifier** (Link & Hoernig's features: duration, ball speed and acceleration, opponents within 0.5-5 m) trained on DFL's true possession changes | M19 | next |
| **Trained on DFL** | **learned possession model** (Borghesi 2023: a sequence model over tracking features) giving P(home / away) per frame | M15 | next |
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

### Deep dive 3: ball missing in live play (5.3 min of our match; v4 wrong ~28% there)

| Track | Experiment | Rows |
|---|---|---|
| Tracking | **broadcast tracker's ball** where tactical has none (tested as a fill: neutral; retest inside this dive) | M5 |
| Papers + trained on DFL | **Ball Radar-lite** (Kim 2023): which team has the ball from player movement, trained on DFL with the ball hidden | M11 |
| Papers | **PathCRF** (2026): possession without the ball, via the most probable player-to-player path | M16 |
| Trained on DFL | **team-shape clue**: the team advancing in an open shape vs the team retreating compactly | M21 |
| Video (tactical) | **football-trained detector** finds the ball in those frames (it was visible in ~2/3 of gap frames) | V2, V6, V9 |
| Video (broadcast) | close-up camera often still shows the ball when the wide view loses it (needs re-download) | V10 |

### Deep dive 4: stoppage edges (when play stops and restarts; worth up to +0.08)

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
| M15 | **Learned possession model**: a sequence model trained on the DFL matches' per-frame possession, as in Borghesi et al. 2023 (Temporal Convolutional Networks on tracking data, *Expert Systems with Applications*) | research 2026-10-26 | planned | DFL gives ~1.4 million labelled frames; leave-one-match-out testing |
| M16 | **Ball-free possession and events** with a CRF/Viterbi over player-to-player paths, as in PathCRF (arXiv 2602.12080, KDD'26) | research 2026-10-26 | planned | targets live play with the ball missing, and fits the decoder (M12) |
| M18 | **Learned stoppage classifier** trained on DFL (gap length, where the ball vanished and returned, team speed, still ball, restart shapes) vs v2's hand rules | deep dive 4 | planned | |
| M19 | **Learned control classifier** trained on DFL's true possession changes, with Link & Hoernig's features (duration, ball speed and acceleration, opponents within 0.5-5 m) | Link & Hoernig 2017 | next (dive 1) | |
| M20 | End-of-possession rule: possession ends when no teammate can reach the ball's predicted position within 1 s | Link & Hoernig 2017 | next (dive 1) | |
| M21 | Team-shape clue for who has the ball while it is missing (advancing open shape vs retreating compact shape), learned on DFL | tactics literature | planned (dive 3) | |
| M22 | Decoder statistics learned from DFL: possession and stoppage length distributions, switch rates | our design | planned (decoder) | |
| M23 | **Restart detector from player positions** (throw-in taker beyond the touchline, corner taker at the flag, keeper in the goal area, kickoff formation); taker's team gets the ball | Vidal-Codina 2022 | next (dive 2) | |
| M8c | Smart Tagging team tags as weighted evidence in the decoder (not a hard override) | deep dive 1 | planned | |
| M8d | Phase-level check: v4 contradicting an entire high-trust Smart Tagging phase | deep dive 1 | planned | |
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
