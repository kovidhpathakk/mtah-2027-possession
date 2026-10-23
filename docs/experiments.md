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
- Baselines call far too much dead ball over the full match: 32–41% D against ~20% in the truth,
  because they write D on every missing-ball frame. First thing to fix in Phase 2.
- In the public window, during ball gaps the truth is ~56% D, ~44% A, ~1% H (small sample).

### 2026-10-23 · Gap clips

The 15 longest blackouts cover 1,007 s, 39% of all missing-ball time. Watching them (~17 min)
tells us what a large share of the problem is.
