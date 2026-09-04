from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_watchdog as watchdog


def source() -> dict:
    return {"slug": "today-article", "content_sha256": "a" * 64}


def public_item(*, youtube_id: str, width: int, height: int) -> dict:
    src = source()
    return {
        "id": f"item-{youtube_id}",
        "status": "uploaded",
        "uploaded": True,
        "source": copy.deepcopy(src),
        "youtube_id": youtube_id,
        "youtube_url": f"https://youtu.be/{youtube_id}",
        "youtube_verification": {
            "channel_id": core.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
        },
        "media": {"width": width, "height": height},
    }


class V5DeliveryWatchdogContractTests(unittest.TestCase):
    def test_horizontal_public_upload_is_not_a_valid_short(self):
        item = public_item(youtube_id="horizontal", width=1920, height=1080)
        self.assertFalse(v5.short_public_portrait_verified(item, source()))

    def test_portrait_public_upload_is_a_valid_short(self):
        item = public_item(youtube_id="portrait", width=1080, height=1920)
        self.assertTrue(v5.short_public_portrait_verified(item, source()))

    def test_delivery_contract_requires_article_overview_and_portrait_short_links(self):
        state = {
            "article": {"live": True, "url": "https://kesher.saharoni.com/blog/today-article"},
            "long_video": {"verified": True, "youtube_url": "https://youtu.be/overview"},
            "short": {
                "verified": True,
                "youtube_url": "https://youtu.be/short",
                "portrait_verified": True,
            },
        }
        ready, deliverables = v5.delivery_contract(state)
        self.assertTrue(ready)
        self.assertEqual(
            deliverables,
            {
                "article_url": "https://kesher.saharoni.com/blog/today-article",
                "overview_youtube_url": "https://youtu.be/overview",
                "short_youtube_url": "https://youtu.be/short",
                "short_portrait_verified": True,
            },
        )

        state["short"]["portrait_verified"] = False
        ready2, _ = v5.delivery_contract(state)
        self.assertFalse(ready2)

    def test_media_watchdog_recovers_then_blocks_unchanged_stall(self):
        stage: dict = {}
        start = datetime(2026, 9, 4, 6, 0, tzinfo=timezone.utc)
        watchdog.observe_media(
            stage,
            identity="long:today-article:item-1",
            fingerprint="pending:item-1",
            now=start,
        )
        self.assertEqual(
            watchdog.media_decision(stage, now=start + timedelta(minutes=21)),
            "recover",
        )
        watchdog.mark_media_recovery(stage, now=start + timedelta(minutes=21))
        watchdog.mark_media_recovery(stage, now=start + timedelta(minutes=42))
        watchdog.mark_media_recovery(stage, now=start + timedelta(minutes=63))
        self.assertEqual(
            watchdog.media_decision(stage, now=start + timedelta(minutes=84)),
            "blocked",
        )

    def test_media_watchdog_resets_recovery_budget_when_provider_progresses(self):
        stage: dict = {}
        start = datetime(2026, 9, 4, 6, 0, tzinfo=timezone.utc)
        watchdog.observe_media(stage, identity="short:today-article:item-2", fingerprint="generating:1", now=start)
        watchdog.mark_media_recovery(stage, now=start + timedelta(minutes=21))
        watchdog.observe_media(
            stage,
            identity="short:today-article:item-2",
            fingerprint="downloaded:2",
            now=start + timedelta(minutes=22),
        )
        self.assertEqual(stage["watchdog"]["recovery_count"], 0)
        self.assertEqual(
            watchdog.media_decision(stage, now=start + timedelta(minutes=23)),
            "wait",
        )


if __name__ == "__main__":
    unittest.main()
