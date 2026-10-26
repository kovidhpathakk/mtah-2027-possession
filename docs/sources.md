# External sources: what we use, how, and what is still unused

Every outside source behind our entry. The organisers require that they can access everything we
use and that the technical document explains it (RULES.md). Last updated: 2026-10-26.

## Research papers

| Paper | What it gives | How we use it | Where |
|---|---|---|---|
| **Vidal-Codina, Evans, El Fakir, Billingham (2022).** "Automatic event detection in football using tracking data." *Sports Engineering* 25:18. [arXiv 2202.00804](https://arxiv.org/abs/2202.00804) | 1 m possession zone; two opponents within 1 m = a duel, not possession; a gain of possession needs the ball to change speed or direction; a missing ball and restart positions mark dead ball; Savitzky-Golay ball smoothing | **In the model**: stoppage rules (v2), the 1 m zone and duel rule (v3), touch logic (v4); smoothing in `precise.py` (tested, neutral) | `stoppages.py`, `control.py`, `precise.py` |
| **Link, Hoernig (2017).** "Individual ball possession in soccer." *PLOS ONE* 12(7). [PMC5503225](https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225/) | possession needs control, not a touch-by; a touch is a sudden change in the ball's motion; a pass stays with the passer's team until someone else controls it | **In the model**: the hold-through-passes logic (v3), touch rule (v4) | `control.py` |
| Kim et al. (2023). "Ball trajectory inference from multi-agent sports contexts using set transformer and hierarchical bi-LSTM" (Ball Radar). KDD. [arXiv 2306.08206](https://arxiv.org/abs/2306.08206) | where the ball is, from player movement alone | **not yet**: planned for live play with the ball missing (deep dive 3) | plan M11 |
| Borghesi et al. (2023). "Using temporal convolutional networks to estimate ball possession in soccer games." *Expert Systems with Applications*. [link](https://iris.polito.it/handle/11583/2976470) | a model trained to read possession from tracking | **not yet**: planned learned model trained on DFL (deep dive 1/3) | plan M15 |
| PathCRF (2026). "Ball-free soccer event detection." KDD'26. [arXiv 2602.12080](https://arxiv.org/html/2602.12080) | possession and events without the ball, decoded with Viterbi | **not yet**: ideas for the decoder and for ball-missing live play | plan M16 |
| Amrita (2011). Automated referee-whistle detection | whistle detection reaches ~92% sensitivity | **not yet**: whistle detector (deep dive 4) | backlog S4 |
| SoccerNet challenges (2025). [arXiv 2508.19182](https://arxiv.org/pdf/2508.19182) | state-of-the-art video models | **dropped**: too heavy for the laptop | backlog V4 |

## Datasets (other matches)

| Dataset | Licence | How we use it |
|---|---|---|
| **DFL / Bassek, Rein, Weber, Memmert (2025).** "An integrated dataset of spatiotemporal and event data in elite soccer." *Scientific Data* 12. [figshare 28196177](https://springernature.figshare.com/articles/dataset/An_integrated_dataset_of_spatiotemporal_and_event_data_in_elite_soccer/28196177): 7 Bundesliga matches, 25 fps tracking, per-frame ball status and possession | CC BY 4.0 | **practice matches**: labels on every frame; all thresholds set here; control audit; case viewing. Not yet: training a learned model, imitation clues from its events |
| **Metrica Sports sample data, Game 3.** [github.com/metrica-sports/sample-data](https://github.com/metrica-sports/sample-data) (commit e706dd5) | none stated; "please acknowledge the source" | practice match (labels derived from its events) |

Both are fetched and checksum-verified by `scripts/fetch_open_data.py`.

## Models and tools (all run on our machine)

| Tool | Version | Used for |
|---|---|---|
| whisper.cpp + Whisper large-v3-turbo (q5_0) | Homebrew 1.9.5; model SHA-256 pinned in `transcribe.py` | commentary transcript (research only so far) |
| Silero VAD v6.2.0 | SHA-256 pinned | speech detection for the transcript |
| Ollama + Qwen3 4B | Ollama 0.40; model id 359d7dd4bcda | commentary labelling (tested: does not track possession) |
| Ollama + Qwen3-VL 4B | model id a1b29c246319 | vision pilot (blocked by memory; parked) |
| PyTorch 2.5.1 + torchvision 0.20.1, Faster R-CNN ResNet-50 FPN v2 (COCO) | `requirements-video.txt` | video audit (people and ball) |
| ffmpeg | Homebrew | frames, audio extraction |
| **WASB** ball tracker (Tarashima, Haq, Wang, Tagawa, BMVC 2023, [arXiv 2311.05237](https://arxiv.org/abs/2311.05237)) | code MIT, cloned to `third_party/WASB-SBDT` (commit 923462c, read before use); soccer weights `wasb_soccer_best.pth.tar` (SHA-256 `d0369572…646c`) from its MODEL_ZOO, trained on the ISSIA-CNR soccer dataset (fixed wide cameras; not our match); tensors only, loaded with weights_only=True; downloaded with Kovidh's approval 2026-10-26 | track T pilot 3 (`scripts/wasb_pilot.py`) |
| Ultralytics 8.3.40 (AGPL-3.0) | `requirements-video.txt` | to run football-trained YOLO detectors (track T); weights not yet downloaded |
| Roboflow "sports" football detectors: ball (YOLOv8x, 1 class, trained at 1280 px, 50 epochs) and players | [github.com/roboflow/sports](https://github.com/roboflow/sports) (MIT), weights from its `examples/soccer/setup.sh`; trained on DFL Bundesliga Data Shootout footage (not our match). SHA-256: ball `678fbad0…2912`, players `75b09c37…faf`. Downloaded with Kovidh's approval (2026-10-26); pickles scanned before loading: only torch, ultralytics, collections and `set` referenced | track T pilot (`scripts/ball_pilot.py`): ~1.4 s per frame on the CPU (the Apple GPU path hangs) |

None of these is part of the submission pipeline yet (`run.py` needs numpy and pandas only).

## Public facts and lists

| Source | Used for |
|---|---|
| LaLiga ball-in-play figures (~54-56 min per match) and restart durations ([PMC study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10442814/table/T3)) | sanity ranges: dead ball ~40-50% of a match (below) |
| Wikipedia, 2024-25 FC Barcelona and Athletic Club season pages | squad lists for reading commentary (`possession/squads.py`); season-level, not match data |

## Candidates still to look at (plan M17)

Sports-analytics workshop papers (MLSA/ECML, 2024-26) on possession and event detection; SoccerNet
game-state reconstruction; football-trained detectors ([YOLOv11 "soccana"](https://huggingface.co/Ssssad542/soccana),
[RF-DETR ball](https://huggingface.co/build-small-hackathon/futheros-ball-rfdetr)), licences and
training data to be checked.

## Notes on the papers we use

### Vidal-Codina et al. 2022, MIT Sports Lab + FIFA — the closest blueprint
"Automatic event detection in football using tracking data", Sports Engineering.
[arXiv](https://arxiv.org/abs/2202.00804v2) · [full text](https://ar5iv.labs.arxiv.org/html/2202.00804)

A deterministic rule tree, no learning, ~3 minutes per match on one CPU.

- **Possession zone:** a player possesses the ball when it is within **0.5–1 m** of him.
- **Duel zone:** if **two opponents** are within **1 m** of the ball, the frame is a duel, not
  possession. (Our ground truth has no "contested" state: a duel keeps the last team.)
- **Smoothing:** ball positions smoothed with a Savitzky–Golay filter, 7 frames (~0.25 s).
- **Possession gain** requires the ball to change direction or speed while near the player;
  control sequences with neither are discarded as false positives.
- **Dead-ball trigger:** an explicit flag, **or the absence of ball data**, which is how some
  trackers mark dead ball. This is exactly the behaviour we found in our tracker.
- **Restart (set-piece) triggers from player positions**, based on the Laws of the Game:
  - kickoff: all players in their own half, one within a tolerance of the centre mark
  - goal kick: a player inside his own goal area
  - corner: a player near a corner mark
  - throw-in: a player beyond the touchline
  - penalty: one player on the goal line, one at the penalty mark, everyone else outside the box
  - free kick: the default when no other trigger matches
  - confirmed when that player has the ball on the first live frame
- **Accuracy:** corners, throw-ins and goal kicks above 90% precision and recall; free kicks
  were the weakest.

A 2026 follow-up applies the same rules to broadcast-derived tracking and validates events
within 3 s of manual annotations.
[Springer 2026](https://link.springer.com/article/10.1007/s12283-026-00549-4)

### Link & Hoernig 2017 — individual ball possession
"Individual ball possession in soccer", PLOS ONE.
[full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225/)

- Possession starts when the **nearest** player is within a distance threshold.
- A **kick** is a local peak in ball acceleration of **at least 4 m/s²** (smoothed).
- Possession ends when the player is too far from where the ball is **predicted to be 1 s later**.
- **Control** (as opposed to a mere touch) is classified from: duration, mean and variance of
  ball speed and acceleration, ball-to-player distance, and the **number of opponents within
  0.5 m, 1 m … 5 m**.
- **A pass counts for the passer's team until someone else gains the ball**, the same convention
  our ground truth uses for loose balls.
- Reported F-score 0.83 for individual possession on 60 Bundesliga matches.

### Kim et al. 2023 — Ball Radar: the ball's path from the players alone
"Ball trajectory inference from multi-agent sports contexts using set transformer and hierarchical
bi-LSTM", KDD 2023. [arXiv](https://arxiv.org/abs/2306.08206) · [code](https://github.com/pientist/ballradar)

First guesses which player has the ball, then where the ball is, from player movement only. Exactly
what our blackouts need, but heavier: a neural net to train on open data (DFL). Stretch goal.

### FIFA Football Language
[In contest](https://www.fifatrainingcentre.com/en/resources-tools/football-language/in-contest/in-contest.php) ·
[In possession](https://www.fifatrainingcentre.com/en/resources-tools/football-language/in-possession/index.php)

FIFA splits play into *in possession*, *out of possession* and *in contest* (duels, loose balls).
Our challenge folds "in contest" into the last team in possession, so contested moments should
never flip the label on their own.

### Video models (SoccerNet)
[SoccerNet 2025 results](https://arxiv.org/pdf/2508.19182)

Team ball-action spotting and game-state reconstruction from broadcast video. These are
state-of-the-art but need GPUs and training data; not practical on our laptop.

### Hidden Markov models
No paper does exactly "HMM for team possession from tracking". Related latent-state work exists
for tactics and momentum. An HMM/Viterbi decoder over H/A/D is still a natural fit for our
spellF1 metric and is our own design, not a published recipe.
[copula HMM, tactics](https://www.researchgate.net/publication/360163826_Football_tracking_data_a_copula-based_hidden_Markov_model_for_classification_of_tactics_in_football)

---

## Open datasets: notes

| Dataset | What | Labels useful to us | Notes |
|---|---|---|---|
| [DFL / Bassek et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/) | 7 Bundesliga matches, 25 fps tracking + official events, via `floodlight` | **per-frame `BallStatus` (alive/dead) and `BallPossession` (home/away)**: almost our H/A/D | CC-BY 4.0. Clean tracking: we must add our tracker's faults |
| [Metrica sample data](https://github.com/metrica-sports/sample-data) | 3 anonymised games, tracking + synchronised events; Game 3 in the same EPTS format as ours | events (passes, set pieces…) → possession and stoppages | Same provider family as our data. No formal licence; credit requested |
| [SkillCorner open data](https://github.com/SkillCorner/opendata) | 10 A-League 2024/25 matches, broadcast tracking at 10 fps | **per-frame possession** (player and home/away); phases only while the ball is in play | MIT licence. Different frame rate and provider |
| [PFF FC World Cup 2022](https://www.blog.fc.pff.com/blog/enhanced-2022-world-cup-dataset) | 64 matches, broadcast tracking + events | events | Access by form; terms not yet checked |

Decision 2026-10-25: use **DFL first, Metrica Game 3 second**, skip SkillCorner for now (10 fps, no
dead-ball labels). The organisers confirmed (issues #8, #10) that labels and parameter choices on
other matches are allowed, and that choosing parameters against hand labels of BAR-ATH is not.

Uses: set every threshold; run the damage test on ~10 matches instead of 5 minutes; train a
learned model later. Their tracking is cleaner than ours, so we add our tracker's faults on
purpose (drop the ball when it is dead and in short occlusions, swap a keeper's team), with the
amounts taken from whole-match counts of our data (docs/data.md), never from the public 5 minutes.
Caveat: each provider defines possession slightly differently, so treat scores there as a
robustness check, not a copy of our metric.

---

## Local models: options and limits

Measured: **Apple M1, 8 GB RAM, ~24 GB free disk.** Run one model at a time.

| Tool | Size (approx., third-party figures) | Good for | Not good for |
|---|---|---|---|
| Moondream | ~1.5–2 GB | quick scene questions | complex reasoning |
| Qwen3-VL 2B | ~3 GB | scene questions, text on screen | — |
| Gemma 4 E2B | ~4.3 GB on disk | scene questions | tight on 8 GB |
| whisper.cpp | small/base models | transcribing commentary, Metal-accelerated | — |
| a person/ball detector (YOLO-class) | small | finding players and the ball in frames | needs homography + team colour |

Sources: [vision models 2026](https://www.promptquorum.com/power-local-llm/local-vision-models-llava-ollama-2026),
[Ollama on 8 GB](https://webscraft.org/blog/ollama-na-8-gb-ram-yaki-modeli-pratsyuyut-u-2026?lang=en),
[whisper.cpp](https://github.com/ggml-org/whisper.cpp). Speeds on an 8 GB M1 are not published;
we must time a pilot.

A vision-language model answers **scene-level** questions well ("is play stopped?", "is a player
holding the ball over his head for a throw-in?"). It is weak at **precise positions**, so it will
not fix missing players; a detector plus the homography would. Any model in the pipeline must be
deterministic (fixed model version, temperature 0) because the organisers may re-run our code.

---

## Audio: notes

The tactical video carries a full stereo audio track. A first, crude test: the share of sound
energy in the referee-whistle band (3–4.5 kHz), in 0.1 s steps.

| Known whistle moment | Peak band share within ±10 s |
|---|---|
| 1st-half kickoff | in the match's top 1% |
| end of 1st half | in the top 1% |
| 2nd-half kickoff | in the top 1% |
| final whistle | not in the top 1% |

52 separate bursts reach the top 0.1% over the recording. So whistles are audible, but a usable
detector needs more than band energy: a steady tone, a typical duration, and a check against the
public 5 minutes. Published detectors of this kind report ~92% sensitivity and ~80% reliability.
[Amrita 2011](https://www.amrita.edu/publication/automated-referee-whistle-sound-detection-for-extraction-of-highlights-from-sports-video/)

What whistles tell us: fouls, offsides, goals, the ends of halves — the **start** of many
stoppages. Throw-ins, goal kicks and corners are usually not whistled, so audio complements the
tracking rather than replacing it.

**Commentary** (English, confirmed 2026-10-25): the broadcast audio is extracted and the
broadcast timeline is aligned to tactical (docs/data.md), so what remains is transcription (local Whisper)
and turning lines into timed events (a small local LLM). Commentators speak late: hints, not labels.

Audio cross-correlation between the two soundtracks turned out weak (correlation ~0.1; the
broadcast mix is mostly commentary), so the alignment comes from the tracking instead.

---

## Published football facts (web, 2026-10-24)

General football facts, not about our match. Use them as sanity ranges, not targets.

- **Ball in play is only ~54–56 minutes of a LaLiga match.** LaLiga's own figure is ~54 min of
  effective playing time; studies put La Liga at ~55% of match time, with Barcelona among the
  highest (~60%). So dead ball is likely **40–45% of a full match**, far more than the ~20% in
  our calm public 5 minutes. Our ball goes missing on 41% of graded frames, which fits the
  "tracker drops the ball when play stops" pattern.
  [Inside World Football](https://insideworldfootball.com/?p=109070),
  [Olive Press](https://theolivepress.es/spain-news/2023/10/17/footballs-90-minutes-why-are-they-not-equal-across-leagues),
  [Football España](https://www.football-espana.net/2021/10/26/valencia-real-madrid-la-liga)
- **How long restarts stop play (study averages):** throw-in ~12–13 s, goal kick ~15–17 s,
  free kick ~21–23 s, corner ~26–27 s. Most of our medium blackouts (5–20 s) are this length, so
  many of them are probably restarts, not hidden live play.
  [PMC study table](https://pmc.ncbi.nlm.nih.gov/articles/PMC10442814/table/T3)
- **Possessions per match:** one provider (ESPN/TruMedia) counts ~95 per team per match in the
  big five leagues, so ~190 per match. Definitions differ: ours also splits at every stoppage, so
  expect more, but probably a few hundred, not 500+.
  [TruMedia](https://www.trumedianetworks.com/analytics-news/tag/espn)
- **Prior work on exactly our problem:** Vidal-Codina et al. (MIT Sports Lab and FIFA, 2022)
  detect possession from tracking with a deterministic, decision-tree possession model, and also
  recognise dead-ball player configurations, reporting 90%+ event detection.
  [arXiv 2202.00804](https://arxiv.org/abs/2202.00804v2)
- Rule changes from 2026-27 add a 5-second countdown for throw-ins and goal kicks; our match is
  from 2024-25, so restarts there could take longer.
  [Eswatini Observer](https://www.eswatiniobserver.com/fifa-five-second-restart-rule/)

What our football eye sees that the tracking does not say. Each note should be general enough to
become a rule or a feature -- never a label for a specific moment of this match (that would be
hand labelling).

Format: the observation, how sure you are, and how we might detect it in tracking.
