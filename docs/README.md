# Docs: which file answers which question

Start with `progress.md`, then `plan.md`. Team rules for Claude are in `../CLAUDE.md`.

| Question | File |
|---|---|
| Where are we? What has been done? How good is each model? | `progress.md` |
| What's next? Every idea with its status, decisions, open questions | `plan.md` |
| How does the current model work, rule by rule? | `model.md` |
| What do we know about our data (audits, trust in each source, rules of use)? | `data.md` |
| Which papers, datasets, models and tools do we use, and how? | `sources.md` |
| Every experiment, with its numbers | `experiments.md` (newest first) |
| One problem studied in depth | `deep-dives/` (one file per dive) |

Rules for keeping them current: after every step update `progress.md` and `plan.md`; log each
experiment in `experiments.md`; when the model changes, update `model.md`; never delete a row in
`plan.md` (mark it `dropped` with the reason).
