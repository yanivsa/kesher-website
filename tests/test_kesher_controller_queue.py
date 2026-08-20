from __future__ import annotations

import unittest

from scripts import kesher_content_controller as controller
from scripts import kesher_content_controller_entry as entry


def item(
    slug: str,
    status: str,
    *,
    technical: bool | None = None,
    uploaded: bool = False,
    day: str | None = None,
) -> dict:
    row = {
        "id": f"video-{slug}",
        "status": status,
        "uploaded": uploaded,
        "source": {"slug": slug},
    }
    if day:
        row["israel_date"] = day
        row["source"]["date"] = day
    if technical is not None:
        row["technical_verified"] = technical
    return row


class ControllerQueueTests(unittest.TestCase):
    def test_prior_day_unresolved_item_is_selected_before_current_day(self) -> None:
        state = {
            "items": [
                item("yesterday", "generating", technical=False, day="2026-08-18"),
            ]
        }
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual([row["source"]["slug"] for row in selected], ["yesterday"])

    def test_verified_prior_day_upload_does_not_block_current_day(self) -> None:
        old = item("yesterday", "uploaded", uploaded=True, day="2026-08-18")
        old.update({
            "youtube_id": "old-id",
            "youtube_url": "https://www.youtube.com/watch?v=old-id",
            "youtube_verification": {
                "channel_id": controller.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        })
        current = item("today", "generating", technical=False, day="2026-08-19")
        state = {"items": [old, current]}
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual(selected, [current])

    def test_unverified_prior_day_upload_is_recovery_backlog(self) -> None:
        old = item("yesterday", "uploaded", uploaded=True, day="2026-08-18")
        old.update({"youtube_id": "old-id"})
        selected = entry.queue_aware_matching({"items": [old]}, "today")
        self.assertEqual(selected, [old])

    def test_multiple_unresolved_videos_form_fifo_queue(self) -> None:
        oldest = item("two-days-ago", "generating", technical=False, day="2026-08-17")
        yesterday = item("yesterday", "source_selected", technical=False, day="2026-08-18")
        current = item("today", "generating", technical=False, day="2026-08-19")
        state = {"items": [current, yesterday, oldest]}
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual(selected, [oldest])

    def test_fifo_tie_breaker_is_deterministic(self) -> None:
        first = item("a", "generating", technical=False, day="2026-08-18")
        second = item("b", "generating", technical=False, day="2026-08-18")
        first["created_at"] = "2026-08-18T01:00:00+00:00"
        second["created_at"] = "2026-08-18T02:00:00+00:00"
        selected = entry.queue_aware_matching({"items": [second, first]}, "today")
        self.assertEqual(selected, [first])

    def test_jules_rejected_prior_day_item_remains_recoverable(self) -> None:
        old = item("yesterday", "rejected", technical=True, day="2026-08-18")
        selected = entry.queue_aware_matching({"items": [old]}, "today")
        self.assertEqual(selected, [old])


if __name__ == "__main__":
    unittest.main()
