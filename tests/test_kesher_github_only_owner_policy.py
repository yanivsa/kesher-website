"""Non-production policy tests; no network, no workflow dispatch."""
import unittest
from scripts.kesher_runtime.github_only_owner_policy import (
    OwnerLedgerBlocked, command_identity, plan_dispatch,
)


class GitHubOnlyOwnerPolicyTests(unittest.TestCase):
    def setUp(self):
        self.cid = command_identity(slot="2026-11-17", source_sha256="a" * 64,
                                    operation="notebooklm_long")
        self.ledger = dict(schema_version=1, epoch="owner-epoch-1",
                           owner="github-only", reviewed_main_sha="b" * 40,
                           activation="PROTECTED_VERIFIED", inventory_complete=True,
                           commands={})
        self.args = dict(ledger=self.ledger, expected_epoch="owner-epoch-1",
                         reviewed_main_sha="b" * 40, command_id=self.cid,
                         observed_provider_tasks={}, pending_github_runs=[])

    def test_stable_id(self):
        self.assertEqual(self.cid, command_identity(slot="2026-11-17",
            source_sha256="a" * 64, operation="notebooklm_long"))

    def test_claim_is_not_dispatch(self):
        self.assertEqual(plan_dispatch(**self.args), "CLAIM_REQUIRED")

    def test_duplicate_wake_is_noop(self):
        self.ledger["commands"][self.cid] = {"phase": "WAITING_PROVIDER"}
        self.assertEqual(plan_dispatch(**self.args), "NOOP")

    def test_uncertain_side_effect_is_noop(self):
        self.ledger["commands"][self.cid] = {"phase": "DISPATCH_UNKNOWN"}
        self.assertEqual(plan_dispatch(**self.args), "NOOP")

    def test_unreviewed_epoch_blocks(self):
        self.ledger["epoch"] = "another-owner"
        with self.assertRaises(OwnerLedgerBlocked):
            plan_dispatch(**self.args)

    def test_missing_protected_activation_blocks(self):
        self.ledger["activation"] = "READY_FOR_REVIEWED_MIGRATION_ONLY"
        with self.assertRaises(OwnerLedgerBlocked):
            plan_dispatch(**self.args)

    def test_parallel_wake_blocks(self):
        self.args["pending_github_runs"] = [{"run_id": 123}]
        with self.assertRaises(OwnerLedgerBlocked):
            plan_dispatch(**self.args)

    def test_provider_pending_blocks(self):
        self.args["observed_provider_tasks"] = {"old-task": "GENERATING"}
        with self.assertRaises(OwnerLedgerBlocked):
            plan_dispatch(**self.args)

    def test_unknown_inventory_blocks(self):
        self.ledger["inventory_complete"] = False
        with self.assertRaises(OwnerLedgerBlocked):
            plan_dispatch(**self.args)

    def test_changed_main_blocks(self):
        self.args["reviewed_main_sha"] = "c" * 40
        with self.assertRaises(OwnerLedgerBlocked):
            plan_dispatch(**self.args)


if __name__ == "__main__":
    unittest.main()
