"""Score every method on the open-data matches, clean and with our tracker's faults added.

This is the test we may tune against. The public 5 minutes of our match are off limits for tuning
(CLAUDE.md, issue #10) and too short to rank methods anyway; these are 8 whole matches (~13 hours)
with an answer on every frame. Each match is scored as it comes (clean) and after
possession/damage.py adds our tracker's faults under each ball-gap scenario. A method we keep must
do well in all three scenarios, not just the one we think is right.

Caveats: DFL's "possession" and our ground truth's are close but not identical (both come from a
tracking provider's fields, CHALLENGE.md), and Metrica's labels are derived from events. Treat
gaps between methods here as real only when they hold across matches and scenarios.

    python scripts/open_test.py                         # every method: one practice score each
    python scripts/open_test.py --methods blackout_v1 v2 --detail   # the full breakdown

The default output is one PRACTICE SCORE per method: its spellF1 averaged over the 8 matches and
the three damage scenarios. That is the number to compare. --detail adds the per-scenario table.

CALIBRATION. The published baselines' real full-match scores (EVALUATION.md) are printed beside
them: a scenario whose numbers and ranking sit near the real ones is the more realistic one.

Prints scores only.
"""

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
sys.path.insert(0, HERE)
import possession_metrics as pm  # noqa: E402
from damage_test import FULL_MATCH  # noqa: E402

from possession.damage import SCENARIOS, damage, our_profile  # noqa: E402
from possession.external import load_source, sources  # noqa: E402
from possession.methods import METHODS  # noqa: E402


def score(method, t, gt_codes):
    labels = np.asarray(method(t), dtype="<U1").copy()
    labels[gt_codes == pm.X] = "X"
    result = pm.evaluate(gt_codes, pm.label_codes(labels))
    graded = gt_codes != pm.X
    return result["spell_f1_mean"], result["macro_f1"], float((labels[graded] == "D").mean())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--methods", nargs="+", default=sorted(METHODS), choices=sorted(METHODS))
    parser.add_argument("--seeds", type=int, default=2, help="damaged copies per match and scenario")
    parser.add_argument("--first-seed", type=int, default=0,
                        help="first damage seed; a new range gives fresh copies to confirm a choice")
    parser.add_argument("--detail", action="store_true", help="also print the per-scenario table")
    args = parser.parse_args()

    profile = our_profile()
    matches = [s for s in sources() if s not in ("tactical", "broadcast")]
    print("{} matches; faults at our match's rates: ball missing {:.0%}, <18 objects {:.0%},"
          " 12+ home/away {:.0%}/{:.0%}; {} seeds each\n".format(
              len(matches), profile["missing_share"], profile["few_players_share"],
              profile["extra_share"][0], profile["extra_share"][1], args.seeds))

    columns = ["clean"] + list(SCENARIOS)
    results = {m: {c: [] for c in columns} for m in args.methods}
    dead = {m: [] for m in args.methods}
    truth_dead = []
    for name in matches:
        t = load_source(name)
        gt_codes = pm.label_codes(t["labels"])
        truth_dead.append(float((gt_codes[gt_codes != pm.X] == pm.D).mean()))
        for scenario in SCENARIOS:
            for seed in range(args.first_seed, args.first_seed + args.seeds):
                damaged = damage(t, scenario, np.random.default_rng(seed), profile)
                for m in args.methods:
                    spell, _, d = score(METHODS[m], damaged, gt_codes)
                    results[m][scenario].append(spell)
                    if scenario == "stoppage":
                        dead[m].append(d)
        for m in args.methods:
            results[m]["clean"].append(score(METHODS[m], t, gt_codes)[0])
        print("  scored {}".format(name))

    practice = {m: np.mean([np.mean(results[m][c]) for c in SCENARIOS]) for m in args.methods}
    print("\n{:<20} {:>15} {:>22} {:>16}".format(
        "method", "practice score", "dead ball (truth {:.0%})".format(np.mean(truth_dead)),
        "real match score"))
    print("-" * 76)
    for m in sorted(args.methods, key=lambda m: -practice[m]):
        real = FULL_MATCH.get(m)
        print("{:<20} {:>15.3f} {:>22.0%} {:>16}".format(
            m, practice[m], np.mean(dead[m]), "{:.3f}".format(real) if real is not None else "-"))
    print("\npractice score: spellF1 averaged over {} matches and 3 ways of damaging them; higher "
          "is better.\nreal match score: the organisers' published full-match score, known only "
          "for their baselines.".format(len(matches)))
    if not args.detail:
        sys.exit(0)

    header = "\n{:<20}".format("spellF1 (mean, min-max)") + "".join(
        "{:>19}".format(c) for c in columns) + "{:>12}{:>12}".format("D share", "real match")
    print(header + "\n" + "-" * len(header))
    for m in args.methods:
        cells = ["{:.3f} ({:.2f}-{:.2f})".format(np.mean(v), np.min(v), np.max(v))
                 for v in (results[m][c] for c in columns)]
        real = FULL_MATCH.get(m)
        print("{:<20}".format(m) + "".join("{:>19}".format(c) for c in cells)
              + "{:>12.0%}{:>12}".format(np.mean(dead[m]),
                                         "{:.3f}".format(real) if real is not None else "-"))
    print("{:<20}".format("truth") + " " * 19 * len(columns) + "{:>12.0%}".format(
        np.mean(truth_dead)))
    print("\nD share: predicted dead-ball share under the stoppage scenario, against the truth")
    print("real match: the published full-match spellF1 on BAR-ATH, where known (calibration)")
