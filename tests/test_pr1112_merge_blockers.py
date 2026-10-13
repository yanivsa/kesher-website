from __future__ import annotations

import copy
import datetime as dt
import importlib.util
from pathlib import Path
import unittest
from unittest import mock

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_stabilized as stabilized


ROOT = Path(__file__).resolve().parents[1]


class PR1112MergeBlockerTests(unittest.TestCase):
    def test_article_public_verification_rejects_title_only_without_expected_sha_marker(self) -> None:
        title = "Expected article title"
        html = f"<html><head><title>{title}</title></head><body><h1>{title}</h1></body></html>"
        self.assertFalse(
            core.article_is_public(
                html,
                title,
                expected_slug="expected-article",
                expected_content_sha256="a" * 64,
            )
        )

    def test_deploy_dispatched_intent_never_blind_reposts_after_visibility_lag(self) -> None:
        class FakeGitHub:
            def __init__(self) -> None:
                self.saved: list[dict] = []

            def save_controller_state(self, state: dict) -> None:
                self.saved.append(copy.deepcopy(state))

            def active_workflow_run(self, workflow: str, production_only: bool = True):
                return None

        gh = FakeGitHub()
        site = mock.Mock()
        now = dt.datetime(2026, 10, 13, 10, 6, tzinfo=core.ISRAEL_TZ)
        ctrl = stabilized.StabilizedRuntimeV5Controller(gh, site, now=now)
        dispatched: list[tuple[str, dict]] = []
        state = {
            "schema_version": 5,
            "cycle": "2026-10-13",
            "article": {},
            "pending_dispatches": {
                core.DEPLOY_WORKFLOW: {
                    "workflow": core.DEPLOY_WORKFLOW,
                    "cycle": "2026-10-13",
                    "inputs": {},
                    "intent_at": "2026-10-13T07:00:00+00:00",
                    "dispatched_at": "2026-10-13T07:00:00+00:00",
                    "status": "dispatched",
                    "previous_run_id": None,
                    "observed_active_run_id": None,
                }
            },
        }

        with self.assertRaises(stabilized._DuplicateDispatchSuppressed):
            ctrl._guarded_dispatch(
                state,
                core.DEPLOY_WORKFLOW,
                {},
                lambda workflow, inputs: dispatched.append((workflow, copy.deepcopy(inputs or {}))),
            )
        self.assertEqual(dispatched, [])

    def test_auto_merge_bridge_is_merge_only_and_never_dispatches_deploy(self) -> None:
        path = ROOT / ".github" / "scripts" / "article-pr-controller-v3.py"
        spec = importlib.util.spec_from_file_location("pr1112_article_controller_v3", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        calls: list[tuple[str, str, dict | None]] = []

        def fake_request(method: str, url: str, token: str, body: dict | None = None):
            calls.append((method, url, copy.deepcopy(body)))
            if method == "PUT" and url.endswith("/merge"):
                return {"merged": True, "sha": "b" * 40}
            return {}

        pr = {"number": 1111, "head": {"sha": "a" * 40}}
        with mock.patch.object(module, "controller_image_stage_terminal", return_value=True), \
             mock.patch.object(module.core, "request_json", side_effect=fake_request):
            module.merge_and_deploy_after_image_stage("yanivsa/kesher-website", pr, "token")

        self.assertEqual([method for method, _, _ in calls], ["PUT"])
        self.assertTrue(calls[0][1].endswith("/pulls/1111/merge"))
        self.assertFalse(any("/actions/workflows/deploy.yml/dispatches" in url for _, url, _ in calls))

    def test_unrelated_same_day_editorial_article_is_not_adopted_from_weak_signals(self) -> None:
        class FakeGitHub:
            pass

        editorial = {
            "id": "manual-editorial-article",
            "slug": "manual-editorial-article",
            "title": "Manual editorial article",
            "excerpt": "An editorial article that is not owned by the daily controller.",
            "content": "<p>This is unrelated editorial content.</p>",
            "date": "2026-10-13",
            "controllerManaged": False,
        }
        state = {
            "schema_version": 5,
            "cycle": "2026-10-13",
            "status": "blocked",
            "article": {
                "pr_number": 9999,
                "attempts": 3,
                "attempt_count": 3,
                "last_error": "ARTICLE_ATTEMPTS_EXHAUSTED",
            },
            "last_error": {
                "stage": "article",
                "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
            },
        }
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            FakeGitHub(),
            mock.Mock(),
            now=dt.datetime(2026, 10, 13, 12, 0, tzinfo=core.ISRAEL_TZ),
        )

        adopted = ctrl._reconcile_existing_current_day_article(state, [editorial])
        self.assertEqual(adopted, [])
        self.assertNotIn("slug", state["article"])


if __name__ == "__main__":
    unittest.main()
