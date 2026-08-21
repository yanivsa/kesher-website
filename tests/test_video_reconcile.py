from __future__ import annotations

import json
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

        self.assertEqual(reconcile.prepare_upload(), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "generating")
        self.assertEqual(saved["task_id"], "task-1")
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
            reconcile.prepare_upload()

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

    def test_technical_retry_is_bounded(self) -> None:
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
        with self.assertRaisesRegex(pipeline.PipelineError, "Technical retry limit"):
            reconcile.prepare_generation()

    def test_technically_verified_prior_day_item_is_uploadable_before_today(self) -> None:
        today = post("today")
        yesterday = post("yesterday", "2026-08-18")
        self.write_posts([today, yesterday])
        item = pipeline.new_item(pipeline.source_metadata(yesterday))
        technically_verified(item)
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_upload(), 0)
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
        self.assertEqual(reconcile.prepare_upload(), 0)
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

        self.assertEqual(reconcile.prepare_upload(), 0)
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

        self.assertEqual(reconcile.prepare_upload(), 0)
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
        self.assertEqual(reconcile.prepare_upload(), 0)
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
            self.assertEqual(reconcile.prepare_upload(), 0)

        saved = pipeline.load_state()["items"][0]
        self.assertTrue(saved["uploaded"])
        self.assertEqual(saved["status"], "uploaded")
        self.assertEqual(saved["youtube_url"], "https://www.youtube.com/watch?v=already-inserted")
        self.assertEqual(saved["youtube_verification"], verification)
        channel.assert_called_once_with("token")
        verify.assert_called_once()
        insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
