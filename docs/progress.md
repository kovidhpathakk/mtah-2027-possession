# Progress log

Everything the team has done, is doing and plans to do, in one place: the model versions, the
tools, what we learned about the data, and the next steps. **Updated after every step**, newest
state at the top of each section.

- `docs/status.md`: a one-page "start here" summary.
- `docs/experiments.md`: one entry per experiment, with full numbers.
- `docs/research.md`: papers, datasets, models and the data audit in detail.

Last updated: 2026-10-25.

---

## Words used here

| Word | Meaning |
|---|---|
| **H / A / D / X** | Barça has the ball / Athletic has it / dead ball / no answer |
| **possession** | an unbroken run of H, or of A |
| **spellF1** | the ranking score: how many true possessions we found, with the right team and roughly the right start and end. 0 = random, 1 = perfect, differences under ~0.04 are noise |
| **ball gap** | a stretch of frames where the tracker has no ball position |
| **public 5 min** | the only part of our match with published answers: 17 possessions. A sanity check only; we may not tune on it |
| **open-data test** | 8 other matches with answers on every frame, damaged to look like our tracker. Where methods are compared |

---

## Model versions

Scores: **open-data test** = mean spellF1 over 8 matches for the three ball-gap scenarios
(stoppage / mixed / random); **public** = the 5-minute window; **real** = the organisers'
published full-match score, known only for their baselines.

| Version | Who, when | What it does | Open-data test | Public | Real | Status |
|---|---|---|---|---|---|---|
| `baseline_raw` | organisers | team of the nearest player to the ball, every frame; missing ball = D | 0.06 / 0.05 / 0.04 | 0.038 | 0.049 | reference |
| `baseline` (smooth50) | organisers | the same, then a majority vote over ±2 s | 0.32 / 0.25 / 0.21 | 0.326 | **0.243** | the floor to beat |
| `insurance_baseline` | Kovidh, Oct 23 | baseline + match rules (X outside the halves, D before the 2nd-half kickoff) | as baseline | 0.326 | – | **ready to upload** |
| exp 001–004 | Dhruv, Oct 24 (`test-v1` branch) | 001 ignore short team flips; 002 long gaps = D; 003 + require slow players; 004 + Smart Tagging restarts | not run yet | 0.287–0.335 | – | judged on the public window only; to re-run on the open-data test |
| **`blackout_v1`** | Kovidh + Claude, Oct 24 | baseline vote, plus: ball gap ≥ 20 s = D; gap 2–20 s = D only if players are slow (< 1 m/s); otherwise keep the last team | **0.35 / 0.28 / 0.23** | 0.362 | – | **current best** |
| `blackout_v1_clean` | Claude, Oct 25 | v1 after the clean-up (frozen objects and a team's 12th+ object removed) | 0.35 / 0.27 / 0.22 | – | – | no change; the clean-up stays in v2 because it is correct |
| v2 | next | clean-up + restart detector + "gap = dead unless evidence says live" + possession logic | – | – | – | **in progress** |

**What v1 gets wrong:** it calls 35% of the match dead against ~43% in reality. It misses stoppages
where the ball stays visible, or where players keep moving.

---

## Timeline

| Date | What | Result |
|---|---|---|
| Oct 22–23 | **Team setup**: data checker, data-leak guard (pre-commit + CI), rules for Claude | Repo safe to keep public |
| Oct 23 | **Measuring tools**: damage test (public 5 min with realistic ball gaps), sanity report (does a full-match prediction look like football) | First way to compare methods |
| Oct 23 | **Insurance submission** built and validated | A safe entry exists |
| Oct 23 | **Gap clips**: Kovidh watched the 15 longest ball gaps | Key insight: the tracker drops the ball when play stops, even when the ball is visible |
| Oct 23–24 | **v1** (`blackout_v1`) | Public 0.362, damage test 0.277 vs baseline 0.326 / 0.226 |
| Oct 23–24 | Web research: ball-in-play time, restart durations | Dead ball is ~40–45% of a match |
| Oct 24 | Dhruv's experiments 001–004 | Small public gains from "long gaps = D" |
| Oct 25 | **Research**: papers (Vidal-Codina, Link & Hoernig, Ball Radar), open datasets, local models, audio | `research.md` §1–6 |
| Oct 25 | **Decisions** on datasets, audits, models; **issue #14** to the organisers | No answer yet |
| Oct 25 | **Tracking audit**, **Smart Tagging audit** | 11 suspected faults; Smart Tagging tags only 42 of 132 long gaps |
| Oct 25 | **Broadcast**: re-downloaded, aligned to tactical frame by frame, audio extracted (commentary confirmed English), video deleted to free disk | Second tracker available |
| Oct 25 | **Tests** for the measuring code (made-up data with known answers) | 10 tests, all pass |
| Oct 25 | **Second-witness check** with the broadcast tracker | Keeper "mix-up" corrected: it is a ghost |
| Oct 25 | **Open data**: 7 DFL + 1 Metrica match downloaded (hash-checked), loaded with answers on every frame | Dead ball is 41–52% of each match |
| Oct 25 | **Control audit** on the 8 clean matches | Real faults separated from the audit's false alarms |
| Oct 25 | **Fault kit + open-data test**, calibrated on the published baselines | Our main judging tool from now on |
| Oct 25 | **Clean-up step**; the ghost explained (Athletic keeper's track frozen across half-time) | Correct, but no score change |
| Oct 25 | **Video audit** with a detector run locally (420 frames) | Ghost is not a person; a ball is visible in ~2/3 of gap frames; tactical ball beats broadcast 2:1 |

---

## What we know about the data

Details and numbers: `research.md` §7.

| Fact | How we know |
|---|---|
| Ball gaps are mostly stoppages: 132 gaps of 5 s or more, almost none of 1–5 s, and a ball is visible in ~2/3 of gap frames | gap counts; broadcast comparison; video audit |
| Dead ball is ~43% of a match; v1 calls 35% | DFL answers; published ball-in-play figures |
| Smart Tagging: team tags ~88% right in open play, ~60% near the box; set-piece tags miss ~2 of 3 restarts | checked against the tracking |
| The "ghost" in Barça's box is the Athletic keeper's track frozen for ~10 min | frozen-position check; video (6% person) |
| The tracker misses 3–4 players on ~9% of frames, and counts some staff and officials as players | clean-data control; video |
| Ball speed column unusable; player speed column 0.28 s late | compared with speed from positions |
| The tactical ball is more reliable than the broadcast ball | video audit |
| Broadcast frame = tactical frame − ~4,014 (1st half) / − ~26,920 (2nd half) | ball and players agree to a frame |

---

## Now

- **v2, step C**: the restart detector is next.
- Waiting on organisers: issues #14 and #11.

## Next steps, in order

| # | Step | Why | Done when |
|---|---|---|---|
| 1 | **Restart detector** (Vidal-Codina): throw-ins, corners, goal kicks, kickoffs from player and ball positions | The main fix for calling too little dead ball; also tells which team restarts | beats v1 on the open-data test in all three scenarios |
| 2 | **Gap rule rethink**: a gap is dead unless the evidence says live | Gaps are mostly stoppages | D share moves towards ~43% without losing score |
| 3 | **Possession logic** (Link & Hoernig): change team only on real control; duels don't flip | Fewer false possessions | beats step 2 |
| 4 | Re-run Dhruv's 001–004 on the open-data test | They were judged on 5 minutes only | done |
| 5 | **Decoder** (HMM/Viterbi): the most believable H/A/D sequence for the whole match | Targets spellF1 directly | beats v2 |
| 6 | **Whistle detector** on the audio | Marks stoppages the tracking misses | helps on our match, or dropped |
| 7 | **Commentary**: Whisper + a small local LLM → timed hints | Fouls, free kicks and who gets them | helps, or dropped |
| 8 | Optional: vision model "is play stopped?", Ball Radar | Catch what nothing else sees | if time allows |
| 9 | **Technical document** + final submission | Required deliverables | by **Nov 17** |

## Open questions

- Organisers: may we save model outputs in the repo for exact reproducibility, and turn what we
  saw in clips into general rules? (#14, #11)
- Why the tactical data has almost no 1–5 s ball gaps.
- Which people the extra objects are (officials? substitutes?). Low impact.
- How `main` is used and who merges; teammates' branches (`test-v1`) to fold in.
