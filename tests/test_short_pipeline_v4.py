from __future__ import annotations

import unittest

from scripts import kesher_short_pipeline_v4 as short


class ShortPipelineV4Tests(unittest.TestCase):
    def source(self):
        return {
            "title": "איך מדברים בלי להפוך כל שיחה לריב",
            "category": "זוגיות",
        }

    def test_prompt_requests_one_complete_short_ready_hebrew_idea(self):
        prompt = short.generation_prompt(self.source())
        self.assertIn("45 עד 55 שניות", prompt)
        self.assertIn("קול של אישה ישראלית", prompt)
        self.assertIn("הרעיון השלם", prompt)
        self.assertIn("בתחילת הווידאו", prompt)

    def test_long_source_uses_bounded_contiguous_opening_window(self):
        start, duration = short.short_window(132.0)
        self.assertEqual(start, 0.0)
        self.assertEqual(duration, 55.0)

    def test_valid_short_source_keeps_its_natural_duration(self):
        start, duration = short.short_window(44.25)
        self.assertEqual(start, 0.0)
        self.assertEqual(duration, 44.25)

    def test_too_short_source_is_rejected_instead_of_looped_or_stretched(self):
        with self.assertRaises(short.core.PipelineError):
            short.short_window(22.0)

    def test_vertical_technical_contract_accepts_exact_short(self):
        failures = short.short_technical_failures(
            {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 45.0}
        )
        self.assertEqual(failures, [])

    def test_vertical_technical_contract_rejects_horizontal_or_long_media(self):
        failures = short.short_technical_failures(
            {"codec": "h264", "audio_codec": "aac", "width": 1280, "height": 720, "duration": 90.0}
        )
        self.assertGreaterEqual(len(failures), 2)


if __name__ == "__main__":
    unittest.main()
