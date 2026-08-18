from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import types
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PATH = ROOT / "scripts" / "jules_video_reviewer.py"
PIPELINE_PATH = ROOT / "scripts" / "kesher_daily_pipeline.py"
EVIDENCE_PATH = ROOT / "scripts" / "prepare_jules_video_evidence.py"
DAILY_GUARD_PATH = ROOT / "scripts" / "daily_video_guard.py"
POLICY_PATH = ROOT / ".github" / "prompts" / "jules-remotion-video-upgrade.md"


def load_reviewer(frame_count: int = 8):
    previous = sys.modules.get("kesher_daily_pipeline")
    stub = types.ModuleType("kesher_daily_pipeline")
    stub.REVIEW_FRAME_COUNT = frame_count
    sys.modules["kesher_daily_pipeline"] = stub
    try:
        spec = importlib.util.spec_from_file_location("jules_video_reviewer_policy_test", REVIEWER_PATH)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            sys.modules.pop("kesher_daily_pipeline", None)
        else:
            sys.modules["kesher_daily_pipeline"] = previous


def load_daily_guard():
    spec = importlib.util.spec_from_file_location("daily_video_guard_policy_test", DAILY_GUARD_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VideoReviewPolicyTestCase(unittest.TestCase):
    def build_with_policy(self, reviewer, policy_text: str) -> str:
        with tempfile.TemporaryDirectory() as temporary:
            policy_path = Path(temporary) / "policy.md"
            policy_path.write_text(policy_text, encoding="utf-8")
            reviewer.REMOTION_POLICY_PATH = policy_path
            return reviewer.build_prompt(
                ".jules-video-review/fixture",
                {"id": "item-1"},
                {
                    "manifest_sha256": "a" * 64,
                    "final_sha256": "b" * 64,
                    "transcript_sha256": "c" * 64,
                    "source_file_sha256": "d" * 64,
                    "visual_review_sha256": "e" * 64,
                    "frame_sha256": {},
                },
            )

    def test_build_prompt_injects_durable_policy_content(self) -> None:
        reviewer = load_reviewer()
        marker = "POLICY_INJECTION_MARKER_404"
        prompt = self.build_with_policy(reviewer, marker)
        self.assertIn("BEGIN DURABLE REMOTION POLICY", prompt)
        self.assertIn(marker, prompt)
        self.assertIn("END DURABLE REMOTION POLICY", prompt)

    def test_prompt_shape_is_generated_from_review_frame_count(self) -> None:
        reviewer = load_reviewer(frame_count=3)
        prompt = self.build_with_policy(reviewer, "fixture policy")
        self.assertIn("EACH of its 3 `frame_paths`", prompt)
        example_text = prompt.split("Use this shape:\n", 1)[1].strip()
        example = json.loads(example_text)
        self.assertEqual(len(example["frame_sha256"]), 3)
        self.assertEqual(len(example["frame_observations"]), 3)
        self.assertIn("relative/frame-3.png", example["frame_sha256"])
        self.assertNotIn("relative/frame-4.png", example["frame_sha256"])

    def test_pipeline_is_single_source_of_truth_for_frame_count(self) -> None:
        pipeline_source = PIPELINE_PATH.read_text(encoding="utf-8")
        reviewer_source = REVIEWER_PATH.read_text(encoding="utf-8")
        evidence_source = EVIDENCE_PATH.read_text(encoding="utf-8")
        literal = re.compile(r"^\s*REVIEW_FRAME_COUNT\s*=\s*\d+\s*$", re.MULTILINE)
        self.assertEqual(len(literal.findall(pipeline_source)), 1)
        self.assertEqual(literal.findall(reviewer_source), [])
        self.assertEqual(literal.findall(evidence_source), [])
        self.assertIn("from kesher_daily_pipeline import REVIEW_FRAME_COUNT", reviewer_source)
        self.assertIn("from kesher_daily_pipeline import REVIEW_FRAME_COUNT", evidence_source)

    def test_durable_policy_covers_upgrade_captions_and_daily_automation(self) -> None:
        policy = POLICY_PATH.read_text(encoding="utf-8")
        self.assertIn("`remotion-upgrade`", policy)
        self.assertIn("Never auto-upgrade", policy)
        self.assertIn("already exists inside the pixels of the NotebookLM source MP4", policy)
        self.assertIn("scheduled daily GitHub Actions pipeline", policy)
        self.assertIn("DO NOT use `remotion-captions`", policy)

    def test_daily_guard_prevents_second_scheduled_upload_on_same_israel_date(self) -> None:
        guard = load_daily_guard()
        today = date(2026, 8, 18)
        uploaded_today = {
            "items": [
                {"israel_date": "2026-08-18", "status": "uploaded", "uploaded": True},
                {"israel_date": "2026-08-17", "status": "uploaded", "uploaded": True},
            ]
        }
        self.assertTrue(guard.already_uploaded_today(uploaded_today, today))
        self.assertFalse(
            guard.already_uploaded_today(
                {"items": [{"israel_date": "2026-08-17", "status": "uploaded", "uploaded": True}]},
                today,
            )
        )
        self.assertFalse(
            guard.already_uploaded_today(
                {"items": [{"israel_date": "2026-08-18", "status": "rejected", "uploaded": False}]},
                today,
            )
        )


if __name__ == "__main__":
    unittest.main()
