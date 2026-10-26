# External sources: what we use, how, and what is still unused

Every outside source behind our entry. The organisers require that they can access everything we
use and that the technical document explains it (RULES.md). Last updated: 2026-10-26.

## Research papers

| Paper | What it gives | How we use it | Where |
|---|---|---|---|
| **Vidal-Codina, Evans, El Fakir, Billingham (2022).** "Automatic event detection in football using tracking data." *Sports Engineering* 25:18. [arXiv 2202.00804](https://arxiv.org/abs/2202.00804) | 1 m possession zone; two opponents within 1 m = a duel, not possession; a gain of possession needs the ball to change speed or direction; a missing ball and restart positions mark dead ball; Savitzky-Golay ball smoothing | **In the model**: stoppage rules (v2), the 1 m zone and duel rule (v3), touch logic (v4); smoothing in `precise.py` (tested, neutral) | `stoppages.py`, `control.py`, `precise.py` |
| **Link, Hoernig (2017).** "Individual ball possession in soccer." *PLOS ONE* 12(7). [PMC5503225](https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225/) | possession needs control, not a touch-by; a touch is a sudden change in the ball's motion; a pass stays with the passer's team until someone else controls it | **In the model**: the hold-through-passes logic (v3), touch rule (v4) | `control.py` |
| Kim et al. (2023). "Ball trajectory inference from multi-agent sports contexts using set transformer and hierarchical bi-LSTM" (Ball Radar). KDD. [arXiv 2306.08206](https://arxiv.org/abs/2306.08206) | where the ball is, from player movement alone | **not yet**: planned for live play with the ball missing (deep dive 3) | backlog M11 |
| Borghesi et al. (2023). "Using temporal convolutional networks to estimate ball possession in soccer games." *Expert Systems with Applications*. [link](https://iris.polito.it/handle/11583/2976470) | a model trained to read possession from tracking | **not yet**: planned learned model trained on DFL (deep dive 1/3) | backlog M15 |
| PathCRF (2026). "Ball-free soccer event detection." KDD'26. [arXiv 2602.12080](https://arxiv.org/html/2602.12080) | possession and events without the ball, decoded with Viterbi | **not yet**: ideas for the decoder and for ball-missing live play | backlog M16 |
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

None of these is part of the submission pipeline yet (`run.py` needs numpy and pandas only).

## Public facts and lists

| Source | Used for |
|---|---|
| LaLiga ball-in-play figures (~54-56 min per match) and restart durations ([PMC study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10442814/table/T3)) | sanity ranges: dead ball ~40-50% of a match (`football-notes.md`) |
| Wikipedia, 2024-25 FC Barcelona and Athletic Club season pages | squad lists for reading commentary (`possession/squads.py`); season-level, not match data |

## Candidates still to look at (backlog M17)

Sports-analytics workshop papers (MLSA/ECML, 2024-26) on possession and event detection; SoccerNet
game-state reconstruction; football-trained detectors ([YOLOv11 "soccana"](https://huggingface.co/Ssssad542/soccana),
[RF-DETR ball](https://huggingface.co/build-small-hackathon/futheros-ball-rfdetr)), licences and
training data to be checked.
