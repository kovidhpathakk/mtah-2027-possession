"""Every method we can run, by name. run.py, the damage test and the sanity report all use this.

A method is a function (tracking, frames=None) -> one H/A/D label per video frame, before the
match rules in possession.polish. `frames`, when given, says only those frames will be scored, so
a method may skip work elsewhere -- the damage test passes the public window and runs each method
hundreds of times. A method must be deterministic: same arrays in, same labels out.
"""

from possession import baseline, blackout

METHODS = {
    "blackout_v1": lambda tracking, frames=None: blackout.predict(tracking, frames),
    "baseline": lambda tracking, frames=None: baseline.predict(tracking, 50, frames),
    "baseline_raw": lambda tracking, frames=None: baseline.predict(tracking, 0, frames),
    "baseline_smooth25": lambda tracking, frames=None: baseline.predict(tracking, 25, frames),
    "baseline_smooth125": lambda tracking, frames=None: baseline.predict(tracking, 125, frames),
}
DEFAULT_METHOD = "baseline"
