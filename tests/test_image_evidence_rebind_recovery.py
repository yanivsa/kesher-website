from __future__ import annotations

import datetime as dt
import unittest
from unittest import mock

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v3_entry as v3
from scripts.kesher_content_controller_v3_best_effort import BestEffortController


class FakeGitHub:
    def __init__(self, *, rebind_ready: bool = True) -> None:
        self.rebind_ready = rebind_ready
        self.dispatches: list[tuple[str, dict[str, str]]] = []

    def article_pr_image_ready(self, pr):
        return False, {}

    def article_pr_image_rebindable(self, pr):
        if not self.rebind_ready:
            return False, {}
        return True, {
            "provider": "Local",
            "sha256": "b" * 64,
            "source": "local://public/images/generated/blog/existing.jpg",
            "head_sha": str((pr.get("head") or {}).get("sha") or ""),
        }

    def active_image_run(self, pr_number):
        return None

    def dispatch(self, workflow, inputs=None):
        self.dispatches.append((workflow, dict(inputs or {})))


class ImageEvidenceRebindRecoveryTests(unittest.TestCase):
    def _controller(self, github: FakeGitHub) -> BestEffortController:
        return BestEffortController(
            github,
            mock.Mock(),
            now=dt.datetime(2026, 10, 15, 9, 0, tzinfo=core.ISRAEL_TZ),
        )

    @staticmethod
    def _state() -> dict:
        return {
            "schema_version": 3,
            "cycle": "2026-10-15",
            "status": "article_image_running",
            "article": {"status": "pending"},
            "image": {
                "status": "retry_wait",
                "attempt_count": v3.MAX_STAGE_ATTEMPTS,
                "run_id": None,
                "processed_run_id": None,
                "next_retry_at": None,
                "last_error": {"code": "IMAGE_OUTPUT_MISSING", "retryable": True},
            },
            "video": {"status": "pending", "attempt_count": 0},
            "history": [],
            "last_error": {
                "stage": "image",
                "code": "IMAGE_OUTPUT_MISSING",
                "retryable": True,
            },
        }

    @staticmethod
    def _pr(head_sha: str = "a" * 40) -> dict:
        return {
            "number": 1113,
            "html_url": "https://github.com/yanivsa/kesher-website/pull/1113",
            "head": {"sha": head_sha},
            "base": {"sha": "c" * 40},
        }

    def test_head_only_staleness_rebinds_without_spending_fourth_generation_attempt(self) -> None:
        github = FakeGitHub(rebind_ready=True)
        state = self._state()

        action = self._controller(github)._handle_open_article_pr(state, self._pr())

        self.assertEqual(
            github.dispatches,
            [(v3.IMAGE_WORKFLOW, {"pr_number": "1113"})],
        )
        self.assertEqual(state["image"]["attempt_count"], v3.MAX_STAGE_ATTEMPTS)
        self.assertEqual(state["image"]["evidence_rebind_head_sha"], "a" * 40)
        self.assertEqual(state["image"]["evidence_rebind_dispatches"], 1)
        self.assertEqual(state["image"]["status"], "running")
        self.assertEqual(action.kind, "dispatch_image")

    def test_non_head_image_failure_stays_exhausted_and_never_dispatches_fourth_attempt(self) -> None:
        github = FakeGitHub(rebind_ready=False)
        state = self._state()

        action = self._controller(github)._handle_open_article_pr(state, self._pr())

        self.assertEqual(github.dispatches, [])
        self.assertEqual(state["image"]["attempt_count"], v3.MAX_STAGE_ATTEMPTS)
        self.assertEqual(state["image"]["status"], "deferred")
        self.assertEqual(action.kind, "wait")


if __name__ == "__main__":
    unittest.main()
