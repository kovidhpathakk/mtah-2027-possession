# Status and next steps

Read this first when picking the project up, together with CLAUDE.md, **docs/model.md** (how
the current model works), **docs/sources.md** (papers, datasets, tools), **docs/progress.md**
(everything done so far, model versions, next steps), docs/experiments.md and docs/research.md. Updated 2026-10-25.

## Where things are

- **Branch:** all work is on `phase1-tools` (PR #1, open). **Do not merge into `main`** until the
  team agrees on how `main` is used.
- **Data:** verified on the owner's machine (`python scripts/check_data.py --baseline`). Broadcast
  video re-downloaded 2026-10-25 and complete (its 164,487 frames vs 164,488 tracking records is
  in the original file). Both soundtracks extracted to `data/derived/*_audio_16k.wav`; nothing we
  plan needs the 14 GB broadcast video any more.
- **Insurance submission:** `python run.py --name insurance_baseline` → baseline + match rules,
  valid. To be uploaded to the form when the link arrives.
- **Best model so far:** `v4` (practice 0.410 vs v3 0.352 vs baseline 0.248 on the harder fault
  kit; public 0.431; dead ball 40%). `evaluation/results/ours_v4.csv` is valid, reproducible, and
  the frozen submission candidate.
- **Tools:** damage test, sanity report, gap clips, and (new) `audit_tracking.py`,
  `audit_tagging.py`, `extract_audio.py`, `align_broadcast.py`.

## Key facts learned

1. **Ball gaps are mostly stoppages.** The tactical data has no ball gaps of 1–5 s (the
   broadcast has 119); all 132 gaps of 5 s or more are about a match's worth of restarts
   (research.md §7). Why the short gaps are missing is still open.
2. Dead ball is likely ~40–45% of the full match, not the ~20% of the calm public 5 minutes.
3. Ball speed column unusable; speed from positions is plausible (p50 5.1, p99 24.4 m/s).
   Player speed column is right but 0.28 s late.
4. **Not a keeper mix-up after all**: the ~3,400 frames with an Athletic object deepest in Barça's
   box are a motionless ghost that reuses the Athletic keeper's track ID; both keepers are
   labelled correctly. Touchline tracks (subs, staff) are never nearest the ball: harmless.
   The two trackers' balls disagree by > 5 m on ~10% of frames: open.
5. Smart Tagging: team tags 87–89% right in build-up/progression, ~60% near the box; set-piece
   tags are fixed 35 s windows and miss most restarts (only 42 of 132 long gaps tagged).
6. Broadcast aligned: tactical = broadcast + ~4,014 (1st half) / +26,920 (2nd half), confirmed
   by ball and players; replays detectable. Commentary is in **English**.
7. Audio: whistles audible; cross-correlating the two soundtracks is weak.

## Decisions (Kovidh, 2026-10-25)

1. Open data: DFL (7 matches, per-frame alive/possession) first, Metrica Game 3 second; damaged
   to look like our tracker; used to set thresholds, as a bigger damage test, and for training.
2. Audit the data before building v2 (done for tracking, tagging, broadcast).
3. v2 = clean-up + restart detector + possession logic, thresholds from open data; then decoder.
4. Broadcast re-downloaded; keep audio + tracking.
5. Models: Whisper + whistle classifier first, then a vision-model timing pilot; Ball Radar later.
6. Questions to organisers: posted as
   [issue #14](https://github.com/metrica-sports/more-than-a-hack-2027/issues/14).

## Plan

| Step | What | Done when |
|---|---|---|
| A | Data audit (tracking, Smart Tagging, broadcast alignment, confirmation by second tracker) | ✅ 2026-10-25 |
| B | Open data: downloaded, loaded with H/A/D labels, control audit, fault kit (`possession/damage.py`), 8-match test (`scripts/open_test.py`), calibrated against the published baselines | ✅ 2026-10-25 |
| A+ | Video audit with a local detector (`scripts/video_audit.py`, `.venv-video`) | ✅ 2026-10-25 |
| C | v2: clean-up + stoppage rules (out, still, gaps) + flicker tidy-up | ✅ 2026-10-25, beats v1 in every scenario |
| C2 | v2.1: who restarts, possession logic | beats v2 |
| D | Decoder (HMM/Viterbi) over v2's clues | beats v2 |
| E | Audio: whistle detector, then commentary (Whisper + small local LLM) | each clue helps, or is dropped |
| F | Pilots: vision model "is play stopped?", Ball Radar | if time allows |

## Open questions

- **Organisers:** issue #14 (saving model outputs for reproducibility; turning what we saw in
  clips into general rules), and #11 (another team's: is byte-identical required across
  hardware?). Check both at the start of each session.
- How `main` is used and who merges.
- Is a ball gap ending in the penalty box a keeper holding the ball (live) or a goal kick (dead)?
  Needs the restart detector and DFL to answer.
