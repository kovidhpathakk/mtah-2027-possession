# Progress log

The story of our entry, stage by stage: why we did each thing, what we did, how it works, what it
scored and what it taught us. **Updated after every step.** The organisers' baselines appear only
as a yardstick.

- `docs/README.md`: which file answers which question.

Last updated: 2026-10-26.

---

## At a glance

| | |
|---|---|
| **Best model** | **v5** (new candidate): practice **0.430** on the realistic kit (v4 0.279 on the same damaged copies; baseline 0.229 here vs its real 0.243). Realistic expectation on the real match: around 0.4 (practice sits within ~0.015 of the real score for the baseline) |
| **Safe entry** | `insurance_baseline`, validated, ready to upload; `ours_v4.csv` and `ours_v5.csv` also valid |
| **Working on** | Next: learned stoppages (deep dive 4, now worth up to +0.17), then v5's missing possessions |
| **Waiting for** | organisers' answers to issues #14 and #11 |
| **Docs** | `docs/README.md` maps every file |
| **Deadline** | 17 November 2026 |

## How to read the scores

Every score is the competition's mark, **spellF1**, from 0 (random guessing) to 1 (perfect): roughly
the share of real possessions we got right (right team, about the right start and end), minus a
penalty for invented ones. Example: 4 real possessions; we find 3 and invent 1 → about 0.75.
Ours are around 0.3: we get roughly 1 possession in 3 properly right. The organisers' own
baseline scored 0.243 on the real match.

We get marks from three "exams":

| Exam | What it is | Who marks it | Use |
|---|---|---|---|
| **Final** | our full match, 106 min | only the organisers, at the end | the ranking; we never see it before |
| **Practice** | 8 other matches with full answers, scuffed up to look like our tracker | us, any time | **how we compare models**; one mark = the average of three ways of scuffing |
| **Quiz** | the 5 public minutes of our match, 17 possessions | us | a sanity look only; we may not study for it |

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

Practice = mean spellF1 over 8 matches × 3 damage scenarios on the **realistic kit** (ball
smoothed like ours, from 2026-10-26). Earlier, sharper-ball numbers are in `experiments.md`.

| Version | Practice | Quiz | Final | Dead ball on our match | Status |
|---|---|---|---|---|---|
| *organisers' baseline* (`baseline`) | *0.238* | *0.326* | *0.243* | *32%* | *yardstick* |
| insurance (`insurance_baseline`) | 0.238 | 0.326 | – | 32% | ready to upload |
| v1 (`blackout_v1`) | 0.259 | 0.362 | – | 32% | superseded |
| v2 (`v2`) | 0.271 | 0.371 | – | 40% | superseded |
| v3 (`v3`) | 0.291 | 0.357 | – | 40% | level with v4 on practice |
| v4 (`v4`) | 0.288 | 0.431 | – | 40% | superseded (fallback) |
| **v5** (`v5`) | **0.430** | **0.607** | – | **40%** | **candidate**: learned team call (fresh seeds; v4 0.279 on the same copies) |

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

**What we found** (details in `docs/sources.md`):

| Source | What it gives us | Used so far | Where it goes |
|---|---|---|---|
| **Vidal-Codina et al. 2022** (MIT + FIFA) | Possession zone (ball within ~1 m; two opponents near = a duel). A **missing ball as a dead-ball signal**, which matches our insight. **Restart detection from player positions** (kickoff, corner, throw-in, goal kick, penalty) | its "clear control" distances in our Smart Tagging audit; a first restart-spot check | **the restart detector in v2** |
| **Link & Hoernig 2017** | A kick = a jump in ball acceleration; a pass stays with the passer's team until someone else controls the ball | – | v2 possession logic |
| **Kim et al. 2023 ("Ball Radar")** | Guesses where the ball is from the players' movement alone | – | optional, for gaps |
| **DFL open data** (7 Bundesliga matches) | Answers on every frame, made the same way as ours | the open-data test | everything from now on |
| **Metrica sample Game 3** | Same format as ours, answers from events | the open-data test | everything from now on |
| Local models (Whisper, audio classifier, detector, vision models) | Clues from audio and video, run on the laptop | detector in the video audit | whistles, commentary |

We also asked the organisers two questions (issue #14) and recorded decisions in `docs/plan.md`.

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

### Stage 6 · v2: find the stoppages (Oct 25)

**Why.** v1 called 35% of a match dead against ~43% in reality, missing stoppages where the ball
stays visible and judging gaps on player speed alone.

**What we did.**
1. **Clean-up** (`possession/cleanup.py`): removed frozen objects (the ghost) and a team's 12th+
   object. Correct, but no score change on its own.
2. **Measured which clues mark a stoppage**, on the practice matches only, following
   Vidal-Codina (a missing ball and restart positions mark dead ball):
   - ball visible but standing still for 2 s or more: catches 96% of dead frames, 0.6% false alarms
   - ball more than 1 m outside the lines: 99% dead
   - ball gap with the players slow: 98–99% dead
   - ball gap that starts or ends at a corner, a touchline or outside the lines: 79–100% dead
   - a gap's length on its own: a weak clue
3. **Built v2** (`possession/stoppages.py`) from those clues. Dead ball when the ball is out, or
   still for 2 s, or in a gap of 1 s+ with slow players, at an edge, or lasting 20 s+. "Slow" is
   relative to each match's own typical speed, because trackers differ. Otherwise the team comes
   from the nearest-player vote, as before.
4. **Found and fixed a flicker problem.** A ball lying near a line jumps in and out by
   centimetres, and each "in" frame became a fake one-frame possession: 2,000 in one match. A
   tidy-up step (short live islands inside a stoppage become dead; tiny dead blips become live)
   fixed it.
5. **Made the practice matches more realistic.** The added ball noise now drifts smoothly, like
   real tracking errors, instead of jumping every frame.
6. **Tried and dropped** "don't let the vote cross a stoppage": slightly worse everywhere.

**Result.** Practice 0.31 (v1 0.29), better in every scenario; dead ball 42% against 43% in the
answers. On our match: 40% dead, quiz 0.371, frame accuracy 0.66 (v1 0.52). The submission file
is valid and rebuilds byte for byte.

**Learned.** Getting the stoppages right is worth more than cleaning the tracking. The "still
ball" clue helps hugely when the tracker keeps the ball in view (practice clean 0.35 → 0.45), but
our tracker usually drops it, so on our match it helps less.

---

### Stage 7 · Use every source, precisely (from Oct 26)

**Why.** Each source we have (tracking, broadcast, Smart Tagging, commentary, audio, video) knows
something the others don't. The goal is to make each one as exact as possible, then let one model
weigh them all.

**The key idea: imitation clues for testing.** Commentary, Smart Tagging, whistles and the
broadcast exist only for our match, so the practice matches cannot show whether they help. But
the practice matches come with official event lists (throw-ins, fouls, free kicks, goals). From
those we make *imitation* commentary and Smart Tagging, with the real ones' flaws measured on our
match (late, incomplete, 35 s windows). Then the practice exams can test whether the model uses
each source well.

**Who sees what.** Kovidh may watch the video to understand it (RULES.md). Claude may not
(FAQ.md: no videos or extracts to a hosted LLM), so Claude works through local tools that print
counts: the detector, Whisper, a local LLM, and clips that Kovidh watches and describes in general
terms.

| Step | Status | Result |
|---|---|---|
| **Precise tracking** (`possession/precise.py`): clean-up, ball blips, Savitzky-Golay smoothing (Vidal-Codina), broadcast ball where tactical has none | ✅ done | ball known on 61.8% of graded frames (was 59.3%); score neutral on practice and on our match: **the tracking is about as precise as it gets; the gains are in interpreting it** |
| **Commentary transcription** (`scripts/transcribe.py`): Whisper large-v3-turbo via whisper.cpp, run locally, pinned model, repeatable output | first full run **failed**: Whisper looped (5 repeated lines = 86% of the transcript, 3% naming a player). Fixed with speech detection (Silero VAD), no carried-over text and no non-speech tokens: 10-min test gives real lines, 26% naming a team or player, English confirmed, still identical on rerun. Full re-run in progress | – |
| **Commentary analyst** (`scripts/commentary_llm.py`): a local LLM (Ollama, qwen3:4b) labels every line: who has the ball, live or stopped, which event; checked against the tracking at different commentary delays | ✅ done | **commentary does not track possession**: the AI's team calls and the player names alike are at chance (55–58% vs 52–57%). Commentators talk about players in general and name Barça 3× as often as Athletic. Parked as a possession clue; may still mark rare long stoppages |
| Better ball-gap rules (your idea): new clue "how far the ball moved while missing" | ✅ done | a ball coming back within 3 m of where it vanished = 98% stoppage; gaps classified 83% right (was 74%), **but the score didn't move** |
| **Where are the points lost?** What-if test on the practice matches | ✅ done | perfect stoppages would give 0.40; **perfect team calls in live play would give 0.72**. The team call is the biggest lever, so the possession paper (Link & Hoernig) goes next |
| **v3: possession by control** (Link & Hoernig, Vidal-Codina). A team gains the ball when its player keeps it within 1 m for 3 frames with no opponent within 1 m; it keeps the ball through passes, loose balls and duels; changes land on the exact frame, with no smoothing | ✅ done | **practice 0.311 → 0.377, better in all 48 runs**. The best distances found were the papers' own. Our match: fewer fake short possessions, Smart Tagging agreement in line with the truth's. Quiz 0.357 vs 0.371: within its noise |
| Precise Smart Tagging: snap each set-piece window to the actual restart, add the taker's team, trust per tag type | next | – |
| Commentary → events: rules first (keywords, squad names), a local LLM second | after transcription | – |
| Imitation clues on the practice matches, from their event lists | planned | – |
| Who restarts | planned | – |
| **Decoder**: one model weighing all clues, each source's trust learned on the practice matches | planned | – |
| Whistle detector | planned | – |
| Local video model on the moments the decoder is unsure about, overnight | planned | – |

### Stage 8 · Deep dives (from Oct 26)

**Why.** Many components had been tried quickly; some ideas were dismissed after one weak
attempt and Smart Tagging went unused. From here, one problem at a time, ordered by points at
stake, with real cases looked at before any fix (`docs/deep-dives/`).

**Also done:** the practice damage gained the two faults it lacked (wrong team labels, large
ball errors). The organisers' baseline now scores 0.248 on practice against 0.243 on the real
match, so practice scores are close to real scores. The commentary was tested properly (it does
not track possession; it may mark rare long stoppages) and two vision-model pilots were run (the
wide view is illegible to a small model; a stronger model ran out of memory, then filled the disk
with swap).

**Deep dive 1: the team call while the ball travels** (`docs/deep-dives/01-ball-travelling.md`)
1. Anatomy: at 2,351 true changes of possession, v3 missed 23% and invented 852.
2. Real cases, drawn top-down from the practice tracking (`scripts/case_viewer.py`): three
   patterns, namely fast passes flying past an opponent, quick one-touch interceptions, and duels
   and pressing. Two of four inferred causes were wrong until the plays were looked at.
3. The papers: possession changes when the ball's speed or direction changes by a player
   (Vidal-Codina; Link & Hoernig).
4. **Touch rule:** control by a touch (≥ 7 m/s change in the ball's velocity) or a slow hold; a ball
   passing by never counts. A firmer duel rule was tried and dropped (it blocks real tackles).
5. **v4: practice 0.352 → 0.410, better in all 48 runs; quiz 0.431; possessions per minute on our
   match now match the truth's (3.45 vs 3.40).**
6. Smart Tagging's team tags tried where v4 is stale: no gain (tags overwrite short possessions).
7. **Our tracker's ball turned out heavily smoothed** (sharp velocity changes 1.9% of live frames
   vs 9-13% in DFL). With the practice damage smoothing the ball the same way, **the touch rule's
   gain disappeared** (v3 0.291, v4 0.288): it had come from practice balls sharper than ours. The
   baseline now scores 0.238 on practice vs 0.243 for real, so this is the most trustworthy test
   yet, and it puts us at ~0.29. v4 stays the candidate on our match's checks. The dive now turns
   to models trained on the practice matches and longer-window cues that suit a smoothed ball.
8. **Where the points are now** (realistic test): perfect stoppages would add +0.09, perfect team
   calls in live play +0.42. Three quarters of the team errors happen while the ball travels
   between players (66% of live play, v4 wrong 21% there).
9. **v5: a team call learned from the practice matches** (`possession/learned.py`). Instead of
   one more hand-made rule, a model weighs 59 clues per frame: who is near the ball, who it came
   from and goes to, v3/v4's control events, the ball's movement, and the shape of both teams. It
   learns from the 8 practice matches, damaged to look like our tracker, and never sees our
   match; each practice match is scored by a model trained on the other seven. A decoder then
   turns frame answers into whole possessions, paying a price for every change of team.
   **Practice 0.279 → 0.430 on fresh damage, better in 48 of 48 runs**; team right on 89.5% of live
   frames (v4 81.0%), including 84% while the ball is missing (v4 71%). On our match: Smart
   Tagging agreement up (76/82% vs 74/78%), fewer flickers (possessions under 1 s: 3% vs 11%),
   damage test 0.440 vs 0.329, quiz 0.607 (noted, never tuned on: its noise band is ~0.37 and
   the 5 minutes are easy, ball missing 12% vs 41% over the match). Rebuilt from nothing, the
   submission is byte-identical.
   **What it learned:** shuffling the team-shape clues costs 17 points of accuracy, everything else
   2-5. The team with the ball pushes up and spreads out; the other team drops goal-side of the
   ball. That stays readable when the ball is smoothed or missing, our tracker's weak spots.
   **Watch:** v5 makes fewer possessions than the truth (practice 3.4 vs 4.5 a minute; our match
   2.8 vs ~3.4).
10. **Where the points are after v5:** perfect stoppages would now add **+0.17** (they added +0.09
   on top of v4: better team calls stop hiding stoppage errors), a perfect team call +0.29. The
   missing possessions are a team-call matter. So the stoppages come next, with the same machinery
   as v5: a model trained on the practice matches instead of hand rules.

### Stage 9 · Can we make better tracking from the video? (Oct 26)

**Why.** The touch rule had worked on a sharp ball and failed only because our tracker's ball is
smoothed. A ball track of our own, made from the video by a ball detector, could be sharp and could
fill the gaps. RULES.md allows improving or replacing the tracking.

**How.** Ball detectors run locally on the video; Claude sees only counts. Each was checked the same
way: on frames where the tracker has a ball, does the detector find a ball within 2 m of it? For a
ball track of our own it would need to be right about 9 times in 10.

| Detector | Video | Ball within 2 m |
|---|---|---|
| Roboflow football ball model (YOLOv8) | tactical, whole frame / zoomed window | 50% / 55% |
| same | broadcast (ball several times larger) | 51%; finds a ball in 80% of the tracker's gaps, 57% confidently |
| WASB (a research tracker built for small fast balls, trained on fixed wide football cameras) | tactical, best window and threshold | 60% |

**Learned.** Off-the-shelf detectors find the ball about half the time on our wide camera: far from
the ~90% needed, so our own ball track is parked. The broadcast-detected ball moves more sharply
than the tracker's (9% vs 4% sharp changes), which supports the smoothing finding. What remains:
combining all ball sources in one filter where a detector is confident (T12), and fine-tuning on
public football video (T14) or on our video with algorithm-made labels (T15, organisers first).
The main effort returns to interpreting the tracking we have.

## Next steps

See `docs/plan.md` (order of work, deep dives, every idea with its status).
