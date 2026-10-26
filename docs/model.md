# How our model works (v5)

Plain-language description of the current best model, every rule and setting with where it came
from. Kept in step with the code (`possession/`); the technical document will be built from it.
Last updated: 2026-10-26 (v5).

    python scripts/fetch_open_data.py   # once: the practice matches v5 learns from
    python run.py                       # builds evaluation/results/ours_v5.csv (the submission)

## The job

For each of the 199,319 frames of the tactical video (25 per second), say `H` (Barça has the
ball), `A` (Athletic has it), `D` (dead ball) or `X` (outside the two halves). The ranking score,
spellF1, rewards getting whole possessions right: right team, roughly right start and end.

## The pipeline, in five steps

### 1. Read the tracking (`possession/tracking.py`)

The provided tracking gives, per frame, the position of every tracked person (with their team)
and of the ball, which is missing on 41% of frames.

### 2. Clean it (`possession/cleanup.py`)

| Rule | Why |
|---|---|
| Remove an object whose position does not change at all for 10 s or more | A frozen leftover track: the "ghost" in front of Barça's goal is the Athletic keeper's track frozen across half-time (data audit; the video detector found no person there) |
| When a team has 12+ objects, remove first a near-duplicate (within 1.5 m of a teammate), then one on a touchline or off the pitch | Double-counted players and substitutes/staff tracked as players (data audit) |

### 3. Find the stoppages (`possession/stoppages.py`, from v2)

A frame is **dead ball** when any of these holds:

| Rule | Example | Evidence (practice matches) |
|---|---|---|
| The ball is visible and more than **1 m outside the lines** | ball by the corner flag for a corner | 99% of such frames are dead |
| The ball is visible and **has not moved for 2 s** (under 0.5 m/s) | ball placed for a free kick | catches 96% of dead frames with the ball in view, 0.6% false alarms |
| The ball is **missing for 1 s or more** and any of: the players are **slow** (average speed under 65% of the match's typical speed); the ball vanished or came back **beyond a line, at a corner or by a touchline**; the gap lasts **20 s or more** | the tracker drops the ball when it goes out for a throw-in, players walk | slow players: 98-99% dead; at an edge: 79-100% dead; long gaps were stoppages in Kovidh's review of the 15 longest gaps |

Then a **tidy-up**: a live stretch shorter than 2 s inside a stoppage becomes dead, and a dead
blip shorter than 0.5 s becomes live. (A ball resting near a line flickers in and out by
centimetres; without this, one practice match got 2,000 fake one-frame possessions.)

The whole idea that a missing ball and restart positions mark dead ball follows Vidal-Codina et
al. 2022.

### 4. Decide which team has the ball in live play (`possession/learned.py`, v5)

**Rule of the game (CHALLENGE.md):** possession changes only when the other team gains
*controlled* possession; contested and loose balls stay with the last team.

v3 and v4 decided this with hand-made rules (4a). v5 keeps those rules as **clues** and lets a
model, trained on the 8 practice matches, weigh them together with about 50 other clues (4b), then
turns its frame-by-frame answers into whole possessions (4c).

#### 4a. The control rules (`possession/control.py`, v3 and v4), now clues

1. Find each team's nearest player to the ball.
2. A team is a **candidate** if its nearest player is within **1 m** of the ball and the other
   team's nearest player is **not** within 1 m (otherwise it is a duel, and nothing changes).
3. The candidate team **gains control** at that frame if either:
   - **touch**: the ball's velocity changes by at least **7 m/s** between 0.12 s before and 0.12 s
     after, however brief; or
   - **hold**: the candidate keeps the ball within reach for **3 frames** or more while the ball
     moves slower than **6 m/s**.
4. The team that last gained control **keeps the ball** until the other team gains control.

Sources: the 1 m zone and "a duel is not possession" are Vidal-Codina et al. 2022; "a touch is a
sudden change in the ball's motion" and "a pass stays with the passer's team" are Link & Hoernig
2017. On their own these rules score 0.28-0.29 on practice: our tracker's ball is smoothed, so
touches are blurred, and a third of the ball positions are missing.

#### 4b. The learned team call: 59 clues per frame

| Family | Clues | Why it helps |
|---|---|---|
| Near | each team's nearest and second-nearest player to the ball; players within 3 m | who is on the ball now |
| Before and after | each team's closest approach to the ball over the last and the next 0.24, 0.5, 1 and 2 s; which team was nearer over ±0.5 s and ±2 s | who the ball came from and who it goes to: still visible when the ball path is smoothed |
| Control | team and distance (frames) of the last and the next control event (both rules of 4a) in the same live stretch; v3's and v4's own answers; the nearest player's team; the ±2 s vote | the rules' knowledge, kept |
| Ball | position along the pitch (towards the goal this team attacks), distance from the centre line, speed, forward speed, change of velocity now and over ±0.5 s, time since and until the ball is seen | a fast forward ball is usually a pass by the team attacking that way |
| Team shape | each team's average position along the pitch, spread (length and width), speed, how it moves forward or back, and the **share of its players goal-side of the ball** | the team with the ball pushes up and spreads out; the team without it drops behind the ball. Works even when the ball is missing |

**The model:** gradient-boosted decision trees (scikit-learn's HistGradientBoostingClassifier, 200
trees, fixed seed). It learns from 8 open-data matches (7 Bundesliga matches from DFL, 1 from
Metrica) whose answers are known on every frame. Their tracking is first **damaged** the way our
tracker is (missing ball, smoothed ball, wrong team labels, missing players, ghost objects), so the
model learns to read tracking that looks like ours. About 620,000 frames, both teams' views.

**Fairness between teams:** every clue is computed once from Barça's point of view and once from
Athletic's, and the answer averages the two. The model therefore cannot learn "the home team has
the ball more".

**Illustration** (made up, to show how clues combine). A long Barça pass flies towards an
Athletic centre-back; the ball is missing for 1 s. v4 had no control event, so it kept Barça. v5
sees that in the next second the centre-back is the closest player and Athletic's players stop
dropping back and push up: it gives Athletic the ball from about the moment the centre-back
reaches it.

#### 4c. From frame answers to possessions

The model gives a probability per frame ("Barça has it: 0.83"). Taking the likelier team each frame
would flicker, and every flicker costs a whole possession in spellF1. So, per live stretch, a
**Viterbi pass** (a standard way to find the best sequence) picks the team sequence that best fits
the probabilities while paying a fixed price for every change of team (switch cost 10, in
log-probability; 5 and 10 tie on practice, 20 is worse).

**Never our match:** the model sees only the practice matches. When `open_test.py` scores a
practice match, that match's labels come from a model trained on the other seven.

### 5. Match rules (`possession/polish.py`)

`X` on every frame outside the two graded halves; `D` from the start of the graded second half to
its kickoff (frame 113,742).

## What the model does *not* use yet

Smart Tagging, the video, the audio (whistles), the commentary and the broadcast tracking. Each
was audited; their use is planned inside the deep dives (`docs/plan.md`, "Data use"). Stoppages
(step 3) are still hand-made rules; a learned stoppage model is deep dive 4.

## How good it is

| Test | v5 | v4 |
|---|---|---|
| Practice matches, realistic damage (8 other matches, fresh damage seeds; the organisers' baseline scores 0.229 here, 0.243 on the real match) | **0.430** | 0.279 |
| Team right on live frames, practice | 89.5% | 81.0% |
| Public 5 minutes (17 possessions; a sanity check only, noise band ~0.33) | 0.607 | 0.431 |
| Our match: Smart Tagging agreement, attacking / defending phases | 76% / 82% | 74% / 78% |
| Our match: possessions per minute / shorter than 1 s | 2.82 / 3% | 3.45 / 11% |

**Caveats.** (1) v5 makes fewer possessions than the truth: on practice 3.4 a minute against 4.5
(v4: 3.5), and on our match 2.8 against ~3.4 in the public 5 minutes. Merging is cheaper in spellF1
than flicker, but it is the next thing to look at. (2) The model is only as good as the practice
damage is realistic; the realism report (`scripts/realism_report.py`) checks 18 measures. On our
match the model is as sure of itself as on practice (mean confidence 0.90), a sign it is not out of
its depth. (3) Needs the open data (`scripts/fetch_open_data.py`) and scikit-learn
(`requirements-lock.txt`); retraining from nothing gives a byte-identical submission.

## Version history

Practice scores on the realistic kit (ball smoothed like ours).

| Version | Idea | Practice |
|---|---|---|
| organisers' baseline | team of the nearest player to the ball, majority vote over ±2 s; missing ball = dead | 0.238 |
| v1 (`blackout_v1`) | baseline + ball gaps: 20 s+ = dead, 2-20 s dead only if players slow, else keep the team (from Kovidh's review of the 15 longest gaps) | 0.259 |
| v2 | stoppages rebuilt from measurements (step 3) + clean-up (step 2) | 0.271 |
| v3 | team by control: 1 m, no duel, held 3 frames (step 4, first version) | 0.291 |
| v4 | + touch rule and pass-by check (4a) | 0.288 (better than v3 on our match's checks) |
| **v5** | v4's stoppages + **learned team call** (4b, 4c): 59 clues, trees trained on the damaged practice matches, Viterbi decoding | **0.430** (fresh seeds; v4 0.279 on the same copies) |
