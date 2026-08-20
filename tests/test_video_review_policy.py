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
        self.assertIn("relative/frame-3.png", example["frame_sha256"])
        self.assertNotIn("relative/frame-4.png", example["frame_sha256"])

    def test_prompt_makes_jules_a_mandatory_publication_gate(self) -> None:
        reviewer = load_reviewer()
        prompt = self.build_with_policy(reviewer, "fixture policy")
        self.assertIn("MANDATORY publication reviewer", prompt)
        self.assertIn("Upload is allowed only when", prompt)
        self.assertNotIn("ADVISORY reviewer", prompt)
        self.assertNotIn("MUST NOT block upload", prompt)
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
        self.assertIn("from kesher_daily_pipeline import REVIEW_FRAME_COUNT", reviewer_source)
        self.assertIn("from kesher_daily_pipeline import REVIEW_FRAME_COUNT", evidence_source)

    def test_durable_policy_covers_mandatory_review_upgrade_captions_and_daily_automation(self) -> None:
        policy = POLICY_PATH.read_text(encoding="utf-8")
        self.assertIn("Jules review is a mandatory publication gate", policy)
        self.assertIn("MUST NOT be uploaded to YouTube until Jules", policy)
        self.assertIn("Never bypass Jules", policy)
        self.assertIn("`remotion-upgrade`", policy)
        self.assertIn("Never auto-upgrade", policy)
        self.assertIn("already exists inside the pixels of the NotebookLM source MP4", policy)
        self.assertIn("controller-driven daily GitHub Actions pipeline", policy)
        self.assertIn("DO NOT use `remotion-captions`", policy)

    def test_central_policy_requires_mandatory_jules_gate(self) -> None:
        policy = json.loads(AUTOMATION_POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(policy["video"]["review_gate"], "mandatory")
        self.assertTrue(policy["video"]["jules_review_required"])
        self.assertTrue(policy["video"]["upload_requires_approved_review"])
        self.assertEqual(policy["article"]["worker_session_attempts"], 1)
        self.assertTrue(policy["invariants"]["controller_owns_retries"])

    def test_video_worker_is_dispatch_only_and_fails_closed_before_upload(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        trigger_block = workflow.split("permissions:", 1)[0]
        self.assertNotIn("  schedule:", trigger_block)
        self.assertIn("scripts/kesher_video_reconcile.py --prepare-generation", workflow)
        self.assertIn("scripts/kesher_video_reconcile.py --prepare-upload", workflow)
        self.assertIn("Jules performs mandatory publication review", workflow)
        self.assertIn("Upload only the exact Jules-approved MP4", workflow)
        self.assertNotIn("Jules is advisory only", workflow)
        self.assertNotIn("regardless of Jules", workflow)
        self.assertNotIn("daily_video_guard.py", workflow)

    def test_upload_guard_binds_approval_to_exact_final_sha(self) -> None:
        guard = UPLOAD_GUARD_PATH.read_text(encoding="utf-8")
        self.assertIn('approved_sha != final_sha', guard)
        self.assertIn('reviewer.get("type") != "jules"', guard)
        self.assertIn('statuses != ["approved", "approved", "approved"]', guard)

    def test_video_worker_fails_closed_on_unrecoverable_state_and_keeps_seven_snapshots(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("none is trustworthy; refusing a fresh state", workflow)
        self.assertIn("Keep the newest seven durable state artifacts", workflow)
        self.assertIn("| .[7:] | .[].id", workflow)
        self.assertIn("retention-days: 14", workflow)

    def test_reviewer_has_one_session_attempt_so_controller_owns_retry(self) -> None:
        reviewer = load_reviewer()
        self.assertEqual(reviewer.MAX_REVIEW_SESSION_ATTEMPTS, 1)
        source = REVIEWER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("handle_non_fatal_review_error", source)
        self.assertNotIn("JULES_REVIEW_SESSION_REPLACEMENT", source)


if __name__ == "__main__":
    unittest.main()
