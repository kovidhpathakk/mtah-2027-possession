"""M15: the team call in live play, learned from the practice matches.

Deep dive 1 (docs/deep-dives/01-ball-travelling.md) found that the team call is worth four times
the stoppages (the true team in live play would lift practice from 0.288 to 0.709), that three
quarters of its errors happen while the ball travels between players, and that our tracker's ball
is smoothed, so v4's rule that reads a touch from the ball's motion gains nothing over v3 on a
realistic practice test. A rule reads one cue at a time; a model trained on the practice matches'
true possession can weigh many weak cues together. Borghesi et al. 2023 learn possession from
tracking features; Link & Hoernig 2017 build control from distances, duration and ball dynamics.
The cues, per frame:
  near      each team's nearest and second-nearest player to the ball, players within NEAR m
  windows   each team's nearest distance over the last and next 0.25-2 s: who the ball came from
            and who it goes to, which a smoothed ball still shows
  control   v3's and v4's control events: team and distance in frames of the last and the next
            one in the same live stretch; v3's and v4's own calls; the nearest player's team
  ball      position, speed, change of velocity, frames since and until it is seen
  shape     each team's position, spread and speed; the share of each team goal-side of the
            ball (the team without the ball drops behind it)
Stoppages stay v4's (possession.stoppages); only the team in live play is learned.

Symmetry: the features are computed from team 0's point of view and again with the teams swapped.
The model is trained on both views and P(team 0) averages the two, so it cannot learn "the home
team has the ball more": true in some practice matches, unknown in ours.

Decoding: per-frame probabilities flicker, and every flicker costs a possession in spellF1. A
two-state Viterbi pass per live stretch picks the team sequence that best fits the probabilities
while paying `switch_cost` (in log-probability) for every change of team.

Training data: only the open-data matches (DFL, Metrica), damaged by possession.damage at our
tracker's measured fault rates under all three ball-gap scenarios. Never our match. A practice
match is labelled by a model trained on the other seven (leave one match out), so
scripts/open_test.py scores v5 honestly; our match gets the model trained on all eight.

Training is deterministic (fixed damage seed, no early stopping, fixed random_state), so a clean
clone retrains the same model. Trained models and training rows are cached in
data/derived/learned/, keyed by a fingerprint of the code that makes them: any change to it
retrains.
"""

import hashlib
import os
import pickle

import numpy as np
import pandas as pd

from possession import baseline, cleanup, control, stoppages
from possession.blackout import VOTE_WINDOW, windowed_mean
from possession.tracking import PITCH

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(os.path.dirname(HERE), "data", "derived", "learned")
# The code that shapes the training rows and the model; the cache key hashes it.
FINGERPRINT_FILES = ("learned.py", "damage.py", "control.py", "stoppages.py", "cleanup.py",
                     "baseline.py", "blackout.py", "external.py")

# Params
FPS = 25
CLIP = 30.0                 # m: farther than this tells nothing more
NEAR = 3.0                  # m
WINDOWS = (6, 12, 25, 50)   # frames looked back and ahead (0.24-2 s)
CAP = 500                   # frames: "since" and "until" counts stop here (20 s)
DIRECTION_WINDOW = 3000     # +/- 2 min: which way each team attacks
SUBSAMPLE = 5               # train on every 5th live frame: neighbours are near copies
SWITCH_COST = 20.0          # log-probability paid per change of team when decoding
TRAIN_SEED = 100            # damage seed of the training copies; tests use seeds 0, 1, ...
MODEL_OPTIONS = dict(max_iter=200, learning_rate=0.1, max_leaf_nodes=31, l2_regularization=1.0,
                     early_stopping=False, random_state=0)
HOME, AWAY, NOBODY = 0, 1, -1


def _signed(codes):
    """HOME -> +1, AWAY -> -1, anything else -> 0."""
    return np.where(codes == HOME, 1.0, np.where(codes == AWAY, -1.0, 0.0))


def _past(values, width, how):
    return getattr(pd.Series(values).rolling(width + 1, min_periods=1), how)().to_numpy()


def _future(values, width, how):
    return _past(values[::-1], width, how)[::-1]


def _team_stats(values, mask):
    """Per frame, over a team's tracked objects: count, mean and standard deviation of `values`."""
    v = values[:, mask]
    on = ~np.isnan(v)
    n = on.sum(axis=1)
    total = np.where(on, v, 0.0).sum(axis=1)
    squares = np.where(on, v * v, 0.0).sum(axis=1)
    mean = np.where(n > 0, total / np.maximum(n, 1), np.nan)
    var = np.where(n > 1, squares / np.maximum(n, 1) - mean ** 2, np.nan)
    return n, mean, np.sqrt(np.maximum(var, 0.0))


def _last_next(events, dead):
    """Signed team of the last and the next control event in the same live stretch, and how many
    frames away each is (CAP if none)."""
    n = len(events)
    index = np.arange(n)
    has = events != NOBODY
    last = np.maximum.accumulate(np.where(has, index, -1))
    following = np.minimum.accumulate(np.where(has, index, n)[::-1])[::-1]
    stretch = np.cumsum(dead)  # equal for two frames only if no dead frame lies between them
    ok_last = (last >= 0) & (stretch[np.maximum(last, 0)] == stretch)
    ok_next = (following < n) & (stretch[np.minimum(following, n - 1)] == stretch)
    signed = _signed(events)
    return (np.where(ok_last, signed[np.maximum(last, 0)], 0.0),
            np.where(ok_last, np.minimum(index - last, CAP), CAP),
            np.where(ok_next, signed[np.minimum(following, n - 1)], 0.0),
            np.where(ok_next, np.minimum(following - index, CAP), CAP))


def _since_until(mask):
    """Frames since the last and until the next True in `mask`, capped at CAP."""
    n = len(mask)
    index = np.arange(n)
    last = np.maximum.accumulate(np.where(mask, index, -CAP))
    following = np.minimum.accumulate(np.where(mask, index, n + CAP)[::-1])[::-1]
    return np.minimum(index - last, CAP), np.minimum(following - index, CAP)


def features(tracking, dead):
    """(n, k) float32 features from team 0's point of view, and their names. `tracking` should
    already be cleaned (possession.cleanup); `dead` is v4's stoppage mask."""
    pitch = np.array(tracking.get("pitch", PITCH), dtype=float)
    team = tracking["team"]
    players = tracking["players"] * pitch
    ball = tracking["ball"] * pitch
    n = len(ball)
    seen = ~np.isnan(ball[:, 0])
    cols = {}

    # Which way team 0 attacks: the other team's players sit nearer the goal team 0 attacks.
    _, home_x, _ = _team_stats(players[:, :, 0], team == HOME)
    _, away_x, _ = _team_stats(players[:, :, 0], team == AWAY)
    forward = np.where(windowed_mean(away_x - home_x, DIRECTION_WINDOW) >= 0, 1.0, -1.0)

    def along(x):  # x in metres measured towards the goal team 0 attacks
        return np.where(forward[:, None] > 0, x, pitch[0] - x) if x.ndim == 2 else \
            np.where(forward > 0, x, pitch[0] - x)

    # Near: distances from the ball to each team.
    d = np.linalg.norm(players - ball[:, None, :], axis=2)
    nearest = {}
    for code, side in ((HOME, "us"), (AWAY, "them")):
        mine = np.where(np.isnan(d[:, team == code]), np.inf, d[:, team == code])
        two = np.sort(mine, axis=1)[:, :2] if mine.shape[1] >= 2 else np.full((n, 2), np.inf)
        first = np.where(seen, np.minimum(two[:, 0], CLIP), np.nan)
        nearest[code] = first
        cols["near_" + side] = first
        cols["second_" + side] = np.where(seen, np.minimum(two[:, 1], CLIP), np.nan)
        cols["within_" + side] = np.where(seen, (mine < NEAR).sum(axis=1), np.nan)
        for w in WINDOWS:
            cols["past{}_{}".format(w, side)] = _past(first, w, "min")
            cols["next{}_{}".format(w, side)] = _future(first, w, "min")
    closer = np.where(seen, (nearest[HOME] < nearest[AWAY]).astype(float), np.nan)
    for w in (12, 50):
        cols["closer_share{}".format(w)] = windowed_mean(closer, w)

    # Control: v3's and v4's events and calls.
    dist = control.team_distances(tracking["players"], tracking["ball"], team, tuple(pitch))
    codes = baseline.nearest_team(tracking["players"], tracking["ball"], team)
    for name, events in (("touch", control.control_events_touch(dist, ball)),
                         ("hold", control.control_events(dist))):
        last, since, following, until = _last_next(events, dead)
        cols[name + "_last"], cols[name + "_since"] = last, since
        cols[name + "_next"], cols[name + "_until"] = following, until
    cols["v4"] = _signed(control.team_by_control(tracking, dead, codes, touch=True))
    cols["v3"] = _signed(control.team_by_control(tracking, dead, codes))
    cols["nearest"] = _signed(codes)
    cols["vote"] = windowed_mean(np.where(codes == NOBODY, np.nan, _signed(codes)), VOTE_WINDOW)
    cols["live_since"], cols["live_until"] = _since_until(dead)

    # Ball.
    v = control.ball_velocity(ball)
    k = control.TOUCH_SPAN
    change = np.full(n, np.nan)
    change[k:-k] = np.linalg.norm(v[2 * k:] - v[:-2 * k], axis=1)
    cols["ball_forward"] = along(ball[:, 0])
    cols["ball_wide"] = np.abs(ball[:, 1] - pitch[1] / 2)
    cols["ball_speed"] = np.linalg.norm(v, axis=1)
    cols["ball_speed_forward"] = v[:, 0] * forward
    cols["ball_change"] = change
    cols["ball_change_past"] = _past(change, 12, "max")
    cols["ball_change_next"] = _future(change, 12, "max")
    cols["ball_since"], cols["ball_until"] = _since_until(seen)

    # Shape: position, spread, speed, goal-side share.
    x_forward = along(players[:, :, 0])
    for code, side in ((HOME, "us"), (AWAY, "them")):
        mask = team == code
        count, mean_x, spread_x = _team_stats(x_forward, mask)
        _, _, spread_y = _team_stats(players[:, :, 1], mask)
        _, mean_speed, _ = _team_stats(tracking["speed"].astype(float), mask)
        cols["x_" + side] = mean_x
        cols["x_" + side + "_moving"] = np.concatenate(([np.nan] * 12, mean_x[24:] - mean_x[:-24],
                                                        [np.nan] * 12)) * FPS / 24
        cols["spread_x_" + side], cols["spread_y_" + side] = spread_x, spread_y
        cols["speed_" + side] = mean_speed
        # Goal-side: between the ball and the team's own goal (team 0 defends the low end).
        behind = x_forward[:, mask] < cols["ball_forward"][:, None] if code == HOME else \
            x_forward[:, mask] > cols["ball_forward"][:, None]
        cols["goalside_" + side] = np.where(seen & (count > 0),
                                            behind.sum(axis=1) / np.maximum(count, 1), np.nan)

    names = list(cols)
    return np.column_stack([np.asarray(cols[c], dtype=np.float32) for c in names]), names


def swapped(tracking):
    """The same match with team codes 0 and 1 exchanged."""
    team = tracking["team"]
    return dict(tracking, team=np.where(team == HOME, AWAY, np.where(team == AWAY, HOME, team))
                .astype(team.dtype))


def both_views(tracking):
    """Clean the tracking, find v4's stoppages, and compute the features from each team's view."""
    tracking = cleanup.clean(tracking)
    dead = stoppages.tidy(stoppages.dead_mask(tracking))
    ours, names = features(tracking, dead)
    theirs, _ = features(swapped(tracking), dead)
    return dead, ours, theirs, names


def training_rows(tracking, labels):
    """Rows for frames live in v4 and in the answers, both views, every SUBSAMPLE-th frame.
    y = 1 when the row's team 0 has the ball."""
    dead, ours, theirs, _ = both_views(tracking)
    rows = np.flatnonzero(~dead & np.isin(labels, ("H", "A")))[::SUBSAMPLE]
    y = labels[rows] == "H"
    return np.concatenate([ours[rows], theirs[rows]]), np.concatenate([y, ~y]).astype(np.int8)


def fit(x, y):
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(**MODEL_OPTIONS).fit(x, y)


def home_probability(model, ours, theirs):
    """P(team 0 has the ball), averaged over the two views."""
    return 0.5 * (model.predict_proba(ours)[:, 1] + 1.0 - model.predict_proba(theirs)[:, 1])


def _viterbi(cost_home, cost_away, switch):
    """Cheapest HOME/AWAY sequence for per-frame costs plus `switch` per change of team."""
    length = len(cost_home)
    came_home, came_away = bytearray(length), bytearray(length)  # 1: came from the other team
    a, b = cost_home[0], cost_away[0]
    for t in range(1, length):
        from_away, from_home = b + switch, a + switch
        if from_away < a:
            came_home[t], a_new = 1, from_away
        else:
            a_new = a
        if from_home < b:
            came_away[t], b_new = 1, from_home
        else:
            b_new = b
        a, b = a_new + cost_home[t], b_new + cost_away[t]
    path = np.empty(length, dtype=np.int8)
    state = HOME if a <= b else AWAY
    for t in range(length - 1, -1, -1):
        path[t] = state
        if (came_home if state == HOME else came_away)[t]:
            state = AWAY if state == HOME else HOME
    return path


def decode(p, dead, switch_cost=SWITCH_COST):
    """HOME/AWAY per frame (dead frames get HOME as a placeholder the caller overwrites)."""
    cost_home = (-np.log(np.clip(p, 1e-4, 1.0))).tolist()
    cost_away = (-np.log(np.clip(1.0 - p, 1e-4, 1.0))).tolist()
    team = np.full(len(p), HOME, dtype=np.int8)
    for a, b in stoppages.runs(~dead):
        team[a:b] = _viterbi(cost_home[a:b], cost_away[a:b], switch_cost)
    return team


def labels_from(team, dead):
    labels = np.where(team == HOME, "H", "A").astype("<U1")
    labels[dead] = "D"
    return labels


def practice_matches():
    from possession.external import sources
    return [s for s in sources() if s not in ("tactical", "broadcast")]


def _fingerprint():
    digest = hashlib.sha256()
    for name in FINGERPRINT_FILES:
        with open(os.path.join(HERE, name), "rb") as f:
            digest.update(f.read())
    return digest.hexdigest()[:12]


def match_rows(name):
    """Training rows of one practice match, from its three damaged copies; cached."""
    path = os.path.join(CACHE_DIR, "rows_{}_{}.npz".format(name, _fingerprint()))
    if os.path.isfile(path):
        with np.load(path) as stored:
            return stored["x"], stored["y"]
    from possession.damage import SCENARIOS, damage, our_profile
    from possession.external import load_source
    t = load_source(name)
    profile = our_profile()
    parts = [training_rows(damage(t, s, np.random.default_rng(TRAIN_SEED), profile), t["labels"])
             for s in SCENARIOS]
    x, y = np.concatenate([p[0] for p in parts]), np.concatenate([p[1] for p in parts])
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez(path, x=x, y=y)
    return x, y


def trained_model(leave_out=None):
    """The model trained on every practice match except `leave_out`; cached."""
    names = [m for m in practice_matches() if m != leave_out]
    path = os.path.join(CACHE_DIR, "model_{}_{}.pkl".format(leave_out or "all", _fingerprint()))
    if os.path.isfile(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    rows = [match_rows(m) for m in names]
    model = fit(np.concatenate([x for x, _ in rows]), np.concatenate([y for _, y in rows]))
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(model, f)
    return model


def predict(tracking, frames=None, switch_cost=SWITCH_COST):
    """H/A/D per frame: v4's stoppages, the learned team in live play. A practice match (its
    `name` from possession.external) gets the model that never saw it."""
    name = tracking.get("name")
    model = trained_model(name if name in practice_matches() else None)
    dead, ours, theirs, _ = both_views(tracking)
    return labels_from(decode(home_probability(model, ours, theirs), dead, switch_cost), dead)
