from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.kesher_automation_policy import POLICY_PATH, load_policy


ROOT = Path(__file__).resolve().parents[1]
LEGACY_POLICY = ROOT / "config" / "kesher-automation-policy.json"


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

    def test_image_stage_is_required_and_has_guaranteed_local_fallback(self) -> None:
        contract = load_policy()
        image = contract["image"]
        self.assertTrue(image["required_for_article"])
        self.assertEqual(image["worker_owner"], "github-actions")
        self.assertTrue(image["fallback_must_be_local"])

    def test_legacy_policy_is_not_the_runtime_policy(self) -> None:
        self.assertNotEqual(POLICY_PATH, LEGACY_POLICY)


if __name__ == "__main__":
    unittest.main()
