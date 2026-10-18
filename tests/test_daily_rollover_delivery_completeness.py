#!/usr/bin/env python3
"""Regressions for P1: DAILY_ROLLOVER_DELIVERY_COMPLETENESS.

Verifies that prior cycles are omitted from backlog only when the complete delivery
contract is proven: Article public exact identity AND Long public exact identity
AND Short public exact identity.
"""

from __future__ import annotations

import unittest
from datetime import date

from scripts.kesher_content_controller import new_cycle_state


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


if __name__ == "__main__":
    unittest.main()
