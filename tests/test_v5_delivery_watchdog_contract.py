from __future__ import annotations

import copy
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime
from scripts import kesher_content_watchdog as watchdog
from scripts import kesher_e2e_delivery_guard as delivery_guard


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
        "signature_verified": True,
        "signature_duration_seconds": 3.0,
        "signature_fullscreen": True,
        "signature_video_sha256": "b" * 64,
    }


class MiniGitHub:
    def __init__(self, item):
        self.item = item

    def newest_short_state(self):
        return {"version": 1, "items": [copy.deepcopy(self.item)]}


class MiniGitHubHistoricalOverview:
    def __init__(self, item):
        self.item = copy.deepcopy(item)
        self.saved_state = None
        self.history_calls = 0

    def newest_video_state(self):
        return {"version": 1, "items": []}

    def verified_video_item_from_history(self, src):
        self.history_calls += 1
        if (self.item.get("source") or {}) == src:
            return copy.deepcopy(self.item)
        return None

    def save_controller_state(self, state):
        self.saved_state = copy.deepcopy(state)


class HistoricalOverviewController(runtime.RuntimeV5Controller):
    def __init__(self, item):
        self.github = MiniGitHubHistoricalOverview(item)
        self.now = datetime(2026, 9, 4, 9, 30, tzinfo=timezone.utc)
        self.dispatched_from = None

    def _tick_short(self, state, src, long_item):
        self.dispatched_from = copy.deepcopy(long_item)
        state["short"]["attempt_count"] = 1
        state["short"]["status"] = "running"
        return core.Action("dispatch_short", "historical Overview adopted; Short dispatched")


class MissingSignatureController(runtime.RuntimeV5Controller):
    def _signature_asset_path(self):
        return Path("/definitely/missing/signature-mask.svg")


class V5DeliveryWatchdogContractTests(unittest.TestCase):
    def short_verified(self, item):
        return delivery_guard.short_public_portrait_verified(
            item,
            source(),
            youtube_verified=core.verified_youtube_item,
        )

    def test_horizontal_public_upload_is_not_a_valid_short(self):
        item = public_item(youtube_id="horizontal", width=1920, height=1080)
        self.assertFalse(self.short_verified(item))

    def test_portrait_public_upload_with_signature_is_a_valid_short(self):
        item = public_item(youtube_id="portrait", width=1080, height=1920)
        self.assertTrue(self.short_verified(item))

    def test_portrait_public_upload_with_svg_signature_is_a_valid_short(self):
        item = public_item(youtube_id="portrait-svg", width=1080, height=1920)
        item.pop("signature_video_sha256")
        item.pop("signature_verified")
        item.pop("signature_duration_seconds")
        item.pop("signature_fullscreen")
        item.update({
            "technical_verified": True,
            "visual_pipeline": "remotion-v4-notebooklm-short-motion-plan-v1",
            "signature_asset": "signature-mask.svg",
            "signature_sha256": "c" * 64,
        })
        self.assertTrue(self.short_verified(item))

    def test_portrait_public_upload_without_signature_is_not_a_valid_short(self):
        item = public_item(youtube_id="portrait", width=1080, height=1920)
        item["signature_verified"] = False
        self.assertFalse(self.short_verified(item))

    def test_runtime_controller_refuses_to_adopt_horizontal_short(self):
        item = public_item(youtube_id="horizontal", width=1920, height=1080)
        controller = object.__new__(runtime.RuntimeV5Controller)
        controller.github = MiniGitHub(item)
        state = {"short": v5.v3._stage_template()}
        self.assertIsNone(controller._adopt_existing_short(state, source()))
        self.assertNotEqual(state["short"].get("status"), "complete")

    def test_runtime_controller_adopts_only_verified_portrait_signature_short(self):
        item = public_item(youtube_id="portrait", width=1080, height=1920)
        controller = object.__new__(runtime.RuntimeV5Controller)
        controller.github = MiniGitHub(item)
        state = {"short": v5.v3._stage_template()}
        adopted = controller._adopt_existing_short(state, source())
        self.assertIsNotNone(adopted)
        self.assertTrue(state["short"]["portrait_verified"])
        self.assertTrue(state["short"]["signature_verified"])
        self.assertEqual(state["short"]["width"], 1080)
        self.assertEqual(state["short"]["height"], 1920)

    def test_missing_approved_signature_asset_blocks_new_short_dispatch(self):
        controller = object.__new__(MissingSignatureController)
        state = {"short": v5.v3._stage_template(), "history": [], "status": "long_video_complete"}
        action = controller._signature_asset_blocker(state)
        self.assertIsNotNone(action)
        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["short"]["status"], "blocked")
        self.assertEqual((state.get("last_error") or {}).get("code"), "SHORT_SIGNATURE_ASSET_MISSING")

    def test_historical_public_overview_is_adopted_and_advances_short_same_tick(self):
        overview = public_item(youtube_id="overview", width=1920, height=1080)
        controller = HistoricalOverviewController(overview)
        state = {
            "article": {
                "live": True,
                "url": "https://kesher.saharoni.com/blog/today-article",
                "status": "complete",
            },
            "image": {"status": "complete"},
            "long_video": v5.v3._stage_template(),
            "short": v5.v3._stage_template(),
            "deliverables": {},
        }

        action = controller._reconcile_historical_long_and_advance_short(state, source())

        self.assertEqual(controller.github.history_calls, 1)
        self.assertEqual(action.kind, "dispatch_short")
        self.assertIsNotNone(controller.dispatched_from)
        self.assertEqual(controller.dispatched_from["youtube_url"], "https://youtu.be/overview")
        self.assertEqual(state["long_video"]["status"], "complete")
        self.assertEqual(state["long_video"]["youtube_url"], "https://youtu.be/overview")
        self.assertEqual(state["short"]["attempt_count"], 1)

    def test_delivery_contract_requires_article_overview_portrait_and_signature_short(self):
        state = {
            "article": {"live": True, "url": "https://kesher.saharoni.com/blog/today-article"},
            "long_video": {"verified": True, "youtube_url": "https://youtu.be/overview"},
            "short": {
                "verified": True,
                "youtube_url": "https://youtu.be/short",
                "portrait_verified": True,
                "signature_verified": True,
            },
        }
        ready, deliverables = delivery_guard.delivery_contract(state)
        self.assertTrue(ready)
        self.assertEqual(
            deliverables,
            {
                "article_url": "https://kesher.saharoni.com/blog/today-article",
                "overview_youtube_url": "https://youtu.be/overview",
                "short_youtube_url": "https://youtu.be/short",
                "short_portrait_verified": True,
                "short_signature_verified": True,
            },
        )

        state["short"]["signature_verified"] = False
        ready2, _ = delivery_guard.delivery_contract(state)
        self.assertFalse(ready2)

    def test_poll_timestamp_changes_do_not_fake_provider_progress(self):
        item = {
            "id": "video-1",
            "status": "generating",
            "last_provider_status": "pending",
            "task_id": "task-1",
            "artifact_id": "task-1",
            "updated_at": "2026-09-04T06:00:00+00:00",
            "last_polled_at": "2026-09-04T06:00:00+00:00",
        }
        before = delivery_guard.media_fingerprint(item)
        item["updated_at"] = "2026-09-04T06:05:00+00:00"
        item["last_polled_at"] = "2026-09-04T06:05:00+00:00"
        after = delivery_guard.media_fingerprint(item)
        self.assertEqual(before, after)

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
