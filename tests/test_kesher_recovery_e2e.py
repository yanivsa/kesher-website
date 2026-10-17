from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime
from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_e2e_delivery_guard as delivery_guard
from scripts import kesher_final_attempt_fallback as fallback
from scripts import kesher_video_reconcile as reconcile
from tests.test_v5_shared_video_controller import FakeGitHub

TZ = ZoneInfo("Asia/Jerusalem")


class FakeSite:
    def get(self, url: str) -> tuple[int, str]:
        return 200, "<html><head><title>כותרת מאמר עברי</title></head><body><h1>כותרת מאמר עברי</h1></body></html>"


class E2EFakeGitHub(FakeGitHub):
    def __init__(self) -> None:
        super().__init__()
        self._video_state: dict | None = None

    def request(self, method: str, path: str, body: dict | None = None, allow_404: bool = False) -> dict | list | None:
        if method == "GET" and "/actions/artifacts" in path:
            return {"artifacts": []}
        return super().request(method, path, body=body, allow_404=allow_404)

    def newest_video_state(self) -> dict:
        if self._video_state is not None:
            return copy.deepcopy(self._video_state)
        return copy.deepcopy(self.long_state)

    def save_video_state(self, state: dict) -> None:
        self._video_state = copy.deepcopy(state)


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


def make_valid_long_item(source: dict, youtube_id: str = "6j-doosfuRk", item_id: str = "video-test-1") -> dict:
    raw_sha = "b" * 64
    final_sha = "c" * 64
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
        "notebook_id": "nb-long-1",
        "source_id": "src-long-1",
        "task_id": "task-long-1",
        "artifact_id": "art-long-1",
        "raw_sha256": raw_sha,
        "final_sha256": final_sha,
        "technical_verified": True,
        "visual_pipeline": "remotion-v1-notebooklm-audio",
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "duration": 120.0,
        "verified": True,
        "media": {
            "width": 1280,
            "height": 720,
            "duration": 120.0,
            "codec": "h264",
            "audio_codec": "aac",
        },
    }


def make_valid_short_item(source: dict, long_item: dict, youtube_id: str = "RBrnnjsYWSg", item_id: str = "short-test-1") -> dict:
    short_raw = "1" * 64
    short_final = "2" * 64
    asset_sha = "3" * 64
    video_sha = "4" * 64
    audio_sha = "5" * 64
    return {
        "id": item_id,
        "type": "article_short",
        "status": "uploaded",
        "uploaded": True,
        "source": copy.deepcopy(source),
        "source_mode": "direct-short",
        "visual_pipeline": "remotion-v4-notebooklm-short-motion-plan-v1",
        "notebook_id": "nb-short-1",
        "source_id": "src-short-1",
        "task_id": "task-short-1",
        "artifact_id": "art-short-1",
        "raw_sha256": short_raw,
        "final_sha256": short_final,
        "provider_video_format": "short",
        "provider_native_short": True,
        "provider_native_short_verified": True,
        "provider_short_fallback_used": False,
        "fresh_generation_attempt": 1,
        "provider_raw_media": {"width": 1080, "height": 1920, "duration": 50.0, "audio_codec": "aac"},
        "media": {"width": 1080, "height": 1920, "duration": 50.0, "codec": "h264", "audio_codec": "aac"},
        "youtube_id": youtube_id,
        "youtube_url": f"https://youtu.be/{youtube_id}",
        "youtube_verification": {
            "channel_id": core.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
        },
        "signature_overlay": True,
        "signature_verified": True,
        "signature_duration_seconds": 3.0,
        "short_duration_seconds": 50.0,
        "short_start_seconds": 0.0,
        "signature_asset_sha256": asset_sha,
        "signature_sha256": asset_sha,
        "signature_video_sha256": video_sha,
        "signature_provenance": {
            "schema_version": 1,
            "final_sha256": short_final,
            "raw_sha256": short_raw,
            "asset_sha256": asset_sha,
            "segment_sha256": video_sha,
            "audio_source_sha256": short_raw,
            "source_duration_seconds": 50.0,
            "final_duration_seconds": 50.0,
            "start_seconds": 47.0,
            "end_seconds": 50.0,
        },
        "audio_provenance": {
            "schema_version": 1,
            "mode": "stream_copy",
            "raw_sha256": short_raw,
            "final_sha256": short_final,
            "raw_audio_sha256": audio_sha,
            "final_audio_sha256": audio_sha,
            "raw_timing": {"codec": "aac", "sample_rate": 44100, "channels": 2, "start_seconds": 0.0, "duration_seconds": 50.0},
            "final_timing": {"codec": "aac", "sample_rate": 44100, "channels": 2, "start_seconds": 0.0, "duration_seconds": 50.0},
        },
        "overview_provider_identity": {
            "notebook_id": long_item.get("notebook_id"),
            "source_id": long_item.get("source_id"),
            "task_id": long_item.get("task_id"),
            "artifact_id": long_item.get("artifact_id"),
            "raw_sha256": long_item.get("raw_sha256"),
        },
        "portrait_verified": True,
        "verified": True,
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

    # -------------------------------------------------------------------------
    # 1. P0: CONTROLLER TO WORKFLOW RECOVERY MODE PROPAGATION
    # -------------------------------------------------------------------------
    def test_controller_to_workflow_recovery_mode_propagates(self) -> None:
        """P0: Controller recovery dispatch sets operation=recovery which translates to recovery mode in Python."""
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
        state = {
            "schema_version": v5.STATE_SCHEMA_VERSION,
            "cycle": post["date"],
            "status": "blocked",
            "article": {"status": "deployed", "live": True, "_tick_live_verified": True},
            "long_video": {
                "status": "running",
                "item_id": item_id,
                "resume_dispatches": 0,
                "watchdog": {},
            },
            "short": {},
            "last_error": {"stage": "long_video", "reason": "LONG_VIDEO_PROVIDER_HARD_TIMEOUT"},
            "history": [],
        }

        gh = E2EFakeGitHub()
        controller = runtime.RuntimeV5Controller(gh, FakeSite(), now=self.now)

        # 1. Controller executes recovery dispatch:
        action = controller._recover_long_video(state, src, existing_item)
        self.assertEqual(action.kind, "long_video_watchdog_recover")
        self.assertTrue(len(gh.dispatches) > 0)
        dispatched = gh.dispatches[-1]
        workflow = dispatched[0] if isinstance(dispatched, tuple) else dispatched["workflow"]
        inputs = dispatched[1] if isinstance(dispatched, tuple) else dispatched["inputs"]
        self.assertEqual(workflow, v5.LONG_VIDEO_WORKFLOW)
        self.assertEqual(inputs["operation"], "recovery")
        self.assertEqual(inputs["target_slug"], src["slug"])
        self.assertEqual(inputs["target_item_id"], item_id)

        # 2. Workflow input mapping into Python step env:
        wf_env = {
            "OPERATION": inputs["operation"],
            "KESHER_RECOVERY_MODE": "true" if inputs["operation"] == "recovery" else "false",
            "TARGET_SLUG": inputs["target_slug"],
            "TARGET_CONTENT_SHA256": inputs["target_content_sha256"],
            "TARGET_ITEM_ID": inputs["target_item_id"],
            "KESHER_MEDIA_MODE": "video_overview",
        }

        # 3. Downstream Python executes with workflow-provided environment:
        with mock.patch.dict(os.environ, wf_env, clear=False):
            self.assertTrue(reconcile.is_recovery_mode())
            self.assertTrue(pipeline.is_recovery_mode())

    # -------------------------------------------------------------------------
    # 2. P0: RECOVERY MODE CREATES ZERO PROVIDER WORK
    # -------------------------------------------------------------------------
    def test_recovery_mode_real_workflow_creates_zero_provider_work(self) -> None:
        """P0: Recovery mode makes new_item, add_source, and start_generation structurally impossible."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        item_id = "video-stalled-a2"
        existing_item = {
            "id": item_id,
            "type": "video_overview",
            "status": "generating",
            "source": copy.deepcopy(src),
            "source_id": "source-orig",
            "task_id": "task-orig",
            "artifact_id": "art-orig",
            "fresh_generation_attempt": 2,
            "uploaded": False,
        }
        state = {"version": 1, "items": [existing_item]}
        pipeline.save_state(state)

        env = {
            "OPERATION": "recovery",
            "KESHER_RECOVERY_MODE": "true",
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": item_id,
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            code = reconcile.prepare_generation(src["slug"])
            self.assertEqual(code, 0)
            self.assertEqual(os.environ.get("TARGET_ITEM_ID"), item_id)

            with (
                mock.patch.object(pipeline, "auth_preflight"),
                mock.patch.object(pipeline, "add_source") as mock_add_src,
                mock.patch.object(pipeline, "start_generation") as mock_start_gen,
                mock.patch.object(pipeline, "new_item") as mock_new_item,
                mock.patch.object(reconcile, "retry_technical_rejection") as mock_retry,
                mock.patch.object(pipeline, "wait_for_generation", return_value=True) as mock_wait,
                mock.patch.object(pipeline, "download_artifact", return_value=Path(self.tmp.name) / "test.mp4"),
                mock.patch.object(pipeline, "validate_and_manifest"),
            ):
                code = pipeline.run_generation(max_wait_seconds=1800, require_israel_hour=None, slug=src["slug"], item_id=item_id)
                self.assertEqual(code, 0)
                mock_add_src.assert_not_called()
                mock_start_gen.assert_not_called()
                mock_new_item.assert_not_called()
                mock_retry.assert_not_called()
                mock_wait.assert_called_once()

    # -------------------------------------------------------------------------
    # 3. P0: NORMAL VOICE RETRY STILL CREATES NEXT ATTEMPT
    # -------------------------------------------------------------------------
    def test_normal_voice_retry_still_creates_next_attempt(self) -> None:
        """P0: Normal voice retry outside recovery mode still creates Attempt 2."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        item_id = "video-attempt-1"
        rejected_item = {
            "id": item_id,
            "type": "video_overview",
            "status": "rejected",
            "technical_verified": False,
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 1,
            "failure_signature": "wrong_narrator_gender",
            "review_notes": {"technical": "נפסל טכנית: Detected male voice"},
            "uploaded": False,
        }
        state = {"version": 1, "items": [rejected_item]}
        pipeline.save_state(state)

        env = {
            "OPERATION": "full",
            "KESHER_RECOVERY_MODE": "false",
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": item_id,
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            code = reconcile.prepare_generation(src["slug"])
            self.assertEqual(code, 0)
            loaded = pipeline.load_state()
            self.assertEqual(len(loaded["items"]), 2)
            replacement = loaded["items"][-1]
            self.assertEqual(replacement.get("fresh_generation_attempt"), 2)
            self.assertEqual(replacement.get("status"), "source_selected")

    # -------------------------------------------------------------------------
    # 4. P1: STALE SNAPSHOT CANNOT OVERRIDE FALLBACK WINNER
    # -------------------------------------------------------------------------
    def test_stale_snapshot_cannot_override_fallback_winner(self) -> None:
        """P1: Snapshot A with late Attempt 3 fails closed when Snapshot B already committed fallback."""
        src = sample_source()
        dummy_media = {"codec": "h264", "duration": 120.0, "width": 1280, "height": 720}

        item2 = {
            "id": "video-attempt-2",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 2,
            "media": dummy_media,
            "final_mp4": "final-2.mp4",
            "final_sha256": "f" * 64,
            "review_notes": {"technical": "נפסל טכנית: pitch shifted"},
            "technical_verified": True,
            "uploaded": False,
        }
        item3 = {
            "id": "video-attempt-3",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "media": dummy_media,
            "final_mp4": "final-3.mp4",
            "final_sha256": "f" * 64,
            "uploaded": False,
        }

        # Snapshot B promotes Attempt 2 and commits to disk
        snapshot_b = {"version": 1, "items": [copy.deepcopy(item2), copy.deepcopy(item3)]}
        pipeline.save_state(snapshot_b)
        promoted = fallback.promote_last_usable_after_third_attempt(
            snapshot_b, state_dir=self.state_dir, require_file=False
        )
        self.assertIsNotNone(promoted)
        self.assertEqual(promoted["id"], "video-attempt-2")

        # Snapshot A (in-memory stale copy) now tries to finalize late Attempt 3
        snapshot_a = {"version": 1, "items": [copy.deepcopy(item2), copy.deepcopy(item3)]}
        raw_path = self.state_dir / "raw.mp4"
        raw_path.write_bytes(b"x" * 2048)

        with self.assertRaises(pipeline.PipelineError):
            pipeline.validate_and_manifest(snapshot_a, snapshot_a["items"][1], raw_path)

        self.assertEqual(snapshot_a["items"][1].get("status"), "superseded")
        self.assertFalse(snapshot_a["items"][1].get("technical_verified", False))

    # -------------------------------------------------------------------------
    # 5. P1: FALLBACK CAS LOSES TO PRIOR ATTEMPT 3 COMPLETION
    # -------------------------------------------------------------------------
    def test_fallback_cas_loses_to_prior_attempt3_completion(self) -> None:
        """P1: Fallback CAS fails if authoritative state already records Attempt 3 completion."""
        src = sample_source()
        dummy_media = {"codec": "h264", "duration": 120.0, "width": 1280, "height": 720}

        item2 = {
            "id": "video-attempt-2",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 2,
            "media": dummy_media,
            "final_mp4": "final-2.mp4",
            "final_sha256": "f" * 64,
            "technical_verified": True,
            "uploaded": False,
        }
        item3 = {
            "id": "video-attempt-3",
            "type": "video_overview",
            "status": "approved",
            "technical_verified": True,
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "media": dummy_media,
            "uploaded": False,
        }

        # Authoritative state records Attempt 3 completion
        auth_state = {"version": 1, "items": [copy.deepcopy(item2), copy.deepcopy(item3)]}
        pipeline.save_state(auth_state)

        # Stale snapshot attempts fallback promotion of Attempt 2
        stale_item3 = copy.deepcopy(item3)
        stale_item3["status"] = "rejected"
        stale_item3["technical_verified"] = False
        stale_snapshot = {"version": 1, "items": [copy.deepcopy(item2), stale_item3]}

        promoted = fallback.promote_last_usable_after_third_attempt(
            stale_snapshot, state_dir=self.state_dir, require_file=False
        )
        self.assertIsNone(promoted)

    # -------------------------------------------------------------------------
    # 6. P1: TWO SNAPSHOTS ONLY ONE UPLOAD ELIGIBLE
    # -------------------------------------------------------------------------
    def test_two_snapshots_only_one_upload_eligible(self) -> None:
        """P1: Two upload workers with stale/current snapshots result in exactly one upload-eligible item."""
        src = sample_source()
        dummy_media = {"codec": "h264", "duration": 120.0, "width": 1280, "height": 720}

        item2 = {
            "id": "video-attempt-2",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 2,
            "media": dummy_media,
            "final_mp4": "final-2.mp4",
            "final_sha256": "f" * 64,
            "technical_verified": True,
            "uploaded": False,
        }
        item3 = {
            "id": "video-attempt-3",
            "type": "video_overview",
            "status": "rejected",
            "source": copy.deepcopy(src),
            "fresh_generation_attempt": 3,
            "media": dummy_media,
            "final_mp4": "final-3.mp4",
            "final_sha256": "f" * 64,
            "uploaded": False,
        }

        state = {"version": 1, "items": [copy.deepcopy(item2), copy.deepcopy(item3)]}
        pipeline.save_state(state)

        # Promote Attempt 2 as winner
        promoted = fallback.promote_last_usable_after_third_attempt(
            state, state_dir=self.state_dir, require_file=False
        )
        self.assertIsNotNone(promoted)

        # Stale snapshot trying to prepare upload for Attempt 3 fails closed
        stale_state = {"version": 1, "items": [copy.deepcopy(item2), copy.deepcopy(item3)]}
        with mock.patch.dict(os.environ, {"KESHER_MEDIA_MODE": "video_overview"}):
            with self.assertRaises(pipeline.PipelineError):
                pipeline.upload_only(src["slug"], "video-attempt-3", state=stale_state)

        disk_state = pipeline.load_state()
        eligible = [row for row in disk_state["items"] if row.get("upload_eligible") is True]
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["id"], "video-attempt-2")

    # -------------------------------------------------------------------------
    # 7. P1: BLOCKED SHORT REAL CONTRACT RELEASE (NO MOCKS)
    # -------------------------------------------------------------------------
    def test_blocked_short_real_contract_release(self) -> None:
        """P1: Blocked Short releases and stays complete using real delivery_contract without mocks."""
        gh = E2EFakeGitHub()
        post = sample_post()
        gh.posts = [post]
        src = sample_source()
        long_item = make_valid_long_item(src)
        short_item = make_valid_short_item(src, long_item)

        gh.long_state = {"version": 1, "items": [long_item]}
        gh.short_state = {"version": 1, "items": []}

        article_url = f"{core.SITE_URL}/blog/{post['slug']}"
        saved_state = {
            "schema_version": v5.STATE_SCHEMA_VERSION,
            "cycle": post["date"],
            "status": "blocked",
            "article": {"status": "deployed", "live": True, "url": article_url, "_tick_live_verified": True},
            "long_video": copy.deepcopy(long_item),
            "short": {"status": "blocked"},
            "last_error": {"stage": "short", "reason": "SHORT_STALLED", "message": "short stalled"},
            "history": [],
        }
        gh.saved_state = saved_state
        controller = runtime.RuntimeV5Controller(gh, FakeSite(), now=self.now)

        # Tick 1: Still blocked
        state, action = controller.tick()
        self.assertEqual(action.kind, "blocked")

        # Now durable Short appears
        gh.short_state = {"version": 1, "items": [copy.deepcopy(short_item)]}

        # Tick 2: Released to complete using real delivery_guard contracts
        state, action = controller.tick()
        self.assertEqual(action.kind, "complete")
        self.assertEqual(state["status"], "complete")
        self.assertIsNone(state.get("last_error"))

        # Tick 3: Remains stably complete
        state, action = controller.tick()
        self.assertEqual(action.kind, "complete")
        self.assertEqual(state["status"], "complete")

    # -------------------------------------------------------------------------
    # 8. P1: BLOCKED SHORT MISSING EVIDENCE REMAINS BLOCKED
    # -------------------------------------------------------------------------
    def test_blocked_short_missing_evidence_remains_blocked(self) -> None:
        """P1: Short missing required structured evidence fails delivery contract and remains blocked."""
        gh = E2EFakeGitHub()
        post = sample_post()
        gh.posts = [post]
        src = sample_source()
        long_item = make_valid_long_item(src)
        short_item = make_valid_short_item(src, long_item)

        # Invalidate portrait dimensions (landscape 1920x1080 instead of 1080x1920)
        short_item["media"]["width"] = 1920
        short_item["media"]["height"] = 1080

        gh.long_state = {"version": 1, "items": [long_item]}
        gh.short_state = {"version": 1, "items": [short_item]}

        article_url = f"{core.SITE_URL}/blog/{post['slug']}"
        saved_state = {
            "schema_version": v5.STATE_SCHEMA_VERSION,
            "cycle": post["date"],
            "status": "blocked",
            "article": {"status": "deployed", "live": True, "url": article_url, "_tick_live_verified": True},
            "long_video": copy.deepcopy(long_item),
            "short": {"status": "blocked"},
            "last_error": {"stage": "short", "reason": "SHORT_STALLED", "message": "short stalled"},
            "history": [],
        }
        gh.saved_state = saved_state
        controller = runtime.RuntimeV5Controller(gh, FakeSite(), now=self.now)

        state, action = controller.tick()
        self.assertEqual(action.kind, "blocked")
        self.assertIsNotNone(state.get("last_error"))
        self.assertNotEqual(state.get("status"), "complete")

    # -------------------------------------------------------------------------
    # 9. P1: DOWNLOADED RECOVERY RUNS LOCAL PROCESSING ONLY
    # -------------------------------------------------------------------------
    def test_downloaded_recovery_runs_local_processing_only(self) -> None:
        """P1: status=downloaded item in recovery does not skip generation and runs local render with 0 provider work."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        item_id = "video-downloaded-a1"
        raw_file = self.state_dir / "raw-downloaded.mp4"
        raw_file.write_bytes(b"x" * 2048)

        downloaded_item = {
            "id": item_id,
            "type": "video_overview",
            "status": "downloaded",
            "source": copy.deepcopy(src),
            "raw_mp4": "raw-downloaded.mp4",
            "fresh_generation_attempt": 1,
            "uploaded": False,
        }
        state = {"version": 1, "items": [downloaded_item]}
        pipeline.save_state(state)

        env = {
            "OPERATION": "recovery",
            "KESHER_RECOVERY_MODE": "true",
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": item_id,
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            outputs = {}
            with mock.patch.object(reconcile, "workflow_output", lambda k, v: outputs.update({k: v})):
                code = reconcile.prepare_generation(src["slug"])
                self.assertEqual(code, 0)
                self.assertEqual(outputs.get("skip_generation"), "false")

            with (
                mock.patch.object(pipeline, "auth_preflight"),
                mock.patch.object(pipeline, "add_source") as mock_add_src,
                mock.patch.object(pipeline, "start_generation") as mock_start_gen,
                mock.patch.object(pipeline, "wait_for_generation") as mock_wait,
                mock.patch.object(pipeline, "download_artifact") as mock_dl,
                mock.patch.object(pipeline, "validate_and_manifest") as mock_validate,
            ):
                code = pipeline.run_generation(max_wait_seconds=1800, require_israel_hour=None, slug=src["slug"], item_id=item_id)
                self.assertEqual(code, 0)
                mock_add_src.assert_not_called()
                mock_start_gen.assert_not_called()
                mock_wait.assert_not_called()
                mock_dl.assert_not_called()
                mock_validate.assert_called_once()

    # -------------------------------------------------------------------------
    # 10. P1: UPLOADED RECOVERY IS IDEMPOTENT
    # -------------------------------------------------------------------------
    def test_uploaded_recovery_is_idempotent(self) -> None:
        """P1: status=uploaded item skips generation, never calls provider, and reconciles idempotently."""
        post = sample_post()
        self.write_posts([post])
        src = sample_source()
        uploaded_item = make_valid_long_item(src, youtube_id="6j-doosfuRk")
        state = {"version": 1, "items": [uploaded_item]}
        pipeline.save_state(state)

        env = {
            "OPERATION": "recovery",
            "KESHER_RECOVERY_MODE": "true",
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": uploaded_item["id"],
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            outputs = {}
            with mock.patch.object(reconcile, "workflow_output", lambda k, v: outputs.update({k: v})):
                code = reconcile.prepare_generation(src["slug"])
                self.assertEqual(code, 0)
                self.assertEqual(outputs.get("skip_generation"), "true")

            with (
                mock.patch.object(pipeline, "auth_preflight"),
                mock.patch.object(pipeline, "add_source") as mock_add_src,
                mock.patch.object(pipeline, "start_generation") as mock_start_gen,
            ):
                code = pipeline.run_generation(max_wait_seconds=1800, require_israel_hour=None, slug=src["slug"], item_id=uploaded_item["id"])
                self.assertEqual(code, 0)
                mock_add_src.assert_not_called()
                mock_start_gen.assert_not_called()

    # -------------------------------------------------------------------------
    # 11. P2: EXACT REMOTE ARTIFACT RESTORE
    # -------------------------------------------------------------------------
    def test_exact_remote_artifact_restore(self) -> None:
        """P2: ArtifactArchiveFetcher restores exact candidate MP4 from zip without pre-created local file."""
        mp4_data = b"test-mp4-stream-data" * 128
        expected_sha = hashlib.sha256(mp4_data).hexdigest()
        candidate = {
            "id": "cand-remote-1",
            "final_mp4": "cand-remote.mp4",
            "final_sha256": expected_sha,
        }

        # Build zip fixture containing state.json and the exact MP4
        zip_path = self.root / "artifact.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("state.json", json.dumps({"items": [candidate]}))
            zf.writestr("cand-remote.mp4", mp4_data)

        fetcher = fallback.ArtifactArchiveFetcher(zip_path)
        ok = fallback.restore_exact_candidate_media(candidate, state_dir=self.state_dir, artifact_fetcher=fetcher)
        self.assertTrue(ok)
        restored = self.state_dir / "cand-remote.mp4"
        self.assertTrue(restored.is_file())
        self.assertEqual(hashlib.sha256(restored.read_bytes()).hexdigest(), expected_sha)

    # -------------------------------------------------------------------------
    # 12. P2: WRONG ARCHIVE REJECTED
    # -------------------------------------------------------------------------
    def test_wrong_archive_rejected(self) -> None:
        """P2: Archive with different item ID or corrupted bytes fails closed."""
        mp4_data = b"test-mp4-stream-data" * 128
        expected_sha = hashlib.sha256(mp4_data).hexdigest()
        candidate = {
            "id": "cand-remote-1",
            "final_mp4": "cand-remote.mp4",
            "final_sha256": expected_sha,
        }

        # Zip has state.json pointing to other item
        zip_path = self.root / "wrong_artifact.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("state.json", json.dumps({"items": [{"id": "other-item"}]}))
            zf.writestr("cand-remote.mp4", mp4_data)

        fetcher = fallback.ArtifactArchiveFetcher(zip_path)
        ok = fallback.restore_exact_candidate_media(candidate, state_dir=self.state_dir, artifact_fetcher=fetcher)
        self.assertFalse(ok)

    # -------------------------------------------------------------------------
    # 13. P2: MALFORMED SHA REJECTED
    # -------------------------------------------------------------------------
    def test_malformed_sha_rejected(self) -> None:
        """P2: Candidate with malformed or invalid SHA-256 fails closed."""
        candidate = {
            "id": "cand-remote-1",
            "final_mp4": "cand-remote.mp4",
            "final_sha256": "not-a-valid-hex-hash",
        }
        ok = fallback.restore_exact_candidate_media(candidate, state_dir=self.state_dir)
        self.assertFalse(ok)

    # -------------------------------------------------------------------------
    # 14. P2: VOICE WAIVER REQUIRES COMPLETE STRUCTURED EVIDENCE
    # -------------------------------------------------------------------------
    def test_voice_waiver_requires_complete_structured_evidence(self) -> None:
        """P2: Structured voice waiver passes only with complete independent technical evidence."""
        src = sample_source()
        manifest_data = {
            "item_id": "cand-voice-1",
            "source": copy.deepcopy(src),
            "final_mp4": "cand-voice.mp4",
            "final_sha256": "f" * 64,
            "raw_sha256": "r" * 64,
            "failure_signature": "wrong_narrator_gender",
            "rejection_reasons": ["נפסל טכנית: גובה צליל לא תקין (קול נשי)"],
            "media": {
                "codec": "h264",
                "audio_codec": "aac",
                "width": 1280,
                "height": 720,
                "duration": 120.0,
            },
            "content_duration_seconds": 120.0,
            "signature_overlay": True,
            "signature_asset_sha256": "s" * 64,
            "youtube_metadata": {
                "title": "כותרת",
                "description": f"תיאור {src['canonical_url']}",
                "tags": ["זוגיות"],
            },
            "visual_pipeline": "remotion-v1-notebooklm-audio",
        }

        candidate = {
            "id": "cand-voice-1",
            "source": copy.deepcopy(src),
            "final_mp4": "cand-voice.mp4",
            "final_sha256": "f" * 64,
            "manifest": manifest_data,
        }

        self.assertTrue(fallback._positive_voice_only_rejection(candidate))

        # Fails if codec is missing
        bad_codec_candidate = copy.deepcopy(candidate)
        bad_codec_candidate["manifest"]["media"]["codec"] = "unknown_codec"
        self.assertFalse(fallback._positive_voice_only_rejection(bad_codec_candidate))

        # Fails if duration is out of bounds
        bad_dur_candidate = copy.deepcopy(candidate)
        bad_dur_candidate["manifest"]["media"]["duration"] = 500.0
        self.assertFalse(fallback._positive_voice_only_rejection(bad_dur_candidate))

    # -------------------------------------------------------------------------
    # 15. P2: AUDIO CORRUPT PLUS VOICE REJECTED
    # -------------------------------------------------------------------------
    def test_audio_corrupt_plus_voice_rejected(self) -> None:
        """P2: Audio corruption cannot be waived even if voice tokens appear."""
        src = sample_source()
        manifest_data = {
            "item_id": "cand-voice-corrupt",
            "source": copy.deepcopy(src),
            "final_mp4": "cand-voice-corrupt.mp4",
            "final_sha256": "f" * 64,
            "raw_sha256": "r" * 64,
            "failure_signature": "wrong_narrator_gender",
            "rejection_reasons": ["AUDIO_TRACK_CORRUPT: קול נשי גובה צליל narrator voice"],
            "media": {
                "codec": "h264",
                "audio_codec": "aac",
                "width": 1280,
                "height": 720,
                "duration": 120.0,
            },
            "content_duration_seconds": 120.0,
            "signature_overlay": True,
            "signature_asset_sha256": "s" * 64,
            "youtube_metadata": {
                "title": "כותרת",
                "description": f"תיאור {src['canonical_url']}",
                "tags": ["זוגיות"],
            },
            "visual_pipeline": "remotion-v1-notebooklm-audio",
        }

        candidate = {
            "id": "cand-voice-corrupt",
            "source": copy.deepcopy(src),
            "final_mp4": "cand-voice-corrupt.mp4",
            "final_sha256": "f" * 64,
            "manifest": manifest_data,
        }

        self.assertFalse(fallback._positive_voice_only_rejection(candidate))


if __name__ == "__main__":
    unittest.main()
