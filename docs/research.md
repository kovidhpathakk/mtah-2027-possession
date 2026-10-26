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
| Ball speed column | ❌ filled on 7.8% of visible frames and does not match the ball's movement (corr 0.06) | compute from position changes instead (§7) |
| Smart Tagging | ✅ verified | 638 phases with team, 59 set pieces with type, timed to the video |
| Homography (tactical) | ✅ 100% valid | pitch ↔ pixel, for overlays and our own detections |
| Tactical video | ✅ 199,319 frames | anything a local vision model or detector can extract |
| **Tactical audio** | ✅ stereo AAC, 48 kHz, whole recording | referee whistles, crowd noise |
| Broadcast tracking + homography | ✅ verified, **aligned to tactical** (§7) | second ball view; replay detection |
| Broadcast video + commentary | ✅ re-downloaded 2026-10-25; audio extracted to `data/derived/`; **commentary is in English** | whistles, commentary via local Whisper |
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

## 3. Labelled data from other matches (allowed in any amount)

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
amounts taken from whole-match counts of our data (§7), never from the public 5 minutes.
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

**Commentary** (English, confirmed 2026-10-25): the broadcast audio is extracted and the
broadcast timeline is aligned to tactical (§7), so what remains is transcription (local Whisper)
and turning lines into timed events (a small local LLM). Commentators speak late: hints, not labels.

Audio cross-correlation between the two soundtracks turned out weak (correlation ~0.1; the
broadcast mix is mostly commentary), so the alignment comes from the tracking instead.

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

## 7. Data audit, 2026-10-25

Scripts: `scripts/audit_tracking.py [--source broadcast]`, `scripts/audit_tagging.py`,
`scripts/align_broadcast.py`. All print whole-match counts only.

### Tracking (tactical, graded halves)

| Finding | Number | What it means for us |
|---|---|---|
| **The tracker fills in ball gaps under ~5 s itself** | gaps: 17 under 1 s, **1** of 1–5 s, 132 of 5 s or more (broadcast: 119 of 1–5 s) | Visible ball positions during short occlusions are the tracker's guesses. Every gap that survives is ≥ 5 s, and 132 is close to a match's number of restarts: gaps are mostly stoppages |
| Ball speed column is unusable | corr 0.06 with the ball's real movement | Use speed from positions: p50 5.1, p90 14.3, p99 24.4 m/s (plausible football) |
| Player speed column is right but late | median ratio 0.99 to speed from positions; best match 7 frames (0.28 s) late | Fine for "is the team slow?", too late for timing a kick |
| Filled-in player paths | 6.0% of moving player-seconds are perfectly straight (broadcast 1.9%) | Positions in occlusions are invented; nearest-player there is a guess |
| **A ghost in Barça's box** (corrected after the confirmation checks below: *not* a mislabelled keeper) | deepest object in Barça's box labelled Athletic with the ball > 40 m away: 515 frames (1st half), **2,866** (2nd half) | The Athletic keeper's track ID gets reused for a motionless object in front of Barça's goal. Fix: drop motionless objects, do not relabel |
| Touchline tracks | 33–36 tracks of 10 s or more living on a touchline (~9 object-minutes) | Confirmed harmless: never nearest the ball (below) |
| Extra objects | home > 11 on 8.1% of frames, away > 11 on 4.7% | Cap 11 per team |
| Identity jumps | home 31 one-frame jumps > 3 m, away 0 | Rare; not a priority |
| Ball oddities | 119 one-frame moves > 2 m; 2.1% of visible frames > 2 m off the pitch; 0.6% > 20 m from every object | Small; filter impossible jumps |
| Camera coverage | object count 19–21 wherever play is | The tactical camera sees the whole pitch |
| Ends | teams swap ends at halftime in the coordinates | Normal; work out each team's goal per half |

### Confirmation checks: the broadcast tracker as a second witness

`scripts/audit_confirm.py`. Half of the graded tactical frames are also seen live by the
broadcast, so the weaker findings above can be tested against an independent tracker.

| Question | Result | Verdict |
|---|---|---|
| Is the Athletic object in Barça's box Barça's keeper? | No. The two slots present longest are the two keepers, both labelled correctly (Barça's in Barça's box 89–96% of each half). The object has median speed **0.00 m/s**, stands at the same spot (2nd half: 4.0 m from the goal line, ±1 m) and always belongs to a track that already existed as Athletic: the Athletic keeper's slot, which spends 9–13% of each half in Barça's box | **Corrected**: a ghost reusing the Athletic keeper's ID. What it physically is needs one look at the video |
| Do the touchline tracks hurt us? | 20 stand still (substitutes, staff), 16 other, **none** move with play like an assistant referee; **never** nearest the ball | **Confirmed harmless** |
| Is the referee tracked as a player? | 1 track in 333 behaves like one (follows play 5–25 m from the ball, never touches it), 4 minutes | Not a problem |
| What are the extra objects (12+ in a team)? | duplicates 14–22%, someone on a touchline 25–40%, **unexplained ~50%** | **Open** |
| Does the tactical tracker fill in short ball gaps? | Where the broadcast loses the ball for 1–5 s in live play, tactical always has one, but its path is no smoother than elsewhere (12 cm off a parabola vs 10 cm). Only 87 frames to test | **Open**; leans against "fills with a smooth curve" |
| Do the two trackers agree on team labels? | 98.2% of matched people; 94.9% inside a penalty box | Labels are reliable; boxes are the weak spot |
| Is "clear control", the yardstick used on Smart Tagging, trustworthy? | When both trackers see clear control they agree on the team **97.2%** | **Confirmed**; Smart Tagging percentages are good to a few points |
| Do they agree on where the ball is? | median 0.76 m apart, but **> 5 m apart on 10.5%** of frames where both have a ball (> 15 m on 2.2%) | **New finding**: one of them has a wrong ball on ~1 frame in 10. Which one is open |

### Smart Tagging, checked against the tracking (not against any answers)

- **Team tags are good in open play, weak near the box.** Tagged team in clear control
  (ball ≤ 1.5 m from one player, no opponent within 3 m): Build Up 89%, Progression 87%,
  Transitions 74%, Ball in Final Third 70%, Ball in the Box 62%, Creating Chances 60%, Players in
  the Box 58%. Defending phases mirror these (phases come in pairs, one per team).
- **Set-piece tags are fixed windows**: every one is exactly 35 s (kickoffs 5 s). Starts sit
  ~4–6 s before the ball reappears for throw-ins and corners, ~0 s for goal kicks. Use them as
  "a restart around here", never as exact times.
- **Types are mostly right where checkable**: the ball reappears at a touchline for 65% of
  throw-ins, at the centre spot for 3 of 4 after-goal kickoffs. Corners: the ball is usually
  picked up after the delivery, so only 4/12 reappear at the corner flag.
- **Most long gaps have no set-piece tag**: 42 of 132. Where the ball reappears in the other 90:
  open field 40 (free kicks?), penalty box 21 (a keeper holding the ball, which is live play?),
  touchline 17 (throw-ins), goal area 10 (goal kicks). Smart Tagging lists 5 free kicks; a match
  has ~25 fouls. **It cannot be our main dead-ball source.**
- Goal tags: inconclusive with this check; needs a better one.

### Broadcast ↔ tactical alignment

| | Offset (tactical = broadcast + offset) | Confirmed by |
|---|---|---|
| 1st half | **+4,012 … +4,015** (drifts 3 frames: the broadcast drops the odd frame) | ball and players agree within 1 frame in every window but one |
| halftime splice | broadcast ~84,700 → ~87,100: mostly no live pictures | — |
| 2nd half | **+26,919 … +26,920** | same |

- At the right offset the two trackers' ball positions agree to a median of 0.6–1.0 m; players
  0.3–1.0 m.
- Broadcast frames: 48% live play (mapped), 14% replays and other inserts (players in view but
  matching nothing), 38% close-ups, crowd or studio. Replays follow stoppages: a clue.
- The broadcast video has 164,487 frames against 164,488 tracking records. The file is complete
  (every frame present, end decodes cleanly), so this is in the original.
- Output: `data/derived/broadcast_offsets.npz` (offset per broadcast frame, -1 where not live).

## 8. What to build, ranked by value for effort

Updated after the audit (§7). Every audit finding maps to a row here.

| # | Idea | From | Effort | Why |
|---|---|---|---|---|
| 1 | **Restart detector from player positions** (kickoff, goal kick, corner, throw-in, penalty) | Vidal-Codina | low | Smart Tagging tags only 42 of 132 long gaps; this must find the rest, and decide which team restarts (throw-in tags have no team) |
| 2 | **Gap rule rethink**: every surviving tactical gap is ≥ 5 s, so default to dead and let the restart detector and player speed overrule | audit | low | v1 calls medium gaps live unless players are slow; the audit says most gaps are stoppages |
| 3 | **Clean-up**: drop motionless ghost objects (the one in Barça's box); cap 11 per team; drop one-frame ball jumps > 2 m; where the two trackers' balls disagree by > 5 m, trust neither | audit, confirmation | low | ~3,400 ghost frames, 8% frames with 12+ home objects, 10% ball disagreement |
| 4 | **Possession logic**: possession zone, duel = keep last team, kick = acceleration peak, speed from positions (not the columns) | Vidal-Codina, Link & Hoernig, audit | low–medium | Ball speed column is unusable; player speed column is 0.28 s late |
| 5 | **Smart Tagging as weighted clues**: team tags strong in open play (~88%), weak near the box (~60%); set pieces as "a restart around here" | audit | low | Uses each tag only as far as it was shown to be right |
| 6 | **Broadcast as a second opinion**: its ball where tactical has none; replays as a stoppage clue | alignment | medium | 48% of broadcast frames map to tactical frames |
| 7 | **HMM / Viterbi decoder** over H/A/D | our design | medium | Directly targets spellF1: whole-match consistent possessions |
| 8 | **Whistle detector** on the tactical audio | literature | medium | Marks stoppage starts the tracking misses |
| 9 | **Commentary**: Whisper (English) + small local LLM → timed events | local models | medium | Fouls, free kicks and the team awarded them |
| 10 | **Learned model** trained on DFL / Metrica | open data | medium–high | Learns how clues combine; validated off-match |
| 11 | **Local vision model pilot**: "is play stopped?" once per second | local VLM | medium (overnight run) | Catches stoppages nothing else sees |

### How the audit numbers were verified

- **Code**: `python -m unittest discover tests` runs each measuring function on made-up data
  with a known answer (a known speed, a known straight path, a broadcast track shifted by a known
  offset). All pass.
- **Against published figures**: the data checker reproduces every number DATA.md publishes.
- **Two independent sources agreeing**: speed from positions matches the tracker's own player
  speed column (ratio 0.99, corr 0.93), which also confirms the metre conversion used for the
  ball. The broadcast offset is found separately from the ball and from the players, and they
  agree to a frame.
- **Second witness** (`audit_confirm.py`): the broadcast tracker settled the keeper question
  (a ghost, not the keeper), the touchline tracks (harmless) and the referee (not tracked).
- **Still open**: why there are no 1–5 s ball gaps; what the unexplained extra objects are;
  which tracker is wrong when the two balls disagree. Next: run the audits on DFL and Metrica as a
  control, and, once issue #14 is answered, look at a handful of these moments on video to
  understand them (never to label them).
