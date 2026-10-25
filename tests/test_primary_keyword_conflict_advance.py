from __future__ import annotations

import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_keyword_recovery as recovery


TZ = ZoneInfo("Asia/Jerusalem")


class FakeGitHub:
    def __init__(self, posts):
        self.posts = copy.deepcopy(posts)
        self.saved_state = None

    def posts_on_main(self, ref="main"):
        return copy.deepcopy(self.posts)

    def active_workflow_run(self, workflow, **kwargs):
        return None

    def open_article_prs(self, slot=None):
        return []

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)


class PrimaryKeywordConflictAdvanceTests(unittest.TestCase):
    def stage(self, status="pending"):
        return {
            "attempt_count": 0,
            "status": status,
            "last_error": None,
            "next_retry_at": None,
            "run_id": None,
            "processed_run_id": None,
            "provider_id": None,
            "failure_fingerprint": None,
            "same_failure_streak": 0,
            "failure_count_by_type": {},
        }

    def blocked_state(self):
        article = self.stage(status="exhausted")
        article.update({"attempts": 3, "attempt_count": 3, "deploy_attempts": 0})
        return {
            "schema_version": 5,
            "cycle": "2026-10-25",
            "status": "blocked",
            "last_error": {
                "stage": "article",
                "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
                "message": "Article generation exhausted 3 attempts",
            },
            "history": [],
            "article": article,
            "image": self.stage(),
            "long_video": self.stage(),
            "short": self.stage(),
            "pending_dispatches": {},
            "processed_child_notifications": [],
            "idea_history": [],
            "active_idea": {
                "idea_id": "parenting-p1-daycare-adjustment",
                "fingerprint": "bad-fp",
                "topic_brief": "מאמר על הסתגלות למעון",
                "required_primary_keyword": "הסתגלות למעון",
                "run_now": False,
                "status": "claimed",
                "publication_slot": "2026-10-25",
                "claimed_at": "2026-10-25T00:01:00Z",
            },
            "idea_queue": [
                {
                    "idea_id": "parenting-p1-daycare-adjustment-difficulties",
                    "fingerprint": "good-fp",
                    "topic_brief": "מאמר ממוקד על קשיי הסתגלות למעון",
                    "required_primary_keyword": "קשיי הסתגלות למעון",
                    "run_now": False,
                    "status": "queued",
                    "requested_at": "2026-10-24T20:00:00Z",
                }
            ],
        }

    def controller(self, posts):
        ctrl = object.__new__(recovery.KeywordConflictAdvancingController)
        ctrl.github = FakeGitHub(posts)
        ctrl.now = datetime(2026, 10, 25, 6, 28, tzinfo=TZ)
        return ctrl

    def test_exact_published_keyword_collision_rejects_active_idea_and_claims_next_without_attempt_debt(self):
        posts = [{
            "id": "transition-from-caregiver-to-daycare",
            "slug": "transition-from-caregiver-to-daycare",
            "date": "2026-10-19",
            "title": "מעבר ממטפלת למעון: מה עושים עם הבכי ואיך צולחים ימי הסתגלות למעון",
            "excerpt": "הצעד של מעבר ממסגרת יחידנית למסגרת קבוצתית מביא איתו אתגרי הסתגלות.",
            "content": "<p>איך נערכים לתהליך ומקלים על ימי הסתגלות למעון.</p>",
        }]
        state = self.blocked_state()
        ctrl = self.controller(posts)

        changed = ctrl._advance_primary_keyword_conflict(state)

        self.assertTrue(changed)
        self.assertEqual(state["status"], "article_needed")
        self.assertIsNone(state["last_error"])
        self.assertEqual(state["active_idea"]["idea_id"], "parenting-p1-daycare-adjustment-difficulties")
        self.assertEqual(state["active_idea"]["publication_slot"], "2026-10-25")
        self.assertEqual(state["article"]["attempts"], 0)
        self.assertEqual(state["article"]["attempt_count"], 0)
        self.assertEqual(state["idea_history"][-1]["idea_id"], "parenting-p1-daycare-adjustment")
        self.assertEqual(state["idea_history"][-1]["status"], "rejected")
        self.assertEqual(state["idea_history"][-1]["rejection_code"], "PRIMARY_KEYWORD_CONFLICT")
        self.assertIn("transition-from-caregiver-to-daycare", state["idea_history"][-1]["conflicting_slugs"])
        self.assertEqual(state["history"][-1]["reason"], "primary_keyword_conflict_advanced")

    def test_keyword_mention_on_semantically_unrelated_slug_does_not_reject(self):
        posts = [{
            "id": "generic-parenting-roundup",
            "slug": "generic-parenting-roundup",
            "date": "2026-10-19",
            "title": "טיפים להורים: גם הסתגלות למעון מוזכרת כאן",
            "excerpt": "אוסף נושאים קצר.",
            "content": "<p>רשימת נושאים כללית.</p>",
        }]
        state = self.blocked_state()
        ctrl = self.controller(posts)

        self.assertFalse(ctrl._advance_primary_keyword_conflict(state))
        self.assertEqual(state["active_idea"]["idea_id"], "parenting-p1-daycare-adjustment")
        self.assertEqual(state["article"]["attempts"], 3)

    def test_existing_article_identity_or_worker_prevents_rejection_race(self):
        posts = [{
            "id": "transition-from-caregiver-to-daycare",
            "slug": "transition-from-caregiver-to-daycare",
            "date": "2026-10-19",
            "title": "מעבר ממטפלת למעון: ימי הסתגלות למעון",
            "excerpt": "הסתגלות למעון",
            "content": "<p>הסתגלות למעון</p>",
        }]
        state = self.blocked_state()
        state["article"]["pr_number"] = 1200
        ctrl = self.controller(posts)
        self.assertFalse(ctrl._advance_primary_keyword_conflict(state))

        state = self.blocked_state()
        ctrl = self.controller(posts)
        ctrl.github.active_workflow_run = lambda workflow, **kwargs: {"id": 999, "status": "in_progress"}
        self.assertFalse(ctrl._advance_primary_keyword_conflict(state))

    def test_production_workflow_uses_keyword_recovery_entrypoint(self):
        from pathlib import Path

        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/kesher-content-controller.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/kesher_content_controller_keyword_recovery.py --report-json", workflow)
        self.assertNotIn("scripts/kesher_content_controller_stabilized.py --report-json", workflow)


if __name__ == "__main__":
    unittest.main()
