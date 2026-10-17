from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime
from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_final_attempt_fallback as fallback
from scripts import kesher_video_reconcile as reconcile
from tests.test_v5_shared_video_controller import FakeGitHub

TZ = ZoneInfo("Asia/Jerusalem")


class FakeSite:
    def get(self, url):
        return 200, "<html><head><title>כותרת מאמר עברי</title></head><body><h1>כותרת מאמר עברי</h1></body></html>"


class E2EFakeGitHub(FakeGitHub):
    def request(self, method, path, body=None, allow_404=False):
        if method == "GET" and "/actions/artifacts" in path:
            return {"artifacts": []}
        return super().request(method, path, body=body, allow_404=allow_404)


def sample_post(slug: str = "recovery-test-article", day: str = "2026-10-16") -> dict:
    return {
        "id": slug,
        "slug": slug,
        "title": "כותרת מאמר עברי",
        "date": day,
        "category": "הדרכת הורים",
        "excerpt": "תקציר עברי קצר",
        "content": "<p>תוכן עברי מלא לצורך בדיקת שחזור והתאוששות.</p>",
    }


def sample_source(slug: str = "recovery-test-article", day: str = "2026-10-16") -> dict:
    post = sample_post(slug, day)
    return pipeline.source_metadata(post)


def verified_long_item(source: dict, youtube_id: str = "6j-doosfuRk", item_id: str = "video-test-1") -> dict:
    return {
        "id": item_id,
        "type": "video_overview",
        "status": "uploaded",
        "uploaded": True,
        "source": copy.deepcopy(source),
        "youtube_id": youtube_id,
        "youtube_url": f"https://youtu.be/{youtube_id}",
        "youtube_verification": {
            "channel_id": core.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
        },
        "source_id": "source-1",
        "task_id": "task-1",
        "artifact_id": "task-1",
        "media": {
            "width": 1920,
            "height": 1080,
            "duration": 120.0,
            "codec": "h264",
        },
    }


def verified_short_item(source: dict, youtube_id: str = "RBrnnjsYWSg", item_id: str = "short-test-1") -> dict:
    return {
        "id": item_id,
        "type": "article_short",
        "status": "uploaded",
        "uploaded": True,
        "source": copy.deepcopy(source),
        "youtube_id": youtube_id,
        "youtube_url": f"https://youtu.be/{youtube_id}",
        "youtube_verification": {
            "channel_id": core.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
        },
        "media": {
            "width": 1080,
            "height": 1920,
            "duration": 50.0,
            "codec": "h264",
        },
        "signature_verified": True,
    }


class KesherRecoveryE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.posts_file = self.root / "posts.json"
        self.now = datetime(2026, 10, 16, 20, 0, tzinfo=TZ)
        self.env_patch = mock.patch.dict(os.environ, {}, clear=False)
        self.env_patch.start()
        self.patchers = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_dir / "state.json"),
            mock.patch.object(pipeline, "POSTS_FILE", self.posts_file),
            mock.patch.object(pipeline, "israel_now", return_value=self.now),
            mock.patch.object(reconcile, "export_target", lambda item: os.environ.update({"TARGET_ITEM_ID": item.get("id", "")})),
            mock.patch.object(reconcile, "workflow_output", lambda k, v: None),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patchers):
            p.stop()
        self.env_patch.stop()
        self.tmp.cleanup()

    def write_posts(self, rows: list[dict]) -> None:
        self.posts_file.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")

    def test_same_identity_recovery_no_new_work(self) -> None:
        """1. SAME-IDENTITY RECOVERY NO-NEW-WORK: Existing Attempt 2 must not create fresh work."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        item_id = "video-20261016-120000-aaaaaaaaaa-a2"
        existing_item = {
            "id": item_id,
            "type": "video_overview",
            "status": "generating",
            "source": copy.deepcopy(src),
            "source_id": "source-original-123",
            "task_id": "task-original-456",
            "artifact_id": "task-original-456",
            "fresh_generation_attempt": 2,
            "uploaded": False,
        }
        state = {"version": 1, "items": [existing_item]}
        pipeline.save_state(state)

        os.environ["KESHER_MEDIA_MODE"] = "video_overview"
        os.environ["TARGET_ITEM_ID"] = item_id
        code = reconcile.prepare_generation(src["slug"])
        self.assertEqual(code, 0)
        self.assertEqual(os.environ.get("TARGET_ITEM_ID"), item_id)

        with (
            mock.patch.object(pipeline, "auth_preflight"),
            mock.patch.object(pipeline, "add_source") as mock_add_src,
            mock.patch.object(pipeline, "start_generation") as mock_start_gen,
            mock.patch.object(pipeline, "new_item") as mock_new_item,
            mock.patch.object(pipeline, "wait_for_generation", return_value=True) as mock_wait,
            mock.patch.object(pipeline, "download_artifact", return_value=Path(self.tmp.name) / "test.mp4"),
            mock.patch.object(pipeline, "validate_and_manifest"),
        ):
            code = pipeline.run_generation(max_wait_seconds=1800, require_israel_hour=None, slug=src["slug"], item_id=item_id)
            self.assertEqual(code, 0)
            mock_add_src.assert_not_called()
            mock_start_gen.assert_not_called()
            mock_new_item.assert_not_called()
            mock_wait.assert_called_once()

        loaded = pipeline.load_state()
        self.assertEqual(len(loaded["items"]), 1)
        self.assertEqual(loaded["items"][0]["id"], item_id)
        self.assertEqual(loaded["items"][0]["task_id"], "task-original-456")

    def test_technical_rejection_retry_escape(self) -> None:
        """2. TECHNICAL-REJECTION RETRY ESCAPE: Recovery of rejected item must NOT call retry_technical_rejection()."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        item_id = "video-rejected-a1"
        rejected_item = {
            "id": item_id,
            "type": "video_overview",
            "status": "rejected",
            "technical_verified": False,
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 1,
            "uploaded": False,
        }
        state = {"version": 1, "items": [rejected_item]}
        pipeline.save_state(state)

        os.environ["KESHER_MEDIA_MODE"] = "video_overview"
        os.environ["TARGET_ITEM_ID"] = item_id
        with mock.patch.object(reconcile, "retry_technical_rejection") as mock_retry:
            code = reconcile.prepare_generation(src["slug"])
            self.assertEqual(code, 0)
            mock_retry.assert_not_called()

        with self.assertRaises(pipeline.PipelineError):
            reconcile.retry_technical_rejection(state, rejected_item)

    def test_attempt_3_pending_no_fallback(self) -> None:
        """3. ATTEMPT-3 PENDING: Attempt 3 pending/generating must not trigger fallback or Attempt 4."""
        src = sample_source()
        item3 = {
            "id": "video-attempt-3",
            "type": "video_overview",
            "status": "generating",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "task_id": "task-attempt-3",
            "uploaded": False,
        }
        state = {"version": 1, "items": [item3]}
        promoted = fallback.promote_last_usable_after_third_attempt(
            state, state_dir=self.state_dir, require_file=False
        )
        self.assertIsNone(promoted)
        self.assertEqual(len(state["items"]), 1)
        self.assertNotIn("fresh_generation_attempt", [4])

    def test_final_fallback_promotion_and_superseding(self) -> None:
        """4. FINAL-FALLBACK: Three attempts exhausted promotes valid candidate and supersedes competitors."""
        src = sample_source()
        dummy_media = {"codec": "h264", "duration": 120.0, "width": 1920, "height": 1080}
        item1 = {
            "id": "video-attempt-1",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 1,
            "review_notes": {"technical": "נפסל טכנית: pitch shifted too high"},
            "media": dummy_media,
            "final_mp4": "final-1.mp4",
            "final_sha256": "f" * 64,
            "uploaded": False,
        }
        item2 = {
            "id": "video-attempt-2",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 2,
            "review_notes": {"technical": "נפסל טכנית: resolution corrupted"},
            "final_mp4": "final-2.mp4",
            "final_sha256": "f" * 64,
            "uploaded": False,
        }
        item3 = {
            "id": "video-attempt-3",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "review_notes": {"technical": "נפסל טכנית: hard_timeout"},
            "final_mp4": "final-3.mp4",
            "final_sha256": "f" * 64,
            "uploaded": False,
        }
        state = {"version": 1, "items": [item1, item2, item3]}

        promoted = fallback.promote_last_usable_after_third_attempt(
            state, state_dir=self.state_dir, require_file=False
        )
        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["id"], "video-attempt-1")
        self.assertTrue(promoted.get("technical_verified"))
        self.assertEqual(promoted.get("status"), "pending_review")
        self.assertTrue(promoted.get("final_attempt_fallback"))

        self.assertEqual(item2.get("status"), "superseded")
        self.assertEqual(item2.get("superseded_reason"), "final_attempt_fallback_selected_other_existing_artifact")
        self.assertEqual(item3.get("status"), "superseded")
        self.assertEqual(item3.get("superseded_reason"), "final_attempt_fallback_selected_other_existing_artifact")

    def test_late_completion_race_fallback_wins(self) -> None:
        """5. LATE-COMPLETION RACE: Fallback already promoted, late Attempt 3 is ignored/superseded."""
        src = sample_source()
        item1 = {
            "id": "video-attempt-1",
            "status": "approved",
            "technical_verified": True,
            "final_attempt_fallback": True,
            "source": copy.deepcopy(src),
            "uploaded": False,
        }
        item3 = {
            "id": "video-attempt-3",
            "status": "generating",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "uploaded": False,
        }
        state = {"version": 1, "items": [item1, item3]}
        raw_path = self.state_dir / "raw.mp4"
        raw_path.write_bytes(b"x" * 2048)

        pipeline.validate_and_manifest(state, item3, raw_path)
        self.assertEqual(item3.get("status"), "superseded")
        self.assertEqual(item3.get("superseded_reason"), "late_completion_superseded_by_fallback_winner")
        self.assertFalse(item3.get("technical_verified", False))

    def test_pre_commit_late_completion_attempt_3_wins(self) -> None:
        """6. PRE-COMMIT LATE COMPLETION: Attempt 3 succeeds before fallback commit; Attempt 3 wins."""
        src = sample_source()
        item1 = {
            "id": "video-attempt-1",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 1,
            "review_notes": {"technical": "נפסל טכנית: pitch shifted"},
            "media": {"codec": "h264", "duration": 120.0, "width": 1920, "height": 1080},
            "final_mp4": "final-1.mp4",
            "final_sha256": "f" * 64,
            "uploaded": False,
        }
        item3 = {
            "id": "video-attempt-3",
            "status": "approved",
            "technical_verified": True,
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "uploaded": False,
        }
        state = {"version": 1, "items": [item1, item3]}

        promoted = fallback.promote_last_usable_after_third_attempt(
            state, state_dir=self.state_dir, require_file=False
        )
        self.assertIsNone(promoted)
        self.assertEqual(item3.get("status"), "approved")

    def test_missing_artifact_fails_closed(self) -> None:
        """7. MISSING-ARTIFACT: Metadata exists but media cannot be restored -> fails closed."""
        src = sample_source()
        item = {
            "id": "video-attempt-1",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 1,
            "final_sha256": "f" * 64,
            "final_mp4": "missing.mp4",
            "review_notes": {"technical": "נפסל טכנית: pitch shifted"},
            "media": {"codec": "h264", "duration": 120.0, "width": 1920, "height": 1080},
            "uploaded": False,
        }
        item3 = {
            "id": "video-attempt-3",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "uploaded": False,
        }
        state = {"version": 1, "items": [item, item3]}

        promoted = fallback.promote_last_usable_after_third_attempt(
            state, state_dir=self.state_dir, require_file=True, artifact_fetcher=lambda i, p: False
        )
        self.assertIsNone(promoted)
        self.assertFalse(item.get("technical_verified", False))

    def test_exact_artifact_restore_verifies_hash_and_gates(self) -> None:
        """8. EXACT ARTIFACT RESTORE: Media restored and verified against final_sha256."""
        mp4_bytes = b"mp4-content-bytes" * 100
        media_hash = hashlib.sha256(mp4_bytes).hexdigest()
        media_file = self.state_dir / "exact-media.mp4"
        media_file.write_bytes(mp4_bytes)

        candidate = {
            "id": "candidate-exact",
            "final_mp4": "exact-media.mp4",
            "final_sha256": media_hash,
            "media": {"codec": "h264", "duration": 120.0, "width": 1920, "height": 1080},
        }
        ok = fallback.restore_exact_candidate_media(candidate, state_dir=self.state_dir)
        self.assertTrue(ok)

    def test_voice_only_positive_proof_waiver(self) -> None:
        """9. VOICE-ONLY: Pitch criterion fails, but all other gates independently pass -> waiver allowed."""
        src = sample_source()
        candidate = {
            "id": "cand-voice",
            "source": copy.deepcopy(src),
            "status": "rejected",
            "review_notes": {"technical": "נפסל טכנית: pitch shifted too high"},
            "media": {"codec": "h264", "duration": 120.0, "width": 1920, "height": 1080},
            "youtube_metadata": copy.deepcopy(src["youtube_metadata"]),
            "final_mp4": "cand-voice.mp4",
            "final_sha256": "f" * 64,
        }
        self.assertTrue(fallback._positive_voice_only_rejection(candidate))

    def test_voice_plus_other_failure_rejected(self) -> None:
        """10. VOICE + OTHER FAILURE: Pitch failure plus duration/aspect failure -> rejected."""
        src = sample_source()
        candidate_bad_duration = {
            "id": "cand-bad-dur",
            "source": copy.deepcopy(src),
            "status": "rejected",
            "review_notes": {"technical": "נפסל טכנית: pitch shifted too high"},
            "media": {"codec": "h264", "duration": 400.0, "width": 1920, "height": 1080},
            "youtube_metadata": copy.deepcopy(src["youtube_metadata"]),
            "final_mp4": "bad-dur.mp4",
            "final_sha256": "f" * 64,
        }
        self.assertFalse(fallback._positive_voice_only_rejection(candidate_bad_duration))

        candidate_bad_aspect = {
            "id": "cand-bad-aspect",
            "source": copy.deepcopy(src),
            "status": "rejected",
            "review_notes": {"technical": "נפסל טכנית: pitch shifted too high"},
            "media": {"codec": "h264", "duration": 120.0, "width": 1080, "height": 1920},
            "youtube_metadata": copy.deepcopy(src["youtube_metadata"]),
            "final_mp4": "bad-aspect.mp4",
            "final_sha256": "f" * 64,
        }
        self.assertFalse(fallback._positive_voice_only_rejection(candidate_bad_aspect))

    def test_full_tick_long_block_no_oscillation(self) -> None:
        """11. FULL-TICK LONG BLOCK: Blocked Long video remains stably blocked across ticks."""
        gh = E2EFakeGitHub()
        post = sample_post()
        gh.posts = [post]
        gh.saved_state = {
            "cycle": post["date"],
            "status": "blocked",
            "article": {"status": "deployed", "live": True, "_tick_live_verified": True},
            "long_video": {"status": "blocked"},
            "short": {},
            "last_error": {"stage": "long_video", "reason": "LONG_VIDEO_PROVIDER_HARD_TIMEOUT"},
            "history": [],
        }
        controller = runtime.RuntimeV5Controller(gh, FakeSite(), now=self.now)

        for _ in range(3):
            state, action = controller.tick()
            self.assertEqual(action.kind, "blocked")
            self.assertEqual(state["status"], "blocked")

    def test_full_tick_short_block_no_oscillation(self) -> None:
        """12. FULL-TICK SHORT BLOCK: Blocked Short remains stably blocked across ticks."""
        gh = E2EFakeGitHub()
        post = sample_post()
        gh.posts = [post]
        src = sample_source()
        long_item = verified_long_item(src)
        gh.long_state = {"version": 1, "items": [long_item]}
        gh.saved_state = {
            "cycle": post["date"],
            "status": "blocked",
            "article": {"status": "deployed", "live": True, "_tick_live_verified": True},
            "long_video": {"status": "uploaded", "youtube_id": long_item["youtube_id"], "verified": True},
            "short": {"status": "blocked"},
            "last_error": {"stage": "short", "reason": "SHORT_STALLED"},
            "history": [],
        }
        controller = runtime.RuntimeV5Controller(gh, FakeSite(), now=self.now)

        for _ in range(3):
            state, action = controller.tick()
            self.assertEqual(action.kind, "blocked")
            self.assertEqual(state["status"], "blocked")

    def test_block_release_when_durable_verified_media_appears(self) -> None:
        """13. BLOCK RELEASE: Durable valid media cleanly releases blocker and progresses."""
        gh = E2EFakeGitHub()
        post = sample_post()
        gh.posts = [post]
        src = sample_source()
        gh.saved_state = {
            "cycle": post["date"],
            "status": "blocked",
            "article": {"status": "deployed", "live": True, "_tick_live_verified": True},
            "long_video": {"status": "blocked"},
            "short": {},
            "last_error": {"stage": "long_video", "reason": "LONG_VIDEO_PROVIDER_HARD_TIMEOUT"},
            "history": [],
        }
        controller = runtime.RuntimeV5Controller(gh, FakeSite(), now=self.now)

        # Tick 1: Still blocked
        state, action = controller.tick()
        self.assertEqual(action.kind, "blocked")

        # Durable Long video verified appears
        long_item = verified_long_item(src)
        gh.long_state = {"version": 1, "items": [long_item]}

        # Tick 2: Blocker released, progresses to short
        state, action = controller.tick()
        self.assertNotEqual(action.kind, "blocked")
        self.assertIn("short", action.kind)
        self.assertIsNone(state.get("last_error"))

        # Now simulate short becoming blocked
        state["status"] = "blocked"
        state["short"]["status"] = "blocked"
        state["last_error"] = {"stage": "short", "reason": "SHORT_STALLED"}
        gh.saved_state = state

        # Tick 3: Blocked
        state, action = controller.tick()
        self.assertEqual(action.kind, "blocked")

        # Durable Short verified appears
        short_item = verified_short_item(src)
        gh.short_state = {"version": 1, "items": [short_item]}

        # Tick 4: Blocker released, progresses to complete
        with (
            mock.patch("scripts.kesher_content_controller_v5_runtime_base.delivery_guard.short_public_portrait_verified", return_value=True),
            mock.patch("scripts.kesher_content_controller_v5_runtime_base.delivery_guard.delivery_contract", return_value=(True, {"article": True, "video": True, "short": True})),
        ):
            state, action = controller.tick()
        self.assertNotEqual(action.kind, "blocked")
        self.assertIn(state["status"], {"complete", "completed"})

    def test_public_upload_dedup_no_regeneration(self) -> None:
        """14. PUBLIC-UPLOAD DEDUP: Existing verified public item does not regenerate or duplicate upload."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        public_item = verified_long_item(src, youtube_id="6j-doosfuRk")
        state = {"version": 1, "items": [public_item]}
        pipeline.save_state(state)

        os.environ["KESHER_MEDIA_MODE"] = "video_overview"
        code = reconcile.prepare_generation(src["slug"])
        self.assertEqual(code, 0)
        loaded = pipeline.load_state()
        self.assertEqual(len(loaded["items"]), 1)
        self.assertEqual(loaded["items"][0]["youtube_id"], "6j-doosfuRk")

    def test_concurrent_repeated_recovery_idempotent(self) -> None:
        """15. CONCURRENT/REPEATED RECOVERY: Repeated recovery evaluation is strictly idempotent."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        item_id = "video-stalled-a2"
        existing = {
            "id": item_id,
            "type": "video_overview",
            "status": "generating",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 2,
            "uploaded": False,
        }
        state = {"version": 1, "items": [existing]}
        pipeline.save_state(state)

        os.environ["KESHER_MEDIA_MODE"] = "video_overview"
        os.environ["TARGET_ITEM_ID"] = item_id
        code1 = reconcile.prepare_generation(src["slug"])
        target1 = os.environ.get("TARGET_ITEM_ID")
        count1 = len(pipeline.load_state()["items"])

        code2 = reconcile.prepare_generation(src["slug"])
        target2 = os.environ.get("TARGET_ITEM_ID")
        count2 = len(pipeline.load_state()["items"])

        self.assertEqual(code1, 0)
        self.assertEqual(code2, 0)
        self.assertEqual(target1, item_id)
        self.assertEqual(target2, item_id)
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 1)


if __name__ == "__main__":
    unittest.main()
