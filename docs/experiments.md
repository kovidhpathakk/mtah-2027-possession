# Experiment log

One row per experiment, newest first. Judge on the damage test and the sanity report, never on
the public 5 minutes alone, and treat spellF1 gaps under ~0.04 as noise.

| Date | Who | Branch | What changed | Public spellF1 / macroF1 | Damage-test spellF1 (mean ± spread) | Possessions (full match) | Mean length (s) | D share | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 2026-10-23 | Claude | phase1-tools | Insurance: baseline smooth50 + match rules (X outside halves, D before 2nd-half kickoff) | 0.3256 / 0.6207 | 0.226 (0.148–0.316) | 584 | 7.2 | 34% | Uploaded as our safety entry |
| 2026-10-23 | — | main | Baseline smooth50, unchanged | 0.3256 / 0.6207 | 0.226 (0.148–0.316) | 594 | 7.2 | 32% | Reference. Full-match spellF1 0.2433 per EVALUATION.md |

## Findings

### 2026-10-23 · Is the damage test honest? Calibrated against the four published baselines

| Baseline | Public 5 min | Damage test (100 runs) | Real full match |
|---|---|---|---|
| raw | 0.038 | 0.037 | 0.049 |
| smooth25 (±1 s) | 0.287 | 0.201 | 0.200 |
| smooth50 (±2 s) | 0.326 | 0.226 | 0.243 |
| smooth125 (±5 s) | 0.424 | 0.302 | 0.224 |

Much closer to reality than the raw window for three of four, but it still over-rewards heavy
smoothing (smooth125). Likely cause: the public 5 minutes have long, calm possessions, which suit
sluggish models, and damaging the ball cannot change the football in them. **Use the damage test
for robustness to ball blackouts. Do not use it to choose how stable or sluggish a model is**;
check that on the full match with the sanity report. Spreads are wide (±0.08): small gaps mean
nothing.

### 2026-10-23 · Sanity report on the baselines

- The truth agrees with Smart Tagging only ~70% (attacking phases) / 75% (defending). That is the
  realistic ceiling for this check, not 100%.
- Baselines call 32–41% D over the full match against ~20% in the public truth, because they
  write D on every missing-ball frame. **Corrected 2026-10-24:** the 20% comes from 5 calm
  minutes; the full match has goals, a hydration break and the end of the 1st half, so its real
  D share is probably higher. The baselines' D share is not necessarily too high; the problem is
  *which* frames they call D (see the gap findings below).
- In the public window, during ball gaps the truth is ~56% D, ~44% A, ~1% H (small sample).

### 2026-10-23 · Gap clips

The 15 longest blackouts cover 1,007 s, 39% of all missing-ball time. Watching them (~17 min)
tells us what a large share of the problem is.

### 2026-10-24 · What the ball blackouts are

Watching the longest clips showed one dominant pattern: **the tracker drops the ball when play
stops, even when the ball is plainly visible** (on the spot, in a player's hands), and picks it
up again when play restarts. The long blackouts were stoppages: goals and the wait for kickoff,
fouls and free kicks, a penalty, a drinks break, the end of a half, goal kicks, corners. A few
were real occlusions in live play, and some long ones contain live play inside them (a corner
delivered and fought over before the ball reappears).

Checked against data we are allowed to measure:

| | |
|---|---|
| Gaps > 20 s | 44 gaps, 67% of all missing-ball time |
| Mean player speed: ball visible / gaps > 20 s / gaps ≤ 20 s | 2.16 / 0.99 / 1.53 m/s |
| Gaps ending within 5 s of a tagged set piece: > 20 s vs shorter | 25% vs 5–9% |
| Public truth inside the 4 gaps of 5–15 s | 2 fully live (A), 1 mostly D, 1 fully D |

Working rule for Phase 2: **long blackout + slow players ≈ stoppage**; medium blackouts are
mixed and need player movement to decide; short ones are usually live play. Edges matter: a
blackout often starts at the moment play stops and ends at the restart, but sometimes ends while
the restart is still being prepared, and long ones can hide live play.
