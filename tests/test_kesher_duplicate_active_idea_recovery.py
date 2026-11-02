from __future__ import annotations

import copy
import unittest

from scripts.kesher_recover_duplicate_active_idea import recover_duplicate_active_idea


class DuplicateActiveIdeaRecoveryTests(unittest.TestCase):
    def state(self):
        stage = {
            "attempt_count": 0,
            "status": "pending",
            "last_error": None,
            "next_retry_at": None,
            "run_id": None,
            "processed_run_id": None,
            "provider_id": None,
            "failure_fingerprint": None,
            "same_failure_streak": 0,
            "failure_count_by_type": {},
        }
        return {
            "schema_version": 5,
            "cycle": "2026-11-02",
            "status": "blocked",
            "last_error": {
                "stage": "article",
                "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
                "message": "Article exhausted 3 fresh generation attempts",
            },
            "history": [],
            "article": {
                **copy.deepcopy(stage),
                "attempt_count": 3,
                "attempts": 3,
                "status": "running",
                "run_id": 41370641101,
                "processed_run_id": 41370641101,
                "pr_number": 1270,
                "pr_url": "https://github.com/yanivsa/kesher-website/pull/1270",
                "current_pr_head_sha": "f" * 40,
                "last_jules_session_id": "sessions/duplicate",
            },
            "image": copy.deepcopy(stage),
            "long_video": copy.deepcopy(stage),
            "short": copy.deepcopy(stage),
            "active_idea": {
                "idea_id": "gifted-asynchronous-development-1268",
                "fingerprint": "duplicate-fp",
                "topic_brief": "Issue #1268 duplicate owner request",
                "required_primary_keyword": "ילדים מחוננים התפתחות רגשית",
                "run_now": True,
                "status": "claimed",
                "publication_slot": "2026-11-02",
                "claimed_at": "2026-11-01T22:36:15Z",
            },
            "idea_queue": [
                {
                    "idea_id": "parenting-p2-stool-withholding-potty-training",
                    "fingerprint": "next-fp",
                    "topic_brief": "התאפקות קקי בגמילה",
                    "required_primary_keyword": "התאפקות קקי בגמילה",
                    "run_now": False,
                    "status": "queued",
                    "requested_at": "2026-10-19T10:22:25Z",
                }
            ],
            "idea_history": [
                {
                    "idea_id": "gifted-children-asynchronous-development",
                    "status": "complete",
                    "completed_at": "2026-11-01T20:36:19Z",
                    "outputs": {
                        "slug": "gifted-children-asynchronous-development",
                        "article_url": "https://kesher.saharoni.com/blog/gifted-children-asynchronous-development",
                        "long_url": "https://youtu.be/hZnOr_12YDU",
                        "short_url": "https://youtu.be/bmofQnopjzw",
                    },
                }
            ],
            "deliverables": {
                "article_url": None,
                "overview_youtube_url": None,
                "short_youtube_url": None,
                "overview_edit_verified": False,
                "short_portrait_verified": False,
                "short_signature_verified": False,
                "short_origin_verified": False,
            },
            "pending_dispatches": {"kesher-article-generation.yml": {"status": "dispatched"}},
        }

    def test_rejects_only_proven_duplicate_and_claims_next_idea(self):
        state = self.state()
        changed = recover_duplicate_active_idea(
            state,
            target_cycle="2026-11-02",
            target_idea_id="gifted-asynchronous-development-1268",
            completed_idea_id="gifted-children-asynchronous-development",
            now_iso="2026-11-02T04:40:00Z",
            pr_is_closed_unmerged=lambda number: number == 1270,
            article_workflow_active=lambda: False,
        )
        self.assertTrue(changed)
        self.assertEqual(state["status"], "article_needed")
        self.assertEqual(state["active_idea"]["idea_id"], "parenting-p2-stool-withholding-potty-training")
        self.assertEqual(state["active_idea"]["status"], "claimed")
        self.assertEqual(state["active_idea"]["publication_slot"], "2026-11-02")
        self.assertEqual(state["article"]["attempts"], 0)
        self.assertEqual(state["article"]["attempt_count"], 0)
        self.assertNotIn("pr_number", state["article"])
        self.assertEqual(state["pending_dispatches"], {})
        rejected = state["idea_history"][-1]
        self.assertEqual(rejected["idea_id"], "gifted-asynchronous-development-1268")
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["rejection_code"], "DUPLICATE_COMPLETED_SOURCE")
        self.assertEqual(rejected["duplicate_of_idea_id"], "gifted-children-asynchronous-development")

    def test_fails_closed_if_duplicate_pr_is_still_open_or_merged(self):
        for predicate in (lambda number: False,):
            state = self.state()
            before = copy.deepcopy(state)
            with self.assertRaisesRegex(RuntimeError, "DUPLICATE_PR_NOT_CLOSED_UNMERGED"):
                recover_duplicate_active_idea(
                    state,
                    target_cycle="2026-11-02",
                    target_idea_id="gifted-asynchronous-development-1268",
                    completed_idea_id="gifted-children-asynchronous-development",
                    now_iso="2026-11-02T04:40:00Z",
                    pr_is_closed_unmerged=predicate,
                    article_workflow_active=lambda: False,
                )
            self.assertEqual(state, before)

    def test_fails_closed_while_article_actor_is_active(self):
        state = self.state()
        before = copy.deepcopy(state)
        with self.assertRaisesRegex(RuntimeError, "ARTICLE_WORKFLOW_ACTIVE"):
            recover_duplicate_active_idea(
                state,
                target_cycle="2026-11-02",
                target_idea_id="gifted-asynchronous-development-1268",
                completed_idea_id="gifted-children-asynchronous-development",
                now_iso="2026-11-02T04:40:00Z",
                pr_is_closed_unmerged=lambda number: True,
                article_workflow_active=lambda: True,
            )
        self.assertEqual(state, before)

    def test_requires_completed_source_with_three_outputs(self):
        state = self.state()
        state["idea_history"][0]["outputs"]["short_url"] = ""
        before = copy.deepcopy(state)
        with self.assertRaisesRegex(RuntimeError, "COMPLETED_SOURCE_NOT_VERIFIED"):
            recover_duplicate_active_idea(
                state,
                target_cycle="2026-11-02",
                target_idea_id="gifted-asynchronous-development-1268",
                completed_idea_id="gifted-children-asynchronous-development",
                now_iso="2026-11-02T04:40:00Z",
                pr_is_closed_unmerged=lambda number: True,
                article_workflow_active=lambda: False,
            )
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
