# How our model works (v4)

Plain-language description of the current best model, every rule and setting with where it came
from. Kept in step with the code (`possession/`); the technical document will be built from it.
Last updated: 2026-10-26.

    python run.py            # builds evaluation/results/ours_v4.csv from data/ (the submission)

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

### 4. Decide which team has the ball in live play (`possession/control.py`, from v3 and v4)

**Rule of the game (CHALLENGE.md):** possession changes only when the other team gains
*controlled* possession; contested and loose balls stay with the last team.

**How we detect "gains control"**, at every frame with the ball in view:

1. Find each team's nearest player to the ball.
2. A team is a **candidate** if its nearest player is within **1 m** of the ball and the other
   team's nearest player is **not** within 1 m (otherwise it is a duel, and nothing changes).
3. The candidate team **gains control** at that frame if either:
   - **touch**: the ball's velocity changes by at least **7 m/s** between 0.12 s before and 0.12 s
     after (the ball was stopped, redirected or kicked by that player), however brief; or
   - **hold**: the candidate keeps the ball within reach for **3 frames** or more while the ball
     moves slower than **6 m/s** (the ball travels with the player).
   A ball that merely **flies past** a player at unchanged speed never counts, however close.
4. The team that last gained control **keeps the ball** through passes, loose balls, duels and
   short ball gaps, until the other team gains control. The change lands on the exact frame: no
   smoothing.
5. At the start of each live stretch, before anyone has gained control, the nearest-player vote
   over ±2 s decides (the organisers' baseline idea).

**Example.** Pedri passes to Yamal; the ball flies past an Athletic midfielder 0.8 m away at
14 m/s without changing course: no change. Yamal stops it (velocity changes by ~14 m/s): Barça,
as before. Vivian steps in and redirects it: a touch, so Athletic from that frame.

**Where it comes from:** the 1 m possession zone and "a duel is not possession" are Vidal-Codina
et al. 2022; "a touch is a sudden change in the ball's motion" and "a pass stays with the passer's
team until someone else controls it" are Link & Hoernig 2017. The numbers (1 m, 7 m/s, 6 m/s,
3 frames) were chosen by sweeps on the practice matches, never on our match; the best distances
matched the papers' own. Deep dive 1 (`docs/deep-dives/01-ball-travelling.md`) has the evidence.

### 5. Match rules (`possession/polish.py`)

`X` on every frame outside the two graded halves; `D` from the start of the graded second half to
its kickoff (frame 113,742).

## What the model does *not* use yet

Smart Tagging, the video, the audio (whistles), the commentary and the broadcast tracking. Each
was audited; their use is planned inside the deep dives (`docs/plan.md`, "Data use").

## How good it is

| Test | Score |
|---|---|
| Practice matches, realistic damage (8 other matches; ball smoothed like ours) | 0.288 (v3: 0.291; the organisers' baseline: 0.238 here, 0.243 on the real match) |
| Public 5 minutes (17 possessions; a sanity check, noise band ~0.33) | 0.431 |
| Our match: possessions per minute / dead-ball share | 3.45 (public truth 3.40) / 40% |

**Caveat.** The touch rule (step 4) was tuned on practice balls sharper than ours. On a ball
smoothed like ours it adds nothing over v3 on practice (0.288 vs 0.291); v4 is kept because it is
better on our match's checks. Deep dive 1 is working on team-call rules that suit a smoothed ball.

## Version history

Practice scores on the realistic kit (ball smoothed like ours).

| Version | Idea | Practice |
|---|---|---|
| organisers' baseline | team of the nearest player to the ball, majority vote over ±2 s; missing ball = dead | 0.238 |
| v1 (`blackout_v1`) | baseline + ball gaps: 20 s+ = dead, 2-20 s dead only if players slow, else keep the team (from Kovidh's review of the 15 longest gaps) | 0.259 |
| v2 | stoppages rebuilt from measurements (step 3) + clean-up (step 2) | 0.271 |
| v3 | team by control: 1 m, no duel, held 3 frames (step 4, first version) | 0.291 |
| **v4** | + touch rule and pass-by check (step 4 as above) | **0.288** (better than v3 on our match's checks) |
