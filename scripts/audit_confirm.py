"""Confirm (or reject) the audit's weaker findings, using the broadcast tracker as a second witness.

audit_tracking.py found patterns whose CAUSE it could only guess. Now that the broadcast tracking
is aligned to tactical (align_broadcast.py), most guesses can be tested against an independent
tracker that watched the same moments from another camera. No video, no labels.

Checks:
  1 filling     Does the tactical tracker invent ball positions in short occlusions? Where the
                broadcast tracker loses the ball for 1-5 s in live play, does tactical still have
                one, and is its path suspiciously smooth (a fitted curve, not a real ball)?
  2 keeper      What is the Athletic-labelled object in Barca's box: Barca's keeper? A keeper
                moves little, and a mislabel shows up as a Barca object turning into an Athletic
                one on the spot; the broadcast tracker gives its own team label.
  3 touchline   What are the long touchline tracks: assistant referees (moving with play) or
                substitutes and staff (standing)? And how often do they end up nearest the ball,
                which is the damage they would do?
  4 extra       On frames where a team has 12+ objects, what is the extra one: a duplicate of a
                teammate, someone on the touchline, or unexplained (the referee?)
  5 labels      Do the two trackers give the same person the same team?
  6 yardstick   Do they agree on which team clearly controls the ball? (The yardstick used to
                score Smart Tagging in audit_tagging.py.)
  7 ball        Do they agree on where the ball is?

    python scripts/audit_confirm.py            # needs align_broadcast.py run first

Prints aggregates only.
"""

import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from audit_tagging import controller  # noqa: E402
from audit_tracking import centred_speed, frame_mask, runs  # noqa: E402
from games import GAME, GAMES, half_video_blocks  # noqa: E402

from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
LENGTH, WIDTH = PITCH
HOME, AWAY, NOBODY = 0, 1, -1
OFFSETS = os.path.join(ROOT, "data", "derived", "broadcast_offsets.npz")
SHORT_GAP = (1 * FPS, 5 * FPS)   # broadcast blackouts to test for tactical filling
SMOOTH = 0.02                    # m: a 1 s ball path within this of a parabola is a fitted curve
BOX_DEPTH, BOX_HALF_WIDTH = 16.5, 20.16
FAR_BALL = 40.0
HANDOVER = 3.0                   # m: a home object this close just before = the same person
TOUCHLINE_BAND = 3.0
LONG_TRACK = 10 * FPS
SAME_PERSON = 1.0                # m between the two trackers' objects
DUPLICATE = 1.5
SAMPLE = 5                       # every 5th frame is plenty for shares


def pct(x):
    return "{:.1%}".format(x) if np.isfinite(x) else "n/a"


def parabola_residual(xy, centres):
    """Max distance (m) of the 1 s path around each centre from its best-fit parabola."""
    k = np.arange(-(FPS // 2), FPS // 2 + 1)
    design = np.stack([np.ones_like(k), k, k ** 2], axis=1).astype(float)
    hat = design @ np.linalg.pinv(design)
    window = xy[centres[:, None] + k[None, :]]                     # (n, 25, 2)
    resid = window - np.einsum("ij,njd->nid", hat, window)
    return np.nanmax(np.linalg.norm(resid, axis=2), axis=1)


def filling(ball_t, ball_b, b_to_t, graded):
    print("\n1 DOES THE TACTICAL TRACKER FILL IN THE BALL?")
    seen_b = ~np.isnan(ball_b[:, 0])
    live = b_to_t >= 0
    inside = []
    for a, z in zip(*runs(~seen_b)):
        if SHORT_GAP[0] <= z - a <= SHORT_GAP[1] and a > 0 and z < len(live) \
                and live[a - 1:z + 1].all():
            inside.extend(range(a, z))
    inside = np.array(inside, dtype=int)
    tac = b_to_t[inside]
    tac = tac[graded[tac]]
    has = ~np.isnan(ball_t[tac, 0])
    print("  broadcast loses the ball for 1-5 s in live play: {:,} frames; tactical has a ball"
          " on {}".format(len(tac), pct(has.mean())))
    edge = FPS // 2 + 1
    centres_in = tac[has & (tac > edge) & (tac < len(ball_t) - edge)][::SAMPLE]
    both = np.flatnonzero(live & seen_b)
    both_t = b_to_t[both]
    keep = graded[both_t] & ~np.isnan(ball_t[both_t, 0])
    rng = np.random.default_rng(0)
    pick = rng.choice(np.flatnonzero(keep), size=min(len(centres_in) * 4, keep.sum()),
                      replace=False)
    centres_out_t, centres_out_b = both_t[pick], both[pick]
    ok_b = (centres_out_b > edge) & (centres_out_b < len(ball_b) - edge)
    rows = [("tactical, where broadcast lost it", parabola_residual(ball_t, centres_in)),
            ("tactical, where both see it", parabola_residual(ball_t, centres_out_t)),
            ("broadcast, where both see it", parabola_residual(ball_b, centres_out_b[ok_b]))]
    for name, r in rows:
        r = r[np.isfinite(r)]
        print("  {:<36} path off a parabola: median {:.1f} cm; smoother than {:.0f} cm: {}"
              .format(name, 100 * np.median(r), 100 * SMOOTH, pct((r < SMOOTH).mean())))


def keeper(players, team, ball, t_to_b, players_b, team_b):
    print("\n2 WHAT IS THE ATHLETIC OBJECT IN BARCA'S BOX?")
    speed = centred_speed(players)
    n_runs = handovers = was_there = 0
    frames, impostor_speed, no_home_back, broadcast_says = 0, [], 0, {HOME: 0, AWAY: 0, NOBODY: 0}
    for half, first, last in half_video_blocks(GAME):
        rows = np.arange(first, last + 1)
        p, b = players[rows], ball[rows]
        present = ~np.isnan(p[:, :, 0])
        goal_x = 0.0 if np.nanmean(p[:, team == HOME, 0]) < np.nanmean(p[:, team == AWAY, 0]) \
            else LENGTH
        depth = np.abs(p[:, :, 0] - goal_x)
        in_box = (depth <= BOX_DEPTH) & (np.abs(p[:, :, 1] - WIDTH / 2) <= BOX_HALF_WIDTH) \
            & present
        judged = (np.abs(b[:, 0] - goal_x) > FAR_BALL) & in_box.any(axis=1)
        deepest = np.argmin(np.where(in_box, depth, np.inf), axis=1)
        wrong = judged & (team[deepest] != HOME)
        frames += int(wrong.sum())
        home_back = (present & (depth < 25.0) & (team == HOME)[None, :]).any(axis=1)
        no_home_back += int((wrong & ~home_back).sum())
        for i in np.flatnonzero(wrong):
            impostor_speed.append(speed[rows[i], deepest[i]])
        # Runs of consecutive mislabelled frames with the same object: how did each one start?
        for a, z in zip(*runs(wrong)):
            n_runs += 1
            slot, f = deepest[a], rows[a]
            spot = players[f, slot]
            before = players[max(0, f - FPS):f]
            near_home = np.linalg.norm(before[:, team == HOME] - spot, axis=2) < HANDOVER
            handovers += bool(near_home.any())
            was_there += bool(not np.isnan(players[f - 1, slot, 0]))
        for i in np.flatnonzero(wrong)[::SAMPLE]:
            fb = t_to_b[rows[i]]
            if fb < 0:
                continue
            d = np.linalg.norm(players_b[fb] - p[i, deepest[i]], axis=1)
            j = np.nanargmin(np.where(np.isnan(d), np.inf, d)) if np.isfinite(np.nanmin(d)) \
                else None
            broadcast_says[team_b[j] if j is not None and d[j] < 2.0 else NOBODY] += 1
    s = np.array(impostor_speed)
    print("  mislabelled frames: {:,}; no Barca-labelled object within 25 m of Barca's goal on"
          " {}".format(frames, pct(no_home_back / max(frames, 1))))
    print("  its speed: median {:.2f} m/s, p90 {:.2f} (a keeper with play far away barely"
          " moves)".format(np.nanmedian(s), np.nanpercentile(s, 90)))
    print("  {} separate stretches; a Barca object stood on that spot in the second before: {};"
          " the object already existed as Athletic: {}".format(n_runs, handovers, was_there))
    print("  where the broadcast also shows it (every {}th frame): broadcast labels it Barca {},"
          " Athletic {}, no object within 2 m {}".format(SAMPLE, broadcast_says[HOME],
                                                         broadcast_says[AWAY],
                                                         broadcast_says[NOBODY]))
    # The keepers are the only people on the pitch for the whole match, so they are the slots
    # present longest. Where does each one spend each half?
    present = ~np.isnan(players[:, :, 0])
    longest = np.argsort(present.sum(axis=0))[::-1][:2]
    for half, first, last in half_video_blocks(GAME):
        rows = np.arange(first, last + 1)
        goal = {HOME: 0.0 if np.nanmean(players[rows][:, team == HOME, 0])
                < np.nanmean(players[rows][:, team == AWAY, 0]) else LENGTH}
        goal[AWAY] = LENGTH - goal[HOME]
        for slot in longest:
            here = present[rows, slot]
            x = players[rows, slot, 0][here]
            print("  half {}, slot present longest, labelled {:<4}: {} of the half; in Barca's"
                  " box {}, in Athletic's box {}; median speed {:.2f} m/s".format(
                      half, "home" if team[slot] == HOME else "away", pct(here.mean()),
                      pct((np.abs(x - goal[HOME]) <= BOX_DEPTH).mean()),
                      pct((np.abs(x - goal[AWAY]) <= BOX_DEPTH).mean()),
                      np.nanmedian(speed[rows, slot][here])))


def touchline(players, team, ball, graded):
    print("\n3 LONG TOUCHLINE TRACKS: WHO ARE THEY, AND DO THEY GET NEAREST THE BALL?")
    x, y = players[:, :, 0], players[:, :, 1]
    beyond = np.fmax(np.fmax(-x, x - LENGTH), np.fmax(-y, y - WIDTH))
    near_line = np.fmin(np.abs(y), np.abs(y - WIDTH)) <= TOUCHLINE_BAND
    present = ~np.isnan(x)
    speed = centred_speed(players)
    member = np.zeros(players.shape[:2], dtype=bool)
    kinds = {"moves with play (assistant referee?)": [0, 0.0],
             "stands still (substitute, staff?)": [0, 0.0], "other": [0, 0.0]}
    for slot in range(players.shape[1]):
        for a, z in zip(*runs(present[:, slot] & graded)):
            if z - a < LONG_TRACK or not near_line[a:z, slot].mean() >= 0.8:
                continue
            member[a:z, slot] = True
            seconds = (z - a) / FPS
            moving = np.nanmedian(speed[a:z, slot])
            bx = ball[a:z, 0]
            ok = ~np.isnan(bx)
            follows = np.corrcoef(x[a:z, slot][ok], bx[ok])[0, 1] if ok.sum() > FPS else np.nan
            if moving > 0.5 and follows > 0.5:
                kind = "moves with play (assistant referee?)"
            elif moving < 0.3:
                kind = "stands still (substitute, staff?)"
            else:
                kind = "other"
            kinds[kind][0] += 1
            kinds[kind][1] += seconds
    for kind, (n, seconds) in kinds.items():
        print("  {:<38} {:>3} tracks, {:.1f} min".format(kind, n, seconds / 60))
    seen = np.flatnonzero(graded & ~np.isnan(ball[:, 0]))
    d = np.linalg.norm(players[seen] - ball[seen][:, None], axis=2)
    d = np.where(np.isnan(d), np.inf, d)
    nearest = np.argmin(d, axis=1)
    hit = member[seen, nearest]
    close = hit & (d[np.arange(len(seen)), nearest] < 1.5)
    print("  ball-visible graded frames where one of them is nearest the ball: {:,} ({});"
          " and within 1.5 m of it: {:,}".format(int(hit.sum()), pct(hit.mean()),
                                                  int(close.sum())))
    print("  off the pitch by > 0.5 m while in such a track: {}".format(
        pct((beyond[member] > 0.5).mean())))


def extra(players, team, graded):
    print("\n4 FRAMES WITH 12+ OBJECTS IN ONE TEAM: WHAT IS THE EXTRA ONE?")
    rows = np.flatnonzero(graded)[::SAMPLE]
    for code in (HOME, AWAY):
        p = players[rows][:, team == code]
        count = (~np.isnan(p[:, :, 0])).sum(axis=1)
        over = count > 11
        p = p[over]
        d = np.linalg.norm(p[:, :, None] - p[:, None, :], axis=3)
        idx = np.arange(d.shape[1])
        d[:, idx, idx] = np.inf
        dup = (np.where(np.isnan(d), np.inf, d) < DUPLICATE).any(axis=(1, 2))
        y = p[:, :, 1]
        line = (np.fmin(np.abs(y), np.abs(y - WIDTH)) <= TOUCHLINE_BAND).any(axis=1) \
            | (y < 0).any(axis=1) | (y > WIDTH).any(axis=1)
        print("  {:<8} {} of frames; of those: a near-duplicate pair {}, else someone on a"
              " touchline {}, else unexplained {}".format(
                  "home" if code == HOME else "away", pct(over.mean()), pct(dup.mean()),
                  pct((~dup & line).mean()), pct((~dup & ~line).mean())))


def cross(players, team, ball, players_b, team_b, ball_b, b_to_t, graded):
    pairs_b = np.flatnonzero(b_to_t >= 0)
    pairs_t = b_to_t[pairs_b]
    keep = graded[pairs_t]
    pairs_b, pairs_t = pairs_b[keep][::SAMPLE], pairs_t[keep][::SAMPLE]

    print("\n5 DO THE TWO TRACKERS GIVE THE SAME PERSON THE SAME TEAM?")
    pb, pt = players_b[pairs_b], players[pairs_t]
    d = np.linalg.norm(pb[:, :, None] - pt[:, None], axis=3)
    d = np.where(np.isnan(d), np.inf, d)
    j = np.argmin(d, axis=2)
    matched = np.take_along_axis(d, j[:, :, None], axis=2)[:, :, 0] < SAME_PERSON
    tb = np.broadcast_to(team_b[None, :], matched.shape)[matched]
    tt = team[j][matched]
    where = pb[matched]
    in_box = (np.fmin(where[:, 0], LENGTH - where[:, 0]) <= BOX_DEPTH) & \
        (np.abs(where[:, 1] - WIDTH / 2) <= BOX_HALF_WIDTH)
    print("  matched object pairs: {:,}; team labels differ: {} (in a penalty box {}, elsewhere"
          " {})".format(len(tb), pct((tb != tt).mean()), pct((tb != tt)[in_box].mean()),
                        pct((tb != tt)[~in_box].mean())))
    for code in (HOME, AWAY):
        print("  tactical says {:<8}: broadcast disagrees on {}".format(
            "home" if code == HOME else "away", pct((tb[tt == code] != code).mean())))

    print("\n6 DO THEY AGREE ON WHICH TEAM CLEARLY CONTROLS THE BALL?")
    own_t = controller(players[pairs_t], ball[pairs_t], team)
    own_b = controller(players_b[pairs_b], ball_b[pairs_b], team_b)
    both = (own_t != NOBODY) & (own_b != NOBODY)
    either = (own_t != NOBODY) | (own_b != NOBODY)
    print("  both see clear control: {} of compared frames; same team on {}".format(
        pct(both.mean()), pct((own_t[both] == own_b[both]).mean())))
    print("  only one of them sees clear control: {} of frames where either does".format(
        pct((either & ~both).sum() / max(either.sum(), 1))))

    print("\n7 DO THEY AGREE ON WHERE THE BALL IS?")
    bt, bb = ball[pairs_t], ball_b[pairs_b]
    has_t, has_b = ~np.isnan(bt[:, 0]), ~np.isnan(bb[:, 0])
    dist = np.linalg.norm(bt - bb, axis=1)[has_t & has_b]
    print("  both have a ball: {}; tactical only: {}; broadcast only: {}; neither: {}".format(
        pct((has_t & has_b).mean()), pct((has_t & ~has_b).mean()),
        pct((~has_t & has_b).mean()), pct((~has_t & ~has_b).mean())))
    print("  distance between them p50 {:.2f} m, p90 {:.2f} m; > 5 m on {}, > 15 m on {}".format(
        np.median(dist), np.percentile(dist, 90), pct((dist > 5).mean()),
        pct((dist > 15).mean())))


if __name__ == '__main__':
    import warnings
    warnings.simplefilter("ignore", RuntimeWarning)
    if not os.path.isfile(OFFSETS):
        sys.exit("run scripts/align_broadcast.py first")
    scale = np.array(PITCH)
    tac, bro = load_tracking("tactical"), load_tracking("broadcast")
    players, ball, team = tac["players"] * scale, tac["ball"] * scale, tac["team"]
    players_b, ball_b, team_b = bro["players"] * scale, bro["ball"] * scale, bro["team"]
    graded = frame_mask(list(half_video_blocks(GAME)), players)

    offset = np.load(OFFSETS)["offset"]
    b_to_t = np.where(offset >= 0, np.arange(len(offset)) + offset, -1)
    b_to_t[b_to_t >= len(ball)] = -1
    t_to_b = np.full(len(ball), -1, dtype=np.int64)
    t_to_b[b_to_t[b_to_t >= 0]] = np.flatnonzero(b_to_t >= 0)
    print("tactical graded frames also seen live by the broadcast: {}".format(
        pct((t_to_b[graded] >= 0).mean())))

    filling(ball, ball_b, b_to_t, graded)
    keeper(players, team, ball, t_to_b, players_b, team_b)
    touchline(players, team, ball, graded)
    extra(players, team, graded)
    cross(players, team, ball, players_b, team_b, ball_b, b_to_t, graded)
