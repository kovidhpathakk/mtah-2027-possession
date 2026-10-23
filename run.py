"""Produce our submission: one command, from the data in data/ to a validated CSV.

    python run.py                          # the current best method -> evaluation/results/
    python run.py --method baseline        # a specific method
    python run.py --check-baseline         # prove possession.baseline matches the organisers'

This is the command the technical document points at, and the one the organisers may re-run, so
it must stay deterministic: same data in, byte-identical file out.
"""

import argparse
import filecmp
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "starter"))
from baseline import write_submission  # noqa: E402

from possession import baseline  # noqa: E402
from possession.methods import DEFAULT_METHOD, METHODS  # noqa: E402
from possession.polish import apply_match_rules  # noqa: E402
from possession.tracking import load_tracking  # noqa: E402

# Params
RESULTS_DIR = os.path.join(HERE, "evaluation", "results")


def check_baseline(tracking):
    """possession.baseline must reproduce the committed baseline files byte for byte."""
    ok = True
    with tempfile.TemporaryDirectory() as folder:
        for name, window in (("baseline_raw", 0), ("baseline_smooth25", 25),
                             ("baseline_smooth50", 50), ("baseline_smooth125", 125)):
            path = write_submission(os.path.join(folder, name + ".csv"),
                                    baseline.predict(tracking, window))
            same = filecmp.cmp(path, os.path.join(RESULTS_DIR, name + ".csv"), shallow=False)
            ok &= same
            print("  {:<20} {}".format(name, "identical" if same else "DIFFERS"))
    return ok


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--method", default=DEFAULT_METHOD, choices=sorted(METHODS))
    parser.add_argument("--name", help="output file name, default ours_<method>")
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()

    tracking = load_tracking()
    if args.check_baseline:
        sys.exit(0 if check_baseline(tracking) else 1)

    labels = apply_match_rules(METHODS[args.method](tracking))
    path = write_submission(
        os.path.join(RESULTS_DIR, (args.name or "ours_" + args.method) + ".csv"), labels)
    print("wrote", os.path.relpath(path, HERE))
    subprocess.run([sys.executable, os.path.join(HERE, "evaluation", "validate_submission.py"),
                    path], check=True)
