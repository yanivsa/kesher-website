"""Governance test: enforce mandatory production-safety coverage and request-scoped idea failures."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_idea_queue as ideas

ROOT = Path(__file__).resolve().parents[1]

MANDATORY_PRODUCTION_SAFETY_MODULES = [
    "tests.test_controller_liveness",
    "tests.test_media_external_effect_crash_consistency",
    "tests.test_daily_rollover_delivery_completeness",
    "tests.test_deploy_sha_supersession_and_budget",
    "tests.test_exact_public_article_identity",
    "tests.test_article_pr_verify_check_ordering",
    "tests.test_article_normalization_head_tracking",
    "tests.test_article_image_fallback_pool_and_cascade",
    "tests.test_controller_child_failure_recovery",
]


def _queued_idea(index: int) -> dict:
    return {
        "idea_id": f"queued-{index}",
        "fingerprint": f"fp-{index}",
        "topic_brief": f"topic {index}",
        "required_primary_keyword": f"keyword {index}",
        "run_now": False,
        "status": "queued",
        "requested_at": "2026-10-19T00:00:00Z",
    }


def _run_now_env() -> dict[str, str]:
    return {
        "KESHER_IDEA_ID": "separate-room-transition-20261019-v1",
        "KESHER_IDEA_TOPIC_BRIEF": "××ª×× ××××¨ ×¢××¨× ××§×¦××¢× ×××¢×©× ××××¨×× ×× ××©× ××¢××¨ ××××¨ × ×¤×¨×.",
        "KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD": "××¢××¨ ××××¨ × ×¤×¨×",
        "KESHER_IDEA_RUN_NOW": "true",
    }


class CiRegressionSuiteCoverageTests(unittest.TestCase):
    def test_mandatory_production_safety_suites_exist_on_disk(self) -> None:
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            rel_path = mod.replace(".", "/") + ".py"
            file_path = ROOT / rel_path
            self.assertTrue(file_path.is_file(), f"Mandatory test module missing on disk: {rel_path}")

    def test_mandatory_suites_included_in_ci_workflow(self) -> None:
        ci_path = ROOT / ".github/workflows/ci.yml"
        self.assertTrue(ci_path.is_file(), "ci.yml missing")
        content = ci_path.read_text(encoding="utf-8")
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            self.assertIn(
                mod,
                content,
                f"Mandatory production-safety test {mod} is omitted from .github/workflows/ci.yml",
            )

    def test_mandatory_suites_included_in_stability_pr_workflow(self) -> None:
        stability_path = ROOT / ".github/workflows/kesher-stability-pr.yml"
        self.assertTrue(stability_path.is_file(), "kesher-stability-pr.yml missing")
        content = stability_path.read_text(encoding="utf-8")
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            self.assertIn(
                mod,
                content,
                f"Mandatory production-safety test {mod} is omitted from .github/workflows/kesher-stability-pr.yml",
            )

    def test_mandatory_suites_included_in_package_json_test_controller(self) -> None:
        pkg_path = ROOT / "package.json"
        self.assertTrue(pkg_path.is_file(), "package.json missing")
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        test_controller_cmd = (pkg.get("scripts") or {}).get("test:controller", "")
        for mod in MANDATORY_PRODUCTION_SAFETY_MODULES:
            self.assertIn(
                mod,
                test_controller_cmd,
                f"Mandatory production-safety test {mod} is omitted from package.json 'test:controller'",
            )

    def test_retired_openclaw_contract_tests_are_not_left_behind(self) -> None:
        retired_modules = [
            "tests.test_openclaw_agent_diagnostic_contract",
            "tests.test_openclaw_clean_rebuild_contract",
            "tests.test_openclaw_cloudflare_primary",
            "tests.test_openclaw_console_diagnostic_contract",
            "tests.test_openclaw_gateway_journal_diagnostics",
            "tests.test_openclaw_oci_agent_self_heal",
            "tests.test_openclaw_offline_proof_contract",
            "tests.test_openclaw_ready_url_extraction",
        ]
        ci_content = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for mod in retired_modules:
            self.assertFalse(
                (ROOT / (mod.replace(".", "/") + ".py")).exists(),
                f"Retired OpenClaw contract test still exists: {mod}",
            )
            self.assertNotIn(mod, ci_content, f"CI still invokes retired OpenClaw test: {mod}")


class IdeaQueueRequestSafetyTests(unittest.TestCase):
    def full_state(self, *, status: str = "complete") -> dict:
        return {
            "cycle": "2026-10-19",
            "status": status,
            "last_error": None,
            "idea_queue": [_queued_idea(i) for i in range(ideas.MAX_QUEUE)],
            "idea_history": [],
            "active_idea": None,
        }

    def test_full_queue_allows_run_now_when_controller_is_idle(self) -> None:
        state = self.full_state(status="complete")
        original_ids = [row["idea_id"] for row in state["idea_queue"]]

        result = ideas.ingest_from_env(state, _run_now_env(), now_iso="2026-10-19T17:30:00Z")

        self.assertEqual(result, "run_now_queued")
        self.assertEqual(state["idea_queue"][0]["idea_id"], "separate-room-transition-20261019-v1")
        self.assertEqual([row["idea_id"] for row in state["idea_queue"][1:]], original_ids)
        self.assertEqual(len(state["idea_queue"]), ideas.MAX_QUEUE + 1)

    def test_full_queue_rejects_normal_request_without_mutating_backlog(self) -> None:
        state = self.full_state(status="complete")
        before = copy.deepcopy(state["idea_queue"])
        env = _run_now_env()
        env["KESHER_IDEA_RUN_NOW"] = "false"

        with self.assertRaisesRegex(ideas.IdeaQueueError, "IDEA_QUEUE_FULL"):
            ideas.ingest_from_env(state, env, now_iso="2026-10-19T17:30:00Z")

        self.assertEqual(state["idea_queue"], before)

    def test_full_queue_rejects_new_run_now_while_busy_without_mutating_backlog(self) -> None:
        state = self.full_state(status="article_generating")
        before = copy.deepcopy(state["idea_queue"])

        with self.assertRaisesRegex(ideas.IdeaQueueError, "IDEA_QUEUE_FULL"):
            ideas.ingest_from_env(state, _run_now_env(), now_iso="2026-10-19T17:30:00Z")

        self.assertEqual(state["idea_queue"], before)

    def test_invalid_keyword_remains_non_mutating_validation_error(self) -> None:
        state = self.full_state(status="complete")
        before = copy.deepcopy(state)
        env = _run_now_env()
        env["KESHER_IDEA_REQUIRED_PRIMARY_KEYWORD"] = ""

        with self.assertRaisesRegex(ideas.IdeaQueueError, "IDEA_PRIMARY_KEYWORD_INVALID"):
            ideas.ingest_from_env(state, env, now_iso="2026-10-19T17:30:00Z")

        self.assertEqual(state, before)

    def test_controller_rejects_request_error_without_blocking_active_cycle(self) -> None:
        state = self.full_state(status="article_generating")
        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)

        with mock.patch.object(controller, "state", return_value=state), \
             mock.patch.object(controller, "_safe_save_controller_state") as save_state, \
             mock.patch.object(ideas, "ingest_from_env", side_effect=ideas.IdeaQueueError("IDEA_QUEUE_FULL")):
            returned_state, action = controller.tick()

        self.assertIs(returned_state, state)
        self.assertEqual(action.kind, "rejected")
        self.assertEqual(state["status"], "article_generating")
        self.assertEqual((state.get("last_error") or {}).get("code"), "IDEA_QUEUE_FULL")
        save_state.assert_called_once_with(state)


if __name__ == "__main__":
    unittest.main()
