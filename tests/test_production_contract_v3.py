from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.kesher_automation_policy import POLICY_PATH, load_policy


ROOT = Path(__file__).resolve().parents[1]
LEGACY_POLICY = ROOT / "config" / "kesher-automation-policy.json"
VIDEO_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
VIDEO_REVIEW_POLICY = ROOT / ".github" / "prompts" / "jules-remotion-video-upgrade.md"


class ProductionContractV3Tests(unittest.TestCase):
    def test_contract_is_the_canonical_policy_source(self) -> None:
        self.assertEqual(POLICY_PATH.name, "kesher-production-contract.json")
        contract = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(contract["contract_version"], 3)
        self.assertNotIn("review_gate", contract["video"])
        self.assertNotIn("jules_review_required", contract["video"])
        self.assertNotIn("upload_requires_approved_review", contract["video"])

    def test_scheduler_and_retry_ownership_are_locked(self) -> None:
        contract = load_policy()
        self.assertEqual(contract["scheduler"]["owner"], "kesher-content-controller")
        self.assertEqual(contract["scheduler"]["heartbeat_minutes"], 15)
        self.assertEqual(contract["scheduler"]["failure_recovery"], "heartbeat")
        self.assertTrue(contract["invariants"]["controller_owns_retries"])
        self.assertTrue(contract["invariants"]["workers_are_single_attempt"])
        self.assertTrue(contract["invariants"]["heartbeat_is_recovery_only"])

    def test_video_publication_contract_is_technical_and_advisory(self) -> None:
        contract = load_policy()
        video = contract["video"]
        self.assertEqual(video["publication_gate"], "technical")
        self.assertEqual(video["jules_review"], "advisory")
        self.assertEqual(video["queue_order"], "fifo")
        self.assertEqual(video["durable_state_artifacts_to_keep"], 3)
        self.assertEqual(video["durable_state_retention_days"], 14)

    def test_image_stage_is_best_effort_with_guaranteed_local_fallback(self) -> None:
        contract = load_policy()
        image = contract["image"]
        self.assertFalse(image["required_for_article"])
        self.assertFalse(image["publication_blocking"])
        self.assertTrue(image["no_image_publication_allowed"])
        self.assertEqual(image["failure_mode"], "best-effort-defer")
        self.assertEqual(image["worker_owner"], "github-actions")
        self.assertTrue(image["fallback_must_be_local"])

    def test_legacy_policy_is_not_the_runtime_policy(self) -> None:
        self.assertNotEqual(POLICY_PATH, LEGACY_POLICY)

    def test_video_workflow_cannot_restore_mandatory_jules_gate(self) -> None:
        workflow = VIDEO_WORKFLOW.read_text(encoding="utf-8")
        review_policy = VIDEO_REVIEW_POLICY.read_text(encoding="utf-8")
        forbidden = (
            "mandatory Jules",
            "Jules-approved MP4",
            "upload_requires_approved_review",
            'review_gate"] == "mandatory"',
            "mandatory publication gate",
        )
        for text in forbidden:
            self.assertNotIn(text.lower(), workflow.lower())
            self.assertNotIn(text.lower(), review_policy.lower())
        self.assertIn("Prepare technically verified upload", workflow)
        self.assertIn("Upload exact technically verified MP4", workflow)
        self.assertIn("Jules performs strict advisory review", workflow)

    def test_video_workflow_retention_matches_contract(self) -> None:
        workflow = VIDEO_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Keep the newest three durable state artifacts", workflow)
        self.assertIn("| .[3:] | .[].id", workflow)
        self.assertNotIn("| .[7:]", workflow)
        self.assertIn("retention-days: 14", workflow)


if __name__ == "__main__":
    unittest.main()
