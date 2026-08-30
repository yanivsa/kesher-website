from __future__ import annotations

import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_v4_structural_hold as v4

TZ = ZoneInfo("Asia/Jerusalem")


class FakeGitHub:
    def __init__(self) -> None:
        self.saved_state = None
        self.posts = []
        self.all_prs = []
        self.slot_prs = []
        self.dispatches = []

    def load_controller_state(self):
        return copy.deepcopy(self.saved_state)

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)

    def contents_json(self, path, ref="main"):
        self.assert_posts_path(path, ref)
        return copy.deepcopy(self.posts)

    @staticmethod
    def assert_posts_path(path, ref):
        assert path == "src/data/posts.json"
        assert ref == "main"

    def open_article_prs(self, target_slot=None):
        return copy.deepcopy(self.slot_prs if target_slot else self.all_prs)

    def active_workflow_run(self, workflow, *, production_only=False):
        return None

    def workflow_run_by_id(self, run_id):
        return None

    def article_result_for_run(self, run_id):
        return None

    def dispatch(self, workflow, inputs=None):
        self.dispatches.append((workflow, copy.deepcopy(inputs)))

    def newest_video_state(self):
        return {"version": 1, "items": []}


class FakeSite:
    def get(self, url):
        return 404, ""


class StructuralHoldTests(unittest.TestCase):
    def now(self):
        return datetime(2026, 8, 30, 12, 0, tzinfo=TZ)

    def make(self, gh):
        return v4.StructuralHoldController(gh, FakeSite(), now=self.now())

    def test_older_article_pr_holds_new_slot_without_dispatch(self):
        gh = FakeGitHub()
        gh.all_prs = [{"number": 579, "html_url": "https://example/pr/579"}]
        state, action = self.make(gh).tick()
        self.assertEqual(action.kind, "wait")
        self.assertEqual(state["status"], v4.STRUCTURAL_HOLD_STATUS)
        self.assertEqual(state["article"]["structural_hold_prs"], [579])
        self.assertEqual(state["article"]["attempt_count"], 0)
        self.assertEqual(gh.dispatches, [])

    def test_duplicate_worker_exhaustion_is_refunded_only_during_structural_hold(self):
        gh = FakeGitHub()
        gh.all_prs = [{"number": 579}, {"number": 582}]
        state = v4.v3.normalize_state(None, self.now().date())
        state["status"] = "blocked"
        state["article"].update({
            "attempt_count": 3,
            "attempts": 3,
            "status": "exhausted",
            "last_worker_result": {
                "outcome": v4.STRUCTURAL_DUPLICATE_OUTCOME,
                "retryable": False,
            },
        })
        state["last_error"] = {
            "stage": "article",
            "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
            "message": "article exhausted 3 total controller dispatch attempts",
        }
        gh.saved_state = state

        repaired, action = self.make(gh).tick()
        self.assertEqual(action.kind, "wait")
        self.assertEqual(repaired["article"]["attempt_count"], 0)
        self.assertEqual(repaired["article"]["attempts"], 0)
        self.assertIsNone(repaired["last_error"])
        self.assertEqual(repaired["article"]["structural_hold_prs"], [579, 582])
        self.assertEqual(gh.dispatches, [])

    def test_unrelated_real_failure_budget_is_not_refunded(self):
        gh = FakeGitHub()
        gh.all_prs = [{"number": 579}]
        state = v4.v3.normalize_state(None, self.now().date())
        state["article"].update({
            "attempt_count": 2,
            "attempts": 2,
            "last_worker_result": {"outcome": "JULES_TIMEOUT", "retryable": True},
        })
        gh.saved_state = state

        held, action = self.make(gh).tick()
        self.assertEqual(action.kind, "wait")
        self.assertEqual(held["article"]["attempt_count"], 2)
        self.assertEqual(held["article"]["attempts"], 2)
        self.assertEqual(gh.dispatches, [])

    def test_current_slot_pr_alone_is_not_mistaken_for_backlog(self):
        gh = FakeGitHub()
        current = {"number": 600, "html_url": "https://example/pr/600"}
        gh.all_prs = [current]
        gh.slot_prs = [current]
        state = v4.v3.normalize_state(None, self.now().date())
        action = self.make(gh)._structural_article_hold(state)
        self.assertIsNone(action)
        self.assertNotIn("structural_hold_prs", state["article"])


if __name__ == "__main__":
    unittest.main()
