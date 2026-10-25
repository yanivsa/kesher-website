#!/usr/bin/env python3
"""Regressions for P1: DAILY_ROLLOVER_DELIVERY_COMPLETENESS.

Verifies that prior cycles are omitted from backlog only when the complete delivery
contract is proven: Article public exact identity AND Long public exact identity
AND Short public exact identity. Also covers owner-idea recovery when a required
Primary Keyword is already owned by a published article.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from scripts.kesher_content_controller import new_cycle_state
from scripts import kesher_idea_queue as idea_queue


class DailyRolloverDeliveryCompletenessTests(unittest.TestCase):
    def test_article_live_and_long_pending_rolls_into_backlog(self):
        old_cycle = {
            "cycle": "2026-10-13",
            "status": "article_live",
            "article": {
                "slug": "meltdown-slug",
                "content_sha256": "sha-art-1",
                "public": True,
                "status": "verified",
                "attempts": 1,
            },
            "long_video": {
                "status": "pending",
                "attempts": 0,
            },
            "short": {
                "status": "pending",
                "attempts": 0,
            },
        }
        new_state = new_cycle_state(date(2026, 10, 14), old_cycle)
        self.assertEqual(len(new_state["backlog"]), 1)
        entry = new_state["backlog"][0]
        self.assertEqual(entry["cycle"], "2026-10-13")
        self.assertEqual(entry["status"], "article_live")
        self.assertEqual(entry["exact_slug"], "meltdown-slug")
        self.assertEqual(entry["content_sha256"], "sha-art-1")
        self.assertEqual(entry["article"]["slug"], "meltdown-slug")
        self.assertEqual(entry["long_video"]["status"], "pending")

    def test_long_complete_and_short_pending_rolls_into_backlog(self):
        old_cycle = {
            "cycle": "2026-10-13",
            "status": "short_needed",
            "article": {
                "slug": "meltdown-slug",
                "content_sha256": "sha-art-1",
                "public": True,
                "status": "verified",
            },
            "long_video": {
                "status": "completed",
                "youtube_id": "yt-long-1",
                "public": True,
            },
            "short": {
                "status": "pending",
                "attempts": 1,
            },
        }
        new_state = new_cycle_state(date(2026, 10, 14), old_cycle)
        self.assertEqual(len(new_state["backlog"]), 1)
        entry = new_state["backlog"][0]
        self.assertEqual(entry["cycle"], "2026-10-13")
        self.assertEqual(entry["exact_slug"], "meltdown-slug")
        self.assertEqual(entry["media_identities"]["long_video_id"], "yt-long-1")
        self.assertIsNone(entry["media_identities"]["short_video_id"])

    def test_full_complete_does_not_create_unnecessary_backlog(self):
        old_cycle = {
            "cycle": "2026-10-13",
            "status": "complete",
            "article": {
                "slug": "meltdown-slug",
                "content_sha256": "sha-art-1",
                "public": True,
                "status": "verified",
            },
            "long_video": {
                "status": "completed",
                "youtube_id": "yt-long-1",
                "public": True,
            },
            "short": {
                "status": "completed",
                "youtube_id": "yt-short-1",
                "public": True,
            },
        }
        new_state = new_cycle_state(date(2026, 10, 14), old_cycle)
        self.assertEqual(len(new_state["backlog"]), 0)

    def test_blocked_exhausted_prior_cycle_preserved_without_starving_current_day(self):
        old_cycle = {
            "cycle": "2026-10-13",
            "status": "blocked",
            "article": {
                "slug": "meltdown-slug",
                "content_sha256": "sha-art-1",
                "status": "exhausted",
                "attempts": 3,
                "generation_attempts": 3,
            },
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
        }
        new_state = new_cycle_state(date(2026, 10, 14), old_cycle)
        self.assertEqual(len(new_state["backlog"]), 1)
        entry = new_state["backlog"][0]
        self.assertEqual(entry["terminal_state"]["blocked"], True)
        self.assertEqual(entry["terminal_state"]["article_exhausted"], True)
        self.assertEqual(entry["counters"]["article_generation_attempts"], 3)

        # Current-day authority starts fresh and unblocked
        self.assertEqual(new_state["cycle"], "2026-10-14")
        self.assertEqual(new_state["status"], "article_needed")
        self.assertEqual(new_state["article"]["attempts"], 0)


class PrimaryKeywordConflictAdvanceTests(unittest.TestCase):
    @staticmethod
    def _blocked_state(attempts: int = 3):
        return {
            "schema_version": 5,
            "cycle": "2026-10-25",
            "status": "blocked" if attempts >= 3 else "article_needed",
            "last_error": (
                {
                    "stage": "article",
                    "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
                    "message": "Article generation exhausted 3 attempts",
                }
                if attempts >= 3
                else None
            ),
            "history": [],
            "article": {
                "attempt_count": attempts,
                "attempts": attempts,
                "status": "exhausted" if attempts >= 3 else "pending",
                "last_error": None,
                "next_retry_at": None,
                "run_id": None,
                "processed_run_id": None,
                "provider_id": None,
                "failure_fingerprint": None,
                "same_failure_streak": 0,
                "failure_count_by_type": {},
                "deploy_attempts": 0,
            },
            "image": {"status": "pending"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "pending_dispatches": {},
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

    def test_published_title_detector_matches_exact_phrase_not_incidental_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "src/data"
            data.mkdir(parents=True)
            (data / "posts.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "transition-from-caregiver-to-daycare",
                            "slug": "transition-from-caregiver-to-daycare",
                            "title": "מעבר ממטפלת למעון: מה עושים עם הבכי ואיך צולחים ימי הסתגלות למעון",
                        },
                        {
                            "id": "unrelated",
                            "slug": "unrelated",
                            "title": "הסתגלות טובה מתחילה בבית לפני הכניסה למעון",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (data / "postsRecent.json").write_text("[]", encoding="utf-8")
            self.assertEqual(
                idea_queue._published_title_keyword_conflicts("הסתגלות למעון", root=root),
                ["transition-from-caregiver-to-daycare"],
            )

    @mock.patch.object(
        idea_queue,
        "_published_title_keyword_conflicts",
        return_value=["transition-from-caregiver-to-daycare"],
    )
    def test_terminal_exhaustion_rejects_conflicting_idea_and_claims_replacement(self, _conflicts):
        state = self._blocked_state(attempts=3)
        changed = idea_queue.finalize_if_complete(state, now_iso="2026-10-25T04:28:00Z")
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
        self.assertEqual(state["idea_history"][-1]["prior_article_attempts"], 3)
        self.assertEqual(
            state["idea_history"][-1]["conflicting_slugs"],
            ["transition-from-caregiver-to-daycare"],
        )
        self.assertEqual(state["history"][-1]["reason"], "primary_keyword_conflict_advanced")

    @mock.patch.object(
        idea_queue,
        "_published_title_keyword_conflicts",
        return_value=["transition-from-caregiver-to-daycare"],
    )
    def test_pre_dispatch_collision_advances_without_spending_article_attempt(self, _conflicts):
        state = self._blocked_state(attempts=0)
        payload = idea_queue.article_dispatch_inputs(state, {"slot": "2026-10-25"})
        self.assertEqual(state["article"]["attempts"], 0)
        self.assertEqual(state["active_idea"]["idea_id"], "parenting-p1-daycare-adjustment-difficulties")
        self.assertIn("Idea Request ID: parenting-p1-daycare-adjustment-difficulties", payload["topic_brief"])
        self.assertIn("Required Primary Keyword: קשיי הסתגלות למעון", payload["topic_brief"])

    @mock.patch.object(
        idea_queue,
        "_published_title_keyword_conflicts",
        return_value=["transition-from-caregiver-to-daycare"],
    )
    def test_existing_article_identity_prevents_collision_reassignment(self, _conflicts):
        state = self._blocked_state(attempts=3)
        state["article"]["pr_number"] = 1200
        self.assertFalse(idea_queue.finalize_if_complete(state, now_iso="2026-10-25T04:28:00Z"))
        self.assertEqual(state["active_idea"]["idea_id"], "parenting-p1-daycare-adjustment")
        self.assertEqual(state["article"]["attempts"], 3)

    @mock.patch.object(
        idea_queue,
        "_published_title_keyword_conflicts",
        return_value=["transition-from-caregiver-to-daycare"],
    )
    def test_prior_cycle_stale_active_idea_is_not_reclassified_as_keyword_collision(self, _conflicts):
        state = self._blocked_state(attempts=0)
        state["cycle"] = "2026-10-26"
        state["active_idea"]["publication_slot"] = "2026-10-25"
        state["status"] = "blocked"
        state["last_error"] = {"stage": "article", "code": "IDEA_SLOT_MISMATCH"}
        state["history"] = [
            {
                "at": "2026-10-26T00:01:00Z",
                "from": "article_needed",
                "to": "blocked",
                "reason": "IDEA_SLOT_MISMATCH",
            }
        ]
        self.assertIsNone(
            idea_queue.recover_primary_keyword_conflict(
                state,
                now_iso="2026-10-26T04:28:00Z",
            )
        )
        self.assertEqual(state["active_idea"]["idea_id"], "parenting-p1-daycare-adjustment")
        self.assertEqual(len(state["idea_history"]), 0)

    @mock.patch.object(idea_queue, "_published_title_keyword_conflicts", return_value=[])
    def test_no_published_exact_phrase_keeps_active_idea_and_attempt_debt(self, _conflicts):
        state = self._blocked_state(attempts=3)
        self.assertFalse(idea_queue.finalize_if_complete(state, now_iso="2026-10-25T04:28:00Z"))
        self.assertEqual(state["active_idea"]["idea_id"], "parenting-p1-daycare-adjustment")
        self.assertEqual(state["article"]["attempts"], 3)


if __name__ == "__main__":
    unittest.main()
