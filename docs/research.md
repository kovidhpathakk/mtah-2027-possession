# Research: what we can use, what others have done, what to build

Compiled 2026-10-25. General research plus aggregate measurements from our own data. No per-moment
detail of the match is recorded here; this file is public.

---

## 1. What we may use in the submission

The rules allow **any algorithm** on **any provided asset**, plus external data and models that the
organisers can inspect. Three different restrictions get confused easily, so they are spelled out:

| Restriction | What it forbids | What it does NOT forbid |
|---|---|---|
| **No hand labels on this match** (RULES.md, updated Oct 22) | A person deciding labels for moments of this match, or hand labels used to train or validate a model | Algorithms that read the video, audio, tracking or tags; watching video to understand the problem |
| **No private ground truth** | The full-match answers | The public 5 minutes |
| **No data to hosted LLMs** (terms) | Sending tracking, video, audio or extracts to Claude, ChatGPT, Gemini, etc. | Running models **locally**; asking hosted LLMs about code, ideas and aggregates |

So every signal below is usable **if an algorithm produces it**. Our own clip notes are for
understanding only; they cannot become labels or a validation set.

### Inventory

| Asset | Status | Usable signals |
|---|---|---|
| Tactical tracking | ✅ verified | player x, y, speed per slot; ball x, y (59.3% of graded frames); team per slot |
| Ball speed column | ⚠ filled on only 8.7% of visible frames | compute from position changes instead |
| Smart Tagging | ✅ verified | 638 phases with team, 59 set pieces with type, timed to the video |
| Homography (tactical) | ✅ 100% valid | pitch ↔ pixel, for overlays and our own detections |
| Tactical video | ✅ 199,319 frames | anything a local vision model or detector can extract |
| **Tactical audio** | ✅ stereo AAC, 48 kHz, whole recording | referee whistles, crowd noise |
| Broadcast tracking + homography | ✅ verified, unsynced | second view; needs alignment |
| Broadcast video + commentary | ❌ deleted locally (14 GB) | re-download if we decide to use it |
| Public answers | ✅ 5 min, 17 possessions | checking correctness, never tuning |
| Labelled **other** matches | allowed in any amount | training and validating learned models (section 3) |

---

## 2. Prior work worth borrowing

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

## 3. Labelled data from other matches (allowed in any amount)

| Dataset | What | Labels useful to us | Notes |
|---|---|---|---|
| [Metrica sample data](https://github.com/metrica-sports/sample-data) | 3 anonymised games, tracking + synchronised events; Game 3 in the same EPTS format as ours | events (passes, set pieces…) → possession and stoppages | Same provider family as our data. No formal licence; credit requested |
| [SkillCorner open data](https://github.com/SkillCorner/opendata) | 10 A-League 2024/25 matches, broadcast tracking at 10 fps | **per-frame possession** (player and home/away); phases only while the ball is in play | MIT licence. Different frame rate and provider |
| [PFF FC World Cup 2022](https://www.blog.fc.pff.com/blog/enhanced-2022-world-cup-dataset) | 64 matches, broadcast tracking + events | events | Access by form; terms not yet checked |

Uses: train or validate a learned model; run the damage test on far more than 17 possessions.
Caveat: each provider defines possession slightly differently, so treat scores there as a
robustness check, not a copy of our metric.

---

## 4. Local models on our machine

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

## 5. Audio

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

**Commentary** needs the broadcast video again (14 GB), an alignment to the tactical timeline
(none is provided; crowd-noise cross-correlation between the two audio tracks is a plausible way),
and transcription. Commentators also speak late. High effort, moderate value: parked.

---

## 6. Errors inside the tracking

- **An Athletic-labelled object in Barça's goal.** On 1,588 frames (152 in the 1st half, 1,436 in
  the 2nd, ~1 minute), with the ball more than 60 m away, an object labelled Athletic stands in
  front of Barça's goal, deeper than every Barça player. This matches a teammate's observation on
  the overlay that Barça's keeper is sometimes labelled Athletic. It is never a duplicate within
  1.5 m of the Barça keeper slot, so it is a mislabelled or ghost object, not a double-count.
  Risk: when the ball comes back, "nearest player" can pick this object and hand Athletic the ball.
- **Too many objects.** 7,102 frames have more than 22 tracked objects; on those, home slots
  average 13.9 (Barça has 11 players), away 10.8. Duplicates are mostly home-labelled.
- **Fixes to try:** treat the deepest object inside a team's own goal area, when no teammate is
  deeper, as that team's keeper whatever its label; cap each team at 11 objects per frame by
  dropping the most implausible ones.

---

## 7. What to build, ranked by value for effort

| # | Idea | From | Effort | Why |
|---|---|---|---|---|
| 1 | **Restart detector from player positions** (kickoff, goal kick, corner, throw-in, penalty) | Vidal-Codina | low | Marks where dead ball ends; covers stoppages with the ball visible |
| 2 | **Possession logic**: possession zone, duel = keep last team, ball smoothing, kick = acceleration peak | Vidal-Codina, Link & Hoernig | low–medium | Replaces "nearest player"; fewer false flips |
| 3 | **Keeper and ghost fixes** | our findings | low | Removes a known source of wrong team |
| 4 | **HMM / Viterbi decoder** over H/A/D | our design | medium | Directly targets spellF1: whole-match consistent possessions |
| 5 | **Whistle detector** on the tactical audio | literature | medium | Marks stoppage starts the tracking misses |
| 6 | **Learned model** trained on SkillCorner / Metrica | open data | medium–high | Learns how signals combine; validated off-match |
| 7 | **Local vision model pilot**: "is play stopped?" once per second | local VLM | medium (overnight run) | Catches stoppages nothing else sees |
| 8 | Broadcast commentary | whisper.cpp | high | Parked |
