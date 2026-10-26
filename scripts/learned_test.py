"""Deep dive 1, M15: the learned team call (possession/learned.py) against v4 on the practice test.

Leave one match out: the model that labels a practice match is trained on the other seven only,
on their damaged copies under all three scenarios with damage seed TRAIN_SEED (the test copies use
seeds 0.., as scripts/open_test.py does). Each held-out match is damaged exactly as in open_test,
and v4 and the learned call are scored on the same copies, so every comparison is paired. Both use
v4's stoppages; only the team in live play differs. The switch cost of the decoder is swept.

Also prints the team call's accuracy on frames live in both the answers and v4, by situation
(ball travelling with nobody within 1 m, ball at a player's feet, ball missing), as in step 9 of
the deep dive.

--importance instead asks what the model leans on: for each held-out match (its leave-one-out
model, possession.learned.trained_model), one family of clues at a time is shuffled across frames
and the drop in the team call's accuracy is measured. A family whose loss costs little is either
useless or duplicated by another.

    .venv/bin/python scripts/learned_test.py [--switch 5 10 20 40 80] [--seeds 2]
    .venv/bin/python scripts/learned_test.py --importance
    .venv/bin/python scripts/learned_test.py --oracle

--oracle asks where v5 still loses points: v5 with the true stoppages (team decoded within the
true live stretches), and v5's stoppages with the true team in live play; plus possessions per
minute against the truth.

Open data only. Prints scores only.
"""

import argparse
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

from possession import learned  # noqa: E402
from possession.damage import SCENARIOS, damage, our_profile  # noqa: E402
from possession.external import load_source, sources  # noqa: E402

TRAIN_SEED = 100
SITUATIONS = ("travelling", "at feet", "missing")
FAMILIES = {
    "near": ("near_", "second_", "within_"),
    "before and after": ("past", "next", "closer_share"),
    "control": ("touch_", "hold_", "v4", "v3", "nearest", "vote", "live_"),
    "ball": ("ball_",),
    "team shape": ("x_", "spread_", "speed_", "goalside_"),
}


def possessions_per_minute(labels, graded):
    live = np.isin(np.where(graded, labels, "D"), ("H", "A"))
    starts = live & np.r_[True, labels[1:] != labels[:-1]]
    return starts.sum() / (graded.sum() / (60 * 25))


def oracle():
    """What-if scores on top of v5 (see the docstring); damage seed 2, three scenarios."""
    profile = our_profile()
    keys = ("v5", "v5 + true stoppages", "v5 stoppages + true team", "truth")
    scores = {k: [] for k in keys}
    rates = {k: [] for k in keys}
    for name in learned.practice_matches():
        t = load_source(name)
        gt_codes = pm.label_codes(t["labels"])
        graded = t["labels"] != "X"
        model = learned.trained_model(name)
        for scenario in SCENARIOS:
            dead, ours, theirs, _ = learned.both_views(
                damage(t, scenario, np.random.default_rng(2), profile))
            p = learned.home_probability(model, ours, theirs)
            v5 = learned.labels_from(learned.decode(p, dead, 10.0), dead)
            true_dead = t["labels"] == "D"
            with_stops = learned.labels_from(learned.decode(p, true_dead, 10.0), true_dead)
            with_team = np.where(np.isin(t["labels"], ("H", "A")) & ~dead, t["labels"], v5)
            for k, labels in zip(keys, (v5, with_stops, with_team, t["labels"])):
                scores[k].append(spell(np.asarray(labels, dtype="<U1"), gt_codes))
                rates[k].append(possessions_per_minute(np.asarray(labels, dtype="<U1"), graded))
        print("  {}".format(name))
    print("\n{:<28} {:>9} {:>16}".format("what-if", "practice", "possessions/min"))
    for k in keys:
        print("{:<28} {:>9.3f} {:>16.2f}".format(k, np.mean(scores[k]), np.mean(rates[k])))


def importance():
    """Accuracy drop on live frames when one family of clues is shuffled (see the docstring)."""
    profile = our_profile()
    drops = {f: [] for f in FAMILIES}
    base = []
    for name in learned.practice_matches():
        t = load_source(name)
        model = learned.trained_model(name)
        truth = np.where(t["labels"] == "H", learned.HOME, learned.AWAY)
        for scenario in SCENARIOS:
            dead, ours, theirs, names = learned.both_views(
                damage(t, scenario, np.random.default_rng(0), profile))
            rows = ~dead & np.isin(t["labels"], ("H", "A"))
            ours, theirs, truth_rows = ours[rows], theirs[rows], truth[rows]

            def accuracy(a, b):
                p = learned.home_probability(model, a, b)
                return np.mean(np.where(p >= 0.5, learned.HOME, learned.AWAY) == truth_rows)

            full = accuracy(ours, theirs)
            base.append(full)
            order = np.random.default_rng(0).permutation(len(ours))
            for family, prefixes in FAMILIES.items():
                cols = [i for i, c in enumerate(names) if c.startswith(prefixes)]
                a, b = ours.copy(), theirs.copy()
                a[:, cols], b[:, cols] = ours[order][:, cols], theirs[order][:, cols]
                drops[family].append(full - accuracy(a, b))
        print("  {}".format(name))
    print("\nteam call right on live frames: {:.1%} with every clue".format(np.mean(base)))
    print("{:<18} {:>8} {:>22}".format("family shuffled", "clues", "accuracy drop (points)"))
    for family, prefixes in FAMILIES.items():
        n = sum(c.startswith(prefixes) for c in names)
        print("{:<18} {:>8} {:>22.1f}".format(family, n, 100 * np.mean(drops[family])))


def spell(labels, gt_codes):
    labels = labels.copy()
    labels[gt_codes == pm.X] = "X"
    return pm.evaluate(gt_codes, pm.label_codes(labels))["spell_f1_mean"]


def situation(ours, names):
    near = np.fmin(ours[:, names.index("near_us")], ours[:, names.index("near_them")])
    return np.where(np.isnan(near), 2, np.where(near < 1.0, 1, 0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--switch", nargs="+", type=float, default=[5, 10, 20, 40, 80])
    parser.add_argument("--seeds", type=int, default=2, help="damaged copies per match and scenario")
    parser.add_argument("--importance", action="store_true", help="which clues the model leans on")
    parser.add_argument("--oracle", action="store_true", help="where v5 still loses points")
    args = parser.parse_args()
    if args.importance:
        importance()
        sys.exit(0)
    if args.oracle:
        oracle()
        sys.exit(0)

    profile = our_profile()
    matches = [s for s in sources() if s not in ("tactical", "broadcast")]
    started = time.time()
    train = {}
    for name in matches:
        t = load_source(name)
        parts = [learned.training_rows(damage(t, s, np.random.default_rng(TRAIN_SEED), profile),
                                       t["labels"]) for s in SCENARIOS]
        train[name] = (np.concatenate([x for x, _ in parts]), np.concatenate([y for _, y in parts]))
    print("training rows: {:,} from {} matches ({:.0f} s)".format(
        sum(len(y) for _, y in train.values()), len(matches), time.time() - started))

    keys = ["v4", "raw"] + ["switch {:g}".format(s) for s in args.switch]
    scores = {k: {s: [] for s in SCENARIOS} for k in keys}
    per_match = {k: {} for k in keys}
    right = {k: np.zeros(len(SITUATIONS)) for k in ("v4", "raw", "learned")}
    total = np.zeros(len(SITUATIONS))
    for name in matches:
        x = np.concatenate([train[m][0] for m in matches if m != name])
        y = np.concatenate([train[m][1] for m in matches if m != name])
        model = learned.fit(x, y)
        del x, y
        t = load_source(name)
        gt_codes = pm.label_codes(t["labels"])
        mine = {k: [] for k in keys}
        for scenario in SCENARIOS:
            for seed in range(args.seeds):
                damaged = damage(t, scenario, np.random.default_rng(seed), profile)
                dead, ours, theirs, names = learned.both_views(damaged)
                p = learned.home_probability(model, ours, theirs)
                v4 = np.where(ours[:, names.index("v4")] > 0, learned.HOME, learned.AWAY)
                calls = {"v4": v4, "raw": np.where(p >= 0.5, learned.HOME, learned.AWAY)}
                for s in args.switch:
                    calls["switch {:g}".format(s)] = learned.decode(p, dead, s)
                for k in keys:
                    result = spell(learned.labels_from(calls[k], dead), gt_codes)
                    scores[k][scenario].append(result)
                    mine[k].append(result)
                both = ~dead & np.isin(t["labels"], ("H", "A"))
                truth = np.where(t["labels"] == "H", learned.HOME, learned.AWAY)
                where = situation(ours, names)
                best = calls["switch {:g}".format(args.switch[len(args.switch) // 2])]
                for j in range(len(SITUATIONS)):
                    rows = both & (where == j)
                    total[j] += rows.sum()
                    for k, call in (("v4", v4), ("raw", calls["raw"]), ("learned", best)):
                        right[k][j] += (call[rows] == truth[rows]).sum()
        for k in keys:
            per_match[k][name] = np.mean(mine[k])
        print("  {:<12} v4 {:.3f}  learned (switch {:g}) {:.3f}  ({:.0f} s)".format(
            name, per_match["v4"][name], args.switch[len(args.switch) // 2],
            per_match["switch {:g}".format(args.switch[len(args.switch) // 2])][name],
            time.time() - started))

    practice = {k: np.mean([np.mean(scores[k][s]) for s in SCENARIOS]) for k in keys}
    print("\n{:<14} {:>9}".format("team call", "practice") + "".join(
        "{:>10}".format(s) for s in SCENARIOS) + "{:>16}".format("beats v4 (runs)"))
    print("-" * 70)
    runs = np.concatenate([scores["v4"][s] for s in SCENARIOS])
    for k in keys:
        mine = np.concatenate([scores[k][s] for s in SCENARIOS])
        print("{:<14} {:>9.3f}".format(k, practice[k]) + "".join(
            "{:>10.3f}".format(np.mean(scores[k][s])) for s in SCENARIOS) +
            "{:>16}".format("{}/{}".format(int((mine > runs).sum()), len(runs))))
    print("\nTeam call right, frames live in the answers and in v4 (switch {:g} for 'learned'):".format(
        args.switch[len(args.switch) // 2]))
    print("{:<12} {:>8} {:>8} {:>8} {:>9}".format("situation", "share", "v4", "raw", "learned"))
    for j, s in enumerate(SITUATIONS):
        print("{:<12} {:>8.0%} {:>8.1%} {:>8.1%} {:>9.1%}".format(
            s, total[j] / total.sum(), right["v4"][j] / total[j], right["raw"][j] / total[j],
            right["learned"][j] / total[j]))
    print("{:<12} {:>8} {:>8.1%} {:>8.1%} {:>9.1%}".format(
        "all", "", right["v4"].sum() / total.sum(), right["raw"].sum() / total.sum(),
        right["learned"].sum() / total.sum()))
