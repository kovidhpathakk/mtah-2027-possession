"""Remove the tracking objects the audits showed are not players, before any method looks at them.

Two faults found in our match and absent from clean data (docs/research.md section 7):

  frozen objects  an object whose position does not change AT ALL for FROZEN frames or more. Our
                  tracker reports positions to ~1 mm, and a person standing still still sways by
                  more than that, so a frozen object is a leftover track. Our match has four such
                  stretches; one is the Athletic keeper's slot stuck in front of Barca's goal for
                  ~10 minutes across half-time -- the "ghost" in Barca's box. (DFL rounds to 1 cm,
                  so its still players repeat exactly for a few seconds; FROZEN is long enough to
                  leave them alone.)
  12+ in a team   on 5-8% of frames a team has more than 11 objects. While it does, the extra
                  ones go: first an object within DUPLICATE m of a teammate (a double-count), then
                  one off the pitch or on a touchline (staff, substitutes).

    from possession.cleanup import clean
    tracking = clean(tracking)
"""

import numpy as np

# Params
FROZEN = 10 * 25          # frames
DUPLICATE = 1.5           # m
TOUCHLINE_BAND = 3.0      # m
MAX_PER_TEAM = 11
PITCH_DEFAULT = (105.3, 68.0)


def drop_frozen(players):
    """NaN every stretch of FROZEN+ frames in which an object does not move at all. In place."""
    same = np.all(players[1:] == players[:-1], axis=2) & ~np.isnan(players[1:, :, 0])
    for slot in range(players.shape[1]):
        edges = np.diff(np.concatenate(([0], same[:, slot].astype(np.int8), [0])))
        for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            if b - a >= FROZEN:
                players[a:b + 1, slot] = np.nan


def cap_team(players, team, pitch):
    """On frames where a team has more than MAX_PER_TEAM objects, drop the likeliest extras."""
    metres = np.array(pitch)
    present = ~np.isnan(players[:, :, 0])
    for code in np.unique(team):
        mine = np.flatnonzero(team == code)
        for f in np.flatnonzero(present[:, mine].sum(axis=1) > MAX_PER_TEAM):
            slots = mine[present[f, mine]]
            while len(slots) > MAX_PER_TEAM:
                xy = players[f, slots] * metres
                d = np.linalg.norm(xy[:, None] - xy[None], axis=2)
                np.fill_diagonal(d, np.inf)
                y = xy[:, 1]
                edge = (np.fmin(np.abs(y), np.abs(y - metres[1])) <= TOUCHLINE_BAND) \
                    | (xy[:, 0] < 0) | (xy[:, 0] > metres[0])
                if d.min() < DUPLICATE:
                    drop = int(np.unravel_index(np.argmin(d), d.shape)[1])
                elif edge.any():
                    drop = int(np.flatnonzero(edge)[0])
                else:
                    break
                players[f, slots[drop]] = np.nan
                slots = np.delete(slots, drop)


def clean(tracking):
    """A copy of `tracking` with frozen objects and a team's extra objects removed."""
    out = dict(tracking)
    players = tracking["players"].copy()
    drop_frozen(players)
    cap_team(players, tracking["team"], tracking.get("pitch", PITCH_DEFAULT))
    out["players"] = players
    speed = tracking["speed"].copy()
    speed[np.isnan(players[:, :, 0])] = np.nan
    out["speed"] = speed
    return out
