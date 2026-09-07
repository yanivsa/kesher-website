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

    def test_prepare_upload_targets_slug_when_specified(self) -> None:
        today = post("today")
        yesterday = post("yesterday", "2026-08-18")
        self.write_posts([today, yesterday])
        today_item = pipeline.new_item(pipeline.source_metadata(today))
        technically_verified(today_item)
        yesterday_item = pipeline.new_item(pipeline.source_metadata(yesterday))
        yesterday_item["status"] = "generating"
        pipeline.save_state({"version": 1, "items": [yesterday_item, today_item], "updated_at": pipeline.utc_now()})

        self.assertEqual(reconcile.prepare_upload("today"), 0)
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


if __name__ == "__main__":
    unittest.main()


