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
REVIEWER_PATH = ROOT / "scripts" / "jules_video_reviewer_v3.py"
LEGACY_REVIEWER_PATH = ROOT / "scripts" / "jules_video_reviewer.py"
PIPELINE_PATH = ROOT / "scripts" / "kesher_daily_pipeline.py"
EVIDENCE_PATH = ROOT / "scripts" / "prepare_jules_video_evidence.py"
POLICY_PATH = ROOT / ".github" / "prompts" / "jules-remotion-video-upgrade.md"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
AUTOMATION_POLICY_PATH = ROOT / "config" / "kesher-production-contract.json"
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
                "Jules review is strict and advisory; technical verification owns publication. MUST NOT block upload.\n\n"
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

    def test_prompt_keeps_strict_but_advisory_jules_review_language(self) -> None:
        reviewer = load_reviewer()
        prompt = self.build_with_policy(reviewer, "fixture policy")
        self.assertIn("STRICT ADVISORY reviewer", prompt)
        self.assertIn("MUST NOT block upload", prompt)
        self.assertNotIn("MANDATORY publication reviewer", prompt)
        self.assertNotIn("Upload is allowed only when", prompt)
        for expected in (
            "slide/card-like", "text-heavy", "timeline or diagram",
            "repeated identical", "generic illustrative",
        ):
            self.assertIn(expected, prompt)

    def test_pipeline_is_single_source_of_truth_for_frame_count(self) -> None:
        pipeline_source = PIPELINE_PATH.read_text(encoding="utf-8")
        reviewer_source = REVIEWER_PATH.read_text(encoding="utf-8")
        legacy_source = LEGACY_REVIEWER_PATH.read_text(encoding="utf-8")
        evidence_source = EVIDENCE_PATH.read_text(encoding="utf-8")
        literal = re.compile(r"^\s*REVIEW_FRAME_COUNT\s*=\s*\d+\s*$", re.MULTILINE)
        self.assertEqual(len(literal.findall(pipeline_source)), 1)
        self.assertEqual(literal.findall(reviewer_source), [])
        self.assertEqual(literal.findall(legacy_source), [])
        self.assertEqual(literal.findall(evidence_source), [])
        self.assertIn("legacy.REVIEW_FRAME_COUNT", reviewer_source)
        self.assertIn("from kesher_daily_pipeline import REVIEW_FRAME_COUNT", legacy_source)
        self.assertIn("from kesher_daily_pipeline import REVIEW_FRAME_COUNT", evidence_source)

    def test_durable_policy_covers_review_upgrade_captions_and_daily_automation(self) -> None:
        policy = POLICY_PATH.read_text(encoding="utf-8")
        self.assertIn("Jules review is strict and advisory", policy)
        self.assertIn("MUST NOT block upload", policy)
        self.assertNotIn("mandatory publication gate", policy.lower())
        self.assertIn("`remotion-upgrade`", policy)
        self.assertIn("Never auto-upgrade", policy)
        self.assertIn("already exists inside the pixels of the NotebookLM source MP4", policy)
        self.assertIn("controller-driven daily GitHub Actions pipeline", policy)
        self.assertIn("DO NOT use `remotion-captions`", policy)

    def test_central_policy_uses_technical_gate_with_advisory_jules(self) -> None:
        policy = json.loads(AUTOMATION_POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(policy["video"]["publication_gate"], "technical")
        self.assertEqual(policy["video"]["jules_review"], "advisory")
        self.assertNotIn("review_gate", policy["video"])
        self.assertNotIn("jules_review_required", policy["video"])
        self.assertNotIn("upload_requires_approved_review", policy["video"])
        self.assertEqual(policy["article"]["worker_session_attempts"], 1)
        self.assertTrue(policy["invariants"]["controller_owns_retries"])

    def test_video_worker_is_dispatch_only_and_advisory_review_cannot_block_upload(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        trigger_block = workflow.split("permissions:", 1)[0]
        self.assertNotIn("  schedule:", trigger_block)
        self.assertIn("scripts/kesher_video_reconcile.py --prepare-generation", workflow)
        self.assertIn("scripts/kesher_video_reconcile.py --prepare-upload", workflow)
        self.assertIn("scripts/jules_video_reviewer_v3.py", workflow)
        self.assertIn("Jules performs strict advisory review", workflow)
        self.assertIn("Prepare technically verified upload", workflow)
        self.assertIn("Upload exact technically verified MP4", workflow)
        self.assertNotIn("mandatory Jules", workflow)
        self.assertNotIn("Jules-approved MP4", workflow)
        self.assertNotIn("daily_video_guard.py", workflow)

    def test_upload_guard_is_bound_to_technical_identity_not_jules_approval(self) -> None:
        guard = UPLOAD_GUARD_PATH.read_text(encoding="utf-8")
        self.assertIn('video_policy.get("publication_gate") != "technical"', guard)
        self.assertIn('video_policy.get("jules_is_advisory") is not True', guard)
        self.assertIn('item.get("technical_verified") is not True', guard)
        self.assertIn('if not final_sha:', guard)
        self.assertNotIn('approved_sha != final_sha', guard)
        self.assertNotIn('reviewer.get("type") != "jules"', guard)

    def test_video_worker_fails_closed_on_unrecoverable_state_and_keeps_three_snapshots(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("none is trustworthy; refusing a fresh state", workflow)
        self.assertIn("Keep the newest three durable state artifacts", workflow)
        self.assertIn("| .[3:] | .[].id", workflow)
        self.assertIn("retention-days: 14", workflow)

    def test_reviewer_has_one_session_attempt_so_controller_owns_retry(self) -> None:
        reviewer = load_reviewer()
        self.assertEqual(reviewer.MAX_REVIEW_SESSION_ATTEMPTS, 1)
        source = REVIEWER_PATH.read_text(encoding="utf-8")
        self.assertNotIn("handle_non_fatal_review_error", source)
        self.assertNotIn("JULES_REVIEW_SESSION_REPLACEMENT", source)


if __name__ == "__main__":
    unittest.main()
