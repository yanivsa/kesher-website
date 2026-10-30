from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_video_reconcile as reconcile


TZ = ZoneInfo("Asia/Jerusalem")


def post(slug: str, day: str = "2026-08-19") -> dict:
    return {
        "id": slug,
        "slug": slug,
        "title": "כותרת יומית בעברית",
        "date": day,
        "category": "הדרכת הורים",
        "excerpt": "תקציר עברי שימושי למשפחה",
        "content": "<p>תוכן עברי מלא ומעשי עבור המאמר היומי.</p>",
    }


def technically_verified(item: dict, status: str = "approved") -> None:
    item.update({
        "status": status,
        "technical_verified": True,
        "visual_review_status": "approved",
        "semantic_review_status": "approved",
        "metadata_review_status": "approved",
        "reviewed_at": "2026-08-19T16:00:00+00:00",
        "reviewer": {"type": "jules", "session": "sessions/review-1"},
        "final_sha256": "f" * 64,
        "manifest_sha256": "m" * 64,
        "transcript_sha256": "t" * 64,
        "source_file_sha256": "q" * 64,
        "visual_review_sha256": "v" * 64,
        "frame_sha256": {"frame-1.png": "a" * 64},
    })


class VideoReconcileTests(unittest.TestCase):
    def test_video_workflow_declares_video_overview_media_mode(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/kesher-daily-video.yml").read_text(encoding="utf-8")
        self.assertIn("KESHER_MEDIA_MODE: video_overview", workflow)

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.posts_file = self.root / "posts.json"
        self.now = datetime(2026, 8, 19, 20, 0, tzinfo=TZ)
        self.patchers = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_dir / "state.json"),
            mock.patch.object(pipeline, "POSTS_FILE", self.posts_file),
            mock.patch.object(pipeline, "israel_now", return_value=self.now),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def write_posts(self, rows: list[dict]) -> None:
        self.posts_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def test_prior_day_active_item_is_preserved_as_backlog(self) -> None:
        today = post("today")
        yesterday = post("yesterday", "2026-08-18")
        self.write_posts([today, yesterday])
        old = pipeline.new_item(pipeline.source_metadata(yesterday))
        old.update({"status": "generating", "task_id": "old-task", "artifact_id": "old-task"})
        pipeline.save_state({"version": 1, "items": [old], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_generation(), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["status"], "generating")
        self.assertEqual(saved[0]["source"]["slug"], "yesterday")
        self.assertNotIn("superseded_reason", saved[0])

    def test_metadata_only_rejection_is_eligible_for_exact_remotion_rebuild(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        item.update({
            "status": "rejected",
            "technical_verified": False,
            "metadata_review_status": "rejected",
            "visual_review_status": "pending",
            "review_notes": {"technical": "נפסל טכנית: מטא דאטה", "metadata": "חסר קישור אתר"},
            "raw_mp4": "raw.mp4",
            "raw_sha256": "a" * 64,
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
        })
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        raw = self.state_dir / "raw.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b"provider-video")
        item["raw_sha256"] = pipeline.sha256_file(raw)
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        with mock.patch.object(pipeline, "validate_and_manifest") as validate:
            self.assertEqual(pipeline.rebuild_rejected_with_remotion(item["id"]), 0)
        validate.assert_called_once()

    def test_legacy_technically_verified_item_can_rebuild_missing_immutable_evidence(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        item.update({
            "status": "pending_review",
            "technical_verified": True,
            "raw_mp4": "raw.mp4",
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
            "final_sha256": "f" * 64,
            # Legacy item deliberately lacks transcript/manifest/source/frame evidence hashes.
        })
        raw = self.state_dir / "raw.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b"provider-video")
        item["raw_sha256"] = pipeline.sha256_file(raw)
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        with mock.patch.object(pipeline, "validate_and_manifest") as validate:
            self.assertEqual(pipeline.rebuild_rejected_with_remotion(item["id"]), 0)

        validate.assert_called_once()
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "downloaded")
        self.assertFalse(saved["technical_verified"])
        self.assertIn("evidence_history", saved)

    def test_resolution_rejected_short_is_eligible_for_exact_remotion_rebuild(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        item.update({
            "type": "article_short",
            "status": "rejected",
            "technical_verified": False,
            "visual_review_status": "pending",
            "review_notes": {
                "technical": "נפסל טכנית: יחס התמונה 720x1280 אינו Short אנכי 1080x1920",
                "visual": "",
                "semantic": "",
                "metadata": "",
            },
            "raw_mp4": "raw.mp4",
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
        })
        raw = self.state_dir / "raw.mp4"
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_bytes(b"provider-short")
        item["raw_sha256"] = pipeline.sha256_file(raw)
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        with mock.patch.object(pipeline, "validate_and_manifest") as validate:
            self.assertEqual(pipeline.rebuild_rejected_with_remotion(item["id"]), 0)

        validate.assert_called_once()
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "downloaded")
        self.assertFalse(saved["technical_verified"])
        self.assertIn("evidence_history", saved)

    def test_provider_pending_item_is_not_an_upload_failure(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        item.update({
            "status": "generating",
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
            "last_provider_status": "pending",
        })
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"]), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "generating")
        self.assertEqual(saved["source_id"], "source-1")
        self.assertEqual(saved["task_id"], "task-1")
        self.assertEqual(saved["artifact_id"], "task-1")
        self.assertNotIn("review_gate", saved)

    def test_inconsistent_pending_review_without_technical_verification_fails_closed(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        item.update({
            "status": "pending_review",
            "technical_verified": False,
            "final_sha256": "f" * 64,
        })
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        with self.assertRaisesRegex(pipeline.PipelineError, "not technically verified"):
            reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"])

    def test_multiple_backlog_items_are_processed_oldest_first(self) -> None:
        today = post("today")
        oldest_post = post("oldest", "2026-08-17")
        newer_post = post("newer", "2026-08-18")
        self.write_posts([today, newer_post, oldest_post])
        newest = pipeline.new_item(pipeline.source_metadata(newer_post))
        newest.update({"status": "generating", "task_id": "newer-task", "artifact_id": "newer-task"})
        oldest = pipeline.new_item(pipeline.source_metadata(oldest_post))
        oldest.update({"status": "generating", "task_id": "old-task", "artifact_id": "old-task"})
        pipeline.save_state({"version": 1, "items": [newest, oldest], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_generation(), 0)
        saved = reconcile.unresolved_items(pipeline.load_state())
        self.assertEqual(saved[0]["source"]["slug"], "oldest")
        self.assertEqual(len(saved), 2)

    def test_targeted_generation_supersedes_stale_rejected_item_after_source_change(self) -> None:
        today = post("today")
        self.write_posts([today])
        current_source = pipeline.source_metadata(today)
        stale = pipeline.new_item(current_source)
        stale.update({
            "status": "rejected",
            "technical_verified": False,
            "type": "article_short",
            "source_mode": "direct-short",
        })
        stale["source"]["content_sha256"] = "0" * 64
        pipeline.save_state({"version": 1, "items": [stale], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_generation("today"), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["status"], "superseded")
        self.assertEqual(saved[0]["superseded_reason"], "published_source_changed")
        replacement = saved[1]
        self.assertEqual(replacement["status"], "source_selected")
        self.assertEqual(replacement["source"]["content_sha256"], current_source["content_sha256"])
        self.assertEqual(replacement["type"], "article_short")
        self.assertEqual(replacement["source_mode"], "direct-short")
        self.assertEqual(replacement["fresh_generation_attempt"], 1)
        self.assertNotIn("retry_of", replacement)

    def test_prior_day_technical_rejection_retries_same_source_not_today(self) -> None:
        today = post("today")
        older = post("older", "2026-08-18")
        self.write_posts([today, older])
        source = pipeline.source_metadata(older)
        rejected = pipeline.new_item(source)
        rejected["status"] = "rejected"
        rejected["technical_verified"] = False
        pipeline.save_state({"version": 1, "items": [rejected], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_generation(), 0)
        saved = pipeline.load_state()
        self.assertEqual(len(saved["items"]), 2)
        old, replacement = saved["items"]
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_reason"], "technical_retry_same_source")
        self.assertEqual(replacement["status"], "source_selected")
        self.assertEqual(replacement["source"]["slug"], "older")
        self.assertEqual(replacement["source"]["content_sha256"], source["content_sha256"])
        self.assertEqual(replacement["technical_retry_count"], 1)
        self.assertEqual(replacement["retry_of"], old["id"])

    def test_technical_retry_is_bounded_to_four_fresh_generations(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        rejected = pipeline.new_item(source)
        rejected.update({
            "status": "rejected",
            "technical_verified": False,
            "technical_retry_count": reconcile.MAX_TECHNICAL_RETRIES,
        })
        pipeline.save_state({"version": 1, "items": [rejected], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.prepare_generation(), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "released_without_short")
        self.assertEqual(saved["release_reason"], "fresh_generation_budget_exhausted")
        self.assertEqual(reconcile.unresolved_items(pipeline.load_state()), [])

    def test_explicit_release_marks_existing_item_and_prevents_fifo_retry(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        item.update({"status": "generating", "source_id": "s", "task_id": "t", "artifact_id": "t"})
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.release_without_short("today"), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["status"], "released_without_short")
        self.assertEqual(saved[0]["source"]["slug"], "today")
        self.assertEqual(reconcile.unresolved_items(pipeline.load_state()), [])

    def test_explicit_release_creates_tombstone_when_no_video_item_exists(self) -> None:
        today = post("today")
        self.write_posts([today])
        pipeline.save_state({"version": 1, "items": [], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.release_without_short("today"), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["status"], "released_without_short")
        self.assertEqual(saved[0]["type"], "short_release")
        self.assertEqual(saved[0]["source"]["slug"], "today")
        self.assertFalse(saved[0]["uploaded"])

    def test_technically_verified_prior_day_item_is_uploadable_before_today(self) -> None:
        today = post("today")
        yesterday = post("yesterday", "2026-08-18")
        self.write_posts([today, yesterday])
        item = pipeline.new_item(pipeline.source_metadata(yesterday))
        technically_verified(item)
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"]), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["source"]["slug"], "yesterday")
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["review_gate"], "advisory-jules")
        self.assertEqual(saved["advisory_review_status_before_upload"], "approved")

    def test_changed_final_sha_does_not_require_jules_reapproval(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(item)
        item["final_sha256"] = "x" * 64
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"]), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["final_sha256"], "x" * 64)
        self.assertEqual(saved["review_gate"], "advisory-jules")

    def test_jules_rejection_does_not_block_technical_upload(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(item, status="rejected")
        item["visual_review_status"] = "rejected"
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"]), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["review_gate"], "advisory-jules")
        self.assertEqual(saved["advisory_review_status_before_upload"], "rejected")
        self.assertEqual(saved["status"], "approved")

    def test_unavailable_or_missing_jules_review_does_not_block_technical_upload(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(item, status="pending_review")
        item.pop("reviewer", None)
        item.pop("reviewed_at", None)
        item["visual_review_status"] = "pending"
        item["semantic_review_status"] = "pending"
        item["metadata_review_status"] = "pending"
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"]), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["review_gate"], "advisory-jules")
        self.assertEqual(saved["advisory_review_status_before_upload"], "pending_review")
        self.assertEqual(saved["status"], "approved")

    def test_non_jules_reviewer_identity_does_not_block_technical_upload(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(item)
        item["reviewer"] = {"type": "manual", "session": "manual"}
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"]), 0)
        self.assertEqual(pipeline.load_state()["items"][0]["review_gate"], "advisory-jules")

    def test_persisted_youtube_id_is_verified_without_second_insert(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        item = pipeline.new_item(source)
        item.update({
            "status": "uploading",
            "technical_verified": True,
            "youtube_id": "already-inserted",
            "uploaded": False,
        })
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        verification = {
            "channel_id": pipeline.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
        }
        with mock.patch.object(pipeline, "youtube_access_token", return_value="token"), mock.patch.object(
            pipeline, "verify_authenticated_channel"
        ) as channel, mock.patch.object(
            pipeline, "verify_public_upload", return_value=verification
        ) as verify, mock.patch.object(
            pipeline, "start_resumable_upload"
        ) as insert:
            self.assertEqual(reconcile.prepare_upload(item["source"]["slug"], item["source"]["content_sha256"], item["id"]), 0)

        saved = pipeline.load_state()["items"][0]
        self.assertTrue(saved["uploaded"])
        self.assertEqual(saved["status"], "uploaded")
        self.assertEqual(saved["youtube_url"], "https://www.youtube.com/watch?v=already-inserted")
        self.assertEqual(saved["youtube_verification"], verification)
        channel.assert_called_once_with("token")
        verify.assert_called_once()
        insert.assert_not_called()


    def test_adopt_long_form_provider_seeds_short_without_new_generation_identity(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        long_item = pipeline.new_item(source)
        long_item.update({
            "id": "long-1",
            "status": "uploaded",
            "uploaded": True,
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
            "youtube_id": "long123",
            "youtube_url": "https://youtu.be/long123",
            "youtube_verification": {
                "channel_id": pipeline.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        })
        long_path = self.root / "long-state.json"
        long_path.write_text(json.dumps({"version": 1, "items": [long_item]}), encoding="utf-8")

        self.assertEqual(
            reconcile.adopt_long_form_provider(str(long_path), "today", source["content_sha256"], "long-1"),
            0,
        )
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["status"], "generating")
        self.assertEqual(saved[0]["type"], "article_short")
        self.assertEqual(saved[0]["fresh_generation_attempt"], 0)
        self.assertEqual(saved[0]["source_id"], "source-1")
        self.assertEqual(saved[0]["task_id"], "task-1")
        self.assertEqual(saved[0]["artifact_id"], "task-1")
        self.assertEqual(saved[0]["adopted_from_long_item_id"], "long-1")
        self.assertTrue(saved[0]["shared_provider_identity"])

    def test_adopt_long_form_provider_rejects_content_hash_mismatch(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        long_item = pipeline.new_item(source)
        long_item.update({
            "id": "long-1",
            "status": "uploaded",
            "uploaded": True,
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
            "youtube_id": "long123",
            "youtube_verification": {
                "channel_id": pipeline.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        })
        long_path = self.root / "long-state.json"
        long_path.write_text(json.dumps({"version": 1, "items": [long_item]}), encoding="utf-8")
        with self.assertRaisesRegex(pipeline.PipelineError, "hash changed"):
            reconcile.adopt_long_form_provider(str(long_path), "today", "0" * 64, "long-1")

    def test_prepare_upload_targets_exact_item_when_specified(self) -> None:
        today = post("today")
        yesterday = post("yesterday", "2026-08-18")
        self.write_posts([today, yesterday])
        today_item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(today_item)
        yesterday_item = pipeline.new_item(pipeline.source_metadata(yesterday))
        yesterday_item["status"] = "generating"
        pipeline.save_state({"version": 1, "items": [yesterday_item, today_item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_upload("today", today_item["source"]["content_sha256"], today_item["id"]), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(saved[1]["status"], "approved")

    def test_adopt_long_form_provider_supersedes_unpublished_items(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        orphan_item = {
            "id": "orphan-1",
            "type": "article_short",
            "status": "downloaded",
            "source": {"slug": "ghost-article", "title": "Ghost", "content_sha256": "g" * 64},
        }
        pipeline.save_state({"version": 1, "items": [orphan_item], "updated_at": pipeline.utc_now()})

        long_item = pipeline.new_item(source)
        long_item.update({
            "id": "long-1",
            "status": "uploaded",
            "uploaded": True,
            "source_id": "source-1",
            "task_id": "task-1",
            "artifact_id": "task-1",
            "youtube_id": "long123",
            "youtube_verification": {
                "channel_id": pipeline.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        })
        long_path = self.root / "long-state.json"
        long_path.write_text(json.dumps({"version": 1, "items": [long_item]}), encoding="utf-8")

        self.assertEqual(reconcile.adopt_long_form_provider(str(long_path), "today", source["content_sha256"], "long-1"), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(saved[0]["status"], "superseded")
        self.assertEqual(saved[0]["superseded_reason"], "unpublished_article_draft")
        self.assertEqual(saved[1]["source"]["slug"], "today")

    def test_prepare_generation_supersedes_unverified_upload_and_initializes_fresh_item(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        # Stale item with uploaded=True but failing valid delivery guard (no video signature, no valid public verification)
        legacy_item = pipeline.new_item(source)
        legacy_item["uploaded"] = True
        legacy_item["status"] = "uploaded"
        pipeline.save_state({"version": 1, "items": [legacy_item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_generation("today"), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["status"], "superseded")
        self.assertEqual(saved[0]["superseded_reason"], "unverified_or_legacy_short")
        self.assertFalse(saved[0]["uploaded"])
        self.assertEqual(saved[1]["status"], "source_selected")
        self.assertEqual(saved[1]["source_mode"], "direct-short")

    def test_active_item_returns_none_when_target_slug_does_not_match(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        item = pipeline.new_item(source)
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}

        found = pipeline.active_item(state, slug="different-slug")
        self.assertIsNone(found)


    def test_retry_technical_rejection_preserves_short_type_and_source_mode(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        old_item = pipeline.new_item(source)
        old_item["type"] = "article_short"
        old_item["source_mode"] = "direct-short"
        old_item["status"] = "rejected"
        old_item["technical_verified"] = False
        state = {"version": 1, "items": [old_item], "updated_at": pipeline.utc_now()}

        replacement = reconcile.retry_technical_rejection(state, old_item)
        self.assertIsNotNone(replacement)
        self.assertEqual(old_item["status"], "superseded")
        self.assertEqual(replacement["type"], "article_short")
        self.assertEqual(replacement["source_mode"], "direct-short")
        self.assertEqual(replacement["status"], "source_selected")
        self.assertEqual(replacement["technical_retry_count"], 1)
        self.assertEqual(replacement["fresh_generation_attempt"], 2)

    def test_prepare_generation_exports_target_to_github_env(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        item = pipeline.new_item(source)
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        env_file = self.root / "mock_github_env"
        with mock.patch.dict(os.environ, {"GITHUB_ENV": str(env_file)}):
            reconcile.prepare_generation()
            content = env_file.read_text(encoding="utf-8")
            self.assertIn(f"TARGET_ITEM_ID={item['id']}", content)
            self.assertIn("TARGET_SLUG=today", content)

    def test_prepare_generation_reconciles_downloaded_item_with_rejection_manifest(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        item = pipeline.new_item(source)
        item["status"] = "downloaded"
        item["technical_verified"] = False
        manifest_path = pipeline.STATE_DIR / f"{item['id']}-short-manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps({"technical_verified": False, "rejection_reasons": ["Detected male voice"]}),
            encoding="utf-8",
        )
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        env_file = self.root / "mock_github_env"
        with mock.patch.dict(os.environ, {"GITHUB_ENV": str(env_file)}):
            reconcile.prepare_generation("today")
            state = pipeline.load_state()
            # Old item should be superseded
            self.assertEqual(state["items"][0]["status"], "superseded")
            # Replacement item should be created
            self.assertEqual(len(state["items"]), 2)
            replacement = state["items"][1]
            self.assertEqual(replacement["status"], "source_selected")
            self.assertEqual(replacement["technical_retry_count"], 1)
            content = env_file.read_text(encoding="utf-8")
            self.assertIn(f"TARGET_ITEM_ID={replacement['id']}", content)


    def test_prepare_upload_honors_exact_target_item_before_fifo_backlog(self) -> None:
        current = post("current", "2026-08-19")
        stale = post("stale", "2026-08-18")
        self.write_posts([current, stale])

        stale_item = pipeline.new_item(pipeline.source_metadata(stale))
        stale_item.update({
            "status": "rejected",
            "technical_verified": False,
            "review_notes": {"technical": "נפסל טכנית: stale failure"},
        })
        current_item = pipeline.new_item(pipeline.source_metadata(current))
        technically_verified(current_item, status="rejected")
        pipeline.save_state({
            "version": 1,
            "items": [stale_item, current_item],
            "updated_at": pipeline.utc_now(),
        })

        with mock.patch.dict(os.environ, {
            "TARGET_SLUG": "current",
            "TARGET_CONTENT_SHA256": current_item["source"]["content_sha256"],
            "TARGET_ITEM_ID": current_item["id"],
            "KESHER_EXACT_UPLOAD_REQUIRED": "true",
        }, clear=False), mock.patch.object(
            reconcile, "validate_upload_candidate"
        ):
            self.assertEqual(reconcile.prepare_upload(), 0)

        saved = {item["id"]: item for item in pipeline.load_state()["items"]}
        self.assertEqual(saved[current_item["id"]]["status"], "approved")
        self.assertEqual(saved[current_item["id"]]["advisory_review_status_before_upload"], "rejected")
        self.assertEqual(saved[stale_item["id"]]["status"], "rejected")

    def test_prepare_upload_exact_identity_lock_selects_only_matching_triple(self) -> None:
        current = post("current", "2026-08-19")
        other = post("other", "2026-08-18")
        self.write_posts([current, other])
        other_item = pipeline.new_item(pipeline.source_metadata(other))
        technically_verified(other_item)
        current_item = pipeline.new_item(pipeline.source_metadata(current))
        technically_verified(current_item, status="rejected")
        pipeline.save_state({
            "version": 1,
            "items": [other_item, current_item],
            "updated_at": pipeline.utc_now(),
        })

        exact_env = {
            "TARGET_SLUG": "current",
            "TARGET_CONTENT_SHA256": current_item["source"]["content_sha256"],
            "TARGET_ITEM_ID": current_item["id"],
            "KESHER_EXACT_UPLOAD_REQUIRED": "true",
        }
        with mock.patch.dict(os.environ, exact_env, clear=False), mock.patch.object(
            reconcile, "validate_upload_candidate"
        ):
            self.assertEqual(reconcile.prepare_upload(), 0)

        saved = {item["id"]: item for item in pipeline.load_state()["items"]}
        self.assertIn("advisory_review_status_before_upload", saved[current_item["id"]])
        self.assertNotIn("advisory_review_status_before_upload", saved[other_item["id"]])

    def test_prepare_upload_exact_identity_lock_rejects_hash_mismatch_without_fallback(self) -> None:
        current = post("current", "2026-08-19")
        other = post("other", "2026-08-18")
        self.write_posts([current, other])
        other_item = pipeline.new_item(pipeline.source_metadata(other))
        technically_verified(other_item)
        current_item = pipeline.new_item(pipeline.source_metadata(current))
        technically_verified(current_item)
        pipeline.save_state({
            "version": 1,
            "items": [other_item, current_item],
            "updated_at": pipeline.utc_now(),
        })

        exact_env = {
            "TARGET_SLUG": "current",
            "TARGET_CONTENT_SHA256": "0" * 64,
            "TARGET_ITEM_ID": current_item["id"],
            "KESHER_EXACT_UPLOAD_REQUIRED": "true",
        }
        with mock.patch.dict(os.environ, exact_env, clear=False):
            with self.assertRaisesRegex(pipeline.PipelineError, "Exact identity lock"):
                reconcile.prepare_upload()

        saved = pipeline.load_state()["items"]
        self.assertTrue(all("advisory_review_status_before_upload" not in item for item in saved))

    def test_bind_short_overview_identity_from_exact_public_long_state(self) -> None:
        from tests.test_media_provenance_contract import bound_short

        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        short = {**bound_short(45.0), "id": "short-1", "source": {"slug": source["slug"], "content_sha256": source["content_sha256"]}}
        short.pop("overview_provider_identity", None)
        short["status"] = "pending_review"
        short["technical_verified"] = True
        pipeline.save_state({"version": 1, "items": [short], "updated_at": pipeline.utc_now()})

        long = {
            "id": "long-1", "type": "video_overview", "source": {"slug": source["slug"], "content_sha256": source["content_sha256"]},
            "notebook_id": "overview-notebook", "source_id": "overview-source", "task_id": "overview-task",
            "artifact_id": "overview-artifact", "raw_sha256": "9" * 64, "technical_verified": True,
            "uploaded": True, "status": "uploaded", "youtube_id": "lCGmwwMGJt8",
            "youtube_verification": {"channel_id": pipeline.YOUTUBE_CHANNEL_ID, "privacy_status": "public", "processing_status": "succeeded"},
        }
        long_path = self.root / "long-state.json"
        long_path.write_text(json.dumps({"version": 1, "items": [long]}), encoding="utf-8")

        self.assertEqual(reconcile.bind_short_overview_identity(str(long_path), "today", source["content_sha256"], "long-1", "short-1"), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["overview_provider_identity"]["task_id"], "overview-task")
        self.assertTrue(reconcile.delivery_guard._short_origin_verified(saved))

    def test_bind_short_overview_identity_fails_closed_on_nonexact_long(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        short = pipeline.new_item(source)
        short.update({"id": "short-1", "type": "article_short", "status": "pending_review"})
        pipeline.save_state({"version": 1, "items": [short], "updated_at": pipeline.utc_now()})
        long_path = self.root / "long-state.json"
        long_path.write_text(json.dumps({"version": 1, "items": []}), encoding="utf-8")
        with self.assertRaisesRegex(pipeline.PipelineError, "Exact authoritative Overview item"):
            reconcile.bind_short_overview_identity(str(long_path), "today", source["content_sha256"], "long-missing", "short-1")

    def test_short_workflow_binds_overview_identity_before_prepare_upload(self) -> None:
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/kesher-short-v4.yml").read_text(encoding="utf-8")
        self.assertIn("Bind exact Short to authoritative Overview identity", workflow)
        self.assertIn("--bind-short-overview-identity", workflow)
        self.assertIn("DERIVE_LONG_ITEM_ID", workflow)

    def test_prepare_upload_exact_identity_lock_rejects_partial_identity(self) -> None:
        current = post("current", "2026-08-19")
        self.write_posts([current])
        current_item = pipeline.new_item(pipeline.source_metadata(current))
        technically_verified(current_item)
        pipeline.save_state({"version": 1, "items": [current_item], "updated_at": pipeline.utc_now()})

        partial_env = {
            "TARGET_SLUG": "",
            "TARGET_CONTENT_SHA256": "",
            "TARGET_ITEM_ID": current_item["id"],
            "KESHER_EXACT_UPLOAD_REQUIRED": "true",
        }
        with mock.patch.dict(os.environ, partial_env, clear=False):
            with self.assertRaisesRegex(pipeline.PipelineError, "requires target_slug, content_sha256, and target_item_id"):
                reconcile.prepare_upload()

    def test_prepare_generation_skips_and_supersedes_stray_duplicates_when_already_public(self) -> None:
        from tests.test_media_provenance_contract import bound_short

        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        uploaded_short = {
            **bound_short(45.0),
            "id": "short-uploaded-1",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "qlVlUZMDKNo",
            "youtube_url": "https://youtu.be/qlVlUZMDKNo",
            "source": {"slug": source["slug"], "content_sha256": source["content_sha256"]},
        }
        uploaded_short.pop("overview_provider_identity", None)
        stray_dup = pipeline.new_item(source)
        stray_dup.update({
            "id": "short-stray-2",
            "type": "article_short",
            "source_mode": "direct-short",
            "status": "generating",
            "uploaded": False,
        })
        pipeline.save_state({"version": 1, "items": [uploaded_short, stray_dup], "updated_at": pipeline.utc_now()})

        output_file = self.root / "github_output"
        env_file = self.root / "github_env"
        with mock.patch.dict(
            os.environ,
            {"GITHUB_OUTPUT": str(output_file), "GITHUB_ENV": str(env_file), "KESHER_MEDIA_MODE": "article_short"},
            clear=False,
        ):
            self.assertEqual(reconcile.prepare_generation("today"), 0)

        self.assertIn("skip_generation=true", output_file.read_text(encoding="utf-8"))
        self.assertIn("TARGET_ITEM_ID=short-uploaded-1", env_file.read_text(encoding="utf-8"))
        saved = {row["id"]: row for row in pipeline.load_state()["items"]}
        self.assertEqual(saved["short-uploaded-1"]["status"], "uploaded")
        self.assertEqual(saved["short-stray-2"]["status"], "superseded")
        self.assertEqual(saved["short-stray-2"]["superseded_reason"], "already_public_same_source")

    def test_run_generation_refuses_duplicate_item_when_uploaded_item_exists(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        uploaded_item = pipeline.new_item(source)
        uploaded_item.update({
            "id": "uploaded-1",
            "type": "article_short",
            "source_mode": "direct-short",
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "qlVlUZMDKNo",
            "youtube_url": "https://youtu.be/qlVlUZMDKNo",
        })
        pipeline.save_state({"version": 1, "items": [uploaded_item], "updated_at": pipeline.utc_now()})

        with mock.patch.object(pipeline, "auth_preflight"), mock.patch.object(
            pipeline, "add_source"
        ) as add_source, mock.patch.object(
            pipeline, "start_generation"
        ) as start_gen:
            self.assertEqual(pipeline.run_generation(10, None, slug="today"), 0)

        add_source.assert_not_called()
        start_gen.assert_not_called()
        items = pipeline.load_state()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "uploaded-1")

    def test_recover_persisted_youtube_id_repairs_metadata_drift(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        item = pipeline.new_item(source)
        item.update({
            "id": "recover-1",
            "type": "video_overview",
            "status": "uploading",
            "uploaded": False,
            "youtube_id": "persisted-yt-id",
        })
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        pipeline.save_state(state)

        mock_repair = mock.Mock()
        mock_verification = {
            "channel_id": pipeline.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
        }
        with mock.patch.object(pipeline, "youtube_access_token", return_value="token"), \
             mock.patch.object(pipeline, "verify_authenticated_channel"), \
             mock.patch.object(pipeline, "verify_public_upload", side_effect=[
                 pipeline.PipelineError("PUBLIC_METADATA_INVALID: remote tags differ from source-derived tags"),
                 mock_verification,
             ]), \
             mock.patch.object(pipeline, "repair_persisted_youtube_metadata", mock_repair):
            recovered = reconcile.recover_persisted_youtube_id(state, item)

        self.assertTrue(recovered)
        self.assertTrue(item["uploaded"])
        self.assertEqual(item["status"], "uploaded")
        self.assertEqual(item["youtube_verification"], mock_verification)
        mock_repair.assert_called_once_with(item, "token")

    def test_export_target_propagates_target_slug_to_github_env_even_when_step_env_set(self) -> None:
        import tempfile
        item = {
            "id": "target-item-42",
            "source": {
                "slug": "relationship-quiescence-test",
                "content_sha256": "a" * 64,
            },
            "fresh_generation_attempt": 2,
        }
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as env_file:
            with mock.patch.dict(os.environ, {"GITHUB_ENV": env_file.name, "TARGET_SLUG": "relationship-quiescence-test"}):
                reconcile.export_target(item)
            env_file.seek(0)
            content = env_file.read()

        self.assertIn("TARGET_ITEM_ID=target-item-42\n", content)
        self.assertIn(f"TARGET_CONTENT_SHA256={'a' * 64}\n", content)
        self.assertIn("TARGET_GENERATION_ATTEMPT=2\n", content)
        self.assertIn("TARGET_SLUG=relationship-quiescence-test\n", content)


    def test_recovery_from_source_selected_continues_exact_item_generation(self) -> None:
        row = post("shared-laughter-couples-intimacy", day="2026-08-19")
        self.posts_file.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
        source = pipeline.source_metadata(row)
        item = pipeline.new_item(source)
        item.update({"type": "video_overview", "status": "source_selected"})
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        output = self.root / "github-output.txt"

        with mock.patch.dict(os.environ, {
            "KESHER_MEDIA_MODE": "video_overview",
            "TARGET_ITEM_ID": item["id"],
            "TARGET_CONTENT_SHA256": source["content_sha256"],
            "GITHUB_OUTPUT": str(output),
            "OPERATION": "recovery",
            "KESHER_RECOVERY_MODE": "true",
        }, clear=False):
            self.assertEqual(reconcile.prepare_generation(source["slug"]), 0)

        self.assertIn("skip_generation=false", output.read_text(encoding="utf-8"))
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["id"], item["id"])
        self.assertEqual(saved[0]["status"], "source_selected")


if __name__ == "__main__":
    unittest.main()

