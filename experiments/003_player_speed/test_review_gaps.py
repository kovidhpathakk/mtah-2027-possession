"""Rejected-gap export checks using synthetic masks only."""

import unittest

import numpy as np

from review_gaps import build_entries


class ReviewGapTests(unittest.TestCase):
    def test_intervals_stay_within_each_half_and_have_elapsed_seconds(self):
        rejected = np.ones(100, dtype=bool)
        entries = build_entries(rejected, rejected, np.zeros(100, dtype=bool),
                                [(1, 0, 19), (2, 80, 99)], 25)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["start_seconds"], 0)
        self.assertEqual(entries[0]["end_seconds"], 0.8)
        self.assertEqual(entries[1]["start_seconds"], 3.2)
        self.assertEqual(entries[1]["end_seconds"], 4)
        self.assertEqual(entries[1]["name"], "Gap 02")
        self.assertIn("Half 2", entries[1]["detail"])
        self.assertIn("100.0%", entries[1]["detail"])


if __name__ == "__main__":
    unittest.main()
