from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime
from scripts import kesher_e2e_delivery_guard as delivery_guard


class FakeHistoryGitHub:
    def __init__(self, *, long_state=None, short_state=None, signature_path=None):
        self.long_state = long_state or {"items": []}
        self.short_state = short_state or {"items": []}
        self.signature_path = signature_path
        self.dispatches = []
        self.history_calls = 0
        self.active_runs = {}
        self.saved_states = []

    def newest_video_state(self):
        self.history_calls += 1
        return copy.deepcopy(self.long_state)

    def newest_short_state(self):
        return copy.deepcopy(self.short_state)

    def active_workflow_run(self, workflow, production_only=False):
        return self.active_runs.get(workflow)

    def dispatch(self, workflow, inputs):
        self.dispatches.append((workflow, copy.deepcopy(inputs)))

    def contents_json(self, path, ref):
        raise AssertionError(f"unexpected contents_json({path!r}, {ref!r})")

    def save_controller_state(self, state):
        self.saved_states.append(copy.deepcopy(state))


class FakeSite:
    def get(self, url):
        raise AssertionError(f"unexpected site get {url!r}")


class V5DeliveryWatchdogContractTests(unittest.TestCase):
    def _controller(self, github):
        controller = object.__new__(runtime.RuntimeV5Controller)
        controller.github = github
        controller.site = FakeSite()
        controller.dry_run = False
        controller._signature_asset_path = lambda: github.signature_path
        return controller

    @staticmethod
    def _source():
        return {"slug": "today-article", "content_sha256": "a" * 64}

    @staticmethod
    def _overview_item(*, source=None):
        source = source or V5DeliveryWatchdogContractTests._source()
        return {
            "id": "long-1",
            "status": "complete",
            "source": dict(source),
            "uploaded": True,
            "verified": True,
            "youtube_id": "overview",
            "youtube_url": "https://youtu.be/overview",
            "youtube_verification": {"public": True},
        }

    @staticmethod
    def _short_item(*, source=None, width=1080, height=1920, signature_verified=True):
        source = source or V5DeliveryWatchdogContractTests._source()
        return {
            "id": "short-1",
            "type": delivery_guard.CANONICAL_SHORT_TYPE,
            "source_mode": delivery_guard.CANONICAL_SHORT_SOURCE_MODE,
            "visual_pipeline": delivery_guard.CANONICAL_SHORT_PIPELINE,
            "status": "complete",
            "source": dict(source),
            "uploaded": True,
            "verified": True,
            "youtube_id": "short",
            "youtube_url": "https://youtu.be/short",
            "youtube_verification": {"public": True},
            "media": {"width": width, "height": height},
            "portrait_verified": width == 1080 and height == 1920,
            "signature_verified": signature_verified,
            "signature_fullscreen": signature_verified,
            "signature_duration_seconds": 3.0 if signature_verified else 0,
            "signature_video_sha256": "s" * 64 if signature_verified else "",
        }

    def test_portrait_public_upload_with_signature_is_a_valid_short(self):
        source = self._source()
        item = self._short_item(source=source)
        self.assertTrue(
            delivery_guard.short_public_portrait_verified(
                item,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        )

    def test_horizontal_public_upload_is_not_a_valid_short(self):
        source = self._source()
        item = self._short_item(source=source, width=1920, height=1080)
        self.assertFalse(
            delivery_guard.short_public_portrait_verified(
                item,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        )

    def test_portrait_public_upload_without_signature_is_not_a_valid_short(self):
        source = self._source()
        item = self._short_item(source=source, signature_verified=False)
        self.assertFalse(
            delivery_guard.short_public_portrait_verified(
                item,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        )

    def test_portrait_public_upload_with_svg_only_signature_is_not_a_valid_short(self):
        source = self._source()
        item = self._short_item(source=source)
        item["signature_video_sha256"] = ""
        self.assertFalse(
            delivery_guard.short_public_portrait_verified(
                item,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        )

    def test_short_public_portrait_verified_rejects_overview_segment(self):
        source = self._source()
        item = self._short_item(source=source)
        item["source_mode"] = "overview-segment"
        self.assertFalse(
            delivery_guard.short_public_portrait_verified(
                item,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        )

    def test_short_public_portrait_verified_rejects_svg_only(self):
        source = self._source()
        item = self._short_item(source=source)
        item["signature_video_sha256"] = ""
        self.assertFalse(
            delivery_guard.short_public_portrait_verified(
                item,
                source,
                youtube_verified=v5.core.verified_youtube_item,
            )
        )

    def test_delivery_contract_rejects_svg_only_short(self):
        state = {
            "article": {"live": True, "url": "https://kesher.saharoni.com/blog/today-article"},
            "long_video": {"verified": True, "youtube_url": "https://youtu.be/overview"},
            "short": {
                "type": delivery_guard.CANONICAL_SHORT_TYPE,
                "source_mode": delivery_guard.CANONICAL_SHORT_SOURCE_MODE,
                "visual_pipeline": delivery_guard.CANONICAL_SHORT_PIPELINE,
                "verified": True,
                "youtube_url": "https://youtu.be/short",
                "portrait_verified": True,
                "signature_verified": True,
                "signature_fullscreen": True,
                "signature_duration_seconds": 3.0,
                "signature_video_sha256": "",
            },
        }
        ready, _ = delivery_guard.delivery_contract(state)
        self.assertFalse(ready)

    def test_delivery_contract_rejects_overview_derived_short(self):
        state = {
            "article": {"live": True, "url": "https://kesher.saharoni.com/blog/today-article"},
            "long_video": {"verified": True, "youtube_url": "https://youtu.be/overview"},
            "short": {
                "type": delivery_guard.CANONICAL_SHORT_TYPE,
                "source_mode": "overview-segment",
                "visual_pipeline": delivery_guard.CANONICAL_SHORT_PIPELINE,
                "verified": True,
                "youtube_url": "https://youtu.be/short",
                "portrait_verified": True,
                "signature_verified": True,
                "signature_fullscreen": True,
                "signature_duration_seconds": 3.0,
                "signature_video_sha256": "s" * 64,
            },
        }
        ready, _ = delivery_guard.delivery_contract(state)
        self.assertFalse(ready)

    def test_delivery_contract_requires_article_overview_portrait_and_signature_short(self):
        state = {
            "article": {"live": True, "url": "https://kesher.saharoni.com/blog/today-article"},
            "long_video": {"verified": True, "youtube_url": "https://youtu.be/overview"},
            "short": {
                "type": delivery_guard.CANONICAL_SHORT_TYPE,
                "source_mode": delivery_guard.CANONICAL_SHORT_SOURCE_MODE,
                "visual_pipeline": delivery_guard.CANONICAL_SHORT_PIPELINE,
                "verified": True,
                "youtube_url": "https://youtu.be/short",
                "portrait_verified": True,
                "signature_verified": True,
                "signature_fullscreen": True,
                "signature_duration_seconds": 3.0,
                "signature_video_sha256": "s" * 64,
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
                "short_origin_verified": True,
                "enhancement_required_for_publication": False,
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
        }
        first = delivery_guard.media_fingerprint(item)
        item["updated_at"] = "2026-09-04T06:05:00+00:00"
        second = delivery_guard.media_fingerprint(item)
        self.assertEqual(first, second)

    def test_media_watchdog_recovers_then_blocks_unchanged_stall(self):
        source = self._source()
        base_state = {
            "cycle": "2026-09-04",
            "status": "video_generating",
            "article": {"slug": source["slug"], "content_sha256": source["content_sha256"]},
            "long_video": {"item_id": "long-1", "status": "generating", "attempt_count": 1},
            "short": {},
            "last_error": {},
        }
        item = {
            "id": "long-1",
            "status": "generating",
            "last_provider_status": "pending",
            "task_id": "task-1",
            "artifact_id": "task-1",
            "source": source,
        }
        github = FakeHistoryGitHub(long_state={"items": [item]})
        controller = self._controller(github)

        with mock.patch.object(v5.core, "utc_now", return_value="2026-09-04T06:00:00+00:00"):
            state1, action1 = controller._apply_media_watchdog(copy.deepcopy(base_state), source)
        self.assertEqual(action1.kind, "dispatch_long_video")
        self.assertEqual(state1["long_video"]["watchdog_recovery_count"], 1)

        controller.github.long_state = {"items": [item]}
        with mock.patch.object(v5.core, "utc_now", return_value="2026-09-04T06:05:00+00:00"):
            state2, action2 = controller._apply_media_watchdog(copy.deepcopy(state1), source)
        self.assertEqual(action2.kind, "blocked")
        self.assertEqual(state2["last_error"]["code"], "VIDEO_STALLED_AFTER_RECOVERY")

    def test_media_watchdog_resets_recovery_budget_when_provider_progresses(self):
        source = self._source()
        state = {
            "cycle": "2026-09-04",
            "status": "video_generating",
            "article": {"slug": source["slug"], "content_sha256": source["content_sha256"]},
            "long_video": {
                "item_id": "long-1",
                "status": "generating",
                "attempt_count": 1,
                "watchdog_recovery_count": 1,
                "watchdog_fingerprint": "stale",
            },
            "short": {},
            "last_error": {},
        }
        progressed = {
            "id": "long-1",
            "status": "pending_review",
            "last_provider_status": "complete",
            "task_id": "task-1",
            "artifact_id": "artifact-2",
            "source": source,
        }
        github = FakeHistoryGitHub(long_state={"items": [progressed]})
        controller = self._controller(github)

        with mock.patch.object(v5.core, "utc_now", return_value="2026-09-04T06:10:00+00:00"):
            state2, action2 = controller._apply_media_watchdog(copy.deepcopy(state), source)
        self.assertEqual(action2.kind, "wait")
        self.assertEqual(state2["long_video"]["watchdog_recovery_count"], 0)
        self.assertEqual(state2["long_video"]["watchdog_fingerprint"], delivery_guard.media_fingerprint(progressed))

    def test_missing_approved_signature_asset_blocks_new_short_dispatch(self):
        source = self._source()
        long_item = self._overview_item(source=source)
        github = FakeHistoryGitHub(long_state={"items": [long_item]}, signature_path=Path("/definitely/missing/signature.svg"))
        controller = self._controller(github)
        state = {
            "cycle": "2026-09-04",
            "status": "video_generating",
            "article": {
                "live": True,
                "url": "https://kesher.saharoni.com/blog/today-article",
                "slug": source["slug"],
                "content_sha256": source["content_sha256"],
            },
            "long_video": {},
            "short": {},
            "last_error": {},
        }
        _, action = controller._run_shared_video_pipeline(state, source)
        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["last_error"]["code"], "SHORT_SIGNATURE_ASSET_MISSING")

    def test_historical_public_overview_is_adopted_and_advances_short_same_tick(self):
        source = self._source()
        long_item = self._overview_item(source=source)
        with tempfile.TemporaryDirectory() as temp_dir:
            signature_path = Path(temp_dir) / "signature.svg"
            signature_path.write_text("<svg></svg>", encoding="utf-8")
            github = FakeHistoryGitHub(long_state={"items": [long_item]}, signature_path=signature_path)
            controller = self._controller(github)
            controller.dispatched_from = None

            def capture_dispatch_short(state, source_arg, long_arg):
                controller.dispatched_from = copy.deepcopy(long_arg)
                return v5.core.Action("dispatch_short", "short")

            controller._dispatch_short_from_long = capture_dispatch_short
            state = {
                "cycle": "2026-09-04",
                "status": "video_generating",
                "article": {
                    "live": True,
                    "url": "https://kesher.saharoni.com/blog/today-article",
                    "slug": source["slug"],
                    "content_sha256": source["content_sha256"],
                },
                "long_video": {},
                "short": {},
                "last_error": {},
            }
            state, action = controller._run_shared_video_pipeline(state, source)
            self.assertEqual(controller.github.history_calls, 1)
            self.assertEqual(action.kind, "dispatch_short")
            self.assertIsNotNone(controller.dispatched_from)
            self.assertEqual(controller.dispatched_from["youtube_url"], "https://youtu.be/overview")
            self.assertEqual(state["long_video"]["status"], "complete")
            self.assertEqual(state["long_video"]["youtube_url"], "https://youtu.be/overview")
            self.assertEqual(state["short"]["attempt_count"], 1)

    def test_adopt_existing_short_adopts_svg_signature_remotion_proof(self):
        source = self._source()
        short_item = self._short_item(source=source)
        short_item.update(
            {
                "signature_asset": "public/images/signature/signature-mask.svg",
                "signature_sha256": "f" * 64,
                "signature_asset_sha256": "f" * 64,
            }
        )
        github = FakeHistoryGitHub(short_state={"items": [short_item]})
        controller = self._controller(github)
        state = {"short": {}}
        adopted = controller._adopt_existing_short(state, source)
        self.assertTrue(adopted)
        self.assertTrue(state["short"]["signature_verified"])
        self.assertEqual(state["short"]["signature_video_sha256"], "s" * 64)

    def test_runtime_controller_adopts_only_verified_portrait_signature_short(self):
        source = self._source()
        short_item = self._short_item(source=source)
        github = FakeHistoryGitHub(short_state={"items": [short_item]})
        controller = self._controller(github)
        state = {"short": {}}
        self.assertTrue(controller._adopt_existing_short(state, source))
        self.assertTrue(state["short"]["portrait_verified"])
        self.assertTrue(state["short"]["signature_verified"])

    def test_runtime_controller_refuses_to_adopt_horizontal_short(self):
        source = self._source()
        short_item = self._short_item(source=source, width=1920, height=1080)
        github = FakeHistoryGitHub(short_state={"items": [short_item]})
        controller = self._controller(github)
        state = {"short": {}}
        self.assertFalse(controller._adopt_existing_short(state, source))


if __name__ == "__main__":
    unittest.main()
