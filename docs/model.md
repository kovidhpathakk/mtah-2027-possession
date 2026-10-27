# How our model works (v6)

Plain-language description of the current best model, every rule and setting with where it came
from. Kept in step with the code (`possession/`); the technical document will be built from it.
Last updated: 2026-10-26 (v6).

    python scripts/fetch_open_data.py   # once: the practice matches the models learn from
    python run.py                       # builds evaluation/results/ours_v6.csv (the submission)

## The job

For each of the 199,319 frames of the tactical video (25 per second), say `H` (Barça has the
ball), `A` (Athletic has it), `D` (dead ball) or `X` (outside the two halves). The ranking score,
spellF1, rewards getting whole possessions right: right team, roughly right start and end.

## The pipeline in one picture

    tracking ──► clean-up ──► 35 stoppage clues ──► STOPPAGE MODEL ──► P(dead) per frame ──┐
                         └──► 59 team clues     ──► TEAM MODEL     ──► P(Barça) per frame ─┤
                                                                                           ▼
                                        DECODER: the most believable H/A/D sequence ──► match rules

Two trained models each give a probability per frame; the decoder turns them into whole
possessions and stoppages at once. Both models are **gradient-boosted decision trees** trained only
on other matches (the practice matches), damaged to look like our tracking.

## 1. Read the tracking (`possession/tracking.py`)

The provided tracking gives, per frame, the position of every tracked person (with their team)
and of the ball, which is missing on 41% of frames. The speed column is used; the ball-speed
column is not (it does not match the ball's movement; speed is computed from positions).

## 2. Clean it (`possession/cleanup.py`)

| Rule | Why |
|---|---|
| Remove an object whose position does not change at all for 10 s or more | A frozen leftover track: the "ghost" in front of Barça's goal is the Athletic keeper's track frozen across half-time (data audit; the video detector found no person there) |
| When a team has 12+ objects, remove first a near-duplicate (within 1.5 m of a teammate), then one on a touchline or off the pitch | Double-counted players and substitutes/staff tracked as players (data audit) |

## 3. Is play stopped? The stoppage model (`possession/learned.py`, v6)

### 3a. v2's stoppage rules (`possession/stoppages.py`), now clues

| Rule | Example | Evidence (practice matches) |
|---|---|---|
| The ball is visible and more than **1 m outside the lines** | ball by the corner flag for a corner | 99% of such frames are dead |
| The ball is visible and **has not moved for 2 s** (under 0.5 m/s) | ball placed for a free kick | catches 96% of dead frames with the ball in view, 0.6% false alarms |
| The ball is **missing for 1 s or more** and any of: the players are **slow** (under 65% of the match's typical speed); the ball vanished or came back **beyond a line, at a corner or by a touchline**; the gap lasts **20 s or more** | the tracker drops the ball when it goes out for a throw-in, players walk | slow players: 98-99% dead; at an edge: 79-100% dead; long gaps were stoppages in Kovidh's review of the 15 longest gaps |

Plus a tidy-up (a live stretch under 2 s inside a stoppage becomes dead; a dead blip under 0.5 s
becomes live). Source: Vidal-Codina et al. 2022 (a missing ball and restart positions mark dead
ball). As rules alone, they miss 24% of dead frames and call 23% of live frames dead on practice.

### 3b. The stoppage clues: 35 per frame

| Family | Clues | Why it helps |
|---|---|---|
| v2's rules | each rule's verdict, before and after the tidy-up; how far the ball is beyond a line | the rules' knowledge, kept |
| Ball still or gone | how long the ball has been still, and will stay still; how long the current ball gap is, how far into it we are, how long until it ends; ball speed now and its peak over the last and next second | a ball placed for a restart; the tracker drops the ball at stoppages |
| Ball where | distance to the goal line and touchline now, where it vanished and where it came back, how far it moved while missing | gaps that start or end at an edge or come back where they began are restarts |
| Player speed | all players' speed against this match's typical speed, over ±1, ±3 and ±8 s and the last and next 3 s; share of players walking; the slower and the faster team | players walk and stand during stoppages |
| Objects tracked | how many people the tracker follows, and the fewest within ±3 s | our tracker drops many players at once, mostly during stoppages |
| Player layout | spread of all players; players within 5 and 10 m of the ball; players in the penalty boxes | walls, corners and free kicks crowd the ball or the boxes |

The model treats both teams alike (team-level clues enter as "the lower and the higher of the two
teams"), so it needs one view. **What it leans on** (shuffle one family, accuracy drop): player
speed 17 points, ball still or gone 8, ball where 5, v2's rules 4, layout 1. Lang et al. 2022 found
the same: player movement alone tells in-play from stoppages 92% of the time.

## 4. Who has the ball? The team model (`possession/learned.py`, from v5)

**Rule of the game (CHALLENGE.md):** possession changes only when the other team gains
*controlled* possession; contested and loose balls stay with the last team.

### 4a. The control rules (`possession/control.py`, v3 and v4), now clues

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
2017. As rules alone they score 0.28-0.29 on practice: our ball is smoothed and often missing.

### 4b. The team clues: 59 per frame

| Family | Clues | Why it helps |
|---|---|---|
| Near | each team's nearest and second-nearest player to the ball; players within 3 m | who is on the ball now |
| Before and after | each team's closest approach to the ball over the last and the next 0.24, 0.5, 1 and 2 s; which team was nearer over ±0.5 s and ±2 s | who the ball came from and who it goes to: still visible when the ball path is smoothed |
| Control | team and distance (frames) of the last and the next control event (both rules of 4a) in the same live stretch; v3's and v4's own answers; the nearest player's team; the ±2 s vote | the rules' knowledge, kept |
| Ball | position along the pitch (towards the goal this team attacks), distance from the centre line, speed, forward speed, change of velocity now and over ±0.5 s, time since and until the ball is seen | a fast forward ball is usually a pass by the team attacking that way |
| Team shape | each team's average position along the pitch, spread (length and width), speed, how it moves forward or back, and the **share of its players goal-side of the ball** | the team with the ball pushes up and spreads out; the team without it drops behind the ball. Works even when the ball is missing (the Ball Radar idea, Kim et al. 2023) |

**Fairness between teams:** every clue is computed once from Barça's point of view and once from
Athletic's, and the answer averages the two, so the model cannot learn "the home team has the ball
more". **What it leans on:** team shape 17 points of accuracy, ball 5, before/after 2, control 2,
near 0.3.

## 5. Deciding everything together: the decoder

Each frame now has two probabilities, e.g. "dead: 0.10; if live, Barça: 0.85". Reading them frame
by frame would flicker, and every flicker invents a possession or a stoppage, which costs points.
The decoder (a **Viterbi pass**, the standard way to find the most believable sequence through a
hidden Markov model) picks the H/A/D sequence that best fits the probabilities while paying a
price for every change:

| Change | Price (log-probability) | Chosen on practice |
|---|---|---|
| live ↔ dead (a stoppage starts or ends) | 40 | 40 and 80 tie (0.555 / 0.554); 5-20 lower |
| Barça ↔ Athletic | 10 | 5 and 10 tie; 20 lower |

**Illustration** (made up). The stoppage model is unsure for 2 s (0.5) while players slow down,
and the team model sees Athletic close in. Deciding separately, a threshold might call those 2 s
dead and then hand the restart to the wrong team. Deciding together, the decoder compares "a
stoppage starts and ends here (pay 80)" with "play goes on and Athletic win the ball (pay 10)" and
takes whichever the evidence supports better.

## 6. Match rules (`possession/polish.py`)

`X` on every frame outside the two graded halves; `D` from the start of the graded second half to
its kickoff (frame 113,742).

## How the two models are trained

- **Material:** 8 open-data matches with an answer on every frame: 7 Bundesliga matches (DFL,
  Bassek et al. 2025) and Metrica's Sample Game 3. Never our match.
- **Damage first:** each match is damaged three ways (`possession/damage.py`) so it looks like our
  tracking: ball missing 41% of the time (gaps placed at stoppages, half at stoppages, or at
  random; our players' pace during gaps matches the first), ball path smoothed and noisy, the ball
  moving in stoppages as ours does (DFL freezes it), wrong team labels, players dropped, a ghost,
  the speed column delayed.
- **Rows:** every 5th frame (neighbours are near copies): ~620,000 team rows (live frames, both
  teams' views) and ~690,000 stoppage rows (all graded frames).
- **Model:** scikit-learn's HistGradientBoostingClassifier: 200 small decision trees, each a chain
  of yes/no questions ("are more than 8 of this team's players goal-side of the ball?"), each new
  tree correcting the ones before; up to 31 leaves per tree, learning rate 0.1, fixed seed.
- **Honest testing:** a practice match is always labelled by models trained on the other seven
  (leave one match out). Settings are chosen on damage seeds 0-1 and confirmed on fresh seeds 2-3.
- **Reproducible:** no randomness left unfixed; retraining from nothing gives a byte-identical
  submission (checked for v5 and v6). Trained models are cached in `data/derived/learned/`.

## What the model does *not* use yet

Smart Tagging, the video, the audio (whistles), the commentary and the broadcast tracking. Each
was audited; their use is planned (`docs/plan.md`, "Data use").

## How good it is

| Test | v6 | v5 | v4 |
|---|---|---|---|
| Practice, corrected kit (dead ball moves; seeds 0-1; baseline 0.237 here, 0.243 on the real match) | **0.538** | 0.422 | 0.280 |
| Practice, previous kit, fresh seeds | 0.558 | 0.430 | 0.279 |
| Practice per scenario: gaps at stoppages / mixed / random | 0.597 / 0.561 / 0.517 | 0.527 / 0.425 / 0.338 | 0.348 / 0.271 / 0.219 |
| Dead-ball frames: missed / false (practice) | 5% / 4% | 24% / 23% | 24% / 23% |
| Damage test (public window, ball deleted to the match's rate; 30 runs) | **0.572** | 0.440 | 0.329 |
| Public 5 minutes (17 possessions; noise band ~0.37) | 0.640 | 0.607 | 0.431 |
| Our match: Smart Tagging agreement, attacking / defending | 79% / 86% | 76% / 82% | 74% / 78% |
| Our match: set-piece windows with a dead ball | 93% | 92% | 92% |
| Our match: possessions per minute / dead-ball share | 2.46 / 47% | 2.82 / 40% | 3.45 / 40% |

**Caveats.** (1) Fewer possessions than the truth, and falling with each version (our match 2.46 a
minute; the public window's truth 3.40; on practice v5 makes 3.4 against 4.5): deep dive 5. (2) In
the public 5 minutes v6 calls 15% of frames dead against the truth's 20% (was 10% before the
practice dead ball was made to move like ours; not tuned on). (3) Everything rests on the practice damage
being realistic (assumptions A5, A12; `scripts/realism_report.py`). On our match the stoppage
model is about as sure of itself as on practice (0.947 vs 0.961) and calls 41% of frames dead.

## Version history

Practice scores on the realistic kit (ball smoothed like ours).

| Version | Idea | Practice |
|---|---|---|
| organisers' baseline | team of the nearest player to the ball, majority vote over ±2 s; missing ball = dead | 0.238 |
| v1 (`blackout_v1`) | baseline + ball gaps: 20 s+ = dead, 2-20 s dead only if players slow, else keep the team (from Kovidh's review of the 15 longest gaps) | 0.259 |
| v2 | stoppages rebuilt from measurements (3a) + clean-up (step 2) | 0.271 |
| v3 | team by control: 1 m, no duel, held 3 frames (4a, first version) | 0.291 |
| v4 | + touch rule and pass-by check (4a) | 0.288 (better than v3 on our match's checks) |
| v5 | v4's stoppages + **learned team model** (4b) + team decoder | 0.430 (fresh seeds; v4 0.279 on the same copies) |
| **v6** | + **learned stoppage model** (3b) + **one decoder for H/A/D** (step 5) | **0.558** (fresh seeds; v5 0.430 on the same copies) |
