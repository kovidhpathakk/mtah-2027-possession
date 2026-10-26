# Status and next steps

Read this first when picking the project up, together with CLAUDE.md, docs/experiments.md and
docs/research.md. Updated 2026-10-25.

## Where things are

- **Branch:** all work is on `phase1-tools` (PR #1, open). **Do not merge into `main`** until the
  team agrees on how `main` is used.
- **Data:** verified on the owner's machine (`python scripts/check_data.py --baseline`). Broadcast
  video re-downloaded 2026-10-25 and complete (its 164,487 frames vs 164,488 tracking records is
  in the original file). Both soundtracks extracted to `data/derived/*_audio_16k.wav`; nothing we
  plan needs the 14 GB broadcast video any more.
- **Insurance submission:** `python run.py --name insurance_baseline` → baseline + match rules,
  valid. To be uploaded to the form when the link arrives.
- **Best model so far:** `blackout_v1` (public spellF1 0.362, damage test 0.277 vs baseline 0.326 /
  0.226). Its thresholds were partly informed by watching clips; v2 re-sets every threshold on
  other matches.
- **Tools:** damage test, sanity report, gap clips, and (new) `audit_tracking.py`,
  `audit_tagging.py`, `extract_audio.py`, `align_broadcast.py`.

## Key facts learned

1. **Ball gaps are mostly stoppages.** The tactical tracker fills in gaps under ~5 s itself;
   all 132 surviving gaps are ≥ 5 s, about a match's worth of restarts (research.md §7).
2. Dead ball is likely ~40–45% of the full match, not the ~20% of the calm public 5 minutes.
3. Ball speed column unusable; speed from positions is plausible (p50 5.1, p99 24.4 m/s).
   Player speed column is right but 0.28 s late.
4. Keeper mix-up: ~3,400 frames where the deepest object in Barça's box is labelled Athletic,
   mostly in the 2nd half. Touchline tracks (assistants, subs) are labelled as players.
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
| A | Data audit (tracking, Smart Tagging, broadcast alignment) | ✅ 2026-10-25 |
| B | Open data: download DFL + Metrica, convert to H/A/D, add our tracker's faults | a ~10-match damage test runs |
| C | v2: clean-up (keeper, touchline tracks, cap 11) + restart detector + possession logic | beats v1 on the new test |
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
