# Team rules for Claude

This is our team's entry to More than a Hack 2027, Phase 1: label every frame of one match
(FC Barcelona vs Athletic Club) as `H` / `A` / `D` / `X`. Ranked on `spellF1` against a private
full-match ground truth. The organisers' docs are README.md, CHALLENGE.md, DATA.md,
EVALUATION.md, SUBMISSION.md and RULES.md; `evaluation/possession_metrics.py` defines the metrics.

## The data never reaches you

The competition terms forbid giving the match data, or any extract of it, to a hosted LLM. That
includes you. The organisers' wording (FAQ.md and OVERVIEW.md on upstream main, checked
2026-10-26): participants "shall not upload, disclose or otherwise make available to any
third-party hosted or cloud-based LLM any videos, datasets, confidential information or other
restricted materials provided in connection with the Competition, or any extracts thereof". It is
not limited to the submission. People on the team may watch the video to understand the data
(RULES.md, upstream); Claude may not see it.

- Never read, print, `head`, `cat` or open files under `data/`, or show rows, frames or cells
  from them. This covers tracking (`*_atd.txt`, `*_atd.xml`), homography, Smart Tagging, video,
  and anything derived from them that keeps per-frame detail (`data/derived/`).
- Write code that the user runs, and have it print **aggregates only**: counts, percentages,
  means, distributions, scores. Never print or log individual rows.
- Never view video frames, screenshots or clips.
- The public ground truth (`evaluation/gt/*_public.csv`) and the baseline CSVs in
  `evaluation/results/` are published by the organisers and fine to read.

## The data never reaches git

The repository is public.

- Everything under `data/` stays local; `.gitignore` covers it. Keep derived outputs in
  `data/derived/` too.
- `scripts/guard.py` runs as a pre-commit hook and in CI. Never bypass it (`--no-verify`).
- Clear notebook outputs before committing.

## Labels come from an algorithm

No hand labelling of this match, including hand-correcting model output. Watching video to
understand failures is fine; turning what you see into labels is not. Labelled data from *other*
matches is allowed.

## Conventions

- Everything is indexed by **tactical video frame, 0..199318**. ATD `frame_id` is video frame + 1.
- Graded halves: video frames 11185..90651 and 110808..190197 (`games.half_video_blocks`).
  Write `X` outside them. Frames 110808..113741 are graded and are `D` (2nd half before kickoff).
- Distances in metres: multiply normalised x by 105.3 and y by 68.0 first.
- Inside the halves, always output `H`, `A` or `D`. `X` there never adds score.
- Never tune on the public 5 minutes. Compare versions on the open-data test, the damage test and
  the full-match sanity report; treat spellF1 differences under ~0.04 as noise.
- Every submission must pass `python evaluation/validate_submission.py <file>` and must be
  reproducible from a clean clone, byte for byte: pinned dependencies, fixed seeds.
- Match the style of the organisers' code: numpy/pandas, docstrings that explain why.

## Machine limits (8 GB Apple M1, disk nearly full)

- One heavy job at a time: never run a local vision model or LLM alongside another heavy job.
  On 2026-10-26 a vision model plus analysis filled the disk with 5.6 GB of swap and macOS ran
  out of memory.
- Keep at least 5 GB of disk free: check `df -h ~` before any download; remove models proven
  useless.
- Stop the Ollama server (`pkill -x ollama`) after each use; ask Kovidh to quit Chrome and other
  heavy apps before a vision-model run.

## Commands

    python scripts/check_data.py --baseline     verify a data copy
    python run.py [--method NAME]               build a submission into evaluation/results/
    python scripts/open_test.py                 8 open-data matches with our faults added: compare methods here
    python scripts/realism_report.py            does the damaged practice data look like our match? (run after any kit change)
    python scripts/damage_test.py               public 5 min with realistic ball blackouts
    python scripts/sanity_report.py             does a full-match submission look like football
    python scripts/gap_clips.py                 local clips of the longest ball blackouts
    python scripts/audit_tracking.py [--source broadcast]   what is wrong with the tracking
    python scripts/audit_tagging.py             Smart Tagging checked against the tracking
    python scripts/extract_audio.py             soundtracks to data/derived/ (16 kHz WAV)
    python scripts/align_broadcast.py           broadcast -> tactical frame offsets, replays
    python scripts/audit_confirm.py             weak audit findings tested against the broadcast tracker
    python scripts/fetch_open_data.py           DFL + Metrica open data into data/external/, hash-checked
    python -m unittest discover tests           the measuring code, checked on made-up data
    python evaluation/validate_submission.py F  check a submission
    python evaluation/run_evaluation.py         score everything in evaluation/results/
    python scripts/guard.py                     the data-leak check

New methods go in possession/methods.py; run.py and both test scripts pick them up from there.
Docs map: docs/README.md. Log every experiment in docs/experiments.md; after every step update
docs/progress.md (story, model versions) and docs/plan.md (next steps, every idea with its status);
when the model changes, update docs/model.md. Check docs/plan.md before choosing the next step;
add every new idea to it at once; never delete a row (mark it `dropped` with the reason).
