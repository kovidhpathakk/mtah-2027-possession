# Progress log

The story of our entry, stage by stage: why we did each thing, what we did, how it works, what it
scored and what it taught us. **Updated after every step.** The organisers' baselines appear only
as a yardstick.

- `docs/status.md`: a one-page "start here" summary.
- `docs/experiments.md`: one entry per experiment, with full numbers.
- `docs/research.md`: papers, datasets, models and the data audit in detail.

Last updated: 2026-10-25.

---

## At a glance

| | |
|---|---|
| **Best model** | **v1** (`blackout_v1`): open-data test 0.23–0.35, public 0.362. Baseline: 0.21–0.32, 0.326 |
| **Safe entry** | `insurance_baseline`, validated, ready to upload |
| **Working on** | v2: restart detector |
| **Waiting for** | organisers' answers to issues #14 and #11 |
| **Deadline** | 17 November 2026 |

## Words used here

| Word | Meaning |
|---|---|
| **H / A / D / X** | Barça has the ball / Athletic has it / dead ball / no answer |
| **possession** | an unbroken run of H, or of A |
| **spellF1** | the ranking score: how many true possessions we found, with the right team and roughly the right start and end. 0 = random, 1 = perfect, differences under ~0.04 are noise |
| **ball gap** | a stretch of frames where the tracker has no ball position |
| **public 5 min** | the only part of our match with published answers (17 possessions). A sanity check only; we may not tune on it |
| **damage test** | the public 5 minutes with the ball deleted the way our tracker loses it, run 100 times |
| **open-data test** | 8 other matches with answers on every frame, damaged to look like our tracker. Where we compare methods since Stage 5 |

---

## Model versions

| Version | Open-data test (stoppage / mixed / random) | Public 5 min | Real full match | Status |
|---|---|---|---|---|
| *organisers' baseline (yardstick)* | *0.32 / 0.25 / 0.21* | *0.326* | *0.243* | *the floor to beat* |
| `insurance_baseline` | as baseline | 0.326 | – | ready to upload |
| **`blackout_v1`** | **0.35 / 0.28 / 0.23** | **0.362** | – | **current best** |
| `blackout_v1_clean` | 0.35 / 0.27 / 0.22 | – | – | no gain; its clean-up goes into v2 |
| v2 | – | – | – | in progress |

---

## The story so far

### Stage 0 · Set up safely (Oct 22–23)

**Why.** The repository must be public, but the match data may never leave the laptop or reach a
hosted AI.

**What we did.**
- A data checker that confirms our copy matches every figure the organisers published.
- A leak guard that runs before every commit and in CI, blocking match data from entering git.
- Rules for Claude (CLAUDE.md): it never sees rows, frames or video, only counts that scripts print.

### Stage 1 · Measure before building (Oct 23)

**Why.** We have no answers for the full match, so we needed ways to tell whether a change helps.

**What we did.**
- **Damage test.** The public 5 minutes are unusually easy (ball missing 12% of the time against
  41% in the full match), so it deletes the ball the way our tracker does and re-scores, 100 times.
- **Sanity report.** Checks a full-match prediction for football sense: how many possessions,
  how long, how much dead ball, agreement with Smart Tagging.
- **Insurance submission.** The organisers' baseline plus two safe match rules: X outside the
  halves, and D between the start of the 2nd half and its kickoff.

**Learned.** The damage test tracks the real full-match scores better than the raw 5 minutes,
but still over-rewards heavy smoothing.

### Stage 2 · Understand the ball gaps and build v1 (Oct 23–24)

**Why.** The ball is missing on 41% of graded frames, and the baseline calls every one of them
dead ball. That splits real possessions wherever the ball is merely hidden.

**What we did.**
1. **Built a clip tool** (`gap_clips.py`) that cuts local clips of the longest ball gaps, with a
   clock showing when the ball returns.
2. **Kovidh watched the 15 longest gaps** (~17 minutes of video, 39% of all missing-ball time),
   to understand them, not to label them.
3. **The key insight: the tracker drops the ball when play stops, even when the ball is plainly
   visible**, and picks it up at the restart. The long gaps were goals, fouls, free kicks, a
   penalty, a drinks break, goal kicks and corners. A few were live play hidden from the camera.
4. **Checked the insight with counts we are allowed to measure:**
   - gaps over 20 s: 44 of them, 67% of all missing-ball time
   - average player speed: 2.16 m/s with the ball visible, 1.53 m/s in short gaps, 0.99 m/s in
     gaps over 20 s (people walk during stoppages)
   - gaps ending within 5 s of a tagged set piece: 25% of long gaps, 5–9% of shorter ones
5. **Designed v1 from those numbers:**
   - ball visible → team of the nearest player, majority vote over ±2 s (the baseline's best)
   - ball gap of 20 s or more → **D**
   - ball gap of 2–20 s → **D only if the players are slow** (team speed under 1.0 m/s, the
     speed that 95% of live play exceeds); otherwise **keep the last team**
   - match rules as in the insurance submission

**Result.** Public 0.362 against the baseline's 0.326; damage test 0.277 against 0.226.

**Learned.**
- v1 calls too little dead ball. Web research put ball-in-play in LaLiga at ~54–56 minutes, so
  dead ball is ~40–45% of a match, and v1 calls ~32–35%.
- Restarts take 12–27 s on average, so many medium gaps are restarts. v1's "dead only if slow"
  rule is probably too strict.
- The tracker's ball-speed column is nearly empty; speed has to be computed from positions.

### Stage 3 · Research (Oct 24–25)

**Why.** Find what others have already solved, and what extra data and tools the rules allow.

**What we found** (details in `research.md`):

| Source | What it gives us | Used so far | Where it goes |
|---|---|---|---|
| **Vidal-Codina et al. 2022** (MIT + FIFA) | Possession zone (ball within ~1 m; two opponents near = a duel). A **missing ball as a dead-ball signal**, which matches our insight. **Restart detection from player positions** (kickoff, corner, throw-in, goal kick, penalty) | its "clear control" distances in our Smart Tagging audit; a first restart-spot check | **the restart detector in v2** |
| **Link & Hoernig 2017** | A kick = a jump in ball acceleration; a pass stays with the passer's team until someone else controls the ball | – | v2 possession logic |
| **Kim et al. 2023 ("Ball Radar")** | Guesses where the ball is from the players' movement alone | – | optional, for gaps |
| **DFL open data** (7 Bundesliga matches) | Answers on every frame, made the same way as ours | the open-data test | everything from now on |
| **Metrica sample Game 3** | Same format as ours, answers from events | the open-data test | everything from now on |
| Local models (Whisper, audio classifier, detector, vision models) | Clues from audio and video, run on the laptop | detector in the video audit | whistles, commentary |

We also asked the organisers two questions (issue #14) and recorded decisions in `status.md`.

### Stage 4 · Audit the data (Oct 25)

**Why.** Before building v2 on the tracking, know exactly what is wrong with it.

**What we did, and what each check found:**

| Check | How | Main findings |
|---|---|---|
| Tracking audit | counts over the whole match | ball gaps are 5 s+ or under 1 s, almost never 1–5 s; 12+ objects in a team on 5–8% of frames; fewer than 18 on 9%; speed column 0.28 s late; ball-speed column unusable |
| Smart Tagging audit | tags compared with the tracking | team tags ~88% right in open play, ~60% near the box; set-piece tags are fixed 35 s windows and cover only 42 of 132 long gaps |
| Broadcast | re-downloaded, aligned frame by frame using ball and player positions; audio extracted; commentary confirmed English | a second, independent tracker for half the match |
| Second witness | weak findings tested against the broadcast tracker | the "keeper mix-up" was wrong: it is a ghost; touchline tracks are harmless |
| Control | the same audit on 8 clean matches | real faults separated from the audit's own false alarms |
| Video | a detector run on the laptop, 420 sampled frames | ghost is not a person; a ball is visible in ~2/3 of gap frames; the tactical ball is right twice as often as the broadcast one |
| Tests | each measuring function run on made-up data with a known answer | 10 tests, all pass |

**Learned.**
- **Ball gaps are mostly stoppages**, so the model should treat them as dead unless the evidence
  says live.
- The "ghost" in Barça's box is the Athletic keeper's track frozen for ~10 minutes across
  half-time.
- One earlier guess ("6% of player movement is filled in") was mostly a false alarm.

### Stage 5 · A test we can trust (Oct 25)

**Why.** The public 5 minutes are too short to rank methods and may not be tuned on.

**What we did.**
1. Loaded the 8 open matches into the same format as ours, with answers on every frame.
2. Built a **fault kit** that damages them to look like our tracker, at our measured rates: ball
   removed at stoppages (three ways of placing the gaps, since we can't know which is exact),
   players dropped, extra objects, a frozen ghost, lagged speeds.
3. **Checked the test against reality:** the organisers' four baselines score close to their
   published real full-match scores, and the test picks the right best one. The old 5-minute
   test picked the wrong one.

**Result.** v1 beats the baseline in every scenario, by 0.01–0.03. Every method calls too little
dead ball (27–39% against 43%).

### Stage 6 · v2, in progress (from Oct 25)

| Step | Status | Result |
|---|---|---|
| Clean-up: remove frozen objects and a team's 12th+ object | ✅ done | correct, but no score change: these objects rarely stand by the ball |
| **Restart detector** (Vidal-Codina) | **next** | – |
| Gap rule: dead unless the evidence says live | planned | – |
| Possession logic (Link & Hoernig) | planned | – |

---

## Next steps, in order

| # | Step | Why | Done when |
|---|---|---|---|
| 1 | **Restart detector**: throw-ins, corners, goal kicks, kickoffs from player and ball positions | The main fix for too little dead ball; also tells which team restarts | beats v1 in all three scenarios |
| 2 | **Gap rule rethink** | Gaps are mostly stoppages | dead share moves towards ~43% without losing score |
| 3 | **Possession logic** | Fewer false possessions | beats step 2 |
| 4 | **Decoder** (HMM/Viterbi): the most believable H/A/D sequence for the whole match | Targets spellF1 directly | beats v2 |
| 5 | **Whistle detector** on the audio | Marks stoppages the tracking misses | helps, or dropped |
| 6 | **Commentary**: Whisper + a small local LLM → timed hints | Fouls, free kicks and who gets them | helps, or dropped |
| 7 | Optional: vision model "is play stopped?", Ball Radar | Catch what nothing else sees | if time allows |
| 8 | **Technical document** + final submission | Required deliverables | by 17 November |

## Open questions

- Organisers (#14, #11): may we save model outputs in the repo for exact reproducibility, and turn
  what we saw in clips into general rules?
- Why the tactical data has almost no 1–5 s ball gaps.
- Which people the extra objects are (officials? substitutes?). Low impact.
