"""Fail-closed regression: no old mutator may cross an activated GH-only owner."""
from __future__ import annotations
import base64
import unittest
from pathlib import Path

from scripts.kesher_runtime.github_only_legacy_exclusion import (
    require_legacy_bridge_not_superseded,
)
from scripts.kesher_runtime.github_only_owner_store import _blob_sha
from scripts.kesher_runtime.identity import canonical_json
from scripts.kesher_runtime.state import StateInvalid

ROOT = Path(__file__).resolve().parents[1]


class FakeGitHub:
    def __init__(self, status="PREPARED_NOT_LIVE", commands=None):
        self.record = {
            "schema_version": 1,
            "owner": "github-only",
            "reviewed_main_sha": "a" * 40,
            "epoch": "kesher-ghonly-20261117-prepare1",
            "commands": {} if commands is None else commands,
            "activation": status,
            "inventory_complete": False,
        }
        self.calls = []
        self.bad_blob = False
        self.missing = False

    def request(self, method, path, body=None, **kwargs):
        self.calls.append((method, path))
        assert method == "GET", "Legacy exclusion may never mutate GitHub"
        if path == "/repos/yanivsa/kesher-website/git/ref/heads/automation-state":
            return {"object": {"sha": "b" * 40}}
        if path == "/repos/yanivsa/kesher-website/contents/.kesher-controller/github-only-owner.json?ref=" + "b" * 40:
            if self.missing:
                return None
            raw = (canonical_json(self.record) + "\n").encode("utf-8")
            return {"sha": "0" * 40 if self.bad_blob else _blob_sha(raw),
                    "encoding": "base64", "content": base64.b64encode(raw).decode("ascii")}
        raise AssertionError(path)


class GHOnlyLegacyExclusionTests(unittest.TestCase):
    def test_prepared_does_not_claim_live_exclusion(self):
        github = FakeGitHub()
        require_legacy_bridge_not_superseded(github)
        self.assertEqual(len(github.calls), 2)
        self.assertTrue(all(method == "GET" for method, _ in github.calls))

    def test_live_owner_blocks_legacy_dispatch_before_credentials(self):
        github = FakeGitHub("PROTECTED_VERIFIED")
        with self.assertRaisesRegex(StateInvalid, "EXCLUDES_LEGACY_BRIDGE"):
            require_legacy_bridge_not_superseded(github)
        self.assertEqual(len(github.calls), 2)

    def test_forged_or_ambiguous_ledger_does_not_grant_legacy_dispatch(self):
        for mode in ("unknown", "live-without-proof", "READY_FOR_REVIEWED_MIGRATION_ONLY"):
            with self.subTest(mode=mode):
                with self.assertRaises(StateInvalid):
                    require_legacy_bridge_not_superseded(FakeGitHub(mode))
        with self.assertRaisesRegex(StateInvalid, "UNRECONCILED_OWNER"):
            require_legacy_bridge_not_superseded(FakeGitHub(commands={"x": {}}))

    def test_missing_or_corrupted_ledger_is_not_silent_permission(self):
        for flag in ("missing", "bad_blob"):
            github = FakeGitHub()
            setattr(github, flag, True)
            with self.subTest(flag=flag), self.assertRaises(StateInvalid):
                require_legacy_bridge_not_superseded(github)

    def test_existing_worker_admission_calls_exclusion_first(self):
        source = (ROOT / "scripts/kesher_runtime/bridge_admission.py").read_text()
        self.assertIn("require_legacy_bridge_not_superseded(github)", source)
        self.assertLess(source.index("require_legacy_bridge_not_superseded(github)"),
                        source.index("require_bridge(GitHubHandover(github"))
        # Never repurpose PREPARED as LIVE, and no new owner controller is created.
        text = (ROOT / "scripts/kesher_runtime/github_only_legacy_exclusion.py").read_text()
        self.assertIn('data.get("activation") == "PROTECTED_VERIFIED"', text)
        self.assertIn("PREPARED_NOT_LIVE", text)
        self.assertNotIn("workflow_dispatch", text)
        self.assertNotIn("/youtube/v3/", text)


if __name__ == "__main__":
    unittest.main()
