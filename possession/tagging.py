"""Smart Tagging as a team clue: the real tags for our match, imitation tags for the practice matches.

Deep dive 1 found v4 gets less reliable the longer it goes without seeing a player gain control
(wrong 9% within 1 s of a control event, 26% after 4-8 s, ~40% after 15 s). About a third of its
team errors sit in those stale stretches, where it only repeats its last call. Smart Tagging's
attacking-phase tags name the team in possession over 12-30 s phases and cover 81% of our live
play, so they may know better there.

Real tags (`real_tags`): every attacking phase with a team, and every defending phase turned
round (the other team has the ball), from data/tactical/*_smart_tagging.xml. Each gets a kind:
  open    build up, progression, defending in middle third   (v4 agrees 83-87%)
  final   ball in final third, long ball, players in the box, creating chances, defending in
          defensive / attacking third                          (v4 agrees 66-71%)
  box     ball in the box                                     (v4 agrees 64%)
  transition  attacking / defensive transition                (v4 agrees 62%)

Imitation tags (`imitation_tags`) give the practice matches tags with the real ones' measured
shape, so whether tags help can be tested where answers exist: phases of 12-30 s laid end to end
over live play until ~81% of it is covered; each phase takes the team that holds the ball for most
of it in the answers, then is flipped with probability 1 - ACCURACY[kind], the kind set by where
the ball mostly is (middle third → open, final third → final, penalty box → box). The accuracies
estimate the real tags' accuracy from v4's agreement with them, allowing for v4's own ~13% error
(agreement a = p·0.87 + (1 − p)·0.13): open ~0.93, final ~0.77, box ~0.66. They are estimates.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "starter"))

# Params
FPS = 25
HOME, AWAY, NOBODY = 0, 1, -1
TEAM_NAMES = {"barcelona": HOME, "atletic club": AWAY}
KIND = {"build up": "open", "progression": "open", "defending in middle third": "open",
        "ball in final third": "final", "long ball": "final", "players in the box": "final",
        "creating chances": "final", "defending in defensive third": "final",
        "defending in attacking third": "final", "ball in the box": "box",
        "attacking transition": "transition", "defensive transition": "transition"}
DEFENDING = {"defending in middle third", "defending in defensive third",
             "defending in attacking third", "defensive transition"}
ACCURACY = {"open": 0.93, "final": 0.77, "box": 0.66, "transition": 0.66}
COVERAGE = 0.81
PHASE_LENGTH = (12, 30)       # s
OUR_FRAMES = 199319


def real_tags():
    """[(start, stop, team, kind)] for our match, from Smart Tagging."""
    import load_smart_tagging
    out = []
    for event in load_smart_tagging.load():
        code = (event["code"] or "").strip().lower()
        team = TEAM_NAMES.get((event["tags"].get("Team") or "").strip().lower())
        if code not in KIND or team is None:
            continue
        holder = (1 - team) if code in DEFENDING else team
        out.append((event["start_frame"], event["end_frame"], holder, KIND[code]))
    return out


def imitation_tags(labels, ball, pitch, rng):
    """Tags shaped like the real ones, for a practice match with answers `labels`."""
    n = len(labels)
    live = np.isin(labels, ["H", "A"])
    length = pitch[0]
    x = ball[:, 0] * length
    depth = np.fmin(x, length - x)
    out, covered = [], np.zeros(n, dtype=bool)
    candidates = np.flatnonzero(live)
    tries = 0
    while covered[live].mean() < COVERAGE and tries < 20000:
        tries += 1
        a = int(rng.choice(candidates))
        if covered[a]:
            continue
        b = min(n, a + int(rng.uniform(*PHASE_LENGTH) * FPS))
        span = labels[a:b]
        home, away = (span == "H").sum(), (span == "A").sum()
        if home + away == 0:
            continue
        team = HOME if home >= away else AWAY
        d = np.nanmedian(depth[a:b])
        kind = "box" if d < 16.5 else "final" if d < length / 3 else "open"
        if rng.random() > ACCURACY[kind]:
            team = 1 - team
        out.append((a, b, team, kind))
        covered[a:b] = True
    return out


def tag_team(n, tags, kinds):
    """Per frame: the team the tags of the given kinds name (NOBODY if none). Where tags overlap,
    the more trusted kind wins (open > final > transition > box)."""
    order = {"open": 3, "final": 2, "transition": 1, "box": 0}
    team = np.full(n, NOBODY, dtype=np.int8)
    rank = np.full(n, -1)
    for a, b, t, kind in tags:
        if kind not in kinds:
            continue
        a, b = max(0, a), min(n, b)
        better = rank[a:b] < order[kind]
        team[a:b][better] = t
        rank[a:b][better] = order[kind]
    return team
