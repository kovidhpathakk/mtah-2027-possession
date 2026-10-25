"""Synthetic checks for the shared, local-only clip reviewer."""

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import clip_reviewer as reviewer


class ClipReviewerTests(unittest.TestCase):
    def test_seconds_csv_builds_bounded_windows_and_safe_html(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "video.mp4"
            video.write_bytes(b"synthetic placeholder")
            clips = root / "clips.csv"
            with clips.open("w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(("start_seconds", "end_seconds", "name", "detail"))
                writer.writerow((0, 2, "First", "</script><script>alert(1)</script>"))
                writer.writerow((8, 10, "Last", "Synthetic note"))
            with patch.object(reviewer, "OUTPUT_ROOT", root / "derived"):
                output, count = reviewer.create_review(
                    video, clips, "test_review", context_seconds=5,
                    expected_duration_seconds=10,
                )
            html = (output / "review.html").read_text()
            timestamps = (output / "timestamps.md").read_text()
            payload = json.loads(html.split("const data = ", 1)[1].split(";\n", 1)[0])
            self.assertEqual(count, 2)
            self.assertEqual(payload["clips"][0]["review_start_seconds"], 0)
            self.assertEqual(payload["clips"][1]["review_end_seconds"], 10)
            self.assertNotIn("</script><script>", html)
            self.assertIn("\\u003c/script\\u003e", html)
            self.assertIn("00:00:00.000", timestamps)
            self.assertIn("00:00:10.000", timestamps)

    def test_frame_csv_uses_supplied_frame_rate_and_rejects_bad_ranges(self):
        with tempfile.TemporaryDirectory() as temporary:
            clips = Path(temporary) / "clips.csv"
            clips.write_text("start_frame,end_frame\n25,50\n")
            self.assertEqual(reviewer.read_clips(clips, fps=25)[0]["start_seconds"], 1)
            self.assertEqual(reviewer.read_clips(clips, fps=25)[0]["end_seconds"], 2)
            with self.assertRaisesRegex(ValueError, "require --fps"):
                reviewer.read_clips(clips)
            clips.write_text("start_frame,end_frame\n50,25\n")
            with self.assertRaisesRegex(ValueError, "start < end"):
                reviewer.read_clips(clips, fps=25)

    def test_timestamp_and_name_validation(self):
        self.assertEqual(reviewer.format_timestamp(3600), "01:00:00.000")
        with self.assertRaisesRegex(ValueError, "Timestamp"):
            reviewer.format_timestamp(float("nan"))
        with self.assertRaisesRegex(ValueError, "Review name"):
            reviewer.create_review("missing.mp4", "missing.csv", "../escape")


if __name__ == "__main__":
    unittest.main()
