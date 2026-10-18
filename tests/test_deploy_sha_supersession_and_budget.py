"""Regression tests for deploy SHA supersession and durable attempt budget."""
from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as controller
from scripts import kesher_content_controller_stabilized as stabilized
from scripts.kesher_content_controller_stabilized import _DuplicateDispatchSuppressed

TZ = ZoneInfo("Asia/Jerusalem")
SITE_URL = controller.SITE_URL


def make_post(slug: str = "test-post", title: str = "כותרת בדיקה", image: str = "/images/generated/blog/test-post.png") -> dict:
    return {
        "id": slug,
        "slug": slug,
        "title": title,
        "date": "2026-08-19",
        "category": "זוגיות",
        "excerpt": "תקציר בדיקה ארוך מספיק לצורך המבחן",
        "content": "<p>תוכן בדיקה מלא</p>",
        "image": image,
    }


def make_html(post: dict, content_sha: str | None = None) -> str:
    slug = post.get("slug") or post.get("id")
    canonical_url = f"{SITE_URL}/blog/{slug}"
    image = post.get("image")
    sha = content_sha or controller._post_source_sha256(post)
    return (
        f"<!doctype html><html><head><title>{post['title']}</title>"
        f"<link rel='canonical' href='{canonical_url}'>"
        f"<meta property='og:url' content='{canonical_url}'>"
        f"<meta property='og:image' content='{SITE_URL}{image}'>"
        f"<meta name='kesher:content-sha256' content='{sha}'>"
        f"</head><body><h1>{post['title']}</h1><div>{post['content']}</div></body></html>"
    )


class MockGitHub:
    def __init__(self, main_sha: str = "sha_main_a") -> None:
        self._main_sha = main_sha
        self.dispatches: list[tuple[str, dict | None]] = []
        self.runs: list[dict] = []
        self.posts: list[dict] = [make_post()]
        self.saved_state: dict = {}

    def main_sha(self) -> str:
        return self._main_sha

    def posts_on_main(self, ref: str = "main") -> list[dict]:
        return copy.deepcopy(self.posts)

    def contents_json(self, path: str, ref: str = "main") -> list[dict]:
        return copy.deepcopy(self.posts)

    def active_workflow_run(self, workflow: str, *, production_only: bool = False) -> dict | None:
        for r in self.runs:
            if r.get("workflow") == workflow and r.get("status") != "completed":
                return copy.deepcopy(r)
        return None

    def workflow_runs(self, workflow: str) -> list[dict]:
        return [copy.deepcopy(r) for r in self.runs if r.get("workflow") == workflow]

    def dispatch(self, workflow: str, inputs: dict | None = None) -> None:
        self.dispatches.append((workflow, copy.deepcopy(inputs)))

    def save_controller_state(self, state: dict) -> None:
        self.saved_state = copy.deepcopy(state)

    def open_article_prs(self, target_slot: str | None = None) -> list:
        return []


class MockSite:
    def __init__(self, responses: dict[str, tuple[int, str]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []

    def get(self, url: str) -> tuple[int, str]:
        self.calls.append(url)
        return self.responses.get(url, (404, "Not Found"))


class DeployShaSupersessionAndBudgetTests(unittest.TestCase):
    def test_completed_deploy_sha_a_superseded_by_newer_main_sha_b(self) -> None:
        gh = MockGitHub(main_sha="sha_b" * 8)
        site = MockSite()  # All 404
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            gh, site, now=datetime(2026, 8, 19, 10, 0, tzinfo=TZ)
        )
        post = make_post()
        gh.posts = [post]

        state = {
            "schema_version": 5,
            "cycle": "2026-08-19",
            "status": "article_deploying",
            "article": {
                "slug": post["slug"],
                "quality_content_sha256": "sha_content_b" * 4,
                "deploy_attempts": 1,
            },
            "pending_dispatches": {
                controller.DEPLOY_WORKFLOW: {
                    "workflow": controller.DEPLOY_WORKFLOW,
                    "cycle": "2026-08-19",
                    "inputs": {},
                    "intent_at": "2026-08-19T06:00:00+00:00",
                    "status": "completed_success",
                    "dispatch_head_sha": "sha_a" * 8,
                    "observed_active_run_id": 101,
                    "conclusion": "success",
                }
            },
            "history": [],
        }

        # Guarded dispatch must detect that main is now sha_b != sha_a, record supersession,
        # clear the completed_success intent for sha_a, and permit dispatching sha_b
        raw_dispatched = []
        def raw_dispatch(wf, inp):
            raw_dispatched.append((wf, inp))

        ctrl._guarded_dispatch(
            state, controller.DEPLOY_WORKFLOW, None, raw_dispatch
        )

        self.assertEqual(len(raw_dispatched), 1)
        self.assertEqual(raw_dispatched[0][0], controller.DEPLOY_WORKFLOW)

        # Deploy history must record the supersession
        deploy_history = state.get("deploy_history", [])
        self.assertEqual(len(deploy_history), 1)
        self.assertEqual(deploy_history[0]["superseded_sha"], "sha_a" * 8)
        self.assertEqual(deploy_history[0]["current_sha"], "sha_b" * 8)
        self.assertEqual(deploy_history[0]["superseded_status"], "completed_success")

        # New pending dispatch must be for sha_b
        pending = state["pending_dispatches"][controller.DEPLOY_WORKFLOW]
        self.assertEqual(pending["dispatch_head_sha"], "sha_b" * 8)
        self.assertEqual(pending["status"], "dispatched")

    def test_repeated_tick_suppresses_duplicate_b_dispatch(self) -> None:
        gh = MockGitHub(main_sha="sha_b" * 8)
        site = MockSite()
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            gh, site, now=datetime(2026, 8, 19, 10, 0, tzinfo=TZ)
        )
        state = {
            "schema_version": 5,
            "cycle": "2026-08-19",
            "pending_dispatches": {
                controller.DEPLOY_WORKFLOW: {
                    "workflow": controller.DEPLOY_WORKFLOW,
                    "cycle": "2026-08-19",
                    "inputs": {},
                    "intent_at": "2026-08-19T07:00:00+00:00",
                    "dispatched_at": "2026-08-19T07:00:00+00:00",
                    "status": "dispatched",
                    "dispatch_head_sha": "sha_b" * 8,
                }
            },
        }

        raw_dispatched = []
        with self.assertRaises(_DuplicateDispatchSuppressed):
            ctrl._guarded_dispatch(
                state, controller.DEPLOY_WORKFLOW, None, lambda w, i: raw_dispatched.append((w, i))
            )
        self.assertEqual(raw_dispatched, [])

    def test_late_completion_of_a_cannot_satisfy_b(self) -> None:
        gh = MockGitHub(main_sha="sha_b" * 8)
        # Old run for sha_a completes on GitHub
        gh.runs = [{
            "id": 999,
            "workflow": controller.DEPLOY_WORKFLOW,
            "event": "workflow_dispatch",
            "head_sha": "sha_a" * 8,
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
            "created_at": "2026-08-19T07:01:00+00:00",
        }]
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            gh, MockSite(), now=datetime(2026, 8, 19, 10, 0, tzinfo=TZ)
        )
        state = {
            "schema_version": 5,
            "cycle": "2026-08-19",
            "pending_dispatches": {
                controller.DEPLOY_WORKFLOW: {
                    "workflow": controller.DEPLOY_WORKFLOW,
                    "cycle": "2026-08-19",
                    "inputs": {},
                    "intent_at": "2026-08-19T07:00:00+00:00",
                    "status": "dispatched",
                    "dispatch_head_sha": "sha_b" * 8,
                }
            },
        }

        # Run 999 for sha_a must NOT match dispatch_head_sha sha_b
        with self.assertRaises(_DuplicateDispatchSuppressed):
            ctrl._guarded_dispatch(
                state, controller.DEPLOY_WORKFLOW, None, lambda w, i: None
            )
        pending = state["pending_dispatches"][controller.DEPLOY_WORKFLOW]
        # Must still be waiting for sha_b run visibility, not marked completed_success
        self.assertNotEqual(pending.get("status"), "completed_success")
        self.assertNotEqual(pending.get("observed_active_run_id"), 999)

    def test_deploy_attempt_budget_exhaustion_blocks(self) -> None:
        post = make_post()
        gh = MockGitHub(main_sha="sha_main" * 8)
        gh.posts = [post]
        site = MockSite()  # 404
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            gh, site, now=datetime(2026, 8, 19, 10, 0, tzinfo=TZ)
        )
        state = {
            "schema_version": 5,
            "cycle": "2026-08-19",
            "status": "article_deploying",
            "article": {
                "slug": post["slug"],
                "quality_content_sha256": controller._post_source_sha256(post),
                "deploy_attempts": controller.MAX_DEPLOY_ATTEMPTS,  # 5
            },
            "history": [],
        }

        is_pub, action = ctrl._ensure_article_public_and_deployed(state)
        self.assertFalse(is_pub)
        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "block")
        self.assertEqual(state.get("status"), "blocked")
        self.assertEqual(state["article"].get("deploy_status"), "exhausted")
        self.assertEqual(state.get("last_error", {}).get("code"), "DEPLOY_ATTEMPTS_EXHAUSTED")
        self.assertEqual(gh.dispatches, [])  # Zero dispatches!

        # Subsequent heartbeat emits zero dispatches and stays blocked
        is_pub2, action2 = ctrl._ensure_article_public_and_deployed(state)
        self.assertFalse(is_pub2)
        self.assertEqual(action2.kind, "block")
        self.assertEqual(gh.dispatches, [])

    def test_external_deployment_reconciliation_does_not_consume_budget(self) -> None:
        post = make_post()
        gh = MockGitHub(main_sha="sha_main" * 8)
        gh.posts = [post]
        content_sha = controller._post_source_sha256(post)
        url = f"{SITE_URL}/blog/{post['slug']}"
        site = MockSite({
            url: (200, make_html(post, content_sha)),
            f"{SITE_URL}{post['image']}": (200, "PNG_BYTES"),
        })
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            gh, site, now=datetime(2026, 8, 19, 10, 0, tzinfo=TZ)
        )
        state = {
            "schema_version": 5,
            "cycle": "2026-08-19",
            "status": "blocked",
            "article": {
                "slug": post["slug"],
                "quality_content_sha256": content_sha,
                "deploy_attempts": controller.MAX_DEPLOY_ATTEMPTS,  # 5
                "deploy_status": "exhausted",
            },
            "history": [],
        }

        is_pub, action = ctrl._ensure_article_public_and_deployed(state)
        self.assertTrue(is_pub)
        self.assertIsNone(action)
        self.assertEqual(state.get("status"), "article_live")
        self.assertTrue(state["article"].get("live"))
        self.assertEqual(state["article"].get("deploy_attempts"), 5)  # Did NOT increment!
        self.assertEqual(gh.dispatches, [])


if __name__ == "__main__":
    unittest.main()
