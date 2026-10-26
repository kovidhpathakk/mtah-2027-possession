"""Every method we can run, by name. run.py, the damage test and the sanity report all use this.

A method is a function (tracking, frames=None) -> one H/A/D label per video frame, before the
match rules in possession.polish. `frames`, when given, says only those frames will be scored, so
a method may skip work elsewhere -- the damage test passes the public window and runs each method
hundreds of times. A method must be deterministic: same arrays in, same labels out.
"""

from possession import baseline, blackout, cleanup, learned, stoppages, tagging


def _tags(tracking):
    """Smart Tagging for a match: imitation tags attached to a practice match, the real tags for
    ours, else none."""
    if "tags" in tracking:
        return tracking["tags"]
    if len(tracking["ball"]) == tagging.OUR_FRAMES:
        return tagging.real_tags()
    return None



METHODS = {
    "v5": lambda tracking, frames=None: learned.predict(tracking, frames, switch_cost=10.0),
    "v5_switch5": lambda tracking, frames=None: learned.predict(tracking, frames, switch_cost=5.0),
    "v5_switch20": lambda tracking, frames=None: learned.predict(tracking, frames, switch_cost=20.0),
    "v4": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, team_by="control", control_options=dict(touch=True)),
    "v4_tags": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, team_by="control",
        control_options=dict(touch=True, tags=_tags(tracking), stale=4)),
    "v3": lambda tracking, frames=None: stoppages.predict(tracking, frames, team_by="control"),
    "v2": lambda tracking, frames=None: stoppages.predict(tracking, frames),
    "v2_precise": lambda tracking, frames=None: stoppages.predict(tracking, frames, precise=True),
    "v2_return": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, near_return=stoppages.NEAR_RETURN),
    "v2_return_nolong": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, near_return=stoppages.NEAR_RETURN, long_gap=10 ** 9),
    "v2_return_nolong_slow75": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, near_return=stoppages.NEAR_RETURN, long_gap=10 ** 9, slow_share=0.75),
    "v2_gaps_only": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, rules=("gaps",)),
    "v2_no_still": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, rules=("out", "gaps")),
    "v2_live_vote": lambda tracking, frames=None: stoppages.predict(
        tracking, frames, live_vote=True),
    "blackout_v1": lambda tracking, frames=None: blackout.predict(tracking, frames),
    "blackout_v1_clean": lambda tracking, frames=None: blackout.predict(
        cleanup.clean(tracking), frames),
    "baseline": lambda tracking, frames=None: baseline.predict(tracking, 50, frames),
    "baseline_raw": lambda tracking, frames=None: baseline.predict(tracking, 0, frames),
    "baseline_smooth25": lambda tracking, frames=None: baseline.predict(tracking, 25, frames),
    "baseline_smooth125": lambda tracking, frames=None: baseline.predict(tracking, 125, frames),
}
DEFAULT_METHOD = "v5"  # python run.py builds the current best model
