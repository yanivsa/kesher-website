"""Regression tests for the non-authorizing GitHub-only LIVE diagnostic."""
from __future__ import annotations

import base64
import json
import unittest
from unittest.mock import patch

from scripts.kesher_runtime.github_only_live_readiness import (
    WORKFLOW_REF, _ledger, diagnose,
)
from scripts.kesher_runtime.github_only_owner_store import _blob_sha
from scripts.kesher_runtime.identity import canonical_json
from scripts.kesher_runtime.state import StateInvalid


class FakeGithub:
    def __init__(self):
        self.main = "a" * 40
        self.ref = "b" * 40
        self.tree = "c" * 40
        self.data = {
            "schema_version": 1,
            "owner": "github-only",
            "epoch": "owner-reviewed-prepare-1",
            "reviewed_main_sha": self.main,
            "activation": "PREPARED_NOT_LIVE",
            "inventory_complete": False,
            "commands": {},
            "migration_basis": {
                "legacy_blob_sha": "d" * 40,
                "legacy_cycle": "2026-11-08",
            },
        }
        self.calls = []
        self.set_document(self.data)

    def set_document(self, document):
        self.raw = (canonical_json(document) + "\n").encode()
        self.sha = _blob_sha(self.raw)

    def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path))
        if method != "GET":
            raise AssertionError("Non-read request in LIVE diagnostic")
        if path.endswith("/git/ref/heads/automation-state"):
            return {"object": {"sha": self.ref}}
        if path.endswith("/git/commits/" + self.ref):
            return {"sha": self.ref, "tree": {"sha": self.tree}}
        if "/contents/.kesher-controller/github-only-owner.json?ref=" in path:
            return {
                "encoding": "base64",
                "content": base64.b64encode(self.raw).decode(),
                "sha": self.sha,
            }
        raise AssertionError(path)


class LiveReadinessTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGithub()
        self.audit = {
            "status": "READY_FOR_REVIEWED_MIGRATION_ONLY",
            "legacy_blob_sha": "d" * 40,
            "legacy_cycle": "2026-11-08",
            "pending": [],
            "production_activated": False,
            "provider_dispatch": False,
        }

    def diagnose(self):
        with patch(
            "scripts.kesher_runtime.github_only_live_readiness.inventory",
            return_value=self.audit,
        ):
            return diagnose(
                self.gh, expected_main=self.gh.main,
                workflow_ref=WORKFLOW_REF,
                event_name="workflow_dispatch",
                repo="yanivsa/kesher-website",
            )

    def test_existing_prepare_is_still_not_live_and_never_dispatches(self):
        report = self.diagnose()
        self.assertEqual(report["status"], "BLOCKED_PRODUCTION_LIVE")
        self.assertTrue(report["read_only"])
        self.assertFalse(report["production_activated"])
        self.assertFalse(report["provider_dispatch"])
        self.assertTrue(report["reviewed_main_matches"])
        self.assertTrue(report["legacy_state_matches"])
        self.assertIn("PROTECTED_LIVE_TRANSITION_NOT_IMPLEMENTED", report["blockers"])
        self.assertIn("SINGLE_WRITER_MEDIA_WORKER_NOT_ATTESTED", report["blockers"])
        self.assertFalse(any(method != "GET" for method, _ in self.gh.calls))

    def test_stale_main_and_changed_legacy_state_report_blockers(self):
        self.gh.data["reviewed_main_sha"] = "f" * 40
        self.gh.set_document(self.gh.data)
        self.audit["legacy_blob_sha"] = "0" * 40
        report = self.diagnose()
        self.assertIn("PREPARE_MAIN_REVISION_STALE", report["blockers"])
        self.assertIn("LEGACY_STATE_CHANGED_SINCE_PREPARE", report["blockers"])

    def test_pending_controller_and_unreconciled_commands_block(self):
        self.audit["status"] = "BLOCKED_EXISTING_OWNER_OR_TASK"
        self.gh.data["commands"]["already-created"] = {"phase": "WAITING_PROVIDER"}
        self.gh.set_document(self.gh.data)
        report = self.diagnose()
        self.assertIn("EXISTING_GITHUB_OWNER_OR_RUN_NOT_DRAINED", report["blockers"])
        self.assertIn("EXISTING_COMMAND_JOURNAL_REQUIRES_RECONCILIATION",
                      report["blockers"])

    def test_fake_live_marker_is_not_positive_authority(self):
        self.gh.data["activation"] = "PROTECTED_VERIFIED"
        self.gh.data["inventory_complete"] = True
        self.gh.set_document(self.gh.data)
        report = self.diagnose()
        self.assertEqual(report["status"], "BLOCKED_PRODUCTION_LIVE")
        self.assertIn("EXISTING_LIVE_CLAIM_REQUIRES_INDEPENDENT_VERIFICATION",
                      report["blockers"])
        self.assertIn("PREPARE_INVENTORY_FLAG_UNEXPECTED", report["blockers"])

    def test_bad_blob_or_duplicate_keys_fail_closed(self):
        self.gh.sha = "f" * 40
        with self.assertRaisesRegex(StateInvalid, "BLOB_INTEGRITY"):
            _ledger(self.gh)
        raw = (b'{"schema_version":1,"schema_version":1,"owner":"github-only"}')
        self.gh.raw = raw
        self.gh.sha = _blob_sha(raw)
        with self.assertRaises(ValueError):
            _ledger(self.gh)

    def test_untrusted_workflow_or_revision_fails_before_api_call(self):
        for kwargs in (
            {"workflow_ref": "forged@main"},
            {"event_name": "push"},
            {"repo": "other/repo"},
            {"expected_main": "injected"},
        ):
            data = dict(
                expected_main=self.gh.main, workflow_ref=WORKFLOW_REF,
                event_name="workflow_dispatch", repo="yanivsa/kesher-website",
            )
            data.update(kwargs)
            with self.assertRaises(StateInvalid):
                diagnose(self.gh, **data)
        self.assertEqual(self.gh.calls, [])


if __name__ == "__main__":
    unittest.main()
