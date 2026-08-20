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


def technically_verified(item: dict, status: str = "pending_review") -> None:
    item.update({
        "status": status,
        "technical_verified": True,
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
        self.assertEqual(saved[0]["source"]["slug"], "yesterday")

    def test_multiple_backlog_items_are_processed_oldest_first(self) -> None:
        oldest_post = post("oldest", "2026-08-17")
        newer_post = post("newer", "2026-08-18")
        self.write_posts([newer_post, oldest_post])
        newer = pipeline.new_item(pipeline.source_metadata(newer_post))
        newer.update({"status": "generating", "task_id": "newer-task", "artifact_id": "newer-task"})
        oldest = pipeline.new_item(pipeline.source_metadata(oldest_post))
        oldest.update({"status": "generating", "task_id": "old-task", "artifact_id": "old-task"})
        pipeline.save_state({"version": 1, "items": [newer, oldest], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.unresolved_items(pipeline.load_state())[0]["source"]["slug"], "oldest")

    def test_technical_rejection_retries_same_source(self) -> None:
        today = post("today")
        self.write_posts([today])
        rejected = pipeline.new_item(pipeline.source_metadata(today))
        rejected.update({"status": "rejected", "technical_verified": False})
        pipeline.save_state({"version": 1, "items": [rejected], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.prepare_generation(), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(saved[0]["status"], "superseded")
        self.assertEqual(saved[1]["source"]["slug"], "today")

    def test_jules_rejection_is_advisory_for_technical_video(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(item, "rejected")
        item.update({
            "visual_review_status": "rejected",
            "semantic_review_status": "approved",
            "metadata_review_status": "approved",
            "reviewer": {"type": "jules", "session": "sessions/review-2"},
        })
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.prepare_upload(), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["review_gate"], "advisory-jules")
        self.assertEqual(saved["advisory_review_status_before_upload"], "rejected")

    def test_missing_jules_review_is_advisory_for_technical_video(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(item, "pending_review")
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        self.assertEqual(reconcile.prepare_upload(), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["advisory_review_status_before_upload"], "pending_review")

    def test_non_technical_video_still_fails_closed(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
        item.update({"status": "pending_review", "technical_verified": False})
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        with self.assertRaisesRegex(pipeline.PipelineError, "not technically verified"):
            reconcile.prepare_upload()

    def test_persisted_youtube_id_is_verified_without_second_insert(self) -> None:
        today = post("today")
        self.write_posts([today])
        item = pipeline.new_item(pipeline.source_metadata(today))
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
        channel.assert_called_once_with("token")
        verify.assert_called_once()
        insert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
