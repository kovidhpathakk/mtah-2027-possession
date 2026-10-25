"""Synthetic football scenarios; no match data is read by these tests."""

import unittest

import numpy as np

from run import apply_gap_rules


class MotionGateTests(unittest.TestCase):
    def apply(self, labels, missing, slow, blocks=None, minimum=10):
        labels = np.array(list(labels))
        return apply_gap_rules(labels, np.array(missing, dtype=bool),
                               np.array(slow, dtype=bool), blocks or [(0, len(labels))],
                               minimum, 0.8)

    def test_sustained_slow_gap_and_exact_duration_threshold(self):
        _, candidate, _, accepted, counts = self.apply(
            "H" * 10, [True] * 10, [True] * 8 + [False] * 2)
        self.assertTrue(np.all(candidate == "D"))
        self.assertEqual(int(np.sum(accepted)), 10)
        self.assertEqual(counts["accepted_gaps"], 1)

    def test_movement_or_insufficient_tracking_preserves_reference(self):
        for slow in ([False] * 10, [True] * 7 + [False] * 3):
            ungated, candidate, _, _, counts = self.apply("H" * 10, [True] * 10, slow)
            self.assertTrue(np.all(ungated == "D"))
            self.assertTrue(np.all(candidate == "H"))
            self.assertEqual(counts["accepted_gaps"], 0)

    def test_gap_never_joins_across_halftime(self):
        _, candidate, _, _, counts = self.apply(
            "H" * 6 + "XX" + "A" * 6, [True] * 14, [True] * 14,
            blocks=[(0, 6), (8, 14)])
        self.assertEqual("".join(candidate), "H" * 6 + "XX" + "A" * 6)
        self.assertEqual(counts["long_gaps"], 0)

    def test_only_qualifying_gap_changes(self):
        _, candidate, _, _, _ = self.apply(
            "HA" + "H" * 10 + "DA", [False] * 2 + [True] * 10 + [False] * 2,
            [True] * 14)
        self.assertEqual("".join(candidate), "HA" + "D" * 10 + "DA")


if __name__ == "__main__":
    unittest.main()
