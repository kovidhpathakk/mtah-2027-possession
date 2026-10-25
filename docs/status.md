# Status and next steps

Read this first when picking the project up, together with CLAUDE.md, docs/experiments.md and
docs/research.md. Updated 2026-10-25.

## Where things are

- **Branch:** all work is on `phase1-tools` (PR #1, open). **Do not merge into `main`** until the
  team agrees on how `main` is used.
- **Data:** verified on the owner's machine (`python scripts/check_data.py --baseline` passes,
  video included). Broadcast video was deleted to save disk.
- **Insurance submission:** `python run.py --name insurance_baseline` → baseline + match rules,
  valid. To be uploaded to the form when the link arrives.
- **Best model so far:** `blackout_v1` (public spellF1 0.362, damage test 0.277 vs baseline 0.326 /
  0.226). Weakness: misses stoppages where the ball is still visible.
- **Tools:** damage test, sanity report, gap clips (clips live in `~/Downloads/mtah_gap_clips/`,
  local only).

## Key facts learned

1. The tracker drops the ball when play stops, even when the ball is visible; long blackouts are
   mostly stoppages. Medium ones (5–20 s) are probably mostly restarts.
2. Dead ball is likely ~40–45% of the full match (LaLiga ball-in-play ~54–56 min), not the ~20%
   of the calm public 5 minutes.
3. The tracker's ball-speed column is nearly empty; compute speed from positions.
4. An Athletic-labelled object sometimes stands in Barça's goal (~1 min of frames).
5. The tactical video has audio; referee whistles are audible.
6. The damage test predicts real scores well except it over-rewards heavy smoothing.

## Next steps, in order

1. **v2**: restart detector from player positions + ball/player speed + keeper/ghost fixes
   (docs/research.md §7, items 1–3).
2. **HMM/Viterbi decoder** using v2's signals.
3. Pilots: whistle detector on the audio; local vision model ("is play stopped?").
4. Download SkillCorner / Metrica open data for a learned model and a bigger damage test.

## Open questions for the team

- How `main` is used and who merges.
- Ask the organisers (GitHub issue): may we watch video to inform general rules; is per-gap
  viewing allowed for validation? (Currently treated as not allowed.)
- Teammates' invites were pending on Oct 23.
