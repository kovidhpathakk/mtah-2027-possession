"""Do the audit and alignment scripts measure what they claim? Checked on made-up data.

Every number in docs/data.md (Data audit) comes from these functions run on the match. Nobody can
look at the match data to check them (CLAUDE.md), so each function is checked here instead on
small synthetic inputs whose right answer is known by construction: a ball moving at a known
speed, a path known to be straight, a broadcast track that is the tactical one shifted by a known
number of frames. No match data is read.

    python -m unittest discover tests
"""

import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import align_broadcast  # noqa: E402
from possession import damage as damage_kit  # noqa: E402
from possession import squads  # noqa: E402
import audit_tagging  # noqa: E402
import audit_tracking  # noqa: E402

from possession.tracking import PITCH  # noqa: E402

LENGTH, WIDTH = PITCH


class Speed(unittest.TestCase):
    def test_metres_per_axis_then_distance(self):
        # 0.002 of the pitch per frame on both axes: 0.2106 m and 0.136 m, so 0.2507 m a frame.
        frames = np.arange(50)[:, None] * np.array([0.002, 0.002])
        speed = audit_tracking.centred_speed(frames * np.array(PITCH))
        expected = np.hypot(0.002 * LENGTH, 0.002 * WIDTH) * 25
        self.assertAlmostEqual(np.nanmedian(speed), expected, places=6)
        self.assertAlmostEqual(expected, 6.267, places=3)

    def test_edges_are_unknown(self):
        speed = audit_tracking.centred_speed(np.zeros((10, 2)))
        self.assertTrue(np.isnan(speed[:2]).all() and np.isnan(speed[-2:]).all())


class Runs(unittest.TestCase):
    def test_half_open_runs(self):
        starts, stops = audit_tracking.runs(np.array([0, 1, 1, 0, 0, 1, 0, 1, 1, 1], bool))
        self.assertEqual(list(zip(starts, stops)), [(1, 3), (5, 6), (7, 10)])


class StraightPaths(unittest.TestCase):
    def test_constant_velocity_is_flagged(self):
        path = np.arange(250)[:, None] * np.array([0.1, 0.05])  # 2.8 m/s in a straight line
        share, n = audit_tracking.straight_share(path, np.ones(250, bool))
        self.assertEqual(share, 1.0)
        self.assertGreater(n, 0)

    def test_curved_path_is_not(self):
        t = np.arange(250) / 25.0
        path = np.stack([10 * np.cos(t), 10 * np.sin(t)], axis=1)  # 10 m/s on a circle
        share, _ = audit_tracking.straight_share(path, np.ones(250, bool))
        self.assertEqual(share, 0.0)


class RestartSpot(unittest.TestCase):
    def test_spots(self):
        cases = {(1.0, 1.0): "corner", (LENGTH - 2.0, WIDTH / 2): "goal area",
                 (40.0, 0.5): "touchline", (LENGTH / 2, WIDTH / 2): "centre spot",
                 (12.0, WIDTH / 2 + 15): "penalty box", (35.0, 30.0): "open field",
                 (np.nan, np.nan): "unknown"}
        for position, name in cases.items():
            self.assertEqual(audit_tagging.restart_spot(np.array(position)), name, position)


class Control(unittest.TestCase):
    def test_clean_control_and_duel(self):
        team = np.array([0, 1])
        ball = np.array([[50.0, 30.0], [50.0, 30.0], [np.nan, np.nan]])
        players = np.array([
            [[51.0, 30.0], [55.0, 30.0]],   # home 1 m away, away 5 m: home has it
            [[51.0, 30.0], [52.0, 30.0]],   # away within 3 m: a duel, nobody
            [[51.0, 30.0], [55.0, 30.0]],   # no ball: nobody
        ])
        owner = audit_tagging.controller(players, ball, team)
        self.assertEqual(list(owner), [0, -1, -1])


class Alignment(unittest.TestCase):
    """A broadcast track that IS the tactical one, shifted by a known offset, plus noise."""

    def setUp(self):
        rng = np.random.default_rng(0)
        n, self.offset = 30000, 1234
        steps = rng.normal(0, 0.3, size=(n, 2))
        ball = np.cumsum(steps, axis=0) % np.array(PITCH)        # a wandering ball
        players = (ball[:, None, :] + rng.normal(0, 8, size=(1, 10, 2))
                   + np.cumsum(rng.normal(0, 0.05, size=(n, 10, 2)), axis=0))
        self.team = np.array([0] * 5 + [1] * 5)
        self.ball_t, self.players_t = ball, players
        shift = slice(self.offset, n)
        self.ball_b = ball[shift] + rng.normal(0, 0.3, size=(n - self.offset, 2))
        self.players_b = players[shift] + rng.normal(0, 0.3, size=(n - self.offset, 10, 2))
        self.ball_b[::7] = np.nan                                # and the ball goes missing

    def test_recovers_the_offset(self):
        coarse = align_broadcast.coarse_offsets(self.ball_b, self.ball_t)
        players = (self.players_b, self.team, self.players_t, self.team)
        for w, c in enumerate(coarse):
            if c is None:
                continue
            ball_off, _, player_off, player_med = align_broadcast.refine(
                self.ball_b, self.ball_t, players, w * align_broadcast.WINDOW, c)
            self.assertEqual(ball_off, self.offset)
            self.assertEqual(player_off, self.offset)
            self.assertLess(player_med, align_broadcast.LIVE_FIT)

    def test_wrong_offset_does_not_fit(self):
        rows = np.arange(0, 20000, 50)
        players = (self.players_b, self.team, self.players_t, self.team)
        right = np.nanmedian(align_broadcast.player_fit(*players, rows, self.offset))
        wrong = np.nanmedian(align_broadcast.player_fit(*players, rows, self.offset + 250))
        self.assertLess(right, 1.0)
        self.assertGreater(wrong, 3 * right)


class Damage(unittest.TestCase):
    """The fault kit hits our match's rates and never touches the answers."""

    def setUp(self):
        rng = np.random.default_rng(1)
        n = 20000
        labels = np.array(list("HHHHHHHHAAAAAAAAADDDDDDDDDDDDDDDDDDDD") * (n // 37 + 1))[:n]
        labels[:100] = "X"
        players = rng.uniform(0.1, 0.9, size=(n, 22, 2))
        self.t = {"ball": rng.uniform(0.2, 0.8, size=(n, 2)), "players": players,
                  "speed": np.ones((n, 22), dtype=np.float32),
                  "team": np.array([0] * 11 + [1] * 11, dtype=np.int8), "labels": labels,
                  "halves": [(1, 100, n - 1)], "pitch": (105.0, 68.0)}
        self.profile = {"missing_share": 0.4, "gap_lengths": np.array([150, 300, 600]),
                        "few_players_share": 0.1, "extra_share": {0: 0.08, 1: 0.05},
                        "few_episodes_per_frame": 1 / 3000, "few_lengths": np.array([50, 500]),
                        "few_counts": np.array([4, 14, 17]), "few_in_stoppage": 0.86}

    def test_rates_and_labels(self):
        for scenario in damage_kit.SCENARIOS:
            out = damage_kit.damage(self.t, scenario, np.random.default_rng(0), self.profile)
            graded = slice(100, None)
            missing = np.isnan(out["ball"][graded, 0]).mean()
            self.assertGreaterEqual(missing, 0.4, scenario)
            self.assertLess(missing, 0.6, scenario)
            self.assertIs(out["labels"], self.t["labels"])
            self.assertEqual(out["players"].shape[1], 25 + 2 * damage_kit.SWAP_SLOTS)
            self.assertEqual(len(out["team"]), 25 + 2 * damage_kit.SWAP_SLOTS)
            self.assertTrue(np.isnan(out["speed"][:damage_kit.SPEED_LAG]).all())


class Squads(unittest.TestCase):
    """Commentary lines are matched to teams by names that belong to one side only."""

    def test_names_and_teams(self):
        cases = {"Pedri finds Lamine Yamal": (2, 0), "free kick to Athletic": (0, 1),
                 "Nico Williams goes past Koundé": (1, 1), "Iñigo with the ball": (0, 0),
                 "Barça lead through Lewandowski": (2, 0), "Unai Simón saves": (0, 1)}
        for text, (home, away) in cases.items():
            counts = squads.teams_mentioned(text)
            self.assertEqual((counts[0], counts[1]), (home, away), text)


if __name__ == '__main__':
    unittest.main()
