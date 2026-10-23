"""Does a full-match submission look like football? Checks that need no ground truth.

The public answers cover 5 minutes; the ranking covers 106. This reads whole-match submission
files and reports what they claim -- how many possessions, how long, how much dead ball -- and how
well they agree with Smart Tagging, which covers the whole match. The same figures are computed
for the public ground truth over its 5 minutes, as the reference for what the truth looks like.

    python scripts/sanity_report.py                                  # every CSV in results/
    python scripts/sanity_report.py evaluation/results/ours_x.csv    # specific files

Columns:
  poss/min    possessions per graded minute. A flickering model reports far too many; an
              over-smoothed one far too few.
  mean/med s  possession length. <1s = share of possessions shorter than a second.
  D%          share of graded frames that are dead ball.  H% = Barça share of live frames.
  tag att     on frames inside an attacking phase (Build Up, Progression, ...), the share of
              live predictions naming the tagged team.
  tag def     the same inside defending phases, where the possessor is the OTHER team.
  setpc D     share of set-piece tags with a predicted D somewhere inside the tagged window.
  gap H/A/D   what the submission says while the tracker has lost the ball.

The truth row is 5 minutes only, so treat it as a rough guide, not a target to hit exactly.
Smart Tagging is automatic and noisy: even the truth will not agree with it everywhere.

Prints aggregates only.
"""

import argparse
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
sys.path.insert(0, os.path.join(ROOT, "starter"))
import possession_metrics as pm  # noqa: E402
import load_smart_tagging  # noqa: E402
from games import GAME, GAMES, half_video_blocks  # noqa: E402

from possession.tracking import load_tracking  # noqa: E402

# Params
RESULTS_DIR = os.path.join(ROOT, "evaluation", "results")
GT_PATH = os.path.join(ROOT, "evaluation", "gt", "BAR-ATH_possession_gt_public.csv")
FPS = GAMES[GAME]["fps"]
TEAM_CODE = {"barcelona": pm.H, "atletic club": pm.A}
# Phases where the tagged team has the ball, and phases where it is defending (so the other team
# has it). GOALS is left out: a goal ends with the ball dead, so the team says little about it.
ATTACKING = {"build up", "progression", "creating chances", "attacking transition",
             "ball in final third", "ball in the box", "players in the box", "long ball"}
DEFENDING = {"defending in defensive third", "defending in middle third",
             "defending in attacking third", "defensive transition"}
SET_PIECES = "set pieces"


def tag_masks(n_frames):
    """Per-frame expected possessor from Smart Tagging (attacking, defending), plus set pieces."""
    attacking = np.full(n_frames, -1, dtype=np.int8)
    defending = np.full(n_frames, -1, dtype=np.int8)
    set_pieces = []
    for event in load_smart_tagging.load():
        code = (event["code"] or "").strip().lower()
        first, stop = event["start_frame"], min(event["end_frame"], n_frames)
        if code == SET_PIECES:
            set_pieces.append((first, stop))
            continue
        team = TEAM_CODE.get((event["tags"].get("Team") or "").strip().lower())
        if team is None:
            continue
        if code in ATTACKING:
            attacking[first:stop] = team
        elif code in DEFENDING:
            defending[first:stop] = pm.A if team == pm.H else pm.H
    return attacking, defending, set_pieces


def describe(codes, mask, attacking, defending, set_pieces, ball_missing):
    """Every column of the report for one label array, over the frames in `mask`."""
    runs = pm.valid_runs(np.where(mask, pm.H, pm.X))  # the graded spans, as the scorer uses them
    filled = pm.fill_abstentions(codes, runs)
    spells = pm.possession_spells(filled, runs)
    lengths = np.array([stop - start for start, stop, _ in spells]) / FPS
    minutes = mask.sum() / FPS / 60.0

    graded = filled[mask]
    alive = np.isin(graded, (pm.H, pm.A))

    def agreement(expected):
        inside = mask & (expected >= 0) & np.isin(filled, (pm.H, pm.A))
        return float((filled[inside] == expected[inside]).mean()) if inside.any() else np.nan

    in_window = [(a, b) for a, b in set_pieces if mask[a:b].any()]
    with_dead = sum(bool((filled[a:b] == pm.D).any()) for a, b in in_window)

    gap = mask & ball_missing
    gap_share = [float((filled[gap] == code).mean()) for code in (pm.H, pm.A, pm.D)]

    return {
        "poss": len(spells),
        "poss/min": len(spells) / minutes,
        "mean s": float(lengths.mean()) if len(lengths) else 0.0,
        "med s": float(np.median(lengths)) if len(lengths) else 0.0,
        "<1s": float((lengths < 1).mean()) if len(lengths) else 0.0,
        "D%": float((graded == pm.D).mean()),
        "H%": float((graded[alive] == pm.H).mean()) if alive.any() else np.nan,
        "tag att": agreement(attacking),
        "tag def": agreement(defending),
        "setpc D": with_dead / len(in_window) if in_window else np.nan,
        "gap": gap_share,
    }


def row(name, stats):
    return ("{:<22} {:>5} {:>8.2f} {:>6.1f} {:>6.1f} {:>5.0%} {:>5.0%} {:>5.0%} {:>7.0%} {:>7.0%}"
            " {:>7.0%}   {:.0%}/{:.0%}/{:.0%}").format(
        name[:22], stats["poss"], stats["poss/min"], stats["mean s"], stats["med s"],
        stats["<1s"], stats["D%"], stats["H%"], stats["tag att"], stats["tag def"],
        stats["setpc D"], *stats["gap"])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", help="submission CSVs (default: all in results/)")
    args = parser.parse_args()
    files = args.files or sorted(glob.glob(os.path.join(RESULTS_DIR, "*.csv")))

    gt_codes = pm.label_codes(pm.read_label_csv(GT_PATH))
    n_frames = len(gt_codes)
    attacking, defending, set_pieces = tag_masks(n_frames)
    ball_missing = np.isnan(load_tracking()["ball"][:, 0])

    match = np.zeros(n_frames, dtype=bool)
    for _, first, last in half_video_blocks(GAME):
        match[first:last + 1] = True
    window = gt_codes != pm.X

    header = ("{:<22} {:>5} {:>8} {:>6} {:>6} {:>5} {:>5} {:>5} {:>7} {:>7} {:>7}   {}").format(
        "submission", "poss", "poss/min", "mean s", "med s", "<1s", "D%", "H%",
        "tag att", "tag def", "setpc D", "gap H/A/D")
    print(header + "\n" + "-" * len(header))
    print(row("TRUTH (5 min only)",
              describe(gt_codes, window, attacking, defending, set_pieces, ball_missing)))
    for path in files:
        codes = pm.label_codes(pm.read_label_csv(path))
        name = os.path.splitext(os.path.basename(path))[0]
        print(row(name, describe(codes, match, attacking, defending, set_pieces, ball_missing)))
        print(row("  same, 5 min only",
                  describe(codes, window, attacking, defending, set_pieces, ball_missing)))
