# Experiment 001: Short possession blips

## Mission statement (MS)

Test whether removing very short `H → A → H` or `A → H → A` runs reduces fake turnovers.
Start with the official `smooth25` baseline. Change only short team reversals; leave dead-ball
labels alone. The main rule removes reversals shorter than 10 frames (0.4 seconds). A 25-frame
version checks whether the conclusion is sensitive to that choice.

## What counts as useful evidence

- Fewer spurious transitions and a sensible full-match possession count.
- No large rise in missed transitions or loss of short real possessions.
- Public `spellF1` and `macroF1` are diagnostics only: the public sample has 17 possessions and
  cannot reliably rank these versions.

## Run

From the repository root:

```bash
.venv/bin/python experiments/001_persistence/run.py
```

The script prints aggregate results and writes candidate CSVs to ignored `data/derived/experiments/001_persistence/`.
Copy the aggregate results and conclusion into `results.md`. Keep each later experiment in its own
numbered folder with a mission statement, method, run command, results, and conclusion.
