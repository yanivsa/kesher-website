from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEWER_PATH = ROOT / "scripts" / "jules_video_reviewer.py"
PIPELINE_PATH = ROOT / "scripts" / "kesher_daily_pipeline.py"
EVIDENCE_PATH = ROOT / "scripts" / "prepare_jules_video_evidence.py"
POLICY_PATH = ROOT / ".github" / "prompts" / "jules-remotion-video-upgrade.md"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
AUTOMATION_POLICY_PATH = ROOT / "config" / "kesher-automation-policy.json"
UPLOAD_GUARD_PATH = ROOT / "scripts" / "kesher_video_upload_guard.py"


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


class VideoReviewPolicyTestCase(unittest.TestCase):
    def build_with_policy(self, reviewer, policy_text: str) -> str:
        with tempfile.TemporaryDirectory() as temporary:
            policy_path = Path(temporary) / "policy.md"
            policy_path.write_text(
                f"Policy-Version: {reviewer.REMOTION_POLICY_VERSION}\n\n"
                "Jules review is a mandatory publication gate\n\n"
                f"{policy_text}",
                encoding="utf-8",
            )
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

    def test_jules_review_itself_remains_strict(self) -> None:
        reviewer = load_reviewer()
        prompt = self.build_with_policy(reviewer, "fixture policy")
        for expected in (
            "slide/card-like", "text-heavy", "timeline or diagram",
            "repeated identical", "generic illustrative",
        ):
            self.assertIn(expected, prompt)

    def test_pipeline_is_single_source_of_truth_for_frame_count(self) -> None:
        pipeline_source = PIPELINE_PATH.read_text(encoding="utf-8")
        reviewer_source = REVIEWER_PATH.read_text(encoding="utf-8")
        evidence_source = EVIDENCE_PATH.read_text(encoding="utf-8")
        literal = re.compile(r"^\s*REVIEW_FRAME_COUNT\s*=\s*\d+\s*$", re.MULTILINE)
        self.assertEqual(len(literal.findall(pipeline_source)), 1)
        self.assertEqual(literal.findall(reviewer_source), [])
        self.assertEqual(literal.findall(evidence_source), [])

    def test_central_policy_makes_publication_technical_and_jules_advisory(self) -> None:
        policy = json.loads(AUTOMATION_POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(policy["video"]["publication_gate"], "technical")
        self.assertTrue(policy["video"]["jules_is_advisory"])
        self.assertEqual(policy["video"]["durable_state_artifacts_to_keep"], 3)
        self.assertEqual(policy["article"]["worker_session_attempts"], 1)
        self.assertTrue(policy["invariants"]["controller_owns_retries"])
        self.assertTrue(policy["invariants"]["heartbeat_is_recovery_only"])

    def test_worker_stays_controller_dispatched_and_uses_reconcile(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        trigger_block = workflow.split("permissions:", 1)[0]
        self.assertNotIn("  schedule:", trigger_block)
        self.assertIn("scripts/kesher_video_reconcile.py --prepare-generation", workflow)
        self.assertIn("scripts/kesher_video_reconcile.py --prepare-upload", workflow)

    def test_upload_guard_requires_technical_evidence_not_jules_approval(self) -> None:
        guard = UPLOAD_GUARD_PATH.read_text(encoding="utf-8")
        self.assertIn('video_policy.get("publication_gate") != "technical"', guard)
        self.assertIn('video_policy.get("jules_is_advisory") is not True', guard)
        self.assertIn('item.get("technical_verified") is not True', guard)
        self.assertNotIn('reviewer.get("type") != "jules"', guard)
        self.assertNotIn('statuses != ["approved", "approved", "approved"]', guard)

    def test_unrecoverable_state_still_fails_closed_and_artifacts_live_14_days(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("none is trustworthy; refusing a fresh state", workflow)
        self.assertIn("retention-days: 14", workflow)

    def test_reviewer_has_one_session_attempt(self) -> None:
        reviewer = load_reviewer()
        self.assertEqual(reviewer.MAX_REVIEW_SESSION_ATTEMPTS, 1)


if __name__ == "__main__":
    unittest.main()
