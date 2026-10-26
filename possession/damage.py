"""Make a clean match look like ours: add our tracker's faults, in our tracker's amounts.

The open-data matches (possession/external.py) have clean tracking: DFL never loses the ball, no
team ever has 12 objects, nobody stands motionless in a goal. A method set up on clean data would
meet our match unprepared. So before testing on them we add the faults the audits measured on our
match (docs/research.md section 7), at the rates measured there. Every rate comes from whole-match
tracking counts of our match (our_profile, or the audits for the two constants) -- never from its
ground truth, public or private.

Faults:
  ball gaps     how our tracker places its gaps is the one thing we cannot measure without
                answers, so there are three scenarios and a method must hold up in all of them:
                  stoppage  the ball vanishes on STOPPAGE_DROP of stoppages of 5 s or more, from
                            about when play stops to about the restart (what the gap clips and
                            the audits suggest), then live-play gaps until the match's missing
                            share is reached
                  mixed     the same with half the stoppages
                  random    gaps of our match's lengths anywhere (the old damage test's view)
  ball noise    BALL_NOISE m of error that drifts smoothly over ~NOISE_SMOOTH frames. Tracking
                errors are smooth, not independent per frame: our tracker's ball moves in steps of
                a millimetre while sitting ~0.8 m from the broadcast tracker's. Independent
                per-frame jitter would make a still ball look like it moves at ~4 m/s.
  missing       players dropped for a few seconds at a time, on our share of frames with fewer
                than 18 objects
  extra         a near-duplicate of a player, on our share of frames with 12+ in a team
  ghost         a motionless away-labelled object in front of the home goal, GHOST_FRAMES frames
  speed lag     the speed column delayed by SPEED_LAG frames

    from possession.damage import our_profile, damage
    profile = our_profile()
    damaged = damage(t, "stoppage", np.random.default_rng(0), profile)
"""

import numpy as np

from possession.external import load_source

# Params
FPS = 25
SCENARIOS = ("stoppage", "mixed", "random")
STOPPAGE_MIN = 5 * FPS        # our tracker has (almost) no gaps shorter than this
STOPPAGE_DROP = {"stoppage": 0.85, "mixed": 0.5}
DROP_EARLY = (-0.5, 1.5)      # s after play stops that the ball vanishes (uniform range)
RETURN_EARLY = (-1.5, 0.5)    # s relative to the restart that it comes back
BALL_NOISE = 0.3              # m, per axis
NOISE_SMOOTH = FPS            # frames over which the error drifts
MISSING_PLAYERS = (2, 5)      # players dropped at once
MISSING_RUN = (1, 10)         # s
EXTRA_RUN = (1, 10)           # s
GHOST_FRAMES = 3381           # audit_confirm.py, our match
GHOST_RUNS = 22               # in this many stretches
GHOST_DEPTH = 4.0             # m in front of the goal line
SPEED_LAG = 7                 # frames, audit_tracking.py
HOME, AWAY = 0, 1


def _graded(halves, n):
    mask = np.zeros(n, dtype=bool)
    for _, first, last in halves:
        mask[first:last + 1] = True
    return mask


def _runs(mask):
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def our_profile():
    """The fault rates of our match, from its tracking alone."""
    t = load_source("tactical")
    graded = _graded(t["halves"], len(t["ball"]))
    missing = np.isnan(t["ball"][:, 0])
    gaps = np.array([b - a for a, b in _runs(missing & graded)])
    present = ~np.isnan(t["players"][:, :, 0])
    per_team = {code: present[:, t["team"] == code].sum(axis=1)[graded] for code in (HOME, AWAY)}
    return {
        "missing_share": float(missing[graded].mean()),
        "gap_lengths": gaps[gaps >= STOPPAGE_MIN],
        "few_players_share": float(((per_team[HOME] + per_team[AWAY]) < 18).mean()),
        "extra_share": {code: float((per_team[code] > 11).mean()) for code in (HOME, AWAY)},
    }


def _cover(n_target, length_range, allowed, rng):
    """A mask of runs (lengths in s from length_range) inside `allowed`, about n_target frames."""
    mask = np.zeros(len(allowed), dtype=bool)
    candidates = np.flatnonzero(allowed)
    if not len(candidates):
        return mask
    while mask.sum() < n_target:
        start = int(rng.choice(candidates))
        length = int(rng.uniform(*length_range) * FPS)
        mask[start:start + length] = True
    return mask & allowed


def _ball_gaps(labels, graded, scenario, profile, rng):
    """Mask of frames whose ball is removed."""
    n = len(labels)
    gone = np.zeros(n, dtype=bool)
    target = profile["missing_share"] * graded.sum()
    if scenario in STOPPAGE_DROP:
        for a, b in _runs((labels == "D") & graded):
            if b - a >= STOPPAGE_MIN and rng.random() < STOPPAGE_DROP[scenario]:
                first = a + int(rng.uniform(*DROP_EARLY) * FPS)
                last = b + int(rng.uniform(*RETURN_EARLY) * FPS)
                gone[max(first, 0):max(last, first)] = True
        allowed = graded & np.isin(labels, ("H", "A"))
    else:
        allowed = graded
    candidates = np.flatnonzero(allowed)
    while (gone & graded).sum() < target and len(candidates):
        length = int(rng.choice(profile["gap_lengths"]))
        start = int(rng.choice(candidates))
        gone[start:start + length] = True
    return gone & graded


def _smooth_noise(n, rng):
    """(n, 2) error in metres: white noise averaged over NOISE_SMOOTH frames, rescaled so each
    axis has a standard deviation of BALL_NOISE."""
    kernel = np.ones(NOISE_SMOOTH) / NOISE_SMOOTH
    raw = rng.normal(size=(n + NOISE_SMOOTH, 2))
    smooth = np.stack([np.convolve(raw[:, k], kernel, mode="valid")[:n] for k in range(2)], axis=1)
    return smooth / smooth.std(axis=0) * BALL_NOISE


def damage(t, scenario, rng, profile):
    """A damaged copy of an external match `t` (from load_source). Labels are left untouched."""
    n, slots = t["players"].shape[:2]
    pitch = np.array(t["pitch"])
    graded = _graded(t["halves"], n)
    labels = t["labels"]
    out = dict(t)

    ball = t["ball"] + _smooth_noise(len(t["ball"]), rng) / pitch
    ball[_ball_gaps(labels, graded, scenario, profile, rng)] = np.nan
    out["ball"] = ball

    # Missing players: a few at a time, for a few seconds.
    players = t["players"].copy()
    few = _cover(profile["few_players_share"] * graded.sum(), MISSING_RUN, graded, rng)
    for a, b in _runs(few):
        on = np.flatnonzero(~np.isnan(players[a, :, 0]))
        if len(on):
            drop = rng.choice(on, size=min(len(on), int(rng.integers(*MISSING_PLAYERS))),
                              replace=False)
            players[a:b, drop] = np.nan

    # Extra objects: one near-duplicate per team, and the ghost, as new slots.
    extra = np.full((n, 3, 2), np.nan)
    extra_team = np.array([HOME, AWAY, AWAY], dtype=np.int8)
    for k, code in enumerate((HOME, AWAY)):
        when = _cover(profile["extra_share"][code] * graded.sum(), EXTRA_RUN, graded, rng)
        for a, b in _runs(when):
            mates = np.flatnonzero((t["team"] == code) & ~np.isnan(players[a, :, 0]))
            if len(mates):
                extra[a:b, k] = players[a:b, rng.choice(mates)] + rng.normal(0, 0.5, 2) / pitch
    for _, first, last in t["halves"]:
        rows = slice(first, last + 1)
        home_x = np.nanmean(t["players"][rows][:, t["team"] == HOME, 0])
        away_x = np.nanmean(t["players"][rows][:, t["team"] == AWAY, 0])
        goal = 0.0 if home_x < away_x else 1.0
        spot = (abs(goal - GHOST_DEPTH / pitch[0]), 0.5)
        far = np.zeros(n, dtype=bool)
        far[rows] = np.abs(t["ball"][rows, 0] - goal) * pitch[0] > 40
        ghost = _cover(GHOST_FRAMES / len(t["halves"]),
                       (GHOST_FRAMES / GHOST_RUNS / FPS,) * 2, far, rng)
        extra[ghost, 2] = spot
    out["players"] = np.concatenate([players, extra], axis=1)
    out["team"] = np.concatenate([t["team"], extra_team])

    speed = np.concatenate([t["speed"], np.zeros((n, 3), dtype=np.float32)], axis=1)
    speed[:, slots:][np.isnan(extra[:, :, 0])] = np.nan
    speed[np.isnan(out["players"][:, :, 0])] = np.nan
    lagged = np.full_like(speed, np.nan)
    lagged[SPEED_LAG:] = speed[:-SPEED_LAG]
    out["speed"] = lagged
    return out
