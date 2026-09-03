from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import kesher_short_motion_plan as motion


class MotionPlanTest(unittest.TestCase):
    def test_salient_focus_tracks_high_contrast_region(self) -> None:
        width, height = 9, 9
        frame = bytearray(width * height)
        for y in range(2, 7):
            for x in range(5, 8):
                frame[y * width + x] = 255
        focus_x, focus_y, energy = motion.salient_focus_from_gray(bytes(frame), width, height)
        self.assertGreater(focus_x, 0.55)
        self.assertGreater(energy, 0)
        self.assertGreaterEqual(focus_y, 0.35)
        self.assertLessEqual(focus_y, 0.65)

    def test_motion_plan_is_timestamped_normalized_and_deterministic(self) -> None:
        samples = [
            (0.20, 0.30, 90.0),
            (0.75, 0.25, 120.0),
            (0.55, 0.70, 60.0),
            (0.35, 0.60, 150.0),
            (0.65, 0.45, 110.0),
            (0.45, 0.35, 80.0),
            (0.70, 0.65, 100.0),
            (0.30, 0.50, 130.0),
        ]
        with patch.object(motion, "sample_focus", side_effect=samples) as mocked:
            plan = motion.build_motion_plan(Path("source.mp4"), 48.0, 30)
        self.assertEqual(plan["planner"], "pixel-gradient-centroid-v1")
        self.assertEqual(plan["sampleCount"], 8)
        self.assertEqual(mocked.call_count, 8)
        self.assertEqual(plan["targets"][0]["startFrame"], 0)
        self.assertEqual(plan["targets"][-1]["endFrame"], 1439)
        for target in plan["targets"]:
            self.assertGreaterEqual(target["focusX"], 0)
            self.assertLessEqual(target["focusX"], 1)
            self.assertGreaterEqual(target["focusY"], 0)
            self.assertLessEqual(target["focusY"], 1)
            self.assertGreaterEqual(target["zoom"], 1.12)
            self.assertLessEqual(target["zoom"], 1.22)
            self.assertIn("timestampSeconds", target)


if __name__ == "__main__":
    unittest.main()
