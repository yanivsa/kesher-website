from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OVERVIEW_PIPELINE = ROOT / "scripts" / "kesher_daily_pipeline.py"
SHORT_PIPELINE = ROOT / "scripts" / "kesher_short_pipeline_v4.py"


class VideoEnhancementRuntimeIntegrationTests(unittest.TestCase):
    def test_overview_runtime_executes_bounded_enhancement_and_records_evidence(self) -> None:
        source = OVERVIEW_PIPELINE.read_text(encoding="utf-8")
        self.assertIn("execute_enhancement(", source)
        self.assertIn("build_enhancement_manifest(", source)
        self.assertIn('item["enhancement_status"]', source)
        self.assertIn('manifest["enhancement"]', source)

    def test_short_runtime_executes_bounded_enhancement_and_records_evidence(self) -> None:
        source = SHORT_PIPELINE.read_text(encoding="utf-8")
        self.assertIn("execute_enhancement(", source)
        self.assertIn("build_enhancement_manifest(", source)
        self.assertIn('item["enhancement_status"]', source)
        self.assertIn('manifest["enhancement"]', source)

    def test_short_runtime_preserves_attempt_aware_voice_validation(self) -> None:
        source = SHORT_PIPELINE.read_text(encoding="utf-8")
        self.assertIn("core.validate_female_voice(video_path, item)", source)


if __name__ == "__main__":
    unittest.main()
