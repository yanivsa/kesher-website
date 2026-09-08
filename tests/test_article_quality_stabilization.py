from __future__ import annotations

import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as controller

TZ = ZoneInfo("Asia/Jerusalem")


def risky_article() -> dict:
    return {
        "id": "gifted-intensity-claim",
        "title": "כותרת מאמר",
        "date": "2026-09-08",
        "category": "הדרכת הורים",
        "excerpt": "תקציר",
        "content": (
            "<p>אחד המאפיינים הבולטים של ילדים מחוננים הוא שהם חווים "
            "את העולם בעוצמה רבה יותר.</p>"
        ),
    }


class FakeGitHub:
    def __init__(self) -> None:
        self.saved_state = None
        self.posts = [risky_article()]
        self.dispatches = []

    def load_controller_state(self):
        return copy.deepcopy(self.saved_state)

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)

    def contents_json(self, path, ref="main"):
        assert path == "src/data/posts.json"
        assert ref == "main"
        return copy.deepcopy(self.posts)

    def open_article_prs(self, target_slot=None):
        return []

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
        return 200, "<html><h1>כותרת מאמר</h1></html>"


class ArticleQualityStabilizationTests(unittest.TestCase):
    def test_risky_live_article_is_blocked_before_video_dispatch(self):
        gh = FakeGitHub()
        now = datetime(2026, 9, 8, 16, 30, tzinfo=TZ)
        state, action = controller.Controller(gh, FakeSite(), now=now).tick()

        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["last_error"]["code"], "ARTICLE_CONTENT_QUALITY_FAILED")
        self.assertEqual(state["article"]["quality_status"], "failed")
        self.assertTrue(state["article"]["quality_content_sha256"])
        self.assertEqual(gh.dispatches, [])


if __name__ == "__main__":
    unittest.main()
