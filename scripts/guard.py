"""Refuse a commit that would publish match data. Runs as a git pre-commit hook and in CI.

This repository is public and the match data is licensed for the competition only, so anything
that reconstructs it -- the files themselves, a notebook that printed tracking rows, a clip from
the video -- must never be committed. .gitignore already keeps data/ out; this catches what it
cannot:

  - any path under data/ other than data/README.md (someone force-added a file)
  - video, archive and pickle files anywhere in the tree
  - file names of the match assets, or of the private full-match ground truth
  - any file over MAX_BYTES (the largest legitimate file here is a 1.7 MB baseline CSV)
  - notebooks with saved outputs, which is how printed tracking rows usually leak

    python scripts/guard.py            # every tracked file (what CI runs)
    python scripts/guard.py --staged   # only what is about to be committed (the hook)

Turn the hook on once per clone:  git config core.hooksPath .githooks
"""

import argparse
import fnmatch
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Params
MAX_BYTES = 5 * 1024 * 1024
ALLOWED_IN_DATA = {"data/README.md"}
BLOCKED_PATTERNS = (
    "*.mp4", "*.mov", "*.avi", "*.mkv", "*.zip", "*.gz", "*.gzip", "*.7z", "*.tar",
    "*.pkl", "*.pickle", "*.parquet", "*.feather", "*.npy", "*.npz", "*.h5",
    "*_atd.txt", "*_atd.xml", "*_homography.csv", "*_smart_tagging.xml",
    "*_possession_gt.csv", "*_possession_gt_meta.json", "*_possession_gt_reference.csv",
)


def listed_files(staged):
    """Paths git would publish: the staged additions and changes, or everything tracked."""
    if staged:
        command = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    else:
        command = ["git", "ls-files"]
    out = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def notebook_has_outputs(path):
    with open(path, encoding="utf-8") as handle:
        notebook = json.load(handle)
    return any(cell.get("outputs") or cell.get("execution_count") is not None
               for cell in notebook.get("cells", []) if cell.get("cell_type") == "code")


def problems(paths):
    found = []
    for path in paths:
        full = os.path.join(ROOT, path)
        name = os.path.basename(path)
        if path.startswith("data/") and path not in ALLOWED_IN_DATA:
            found.append((path, "inside data/, which must stay local"))
        elif any(fnmatch.fnmatch(name, pattern) for pattern in BLOCKED_PATTERNS):
            found.append((path, "file type or name of a match asset"))
        elif os.path.isfile(full) and os.path.getsize(full) > MAX_BYTES:
            found.append((path, "larger than {} MB".format(MAX_BYTES // (1024 * 1024))))
        elif path.endswith(".ipynb") and os.path.isfile(full) and notebook_has_outputs(full):
            found.append((path, "notebook has saved outputs -- clear them before committing"))
    return found


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--staged", action="store_true", help="check only staged files")
    args = parser.parse_args()

    found = problems(listed_files(args.staged))
    if not found:
        print("guard: OK")
        sys.exit(0)
    print("guard: refusing -- this would publish something that must stay local:\n")
    for path, why in found:
        print("  {}  ({})".format(path, why))
    print("\nUnstage it (git restore --staged <path>) or fix it, then commit again.")
    sys.exit(1)
