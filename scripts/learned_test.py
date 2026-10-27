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
    .venv/bin/python scripts/learned_test.py --stoppages
    .venv/bin/python scripts/learned_test.py --possessions [--method v5]
    .venv/bin/python scripts/learned_test.py --air
    .venv/bin/python scripts/learned_test.py --short

--short asks why short possessions (under 5 s) are missed: inside each true one, does the team
model favour the right team (mean P >= 0.5: the decoder suppresses it) or not (the model misses
it)? Broken down by situation: ball in the air (DFL height), a duel (both teams within 2 m), just
after a stoppage (first 3 s), ball missing in the damaged copy.

--air asks how v6 copes with the ball in the air. Our tracking is flat (no height): a lofted ball
is lost or placed where its shadow falls, under players' heads. DFL measures the ball's height,
so on the DFL matches (clean height, damaged tracking, held-out models) the team call and the
stoppage call are scored by ball height, and the 2 s after a high ball comes down are scored on
their own (who wins the landing). Also checks the 2D proxy "ball moving at 18 m/s+" for "in the
air", which is all we could use on our match.

--possessions asks which possessions a method finds: each true possession (a run of H or of A in
the answers) counts as found when a predicted possession of the same team overlaps it with
temporal IoU >= 0.5 (the middle of spellF1's 0.3-0.7 range); each predicted one counts as real
when it matches a true one the same way. Broken down by length, to see whether the missing
possessions are the short ones.

--stoppages tests learned stoppages (deep dive 4) on top of v5's team call: the stoppage model's
answers thresholded and tidied like v2's, or decoded together with the team model
(possession.learned.decode_joint) at several costs per stoppage edge. Same held-out copies as the
main test; v5 (v4's stoppage rules) is the reference. Also prints how many truly dead frames each
calls live (missed) and how many live frames it calls dead (false), per scenario, because the
three ways of placing ball gaps are where a learned stoppage model could fool itself.

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

from possession import cleanup, control, learned, stoppages  # noqa: E402
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


THRESHOLDS = (0.4, 0.5, 0.6)
LIVE_COSTS = (5.0, 10.0, 20.0, 40.0)


def stoppage_test(seeds, live_costs=LIVE_COSTS, switch_costs=(10.0,), first_seed=0):
    """Learned stoppages vs v4's rules, both with v5's team call (see the docstring)."""
    profile = our_profile()
    pairs = [(c, w) for c in live_costs for w in switch_costs]
    label = {pair: "joint {:g}".format(pair[0]) if len(switch_costs) == 1 else
             "joint {:g}/{:g}".format(*pair) for pair in pairs}
    keys = ["v5"] + ["threshold {:.1f}".format(th) for th in THRESHOLDS] + [label[p] for p in pairs]
    scores = {k: {s: [] for s in SCENARIOS} for k in keys}
    missed = {k: {s: [] for s in SCENARIOS} for k in keys}
    false = {k: {s: [] for s in SCENARIOS} for k in keys}
    started = time.time()
    for name in learned.practice_matches():
        t = load_source(name)
        gt_codes = pm.label_codes(t["labels"])
        graded = t["labels"] != "X"
        true_dead = graded & (t["labels"] == "D")
        true_live = graded & ~true_dead
        mine = {k: [] for k in keys}
        for scenario in SCENARIOS:
            for seed in range(first_seed, first_seed + seeds):
                damaged = damage(t, scenario, np.random.default_rng(seed), profile)
                p_dead, p_home = learned.probabilities(damaged, name)
                rules = stoppages.tidy(stoppages.dead_mask(cleanup.clean(damaged)))
                calls = {"v5": learned.labels_from(learned.decode(p_home, rules, 10.0), rules)}
                for th in THRESHOLDS:
                    dead = stoppages.tidy(p_dead >= th)
                    calls["threshold {:.1f}".format(th)] = learned.labels_from(
                        learned.decode(p_home, dead, 10.0), dead)
                for pair in pairs:
                    path = learned.decode_joint(p_dead, p_home, *pair)
                    calls[label[pair]] = learned.labels_from(path, path == 2)
                for k in keys:
                    result = spell(calls[k], gt_codes)
                    scores[k][scenario].append(result)
                    mine[k].append(result)
                    missed[k][scenario].append(np.mean(calls[k][true_dead] != "D"))
                    false[k][scenario].append(np.mean(calls[k][true_live] == "D"))
        best = max(keys[1:], key=lambda k: np.mean(mine[k]))
        print("  {:<12} v5 {:.3f}  best learned stoppages ({}) {:.3f}  ({:.0f} s)".format(
            name, np.mean(mine["v5"]), best, np.mean(mine[best]), time.time() - started))

    reference = np.concatenate([scores["v5"][s] for s in SCENARIOS])
    print("\n{:<15} {:>9}".format("stoppages", "practice") + "".join(
        "{:>10}".format(s) for s in SCENARIOS) + "{:>12}{:>16}".format("beats v5", "missed / false"))
    print("-" * 86)
    for k in keys:
        mine = np.concatenate([scores[k][s] for s in SCENARIOS])
        print("{:<15} {:>9.3f}".format(k, np.mean([np.mean(scores[k][s]) for s in SCENARIOS])) +
              "".join("{:>10.3f}".format(np.mean(scores[k][s])) for s in SCENARIOS) +
              "{:>12}".format("{}/{}".format(int((mine > reference).sum()), len(mine))) +
              "{:>16}".format("{:.0%} / {:.0%}".format(
                  np.mean([np.mean(missed[k][s]) for s in SCENARIOS]),
                  np.mean([np.mean(false[k][s]) for s in SCENARIOS]))))
    print("\nmissed: truly dead frames called live; false: live frames called dead (graded frames)")
    print("\nper scenario, missed / false:")
    for k in ("v5", "threshold 0.5", label[pairs[len(pairs) // 2]]):
        print("  {:<15}".format(k) + "".join("{:>10}: {:.0%} / {:.0%}".format(
            s, np.mean(missed[k][s]), np.mean(false[k][s])) for s in SCENARIOS))


LENGTHS = ((0, 2), (2, 5), (5, 10), (10, 20), (20, 10 ** 6))  # s


def possession_runs(labels):
    """(start, stop, team) of every run of H or of A."""
    change = np.flatnonzero(np.r_[True, labels[1:] != labels[:-1]])
    stops = np.r_[change[1:], len(labels)]
    keep = np.isin(labels[change], ("H", "A"))
    return change[keep], stops[keep], labels[change][keep]


def matched(a_runs, b_runs, iou=0.5):
    """For each run in a: does a run of b with the same team overlap it with IoU >= iou?"""
    starts, stops, teams = b_runs
    out = []
    for a, b, team in zip(*a_runs):
        lo = np.searchsorted(stops, a, side="right")
        hi = np.searchsorted(starts, b, side="left")
        best = 0.0
        for k in range(lo, hi):
            if teams[k] == team:
                inter = min(b, stops[k]) - max(a, starts[k])
                best = max(best, inter / (max(b, stops[k]) - min(a, starts[k])))
        out.append(best >= iou)
    return np.array(out, dtype=bool)


def possession_test(method, seeds):
    """Found and invented possessions by length (see the docstring)."""
    from possession.methods import METHODS
    profile = our_profile()
    found = {k: [0, 0] for k in LENGTHS}
    real = {k: [0, 0] for k in LENGTHS}
    for name in learned.practice_matches():
        t = load_source(name)
        truth = np.where(t["labels"] == "X", "D", t["labels"])
        true_runs = possession_runs(truth)
        for scenario in SCENARIOS:
            for seed in range(seeds):
                labels = np.asarray(METHODS[method](damage(t, scenario, np.random.default_rng(seed),
                                                           profile)), dtype="<U1").copy()
                labels[t["labels"] == "X"] = "D"
                ours = possession_runs(labels)
                for runs, hits, table in ((true_runs, matched(true_runs, ours), found),
                                          (ours, matched(ours, true_runs), real)):
                    seconds = (runs[1] - runs[0]) / 25
                    for low, high in LENGTHS:
                        inside = (seconds >= low) & (seconds < high)
                        table[(low, high)][0] += int(hits[inside].sum())
                        table[(low, high)][1] += int(inside.sum())
        print("  {}".format(name))
    print("\n{}: possessions by length (IoU >= 0.5, same team)".format(method))
    print("{:<10} {:>12} {:>10} {:>14} {:>10}".format("length s", "true ones", "found", "predicted",
                                                       "real"))
    for low, high in LENGTHS:
        f, r = found[(low, high)], real[(low, high)]
        print("{:<10} {:>12,} {:>10.0%} {:>14,} {:>10.0%}".format(
            "{}-{}".format(low, high if high < 10 ** 6 else ""), f[1], f[0] / max(f[1], 1), r[1],
            r[0] / max(r[1], 1)))


HEIGHTS = (("on the ground (< 0.5 m)", 0.0, 0.5), ("low (0.5-2 m)", 0.5, 2.0),
           ("high (2 m+)", 2.0, 99.0))


def air_test():
    """v6 by ball height on the DFL matches (see the docstring); damage seed 0."""
    profile = our_profile()
    rows = {h[0]: np.zeros(5) for h in HEIGHTS}   # live frames, both live, team right, called dead, visible
    landing = np.zeros(2)
    fast_high, fast_all = 0, 0
    heights = []
    for name in learned.practice_matches():
        t = load_source(name)
        if "ball_z" not in t:
            continue
        z = t["ball_z"].astype(float)
        live = np.isin(t["labels"], ("H", "A"))
        heights.append(np.nanmedian(z[live]))
        pitch = np.array(t["pitch"])
        clean_speed = stoppages.ball_speed(t["ball"] * pitch)
        fast = live & (clean_speed >= 18.0)
        fast_all += int(fast.sum())
        fast_high += int((fast & (z >= 2.0)).sum())
        high = live & (z >= 2.0)
        came_down = np.flatnonzero(high[:-1] & ~high[1:])
        after = np.zeros(len(z), dtype=bool)
        for f in came_down:
            after[f + 1:f + 51] = True
        for scenario in SCENARIOS:
            damaged = damage(t, scenario, np.random.default_rng(0), profile)
            p_dead, p_home = learned.probabilities(damaged, name)
            path = learned.decode_joint(p_dead, p_home, 40.0, 10.0)  # v6
            v6 = learned.labels_from(path, path == 2)
            visible = ~np.isnan(damaged["ball"][:, 0])
            for label, low, top in HEIGHTS:
                rows_ = live & (z >= low) & (z < top)
                both = rows_ & (v6 != "D")
                rows[label] += [rows_.sum(), both.sum(), (v6[both] == t["labels"][both]).sum(),
                                (v6[rows_] == "D").sum(), visible[rows_].sum()]
            both = after & live & (v6 != "D")
            landing += [both.sum(), (v6[both] == t["labels"][both]).sum()]
        print("  {}".format(name))
    print("\nDFL ball height on live frames: median {:.2f} m (sanity: a ball on the ground ~0.1-0.2 m)".format(
        np.median(heights)))
    total = sum(r[0] for r in rows.values())
    print("{:<26} {:>9} {:>14} {:>15} {:>20}".format("ball", "of live", "team right", "called dead",
                                                       "visible (damaged)"))
    for label, r in rows.items():
        print("{:<26} {:>9.1%} {:>14.1%} {:>15.1%} {:>20.0%}".format(
            label, r[0] / total, r[2] / max(r[1], 1), r[3] / max(r[0], 1), r[4] / max(r[0], 1)))
    print("first 2 s after a high ball comes down: team right {:.1%} ({:,} frames)".format(
        landing[1] / max(landing[0], 1), int(landing[0])))
    print("2D proxy: live frames with the ball at 18 m/s+ are high (2 m+) {:.0%} of the time".format(
        fast_high / max(fast_all, 1)))


def short_test():
    """Why short possessions are missed (see the docstring); mixed scenario, damage seed 0."""
    profile = our_profile()
    keys = ("all", "ball high (2 m+)", "duel (both within 2 m)", "first 3 s after a stoppage",
            "ball missing (damaged)", "none of these")
    stats = {(k, band): np.zeros(3) for k in keys for band in ("0-2", "2-5")}  # n, model favours, found
    for name in learned.practice_matches():
        t = load_source(name)
        labels = np.where(t["labels"] == "X", "D", t["labels"])
        damaged = damage(t, "mixed", np.random.default_rng(0), profile)
        p_dead, p_home = learned.probabilities(damaged, name)
        path = learned.decode_joint(p_dead, p_home, 40.0, 10.0)
        v6 = learned.labels_from(path, path == 2)
        v6[t["labels"] == "X"] = "D"
        z = t["ball_z"].astype(float) if "ball_z" in t else np.full(len(labels), np.nan)
        dist = control.team_distances(t["players"], t["ball"], t["team"], tuple(t["pitch"]))
        duel = (dist < 2.0).all(axis=1)
        dead = labels == "D"
        last_dead = np.maximum.accumulate(np.where(dead, np.arange(len(dead)), -10 ** 6))
        after_stop = np.arange(len(dead)) - last_dead <= 75
        missing = np.isnan(damaged["ball"][:, 0])
        true_runs = possession_runs(labels)
        hits = matched(true_runs, possession_runs(v6))
        for (a, b, team), hit in zip(zip(*true_runs), hits):
            seconds = (b - a) / 25
            if seconds >= 5:
                continue
            band = "0-2" if seconds < 2 else "2-5"
            p_team = p_home[a:b] if team == "H" else 1 - p_home[a:b]
            favours = np.mean(p_team) >= 0.5
            flags = {"ball high (2 m+)": np.nanmean(z[a:b]) >= 2.0 if not np.isnan(z[a:b]).all() else False,
                     "duel (both within 2 m)": duel[a:b].mean() >= 0.5,
                     "first 3 s after a stoppage": after_stop[a],
                     "ball missing (damaged)": missing[a:b].mean() >= 0.5}
            flags["none of these"] = not any(flags.values())
            flags["all"] = True
            for k, on in flags.items():
                if on:
                    stats[(k, band)] += [1, favours, hit]
        print("  {}".format(name))
    print("\nshort true possessions: share where the team model favours the right team on average"
          " (the decoder suppressed it) and share v6 found")
    print("{:<30} {:>22} {:>22}".format("situation", "0-2 s: n / favours / found", "2-5 s: n / favours / found"))
    for k in keys:
        cells = []
        for band in ("0-2", "2-5"):
            n, fav, hit = stats[(k, band)]
            cells.append("{:>6,.0f} / {:>4.0%} / {:>4.0%}".format(n, fav / max(n, 1), hit / max(n, 1)))
        print("{:<30} {:>22} {:>22}".format(k, *cells))


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
    parser.add_argument("--stoppages", action="store_true", help="learned stoppages (deep dive 4)")
    parser.add_argument("--possessions", action="store_true", help="found and invented possessions")
    parser.add_argument("--air", action="store_true", help="v6 by ball height (DFL)")
    parser.add_argument("--short", action="store_true", help="why short possessions are missed")
    parser.add_argument("--method", default="v5", help="for --possessions")
    parser.add_argument("--first-seed", type=int, default=0, help="first damage seed of the test copies")
    parser.add_argument("--live-costs", nargs="+", type=float, default=list(LIVE_COSTS),
                        help="for --stoppages")
    parser.add_argument("--switch-costs", nargs="+", type=float, default=[10.0], help="for --stoppages")
    args = parser.parse_args()
    if args.possessions:
        possession_test(args.method, args.seeds)
        sys.exit(0)
    if args.air:
        air_test()
        sys.exit(0)
    if args.short:
        short_test()
        sys.exit(0)
    if args.stoppages:
        stoppage_test(args.seeds, args.live_costs, args.switch_costs, args.first_seed)
        sys.exit(0)
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
