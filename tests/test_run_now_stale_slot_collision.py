from __future__ import annotations

import copy
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_stabilized as stabilized

TZ = ZoneInfo("Asia/Jerusalem")


class FakeGitHub:
    def __init__(self, state, posts):
        self.saved_state = copy.deepcopy(state)
        self.posts = copy.deepcopy(posts)
        self.recent_posts = []

    def load_controller_state(self):
        return copy.deepcopy(self.saved_state)

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)

    def contents_json(self, path, ref="main"):
        if path == "src/data/posts.json":
            return copy.deepcopy(self.posts)
        if path == "src/data/postsRecent.json":
            return copy.deepcopy(self.recent_posts)
        raise AssertionError(path)

    def posts_on_main(self, ref="main"):
        return copy.deepcopy(self.posts)

    def open_article_prs(self, target_slot=None):
        self.asserted_slot = target_slot
        return [{"number": 1156, "title": "Publish Kesher article: מעבר לחדר נפרד"}]


class FakeSite:
    def get(self, url):
        return 404, ""


class RunNowStaleSlotCollisionTests(unittest.TestCase):
    def test_past_run_now_slot_occupied_by_archived_article_is_deferred_before_stale_pr_handling(self):
        stage = {
            "attempt_count": 0,
            "status": "complete",
            "last_error": None,
            "next_retry_at": None,
            "run_id": None,
            "processed_run_id": None,
            "provider_id": None,
            "failure_fingerprint": None,
            "same_failure_streak": 0,
            "failure_count_by_type": {},
        }
        state = {
            "schema_version": 5,
            "cycle": "2026-10-19",
            "status": "blocked",
            "last_error": {"stage": "article", "code": "ARTICLE_NORMALIZATION_ERROR"},
            "history": [],
            "backlog": [],
            "article": {**stage, "attempts": 1, "status": "blocked"},
            "image": copy.deepcopy(stage),
            "long_video": copy.deepcopy(stage),
            "short": copy.deepcopy(stage),
            "idea_queue": [
                {
                    "idea_id": "parenting-p1-potty-training-age-4",
                    "fingerprint": "potty-fp",
                    "topic_brief": "גמילה בגיל 4",
                    "required_primary_keyword": "גמילה מחיתולים בגיל 4",
                    "run_now": False,
                    "status": "queued",
                }
            ],
            "idea_history": [],
            "active_idea": {
                "idea_id": "separate-room-transition-20261019-v1",
                "fingerprint": "room-fp",
                "topic_brief": "מעבר לחדר נפרד",
                "required_primary_keyword": "מעבר לחדר נפרד",
                "run_now": True,
                "status": "claimed",
                "publication_slot": "2026-10-19",
                "claimed_at": "2026-10-19T18:00:00Z",
            },
            "owner_cycle_archive": [
                {"article": {"slug": "toddler-bed-transition"}}
            ],
        }
        posts = [
            {
                "id": "toddler-bed-transition",
                "date": "2026-10-19",
                "title": "מעבר למיטת מעבר",
                "content": "<p>x</p>",
                "category": "הדרכת הורים",
                "excerpt": "x",
            }
        ]
        gh = FakeGitHub(state, posts)
        ctrl = stabilized.StabilizedRuntimeV5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 10, 20, 11, 0, tzinfo=TZ),
        )
        ctrl._active_state_ref = state

        with mock.patch.object(
            ctrl,
            "_handle_open_article_pr",
            side_effect=AssertionError("stale PR must not enter normalization/merge handling"),
        ):
            action = ctrl._run_now_article_phase(state)

        self.assertEqual(action.kind, "defer_stale_run_now")
        self.assertEqual(state["status"], "complete")
        self.assertIsNone(state["active_idea"])
        self.assertIsNone(state["last_error"])
        self.assertEqual(state["idea_queue"][0]["idea_id"], "parenting-p1-potty-training-age-4")
        self.assertEqual(state["idea_queue"][-1]["idea_id"], "separate-room-transition-20261019-v1")
        self.assertFalse(state["idea_queue"][-1]["run_now"])
        self.assertEqual(state["idea_queue"][-1]["status"], "queued")
        self.assertEqual(state["idea_queue"][-1]["deferred_reason"], "RUN_NOW_SLOT_OCCUPIED_AFTER_ROLLOVER")
        self.assertTrue(any(h.get("reason") == "run_now_slot_occupied_after_rollover" for h in state["history"]))


if __name__ == "__main__":
    unittest.main()
