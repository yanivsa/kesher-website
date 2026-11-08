"""Fail-closed regression tests for emergency owner run-now handoff.

An exhausted prior Short must never be marked published to make a newer idea
run. Old articles, media evidence and claimed topic survive in durable history.
"""
from __future__ import annotations

import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_content_controller_v5 as v5


SHA = "e" * 64


class FakeGitHub:
    def __init__(self):
        self.active = {}

    def active_workflow_run(self, workflow, *, production_only=False):
        return self.active.get(workflow)


class OwnerTerminalShortHandoffTests(unittest.TestCase):
    def controller(self):
        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = FakeGitHub()
        controller.now = datetime(2026, 11, 8, 20, 30, tzinfo=ZoneInfo("Asia/Jerusalem"))
        controller.posts_on_main = lambda ref: []
        return controller

    def blocked_state(self):
        return {
            "cycle": "2026-11-06",
            "status": "blocked",
            "last_error": {
                "stage": "controller", "code": "SHORT_ATTEMPTS_EXHAUSTED",
                "message": "Short exhausted original attempts",
            },
            "article": {
                "slug": "relationship-memory-reconstruction",
                "live": True, "quality_status": "passed",
                "quality_content_sha256": SHA,
                "url": "https://kesher.saharoni.com/blog/relationship-memory-reconstruction",
            },
            "long_video": {
                "source_slug": "relationship-memory-reconstruction",
                "source_content_sha256": SHA, "verified": True,
                "youtube_url": "https://youtu.be/VPUSEiBk2es",
            },
            "short": {"attempt_count": 3, "status": "running", "verified": False},
            "image": {"status": "complete"},
            "history": [],
            "idea_history": [],
            "owner_cycle_archive": [],
            "idea_queue": [{
                "idea_id": "couples-after-work-stress-crossover",
                "fingerprint": "new-fingerprint",
                "topic_brief": "סטרס מהעבודה בזוגיות",
                "required_primary_keyword": "סטרס מהעבודה בזוגיות",
                "run_now": True, "status": "queued",
            }],
            "active_idea": {
                "idea_id": "parenting-p2-child-not-playing-kindergarten",
                "fingerprint": "old-fingerprint",
                "topic_brief": "ילד לא משחק בגן",
                "required_primary_keyword": "ילד לא משחק בגן",
                "run_now": False, "status": "claimed",
                "publication_slot": "2026-11-06",
            },
        }

    def test_terminal_short_is_archived_incomplete_before_claiming_today(self):
        ctrl = self.controller()
        state = self.blocked_state()
        self.assertTrue(ctrl._begin_run_now_cycle(state))
        self.assertEqual(state["cycle"], "2026-11-08")
        self.assertEqual(state["status"], "article_needed")
        self.assertEqual(state["active_idea"]["idea_id"], "couples-after-work-stress-crossover")
        archive = state["owner_cycle_archive"][-1]
        self.assertEqual(archive["cycle"], "2026-11-06")
        self.assertEqual(archive["status"], "blocked")
        self.assertEqual(archive["last_error"]["code"], "SHORT_ATTEMPTS_EXHAUSTED")
        self.assertFalse(archive["short"]["verified"])
        queued = [x for x in state["idea_queue"] if x["idea_id"] == "parenting-p2-child-not-playing-kindergarten"]
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["status"], "queued")
        self.assertFalse(queued[0]["run_now"])
        self.assertNotIn("publication_slot", queued[0])
        self.assertEqual(state["short"]["status"], "pending")
        archived_count = len(state["owner_cycle_archive"])
        self.assertTrue(ctrl._begin_run_now_cycle(state))
        self.assertEqual(len(state["owner_cycle_archive"]), archived_count)

    def test_live_short_actor_blocks_handoff(self):
        ctrl = self.controller()
        ctrl.github.active[v5.SHORT_WORKFLOW] = {"id": 123, "status": "in_progress"}
        state = self.blocked_state()
        self.assertFalse(ctrl._begin_run_now_cycle(state))
        self.assertEqual(state["cycle"], "2026-11-06")
        self.assertEqual(len(state["owner_cycle_archive"]), 0)

    def test_unproven_overview_or_article_blocks_handoff(self):
        ctrl = self.controller()
        for field, val in (("verified", False), ("source_content_sha256", "f" * 64)):
            state = self.blocked_state()
            state["long_video"][field] = val
            self.assertFalse(ctrl._begin_run_now_cycle(state))
        state = self.blocked_state()
        state["article"]["quality_status"] = "pending"
        self.assertFalse(ctrl._begin_run_now_cycle(state))

    def test_nonterminal_error_does_not_preempt(self):
        ctrl = self.controller()
        state = self.blocked_state()
        state["last_error"]["code"] = "SHORT_RETRY_WAIT"
        self.assertFalse(ctrl._begin_run_now_cycle(state))
        self.assertEqual(state["active_idea"]["status"], "claimed")

    def test_other_active_owner_request_not_preempted(self):
        ctrl = self.controller()
        state = self.blocked_state()
        state["active_idea"]["run_now"] = True
        self.assertFalse(ctrl._begin_run_now_cycle(state))
        self.assertEqual(state["idea_queue"][0]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
