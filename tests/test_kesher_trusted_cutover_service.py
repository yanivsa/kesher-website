"""Fail-closed composition tests for the administrator-owned cutover service."""
from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.kesher_runtime.production_ports import PrerequisitePort
from scripts.kesher_runtime.state import StateInvalid


class RealPort:
    def inspect(self, repo):
        raise AssertionError("not called during composition")

    def exclude(self, repo, observed_revision, policy):
        raise AssertionError("not called during composition")


class GithubBoundary(RealPort):
    pass


class FakeGithub:
    def request(self, method, path, body=None, **kwargs):
        raise AssertionError("not called during composition")


class TrustedCutoverServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.files = {
            "review": {
                "repo": "yanivsa/kesher-website",
                "main_sha": "a" * 40,
                "policy_sha256": "b" * 64,
                "code_sha256": "c" * 64,
                "closed_evidence_sha256": "d" * 64,
                "registrations_sha256": "e" * 64,
                "migration_material_sha256": "f" * 64,
            },
            "material": {"sources": [], "archives": [], "retained": []},
            "closure": {"retained_evidence": "d" * 64},
            "bindings": {
                "github": "github-repository-1239881973",
                "jules": "jules-account",
                "notebooklm": "e101e7d7-5305-45b3-a611-21a5475ceb63",
                "youtube": "UCx5fEFvdVf28HLAR2dFW64Q",
                "cloudflare": "cloudflare-pages-kesher",
                "image_provider": "image-provider-project",
            },
            "registrations": {".github/workflows/a.yml": 1},
            "key_binding": {
                "name": "NOTEBOOKLM_STATE_KEY",
                "available": True,
                "updated_at": "2026-10-10T00:00:00Z",
            },
        }
        for name, payload in self.files.items():
            (self.root / f"{name}.json").write_text(
                json.dumps(payload, sort_keys=True), encoding="utf-8"
            )
        self.journal = self.root / "invocations.sqlite"
        with sqlite3.connect(self.journal) as db:
            db.execute(
                "CREATE TABLE invocations (epoch TEXT NOT NULL, run TEXT NOT NULL, PRIMARY KEY(epoch,run))"
            )
        self.native_name = "tests._fixture_trusted_cutover_native"
        module = types.ModuleType(self.native_name)
        module.build = self.native_bundle
        sys.modules[self.native_name] = module
        self.env = {
            "KESHER_CUTOVER_REVIEW_FILE": str(self.root / "review.json"),
            "KESHER_CUTOVER_MATERIAL_FILE": str(self.root / "material.json"),
            "KESHER_CUTOVER_CLOSURE_FILE": str(self.root / "closure.json"),
            "KESHER_CUTOVER_BINDINGS_FILE": str(self.root / "bindings.json"),
            "KESHER_CUTOVER_REGISTRATIONS_FILE": str(self.root / "registrations.json"),
            "KESHER_CUTOVER_KEY_BINDING_FILE": str(self.root / "key_binding.json"),
            "KESHER_CUTOVER_NATIVE_FACTORY": self.native_name + ":build",
            "KESHER_CUTOVER_OIDC_AUDIENCE": "https://cutover.example",
            "KESHER_CUTOVER_JOURNAL": str(self.journal),
            "KESHER_CUTOVER_EPOCH": "epoch-20261010",
            "KESHER_CUTOVER_OWNER": "kesher-canonical-controller",
            "KESHER_GITHUB_REPOSITORY": "yanivsa/kesher-website",
            "KESHER_GITHUB_REPOSITORY_ID": "1239881973",
            "KESHER_CUTOVER_ROOT": str(self.root),
        }

    def tearDown(self):
        sys.modules.pop(self.native_name, None)
        self.temp.cleanup()

    def native_bundle(self):
        return {
            "github": FakeGithub(),
            "github_boundary": GithubBoundary(),
            "external_ports": {
                name: RealPort()
                for name in ("jules", "notebooklm", "youtube", "cloudflare", "image_provider")
            },
            "separation_observer": lambda: {"proofs": {}},
            "key": lambda: "fixture-key-kept-outside-repository",
        }

    def load_module(self):
        return importlib.import_module("trusted_kesher_cutover")

    def test_missing_required_configuration_refuses(self):
        module = self.load_module()
        env = dict(self.env)
        env.pop("KESHER_CUTOVER_REVIEW_FILE")
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            StateInvalid, "CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED"
        ):
            module.build()

    def test_missing_or_uninitialized_journal_refuses_without_creating_it(self):
        module = self.load_module()
        missing = self.root / "missing.sqlite"
        env = dict(self.env, KESHER_CUTOVER_JOURNAL=str(missing))
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            StateInvalid, "CUTOVER_INVOCATION_LEDGER_REQUIRED"
        ):
            module.build()
        self.assertFalse(missing.exists())

        malformed = self.root / "malformed.sqlite"
        sqlite3.connect(malformed).close()
        env["KESHER_CUTOVER_JOURNAL"] = str(malformed)
        with patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
            StateInvalid, "CUTOVER_INVOCATION_LEDGER_REQUIRED"
        ):
            module.build()

    def test_missing_or_invalid_native_factory_refuses(self):
        module = self.load_module()
        for value in ("", "not-a-factory", "missing.module:build"):
            env = dict(self.env, KESHER_CUTOVER_NATIVE_FACTORY=value)
            with self.subTest(value=value), patch.dict(os.environ, env, clear=True), self.assertRaisesRegex(
                StateInvalid, "CUTOVER_NATIVE_FACTORY_REQUIRED"
            ):
                module.build()

    def test_incomplete_native_bundle_refuses_before_runtime_construction(self):
        module = self.load_module()
        fixture = sys.modules[self.native_name]
        original = fixture.build
        try:
            fixture.build = lambda: {"github": FakeGithub()}
            with patch.dict(os.environ, self.env, clear=True), self.assertRaisesRegex(
                StateInvalid, "CUTOVER_COMPLETE_NATIVE_BUNDLE_REQUIRED"
            ):
                module.build()
        finally:
            fixture.build = original

    def test_prerequisite_port_cannot_masquerade_as_native_port(self):
        module = self.load_module()
        fixture = sys.modules[self.native_name]
        original = fixture.build

        def unavailable():
            bundle = self.native_bundle()
            bundle["external_ports"]["youtube"] = PrerequisitePort("youtube", "channel")
            return bundle

        try:
            fixture.build = unavailable
            with patch.dict(os.environ, self.env, clear=True), self.assertRaisesRegex(
                StateInvalid, "CUTOVER_REAL_NATIVE_PORT_REQUIRED"
            ):
                module.build()
        finally:
            fixture.build = original

    def test_complete_bundle_composes_existing_runtime_identity_and_application(self):
        module = self.load_module()
        runtime = object()
        identity = object()
        application = object()
        with patch.dict(os.environ, self.env, clear=True), \
             patch.object(module, "build_runtime", return_value=runtime) as runtime_builder, \
             patch.object(module, "ActionsIdentity", return_value=identity) as identity_builder, \
             patch.object(module, "CutoverApplication", return_value=application) as app_builder, \
             patch.object(module, "_verify_installed_review", return_value=None):
            result = module.build()
        self.assertIs(result, application)
        kwargs = runtime_builder.call_args.kwargs
        self.assertEqual(kwargs["repo"], "yanivsa/kesher-website")
        self.assertEqual(kwargs["epoch"], "epoch-20261010")
        self.assertEqual(kwargs["bindings"], self.files["bindings"])
        self.assertEqual(set(kwargs["external_ports"]), {"jules", "notebooklm", "youtube", "cloudflare", "image_provider"})
        identity_builder.assert_called_once()
        self.assertEqual(identity_builder.call_args.kwargs["repository_id"], "1239881973")
        self.assertEqual(identity_builder.call_args.kwargs["main_sha"], "a" * 40)
        self.assertEqual(identity_builder.call_args.kwargs["audience"], "https://cutover.example")
        app_kwargs = app_builder.call_args.kwargs
        self.assertIs(app_kwargs["runtime"], runtime)
        self.assertIs(app_kwargs["identity"], identity)
        self.assertEqual(app_kwargs["epoch"], "epoch-20261010")
        self.assertEqual(app_kwargs["reviewed_revision"], "a" * 40)
        self.assertTrue(callable(app_kwargs["review_check"]))


if __name__ == "__main__":
    unittest.main()
