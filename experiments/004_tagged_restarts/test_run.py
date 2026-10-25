"""Synthetic scenarios for restart evidence and boundary handling."""

import unittest

import numpy as np

from run import apply_restart_rule, position_speeds, review_intervals


CONFIG = {
    "tag_margin_frames": 0, "minimum_quiet_frames": 3,
    "maximum_stationary_ball_speed_mps": 0.5,
    "minimum_moving_ball_speed_mps": 2.0, "minimum_moving_frames": 2,
}


class RestartTests(unittest.TestCase):
    def setUp(self):
        self.labels = np.full(20, "H")
        self.missing = np.zeros(20, dtype=bool)
        self.missing[2:9] = True
        self.speeds = np.full(20, 3.0)
        self.speeds[2:9] = np.nan
        self.speeds[9:12] = 0.0
        self.gaps = self.missing.copy()
        self.event = {"code": "SET PIECES", "start_frame": 7, "end_frame": 17}

    def apply(self, events=None, blocks=None):
        return apply_restart_rule(self.labels, self.missing, self.speeds, self.gaps,
                                  [self.event] if events is None else events,
                                  [(0, 20)] if blocks is None else blocks, CONFIG)

    def test_tag_and_motion_limit_dead_section_and_leave_restart_live(self):
        candidate, supported, counts = self.apply()
        self.assertTrue(np.all(candidate[:7] == "H"))
        self.assertTrue(np.all(candidate[7:12] == "D"))
        self.assertTrue(np.all(candidate[12:] == "H"))
        self.assertEqual(int(np.sum(supported)), 5)
        self.assertEqual(counts["distinct_restart_estimates"], 1)

    def test_no_tag_or_no_long_gap_preserves_predictions(self):
        self.assertTrue(np.array_equal(self.apply(events=[])[0], self.labels))
        self.gaps[:] = False
        self.assertTrue(np.array_equal(self.apply()[0], self.labels))

    def test_one_moving_frame_is_insufficient(self):
        self.speeds[13:] = np.nan
        self.assertTrue(np.array_equal(self.apply()[0], self.labels))

    def test_quiet_evidence_cannot_cross_half_boundary(self):
        self.event["start_frame"] = 0
        self.assertTrue(np.array_equal(self.apply(blocks=[(0, 10), (11, 20)])[0], self.labels))

    def test_review_grouping_does_not_join_halves(self):
        changed = np.zeros(20, dtype=bool)
        changed[[2, 4, 9, 10]] = True
        self.assertEqual(review_intervals(changed, [(0, 10), (10, 20)], 2),
                         [(2, 5), (9, 10), (10, 11)])

    def test_position_speed_scales_metres_without_bridging_missing_frames(self):
        positions = np.zeros((20, 2))
        positions[:, 0] = np.arange(20) / 100
        positions[7:10] = np.nan
        speeds = position_speeds(positions, (100, 60), 25, [(0, 15), (15, 20)])
        self.assertAlmostEqual(speeds[0], 25)
        self.assertAlmostEqual(speeds[10], 25)
        self.assertTrue(np.all(np.isnan(speeds[4:10])))
        self.assertTrue(np.all(np.isnan(speeds[12:15])))
        self.assertAlmostEqual(speeds[15], 25)


if __name__ == "__main__":
    unittest.main()
