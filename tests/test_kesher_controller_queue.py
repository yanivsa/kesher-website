from __future__ import annotations

import unittest

from scripts import kesher_content_controller as controller
from scripts import kesher_content_controller_entry as entry


def item(slug: str, status: str, *, technical: bool | None = None, uploaded: bool = False) -> dict:
    row = {
        "id": f"video-{slug}",
        "status": status,
        "uploaded": uploaded,
        "source": {"slug": slug},
    }
    if technical is not None:
        row["technical_verified"] = technical
    return row


class ControllerQueueTests(unittest.TestCase):
    def test_prior_day_unresolved_item_is_selected_before_current_day(self) -> None:
        state = {
            "items": [
                item("yesterday", "generating", technical=False),
            ]
        }
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual([row["source"]["slug"] for row in selected], ["yesterday"])

    def test_verified_prior_day_upload_does_not_block_current_day(self) -> None:
        old = item("yesterday", "uploaded", uploaded=True)
        old.update({
            "youtube_id": "old-id",
            "youtube_url": "https://www.youtube.com/watch?v=old-id",
            "youtube_verification": {
                "channel_id": controller.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        })
        current = item("today", "generating", technical=False)
        state = {"items": [old, current]}
        selected = entry.queue_aware_matching(state, "today")
        self.assertEqual(selected, [current])

    def test_unverified_prior_day_upload_is_recovery_backlog(self) -> None:
        old = item("yesterday", "uploaded", uploaded=True)
        old.update({"youtube_id": "old-id"})
        selected = entry.queue_aware_matching({"items": [old]}, "today")
        self.assertEqual(selected, [old])

    def test_two_unresolved_daily_videos_fail_closed(self) -> None:
        state = {
            "items": [
                item("yesterday", "generating", technical=False),
                item("today", "source_selected", technical=False),
            ]
        }
        with self.assertRaisesRegex(controller.ControllerError, "VIDEO_BACKLOG_CONFLICT"):
            entry.queue_aware_matching(state, "today")

    def test_jules_rejected_prior_day_item_remains_recoverable(self) -> None:
        old = item("yesterday", "rejected", technical=True)
        selected = entry.queue_aware_matching({"items": [old]}, "today")
        self.assertEqual(selected, [old])


if __name__ == "__main__":
    unittest.main()
