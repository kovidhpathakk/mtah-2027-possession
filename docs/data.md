# What we know about our data

Everything learned about the provided assets: what we may use, what the audits found, how far each
source can be trusted. Numbers are whole-match counts; nothing here is a row, a frame or a cell of
the match data. The scripts that produced each figure are named in each section.

## Assumptions register

What our methods and tests rely on, how well each is verified, and how to verify it better.
Confidence: **high** (several independent checks), **medium** (one kind of evidence), **low**
(estimated or inferred). Re-read before relying on any of them.

| # | Assumption | Evidence so far | Confidence | How to verify better |
|---|---|---|---|---|
| A1 | Ball gaps of 5 s+ are mostly stoppages | Kovidh's review of the 15 longest gaps; gap-length counts; the broadcast tracker; the video detector sees a ball in ~2/3 of gap frames | high | – |
| A2 | Dead ball is ~40-50% of our match | LaLiga ball-in-play figures; DFL matches 41-52% | medium | – |
| A3 | **The provided ball path is smoothed over ~0.9 s** | tracking numbers only (sharp velocity changes 1.9% vs 9-13% in DFL) | medium | **detector on runs of consecutive video frames: does the real ball stop sharply where the recorded one glides? (plan V17)** |
| A4 | DFL's possession definition matches our ground truth's | both come from a tracking provider's fields (CHALLENGE.md); in DFL the new team is within 1 m at 84% of changes | medium-low | compare definitional patterns (where changes happen relative to players), without tuning anything |
| A5 | The damaged practice matches look like our match | realism report: 17 of 18 measures within 1.5× (2026-10-26) after adding ball smoothing and missing-player episodes | medium-high | re-run the realism report whenever the kit or the methods change |
| A6 | A practice score predicts the real score | the published baseline: 0.238 practice vs 0.243 real; other baselines within 0.02-0.04 | medium-high | – |
| A7 | Imitation Smart Tagging resembles the real tags | coverage and phase lengths measured; accuracy estimated from v4's agreement | low | – |
| A8 | Commentary trails play by ~5 s | best agreement at 5 s, but agreement is near chance | low | event-focused pass (plan S3e) |
| A9 | The tactical ball is more reliable than the broadcast one | video detector: closer to tactical 23 times, broadcast 11, neither 29 | medium | – |
| A10 | The "ghost" is a frozen leftover track | frozen to the mm for ~10 min; detector finds no person there (6% vs 94%) | high | – |
| A11 | Smart Tagging team tags are ~88% right in open play, ~60% near the box | vs clear control in the tracking; the two trackers agree on clear control 97% | medium | – |

## Data-quality register

Every problem found in the provided data, and what we do about it. Status: **fixed** (code removes
or corrects it), **worked around** (the model avoids relying on it), **copied into practice** (the
fault kit reproduces it so methods are tested against it), **open**.

### Tactical tracking

| Problem | Evidence | Status | Where |
|---|---|---|---|
| **Ball-speed column unusable** | filled on 7.8% of visible graded frames, in 28 stretches; best correlation with the ball's movement 0.09 at any lag ±1 s (players' column: 0.93); values ~4× too low | worked around: speed always computed from positions | `control.ball_velocity`, `stoppages.ball_speed` |
| Player-speed column 7 frames (0.28 s) late | best match with speed from positions at lag 7 (corr 0.95); clean data 0-3 | worked around: used only over ±2 s windows ("are players slow?"), where 0.28 s does not matter; copied into practice | `stoppages.dead_mask`; `damage.py` SPEED_LAG |
| **Ball missing on 41% of graded frames** | counts | worked around: gaps are read as stoppage clues (v1/v2 rules); copied into practice (3 scenarios). Broadcast ball fills 2% more frames: tested, neutral, kept as an option | `stoppages.py`; `precise.py` |
| Almost no ball gaps of 1-5 s (the tracker fills short ones) | 1 gap of 1-5 s vs 119 on the broadcast tracker | worked around: surviving gaps (≥ 5 s) are mostly stoppages; copied into practice (gap lengths drawn from ours). Cause unproven | `damage.py` |
| **Ball path heavily smoothed** (~0.9 s) | sharp velocity changes on 1.9% of live frames vs 9-13% in DFL | copied into practice (23-frame moving average). Consequence: short-window touch detection adds nothing on a ball like ours (v4 = v3 on the realistic kit) | `damage.py` BALL_SMOOTH |
| Ball badly misplaced (5-15 m) on ~3.5% of frames | the two trackers' balls > 5 m apart on 10.5% of frames; the video sided against tactical 1 time in 3 | copied into practice; tactical ball kept as first choice | `damage.py` |
| Ball "blips" (jumps away and back) | none found; 119 one-frame jumps > 2 m are persistent re-acquisitions | open (not cleaned; normal level vs Metrica) | – |
| **Frozen "ghost"** (Athletic keeper's track frozen ~10 min across half-time) | position unchanged to the mm; detector found no person there (6%) | **fixed**: objects frozen ≥ 10 s removed | `cleanup.drop_frozen` |
| 12+ objects in a team (home 8.1%, away 4.7% of frames) | counts; clean data 0% | **half fixed**: near-duplicates and touchline objects removed (→ 4.1% / 2.5%); the rest are real people (officials, subs) per the detector; copied into practice | `cleanup.cap_team` |
| Touchline tracks (subs, staff) | 33 tracks ≥ 10 s; detector: real people | harmless (never nearest the ball); partly removed by the cap | `cleanup.cap_team` |
| Players missing (< 18 objects on 9% of frames) | 56 episodes, median 2 s (some > 30 s), median 14 tracked (sometimes 4), 86% while the ball is missing; detector sees ~3.6 untracked people per such frame | open; copied into practice as episodes | `damage.py` |
| Wrong team labels (~2% of objects, ~5% in the boxes) | the two trackers disagree on 1.8% (5.1% in boxes) | open (shirt-colour check planned, plan V8); copied into practice | `damage.py` |
| Referee not tracked | 1 of 333 long tracks looks like a referee | not a problem | – |
| "6% of player movement filled in" | the same test flags 2-4.5% on clean data | not a problem (false alarm) | – |

### Smart Tagging

| Problem | Evidence | Status |
|---|---|---|
| Set-piece tags are fixed 35 s windows, starting ~5 s before the restart | all set-piece tags | open: "precise Smart Tagging" (plan M8) will snap them to the restart frame |
| Most restarts untagged | 42 of 132 long ball gaps have a set-piece tag | open: our own restart detection must fill the rest (deep dive 2) |
| Throw-ins carry no team | all throw-in tags | open: the taker's team from tracking (deep dive 2) |
| Team tags right ~88% in open play, ~60% near the box | vs clear control in tracking | measured; used only as a test so far (team override: no gain) |
| Kickoff tags timed correctly | contain both real kickoffs | fine |

### Broadcast

| Problem | Evidence | Status |
|---|---|---|
| Own timeline, no mapping given | – | **fixed**: aligned per half by ball and player positions (agree to a frame) | 
| Offset drifts 3 frames over the 1st half | per-window offsets 4,012-4,015 | handled: per-window offsets |
| Video has 164,487 frames, tracking 164,488 | file complete | harmless |
| 38% of frames show no pitch (close-ups, crowd), 14% replays | alignment fit | flagged per frame; usable as a stoppage clue (plan S6) |

### Audio and commentary

| Problem | Evidence | Status |
|---|---|---|
| Whisper looped on the long, noisy commentary (5 lines = 86% of the first transcript) | counts | **fixed**: voice-activity detection, no carried-over text |
| Commentary names Barça 3× as often as Athletic and does not narrate possession | name test and LLM test both at chance | worked around: not used for the team call |

### Video

| Problem | Evidence | Status |
|---|---|---|
| Wide tactical view illegible to a small vision model (players a few pixels tall) | pilot 1: "stopped" on 100% of frames | worked around: crops around the action (pilot 2, parked for memory) |
| 8 GB laptop: a 4B vision model swaps, filled the disk | 2026-10-26 | one heavy job at a time; overnight runs with apps closed |

## Rules of use

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
| Ball speed column | ❌ filled on 7.8% of visible frames and does not match the ball's movement (corr 0.06) | compute from position changes instead (docs/data.md) |
| Smart Tagging | ✅ verified | 638 phases with team, 59 set pieces with type, timed to the video |
| Homography (tactical) | ✅ 100% valid | pitch ↔ pixel, for overlays and our own detections |
| Tactical video | ✅ 199,319 frames | anything a local vision model or detector can extract |
| **Tactical audio** | ✅ stereo AAC, 48 kHz, whole recording | referee whistles, crowd noise |
| Broadcast tracking + homography | ✅ verified, **aligned to tactical** (docs/data.md) | second ball view; replay detection |
| Broadcast video + commentary | ✅ re-downloaded 2026-10-25; audio extracted to `data/derived/`; **commentary is in English** | whistles, commentary via local Whisper |
| Public answers | ✅ 5 min, 17 possessions | checking correctness, never tuning |
| Labelled **other** matches | allowed in any amount | training and validating learned models (section 3) |

---

## Data audit (2026-10-25)

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

### Control: the same audit on 8 clean matches (DFL ×7, Metrica Game 3)

`python scripts/audit_tracking.py --source dfl-J03WMX` etc. Whatever the audit reports on clean,
professionally collected tracking is its own false-alarm level.

| Measure | Our match | Clean matches | Verdict |
|---|---|---|---|
| frames with 12+ objects in a team | home 8.1%, away 4.7% | 0% | **real** |
| frames with fewer than 18 objects | 9.2% | 0% | **real**: players go missing |
| long touchline tracks | 33 | 0 | **real** (harmless) |
| ghost deepest in a box, ball far away | 3,381 frames | 0–314 | **real** |
| player speed column lag | 7 frames | 0–3 | **real** |
| "perfectly straight" player seconds | 6.0% | 1.9–4.5% | **mostly a false alarm**; excess ~2–3% |
| one-frame identity jumps | 0–0.3 per min | 0.1–0.7 per min | normal |
| ball moves > 2 m in a frame | 119 | Metrica 106 | normal |
| "perfectly straight" ball seconds | 0.4% | Metrica **37.6%**, DFL 0–0.3% | our ball is *not* filled in with straight lines; the test does catch it where it happens (Metrica) |
| ball gaps of 1–5 s | 1 | Metrica 16 (DFL never loses the ball) | our missing short gaps are unusual; cause still open |
| no own object in the box, ball far away | thousands | thousands | meaningless: keepers step out of the box |

The audit also found that DFL records speed in km/h (exactly 3.6× speed from positions); the
loader converts it. DFL's labels give dead ball at **41–52%** of each match, which confirms the
"40–45% dead" estimate from published ball-in-play figures. Metrica's event-derived labels give
27%, because events mark stoppages less completely than a tracking flag does.

### Checked against the video itself (`scripts/video_audit.py`)

A COCO-trained person and ball detector (torchvision Faster R-CNN, never trained on this match),
run locally on 60 sampled frames per question, mapped to the pitch through the homography and
compared with the tracking. Counts only.

| Question | Result | Verdict |
|---|---|---|
| Does the detector work here? | finds a person within 2 m of **94%** of ordinary tracked objects; a ball within 3 m of the tracker's ball on 80% of ordinary frames | good enough to judge the tracking |
| Is the box ghost a person? | **6%** confirmed (vs 94%) | **No**: a frozen leftover track, as the tracking analysis found |
| Are touchline tracks people? | 99% confirmed | yes: substitutes and staff, tracked as players |
| Are the extra objects (12+ in a team) people? | 95% confirmed for the whole team on those frames; if the 12th were not a person this would fall to ~86% | mostly real people (officials, subs?) labelled as a team |
| Does the tracker miss players? | untracked people seen per frame: 7.1 on "fewer than 18" frames vs 3.5 on ordinary ones (referee and assistants are never tracked) | **yes**: ~3–4 players missing on those frames |
| Is the ball visible during the tracker's ball gaps? | a ball on the pitch in **67%** (gaps 5–20 s) and **70%** (20 s+) of gap frames, vs 95% on ordinary frames | **yes, mostly**: the tracker drops a visible ball, which fits "gaps are stoppages" |
| When the two trackers' balls are > 5 m apart, who is right? | detector's ball closer to tactical 23, broadcast 11, neither 29 | tactical right about twice as often; keep the tactical ball |

Ball detection is the weaker half (it also finds ball-like things), so the ball rows are
indicative, not exact.

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

## How the ball moves in our tracking (2026-10-26)

Our tracker's ball path is heavily smoothed. In graded live play its velocity changes by at least
7 m/s within 0.24 s on 1.9% of frames (clean DFL: 9-13%), by at least 3 m/s on 23%, 90th
percentile 4.3 m/s. That is what the true ball looks like after a ~23-frame (~0.9 s) moving
average: a kick looks gradual rather than sharp. Speed itself is plausible (median ~5-6 m/s in
live play). The fault kit (`possession/damage.py`) now smooths practice balls the same way, so
rules tuned on practice data transfer.

## How the audit numbers were verified

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

## Football notes from watching (Kovidh)

General patterns seen on video, written so they could become rules; never labels for specific
moments of this match.

### Control and turnovers
-

### Restarts and stoppages
-

### How Barça play
-

### How Athletic play
-

### Ball blackouts (from the gap clips)
- The tracker usually drops the ball the moment play stops (ball over a line, whistle) and picks
  it up when play restarts, even though the ball is plainly visible on the spot or in a player's
  hands. Confidence: high (most of the 15 longest gaps). Detect: long gap + players walking.
- Typical stoppages behind long gaps: goals (celebration, walk back, kickoff wait), fouls and
  free kicks, penalties, drinks breaks, end of a half, goal kicks, corners, throw-ins.
- The restart edge is fuzzy: sometimes the ball reappears when the kick is taken, sometimes a
  little earlier while it is placed or rolled to the taker (play still stopped).
- Some long gaps contain live play: a corner is delivered and fought over, or a clearance goes
  high off-camera and comes down into a contest. Detect: player speed picks up inside the gap.
- Some gaps are real occlusions in live play: a defender steps between the camera and the ball
  during a tackle. These are usually shorter.
- After a goalkeeper catches the ball, play is live but slow; the tracker may still miss the ball
  until he releases it.
