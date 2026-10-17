import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_final_attempt_fallback as fallback
from scripts import kesher_intervention_policy as intervention
from scripts import kesher_three_strike_runtime as three_strike
from scripts import kesher_video_reconcile as reconcile


def sample_post(slug: str = "test-fail-closed-article", day: str = "2026-10-18") -> dict:
    return {
        "id": slug,
        "slug": slug,
        "title": "כותרת מאמר עברי",
        "date": day,
        "category": "הדרכת הורים",
        "excerpt": "תקציר עברי קצר",
        "content": "<p>תוכן עברי מלא לצורך בדיקת שחזור והתאוששות.</p>",
    }


def sample_source(slug: str = "test-fail-closed-article", day: str = "2026-10-18") -> dict:
    post = sample_post(slug, day)
    return pipeline.source_metadata(post)


def make_item(item_id: str, attempt: int, *, status: str = "approved", technical_verified: bool = True, final_fallback: bool = False):
    src = sample_source()
    canonical_url = src["canonical_url"]
    description = f"כותרת עברית\n{canonical_url}\nhttps://kesher.saharoni.com\nhttps://kesher.saharoni.com/appointment"
    manifest = {
        "item_id": item_id,
        "source": src,
        "final_mp4": f"{item_id}.mp4",
        "final_sha256": "f" * 64,
        "raw_sha256": "r" * 64,
        "failure_signature": "none" if technical_verified else "wrong_narrator_gender",
        "rejection_reasons": [] if technical_verified else ["male voice"],
        "media": {"codec": "h264", "audio_codec": "aac", "width": 1280, "height": 720, "duration": 120.0},
        "content_duration_seconds": 120.0,
        "signature_overlay": True,
        "signature_asset_sha256": "s" * 64,
        "youtube_metadata": {
            "title": "כותרת",
            "description": description,
            "tags": ["זוגיות"],
        },
        "visual_pipeline": "remotion-v1-notebooklm-audio",
    }
    return {
        "id": item_id,
        "type": "video_overview",
        "fresh_generation_attempt": attempt,
        "source": src,
        "uploaded": False,
        "status": status,
        "technical_verified": technical_verified,
        "upload_eligible": (status not in {"superseded", "rejected"}),
        "final_attempt_fallback": final_fallback,
        "final_mp4": f"{item_id}.mp4",
        "final_sha256": "f" * 64,
        "raw_sha256": "r" * 64,
        "manifest_sha256": "m" * 64,
        "transcript_sha256": "t" * 64,
        "source_file_sha256": "s" * 64,
        "visual_review_sha256": "v" * 64,
        "frame_sha256": {"0": "f" * 64},
        "media": {"codec": "h264", "audio_codec": "aac", "width": 1280, "height": 720, "duration": 120.0},
        "manifest": manifest,
        "manifest_path": f"{item_id}-manifest.json",
        "youtube_metadata": manifest["youtube_metadata"],
        "visual_pipeline": "remotion-v1-notebooklm-audio",
    }


class _TestControllerHarness(three_strike.ThreeStrikeMediaInterventionMixin):
    def __init__(self, now, github):
        self.now = now
        self.github = github

    @staticmethod
    def _watchdog_candidate(snapshot, source):
        return None

    def _supervisor_decision(self, *args, **kwargs):
        return None


class FailClosedFallbackAuthorityTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name)
        self.posts_file = self.state_dir / "posts.json"
        self.posts_file.write_text(json.dumps([sample_post()], ensure_ascii=False), encoding="utf-8")

        self.patchers = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_dir / "state.json"),
            mock.patch.object(pipeline, "POSTS_FILE", self.posts_file),
            mock.patch.object(fallback, "STATE_DIR", self.state_dir),
            mock.patch.object(fallback, "STATE_FILE", self.state_dir / "state.json"),
            mock.patch.object(reconcile, "export_target", lambda item: os.environ.update({"TARGET_ITEM_ID": item.get("id", "")})),
            mock.patch.object(reconcile, "workflow_output", lambda k, v: None),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self.tmp.cleanup()
        super().tearDown()

    # -------------------------------------------------------------------------
    # Scenario A: Two exact technically-valid attempts + no authoritative winner
    #             -> Both prepare_upload calls fail closed
    # -------------------------------------------------------------------------
    def test_two_exact_technically_valid_attempts_no_winner_fails_closed(self):
        """A: Two non-superseded exact attempts without an authoritative winner fail closed on upload."""
        src = sample_source()
        item1 = make_item("attempt-1", 1, status="approved", technical_verified=True)
        item2 = make_item("attempt-2", 2, status="approved", technical_verified=True)
        state = {"version": 1, "state_revision": 1, "items": [item1, item2]}
        pipeline.save_state(state)

        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "KESHER_MEDIA_MODE": "video_overview",
        }

        # Attempt 1 prepare_upload fails closed
        with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-1"}):
            with self.assertRaises(pipeline.PipelineError) as ctx:
                reconcile.prepare_upload(src["slug"])
            self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

        # Attempt 2 prepare_upload fails closed
        with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-2"}):
            with self.assertRaises(pipeline.PipelineError) as ctx:
                reconcile.prepare_upload(src["slug"])
            self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

        # upload_only directly fails closed
        with self.assertRaises(pipeline.PipelineError) as ctx:
            pipeline.upload_only(src["slug"], "attempt-1")
        self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Scenario B: Stale snapshot with lower revision raises before save
    #             -> Persisted winner/revision unchanged
    # -------------------------------------------------------------------------
    def test_stale_snapshot_with_lower_revision_raises_before_save(self):
        """B: Stale snapshot with lower state_revision raises before save; persisted winner unchanged."""
        src = sample_source()
        item1 = make_item("attempt-1", 1, status="approved")
        persisted_state = {
            "version": 1,
            "state_revision": 5,
            "fallback_winner": {
                "slug": src["slug"],
                "content_sha256": src["content_sha256"],
                "winner_item_id": "attempt-1",
                "fallback_committed": True,
                "revision": 5,
            },
            "items": [item1],
        }
        pipeline.save_state(persisted_state)

        # Stale worker tries to save state with state_revision: 4
        stale_item = make_item("attempt-2", 2, status="approved")
        stale_snapshot = {
            "version": 1,
            "state_revision": 4,
            "fallback_winner": {
                "slug": src["slug"],
                "content_sha256": src["content_sha256"],
                "winner_item_id": "attempt-2",
                "fallback_committed": True,
                "revision": 4,
            },
            "items": [item1, stale_item],
        }

        with self.assertRaises(pipeline.PipelineError) as ctx:
            pipeline.save_state(stale_snapshot)
        self.assertIn("STALE_SNAPSHOT_REGRESSION", str(ctx.exception))

        # Verify disk state was NOT mutated
        disk_state = pipeline.load_state()
        self.assertEqual(disk_state.get("state_revision"), 5)
        self.assertEqual(disk_state.get("fallback_winner", {}).get("winner_item_id"), "attempt-1")

        # Also verify validate_and_manifest on late attempt raises without calling save_state
        raw_mp4 = self.state_dir / "raw.mp4"
        raw_mp4.write_bytes(b"x" * 2048)
        with self.assertRaises(pipeline.PipelineError) as ctx2:
            pipeline.validate_and_manifest(stale_snapshot, stale_item, raw_mp4)
        self.assertIn("STALE_SNAPSHOT_SUPERSEDED", str(ctx2.exception))

        disk_after = pipeline.load_state()
        self.assertEqual(disk_after.get("state_revision"), 5)
        self.assertEqual(disk_after.get("fallback_winner", {}).get("winner_item_id"), "attempt-1")

    # -------------------------------------------------------------------------
    # Scenario C: Fallback requested -> Production default refuses promotion
    # -------------------------------------------------------------------------
    def test_fallback_requested_production_default_refuses_promotion(self):
        """C: Production default disables fallback promotion fail-closed."""
        src = sample_source()
        item1 = make_item("attempt-1", 1, status="rejected", technical_verified=False)
        item2 = make_item("attempt-2", 2, status="rejected", technical_verified=False)
        item3 = make_item("attempt-3", 3, status="rejected", technical_verified=False)
        state = {"version": 1, "items": [item1, item2, item3]}

        # 1. Direct helper refuses promotion
        self.assertFalse(fallback.is_fallback_promotion_enabled())
        promoted = fallback.promote_last_usable_after_third_attempt(state)
        self.assertIsNone(promoted)

        # 2. Controller runtime refuses promotion and blocks with FALLBACK_WINNER_AUTHORITY_UNAVAILABLE
        gh = mock.MagicMock()
        gh.newest_video_state.return_value = state
        gh.save_video_state = mock.MagicMock()
        gh.save_controller_state = mock.MagicMock()
        gh.active_workflow_run.return_value = None

        ctrl_state = {
            "schema_version": 5,
            "cycle": "2026-10-18",
            "status": "long_video_running",
            "history": [],
            "interventions": {},
            "article": {"status": "complete"},
            "long_video": {
                "status": "pending",
                "attempt_count": 3,
                "item_id": "attempt-3",
                "processed_run_id": None,
                "run_id": None,
            },
            "short": {"status": "pending"},
        }
        gh.load_controller_state.return_value = ctrl_state

        now = datetime(2026, 10, 18, 1, 0, tzinfo=timezone.utc)
        harness = _TestControllerHarness(now, gh)
        with (
            mock.patch.object(harness, "_watchdog_candidate", return_value=item3),
            mock.patch.object(three_strike.watchdog, "media_decision", return_value="hard_timeout"),
            mock.patch.object(intervention, "observe_incident", return_value=intervention.InterventionDecision(
                incident_key="test-incident",
                strike=3,
                action=intervention.FORCE_CONTROLLER_RECOVERY,
            )),
        ):
            action = harness._media_watchdog_preflight(ctrl_state, src)
            self.assertEqual(action.kind, "blocked")
            self.assertEqual(action.reason, "FALLBACK_WINNER_AUTHORITY_UNAVAILABLE")
            self.assertEqual(ctrl_state["long_video"]["status"], "blocked")

        # 3. prepare_upload refuses fallback items
        fallback_item = make_item("attempt-2", 2, status="approved", technical_verified=True, final_fallback=True)
        fallback_state = {"version": 1, "items": [fallback_item]}
        pipeline.save_state(fallback_state)
        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": "attempt-2",
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with mock.patch.dict(os.environ, env):
            with self.assertRaises(pipeline.PipelineError) as ctx:
                reconcile.prepare_upload(src["slug"])
            self.assertIn("FALLBACK_WINNER_AUTHORITY_UNAVAILABLE", str(ctx.exception))

        # 4. upload_only refuses fallback items
        with self.assertRaises(pipeline.PipelineError) as ctx:
            pipeline.upload_only(src["slug"], "attempt-2")
        self.assertIn("FALLBACK_WINNER_AUTHORITY_UNAVAILABLE", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Scenario D: Normal Attempt 3 completes successfully -> Continues normally
    # -------------------------------------------------------------------------
    def test_normal_attempt_3_completes_successfully_continues_normally(self):
        """D: Normal Attempt 3 completion continues through upload without obstruction."""
        src = sample_source()
        item1 = make_item("attempt-1", 1, status="rejected", technical_verified=False)
        item2 = make_item("attempt-2", 2, status="rejected", technical_verified=False)
        item3 = make_item("attempt-3", 3, status="approved", technical_verified=True)
        state = {"version": 1, "items": [item1, item2, item3]}
        pipeline.save_state(state)

        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": "attempt-3",
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with mock.patch.dict(os.environ, env):
            code = reconcile.prepare_upload(src["slug"])
            self.assertEqual(code, 0)
            self.assertEqual(os.environ.get("TARGET_ITEM_ID"), "attempt-3")

    # -------------------------------------------------------------------------
    # Scenario E: Same-identity recovery of existing Attempt 3 -> Zero provider creation
    # -------------------------------------------------------------------------
    def test_same_identity_recovery_existing_attempt_3_zero_provider_creation(self):
        """E: Recovery of existing Attempt 3 in downloaded state runs local processing only."""
        src = sample_source()
        item3 = make_item("attempt-3", 3, status="downloaded", technical_verified=False)
        state = {"version": 1, "items": [item3]}
        pipeline.save_state(state)

        env = {
            "OPERATION": "recovery",
            "KESHER_RECOVERY_MODE": "true",
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": "attempt-3",
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with (
            mock.patch.dict(os.environ, env),
            mock.patch.object(pipeline, "new_item") as mock_new_item,
            mock.patch.object(pipeline, "add_source") as mock_add_src,
            mock.patch.object(pipeline, "start_generation") as mock_start_gen,
            mock.patch.object(reconcile, "retry_technical_rejection") as mock_retry,
        ):
            code = reconcile.prepare_generation(src["slug"])
            self.assertEqual(code, 0)
            mock_new_item.assert_not_called()
            mock_add_src.assert_not_called()
            mock_start_gen.assert_not_called()
            mock_retry.assert_not_called()
            self.assertEqual(os.environ.get("TARGET_ITEM_ID"), "attempt-3")

    # -------------------------------------------------------------------------
    # Scenario F: Already uploaded exact item -> No duplicate upload
    # -------------------------------------------------------------------------
    def test_already_uploaded_exact_item_no_duplicate_upload(self):
        """F: Already public/uploaded exact item is recognized; no duplicate upload executed."""
        src = sample_source()
        item = make_item("attempt-1", 1, status="uploaded", technical_verified=True)
        item["uploaded"] = True
        item["youtube_id"] = "existing-yt-id"
        item["youtube_verification"] = {
            "channel_id": pipeline.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
            "verified_at": "2026-10-18T00:00:00Z",
        }
        state = {"version": 1, "items": [item]}
        pipeline.save_state(state)

        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": "attempt-1",
            "KESHER_MEDIA_MODE": "video_overview",
        }
        with mock.patch.dict(os.environ, env):
            code = reconcile.prepare_upload(src["slug"])
            self.assertEqual(code, 0)

            upload_code = pipeline.upload_only(src["slug"], "attempt-1")
            self.assertEqual(upload_code, 0)


if __name__ == "__main__":
    unittest.main()
