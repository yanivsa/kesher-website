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
        pipeline.save_state({
            "version": 1,
            "items": [old],
            "updated_at": pipeline.utc_now(),
        })

        self.assertEqual(reconcile.prepare_generation(), 0)
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["status"], "generating")
        self.assertEqual(saved[0]["source"]["slug"], "yesterday")
        self.assertNotIn("superseded_reason", saved[0])

    def test_prior_day_technical_rejection_retries_same_source_not_today(self) -> None:
        today = post("today")
        older = post("older", "2026-08-18")
        self.write_posts([today, older])
        source = pipeline.source_metadata(older)
        rejected = pipeline.new_item(source)
        rejected["status"] = "rejected"
        rejected["technical_verified"] = False
        pipeline.save_state({
            "version": 1,
            "items": [rejected],
            "updated_at": pipeline.utc_now(),
        })

        self.assertEqual(reconcile.prepare_generation(), 0)
        saved = pipeline.load_state()
        self.assertEqual(len(saved["items"]), 2)
        old, replacement = saved["items"]
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(old["superseded_reason"], "technical_retry_same_source")
        self.assertEqual(replacement["status"], "source_selected")
        self.assertEqual(replacement["source"]["slug"], "older")
        self.assertEqual(
            replacement["source"]["content_sha256"],
            source["content_sha256"],
        )
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
        pipeline.save_state({
            "version": 1,
            "items": [rejected],
            "updated_at": pipeline.utc_now(),
        })
        with self.assertRaisesRegex(pipeline.PipelineError, "Technical retry limit"):
            reconcile.prepare_generation()

    def test_prior_day_review_item_is_uploadable_before_today(self) -> None:
        today = post("today")
        yesterday = post("yesterday", "2026-08-18")
        self.write_posts([today, yesterday])
        item = pipeline.new_item(pipeline.source_metadata(yesterday))
        item.update({
            "status": "pending_review",
            "technical_verified": True,
            "visual_review_status": "unavailable",
            "semantic_review_status": "unavailable",
            "metadata_review_status": "unavailable",
        })
        pipeline.save_state({
            "version": 1,
            "items": [item],
            "updated_at": pipeline.utc_now(),
        })

        reconcile.prepare_upload()
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["source"]["slug"], "yesterday")
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["advisory_review_decision"], "unavailable")

    def test_jules_rejection_is_advisory_and_remains_uploadable(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        item = pipeline.new_item(source)
        item.update({
            "status": "rejected",
            "technical_verified": True,
            "visual_review_status": "rejected",
            "semantic_review_status": "approved",
            "metadata_review_status": "approved",
        })
        pipeline.save_state({
            "version": 1,
            "items": [item],
            "updated_at": pipeline.utc_now(),
        })

        self.assertEqual(reconcile.prepare_upload(), 0)
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["visual_review_status"], "rejected")
        self.assertEqual(saved["advisory_review_decision"], "rejected")
        self.assertTrue(saved["review_is_advisory"])

    def test_unavailable_jules_review_is_also_uploadable(self) -> None:
        today = post("today")
        self.write_posts([today])
        source = pipeline.source_metadata(today)
        item = pipeline.new_item(source)
        item.update({
            "status": "pending_review",
            "technical_verified": True,
            "visual_review_status": "unavailable",
            "semantic_review_status": "unavailable",
            "metadata_review_status": "unavailable",
        })
        pipeline.save_state({
            "version": 1,
            "items": [item],
            "updated_at": pipeline.utc_now(),
        })

        reconcile.prepare_upload()
        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "approved")
        self.assertEqual(saved["advisory_review_decision"], "unavailable")

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
        pipeline.save_state({
            "version": 1,
            "items": [item],
            "updated_at": pipeline.utc_now(),
        })

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
