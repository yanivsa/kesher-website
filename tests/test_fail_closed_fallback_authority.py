import copy
import json
import os
import subprocess
import sys
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

    # -------------------------------------------------------------------------
    # Codex Test A: Legacy rejected + technical_verified Attempt 2 AND approved Attempt 3
    #               -> Both fail closed on prepare_upload and upload_only before credentials/network
    # -------------------------------------------------------------------------
    def test_codex_scenario_a_legacy_rejected_tech_verified_competing_with_approved_fails_closed(self):
        """A: Legacy Attempt 2 (rejected + technical_verified + no upload_eligible) competing with Attempt 3 (approved + technical_verified) fails closed."""
        src = sample_source()
        item2 = make_item("attempt-2", 2, status="rejected", technical_verified=True)
        item2.pop("upload_eligible", None)  # legacy item with no explicit upload_eligible field
        item3 = make_item("attempt-3", 3, status="approved", technical_verified=True)
        state = {"version": 1, "state_revision": 1, "items": [item2, item3]}
        pipeline.save_state(state)

        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "KESHER_MEDIA_MODE": "video_overview",
        }

        with mock.patch.object(pipeline, "youtube_access_token") as mock_token:
            # 1. Attempt 2 prepare_upload fails closed
            with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-2"}):
                with self.assertRaises(pipeline.PipelineError) as ctx:
                    reconcile.prepare_upload(src["slug"])
                self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

            # 2. Attempt 3 prepare_upload fails closed
            with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-3"}):
                with self.assertRaises(pipeline.PipelineError) as ctx:
                    reconcile.prepare_upload(src["slug"])
                self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

            # 3. Attempt 2 upload_only fails closed before credentials/network
            with self.assertRaises(pipeline.PipelineError) as ctx:
                pipeline.upload_only(src["slug"], "attempt-2")
            self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

            # 4. Attempt 3 upload_only fails closed before credentials/network
            with self.assertRaises(pipeline.PipelineError) as ctx:
                pipeline.upload_only(src["slug"], "attempt-3")
            self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

            # Assert credentials were never requested
            mock_token.assert_not_called()

    # -------------------------------------------------------------------------
    # Codex Test B: Same with Attempt 2 marked approved in stale snapshot -> both fail closed
    # -------------------------------------------------------------------------
    def test_codex_scenario_b_attempt_2_marked_approved_stale_snapshot_fails_closed(self):
        """B: Both Attempt 2 and Attempt 3 approved without winner fail closed."""
        src = sample_source()
        item2 = make_item("attempt-2", 2, status="approved", technical_verified=True)
        item3 = make_item("attempt-3", 3, status="approved", technical_verified=True)
        state = {"version": 1, "state_revision": 1, "items": [item2, item3]}
        pipeline.save_state(state)

        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "KESHER_MEDIA_MODE": "video_overview",
        }

        with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-2"}):
            with self.assertRaises(pipeline.PipelineError) as ctx:
                reconcile.prepare_upload(src["slug"])
            self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

        with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-3"}):
            with self.assertRaises(pipeline.PipelineError) as ctx:
                reconcile.prepare_upload(src["slug"])
            self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Codex Test C: Single legacy technically-valid item -> succeeds normally
    # -------------------------------------------------------------------------
    def test_codex_scenario_c_single_legacy_technically_valid_item_succeeds_normally(self):
        """C: Single legacy item (rejected + technical_verified + no upload_eligible) succeeds normally."""
        src = sample_source()
        item2 = make_item("attempt-2", 2, status="rejected", technical_verified=True)
        item2.pop("upload_eligible", None)
        state = {"version": 1, "state_revision": 1, "items": [item2]}
        pipeline.save_state(state)

        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": "attempt-2",
            "KESHER_MEDIA_MODE": "video_overview",
        }

        # prepare_upload transitions item to approved and succeeds
        with mock.patch.dict(os.environ, env):
            code = reconcile.prepare_upload(src["slug"])
            self.assertEqual(code, 0)

        # verify state on disk now has approved status
        saved = pipeline.load_state()
        saved_item = next(r for r in saved["items"] if r["id"] == "attempt-2")
        self.assertEqual(saved_item["status"], "approved")

        # mock MP4 and manifest on disk for upload_only
        video_path = self.state_dir / saved_item["final_mp4"]
        video_path.write_bytes(b"v" * 1024)
        manifest_path = self.state_dir / saved_item["manifest_path"]
        manifest_path.write_text("{}", encoding="utf-8")
        saved_item["final_sha256"] = pipeline.sha256_file(video_path)
        saved_item["manifest_sha256"] = pipeline.sha256_file(manifest_path)
        pipeline.save_state(saved)

        with (
            mock.patch.object(pipeline, "youtube_access_token", return_value="test-token"),
            mock.patch.object(pipeline, "verify_authenticated_channel"),
            mock.patch.object(pipeline, "start_resumable_upload", return_value="https://upload.youtube.com/session/123"),
            mock.patch.object(pipeline, "upload_bytes", return_value="yt-new-123"),
            mock.patch.object(pipeline, "_verify_and_record_upload") as mock_record,
        ):
            up_code = pipeline.upload_only(src["slug"], "attempt-2")
            self.assertEqual(up_code, 0)
            mock_record.assert_called_once()

    # -------------------------------------------------------------------------
    # Codex Test D: Already-public exact item -> idempotent no-op
    # -------------------------------------------------------------------------
    def test_codex_scenario_d_already_public_exact_item_idempotent_no_op(self):
        """D: Already public exact deliverable is an idempotent no-op without re-upload."""
        src = sample_source()
        item = make_item("attempt-1", 1, status="uploaded", technical_verified=True)
        item["uploaded"] = True
        item["youtube_id"] = "pub-yt-123"
        item["youtube_verification"] = {
            "channel_id": pipeline.YOUTUBE_CHANNEL_ID,
            "privacy_status": "public",
            "processing_status": "succeeded",
            "verified_at": "2026-10-18T00:00:00Z",
        }
        state = {"version": 1, "state_revision": 1, "items": [item]}
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

            with mock.patch.object(pipeline, "youtube_access_token") as mock_token:
                up_code = pipeline.upload_only(src["slug"], "attempt-1")
                self.assertEqual(up_code, 0)
                mock_token.assert_not_called()

    # -------------------------------------------------------------------------
    # Codex Test E: Truly non-publication-capable rejected item -> no false ambiguity
    # -------------------------------------------------------------------------
    def test_codex_scenario_e_non_publication_capable_rejected_no_false_ambiguity(self):
        """E: Truly rejected item (technical_verified=False) does not create false ambiguity with approved attempt."""
        src = sample_source()
        item1 = make_item("attempt-1", 1, status="rejected", technical_verified=False)
        item2 = make_item("attempt-2", 2, status="approved", technical_verified=True)
        state = {"version": 1, "state_revision": 1, "items": [item1, item2]}
        pipeline.save_state(state)

        # Attempt 1 cannot proceed toward publication
        self.assertFalse(pipeline.can_long_item_proceed_toward_publication(item1))
        # Attempt 2 can proceed
        self.assertTrue(pipeline.can_long_item_proceed_toward_publication(item2))

        env = {
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "KESHER_MEDIA_MODE": "video_overview",
        }

        # Attempt 2 prepare_upload succeeds normally without ambiguity
        with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-2"}):
            code = reconcile.prepare_upload(src["slug"])
            self.assertEqual(code, 0)
            self.assertEqual(os.environ.get("TARGET_ITEM_ID"), "attempt-2")

        # Attempt 1 prepare_upload fails closed (not authorized publication candidate)
        with mock.patch.dict(os.environ, {**env, "TARGET_ITEM_ID": "attempt-1"}):
            with self.assertRaises(pipeline.PipelineError) as ctx:
                reconcile.prepare_upload(src["slug"])
            self.assertIn("AMBIGUOUS_LONG_UPLOAD_AUTHORITY", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Codex Test F1: Two independent OS processes -> Winner survives, no 11 -> 1 regression
    # -------------------------------------------------------------------------
    def test_codex_scenario_f1_concurrency_winner_survives_stale_revision_regression(self):
        """F1: Two independent OS processes verify revision 11 + winner survives stale revision 1 writer."""
        src = sample_source()
        item1 = make_item("attempt-1", 1, status="approved")
        initial_state = {"version": 1, "state_revision": 1, "items": [item1]}
        pipeline.save_state(initial_state)

        state_path = str(self.state_dir / "state.json")

        # Process B script: writes revision 11 + committed fallback winner
        proc_b_code = f"""
import json, sys
from pathlib import Path
from scripts import kesher_daily_pipeline as pipeline

state_path = Path({repr(state_path)})
pipeline.STATE_FILE = state_path
state = pipeline.load_state()
state["state_revision"] = 11
state["fallback_winner"] = {{
    "slug": {repr(src["slug"])},
    "content_sha256": {repr(src["content_sha256"])},
    "winner_item_id": "attempt-1",
    "fallback_committed": True,
    "revision": 11,
}}
pipeline.save_state(state)
sys.exit(0)
"""
        res_b = subprocess.run([sys.executable, "-c", proc_b_code], cwd=str(pipeline.PROJECT_DIR), capture_output=True, text=True)
        self.assertEqual(res_b.returncode, 0, f"Process B failed: {res_b.stderr}")

        # Verify disk state has revision 11 + winner
        current = pipeline.load_state()
        self.assertEqual(current["state_revision"], 11)
        self.assertEqual(current["fallback_winner"]["winner_item_id"], "attempt-1")

        # Process A script: stale worker attempting to write revision 1
        stale_state = copy.deepcopy(initial_state)
        stale_state["state_revision"] = 1
        stale_json = json.dumps(stale_state)

        proc_a_code = f"""
import json, sys
from pathlib import Path
from scripts import kesher_daily_pipeline as pipeline

state_path = Path({repr(state_path)})
pipeline.STATE_FILE = state_path
stale_state = json.loads({repr(stale_json)})
try:
    pipeline.save_state(stale_state)
    sys.exit(0)
except pipeline.PipelineError as exc:
    if "STALE_SNAPSHOT_REGRESSION" in str(exc):
        sys.exit(42)
    sys.exit(1)
"""
        res_a = subprocess.run([sys.executable, "-c", proc_a_code], cwd=str(pipeline.PROJECT_DIR), capture_output=True, text=True)
        self.assertEqual(res_a.returncode, 42, f"Process A did not fail with STALE_SNAPSHOT_REGRESSION: exit={res_a.returncode}, err={res_a.stderr}")

        # Verify disk state was NOT overwritten: revision 11 and winner item ID remain intact!
        after = pipeline.load_state()
        self.assertEqual(after["state_revision"], 11)
        self.assertIsNotNone(after.get("fallback_winner"))
        self.assertEqual(after["fallback_winner"]["winner_item_id"], "attempt-1")
        self.assertTrue(after["fallback_winner"]["fallback_committed"])

    # -------------------------------------------------------------------------
    # Codex Test F2: Inverse ordering test
    # -------------------------------------------------------------------------
    def test_codex_scenario_f2_concurrency_inverse_ordering(self):
        """F2: Writing revision 1 to disk at revision 11 fails closed, while writing revision 12 succeeds."""
        src = sample_source()
        item1 = make_item("attempt-1", 1, status="approved")
        state_path = str(self.state_dir / "state.json")

        initial_state = {
            "version": 1,
            "state_revision": 11,
            "fallback_winner": {
                "slug": src["slug"],
                "content_sha256": src["content_sha256"],
                "winner_item_id": "attempt-1",
                "fallback_committed": True,
                "revision": 11,
            },
            "items": [item1],
        }
        pipeline.save_state(initial_state)

        # 1. Stale writer at rev 1 fails closed
        stale_rev_1 = copy.deepcopy(initial_state)
        stale_rev_1["state_revision"] = 1
        with self.assertRaises(pipeline.PipelineError) as ctx:
            pipeline.save_state(stale_rev_1)
        self.assertIn("STALE_SNAPSHOT_REGRESSION", str(ctx.exception))

        # 2. Advance to rev 12 succeeds
        advance_rev_12 = copy.deepcopy(initial_state)
        advance_rev_12["state_revision"] = 12
        advance_rev_12["fallback_winner"]["revision"] = 12
        pipeline.save_state(advance_rev_12)

        disk = pipeline.load_state()
        self.assertEqual(disk["state_revision"], 12)
        self.assertEqual(disk["fallback_winner"]["winner_item_id"], "attempt-1")

    # -------------------------------------------------------------------------
    # Codex Test F3: Multi-process stress test (revisions 2..N)
    # -------------------------------------------------------------------------
    def test_codex_scenario_f3_concurrency_multiprocess_stress_test(self):
        """F3: N independent OS processes increment revision under exclusive flock with zero corruption."""
        state_path = str(self.state_dir / "state.json")
        initial_state = {"version": 1, "state_revision": 1, "items": []}
        pipeline.save_state(initial_state)

        # Worker script: loads state, increments state_revision, calls save_state
        worker_code = f"""
import json, sys
from pathlib import Path
from scripts import kesher_daily_pipeline as pipeline

state_path = Path({repr(state_path)})
pipeline.STATE_FILE = state_path
state = pipeline.load_state()
state["state_revision"] = int(state.get("state_revision", 1)) + 1
pipeline.save_state(state)
sys.exit(0)
"""
        for step in range(2, 7):
            res = subprocess.run([sys.executable, "-c", worker_code], cwd=str(pipeline.PROJECT_DIR), capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, f"Worker at step {step} failed: {res.stderr}")

        final_state = pipeline.load_state()
        self.assertEqual(final_state["state_revision"], 6)
        self.assertEqual(final_state["version"], 1)

    # -------------------------------------------------------------------------
    # Codex P1 Fix Tests: Authoritative Rebinding & Short Routing Boundary
    # -------------------------------------------------------------------------

    def test_codex_p1_authoritative_rebinding_stale_snapshot_rejected_on_disk(self):
        """P1 #1 Scenario A:
        authoritative disk state has status=rejected, technical_verified=False,
        but stale caller snapshot has status=approved, technical_verified=True.
        verify_single_upload_authority must load disk, return rejected item,
        and downstream must fail closed (no upload).
        """
        src = sample_source()
        item_id = "attempt-stale-1"

        # Item on disk is REJECTED
        disk_item = make_item(item_id, 1, status="rejected", technical_verified=False)
        disk_state = {
            "version": 1,
            "state_revision": 5,
            "items": [disk_item],
        }
        pipeline.save_state(disk_state)

        # Stale in-memory snapshot has status="approved", technical_verified=True
        stale_item = make_item(item_id, 1, status="approved", technical_verified=True)
        stale_state = {
            "version": 1,
            "state_revision": 4,
            "items": [stale_item],
        }

        # 1. verify_single_upload_authority must read disk, ignore stale state, and return disk_item
        returned = pipeline.verify_single_upload_authority(
            stale_state, src["slug"], src["content_sha256"], target_item_id=item_id
        )
        self.assertEqual(returned.get("status"), "rejected")
        self.assertFalse(returned.get("technical_verified"))
        self.assertFalse(pipeline.can_long_item_proceed_toward_publication(returned))

    def test_codex_p1_prepare_upload_does_not_revert_to_stale_caller_snapshot(self):
        """P1 #1 Scenario B:
        prepare_upload() must use the returned authoritative item directly and NOT
        revert to stale caller snapshot values. Must return ready=false and stop.
        """
        src = sample_source()
        item_id = "attempt-stale-2"

        # Item on disk is REJECTED with upload_eligible True (legacy unflagged)
        disk_item = make_item(item_id, 1, status="rejected", technical_verified=False)
        disk_item["upload_eligible"] = True
        disk_state = {
            "version": 1,
            "state_revision": 5,
            "items": [disk_item],
        }
        pipeline.save_state(disk_state)

        # Stale in-memory snapshot has status="approved", technical_verified=True
        stale_item = make_item(item_id, 1, status="approved", technical_verified=True)
        stale_state = {
            "version": 1,
            "state_revision": 4,
            "items": [stale_item],
        }

        outputs = {}
        with mock.patch.dict(os.environ, {
            "KESHER_MEDIA_MODE": "video_overview",
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": item_id,
        }), mock.patch.object(reconcile, "current_source_snapshot", return_value=src), \
           mock.patch.object(reconcile, "workflow_output", lambda k, v: outputs.update({k: v})):
            code = reconcile.prepare_upload(src["slug"], src["content_sha256"], item_id)
            self.assertEqual(code, 0)
            self.assertEqual(outputs.get("ready"), "false")

    def test_codex_p1_upload_only_does_not_revert_to_stale_caller_snapshot(self):
        """P1 #1 Scenario C:
        upload_only() must use the returned authoritative item directly and NOT
        revert to stale caller snapshot values. Must print NO_TECHNICALLY_VERIFIED_UPLOAD and return 0.
        """
        src = sample_source()
        item_id = "attempt-stale-3"

        # Item on disk is REJECTED with upload_eligible True (legacy or unflagged)
        disk_item = make_item(item_id, 1, status="rejected", technical_verified=False)
        disk_item["upload_eligible"] = True
        disk_state = {
            "version": 1,
            "state_revision": 5,
            "items": [disk_item],
        }
        pipeline.save_state(disk_state)

        # Stale caller snapshot
        stale_item = make_item(item_id, 1, status="approved", technical_verified=True)
        stale_state = {
            "version": 1,
            "state_revision": 4,
            "items": [stale_item],
        }

        with mock.patch.dict(os.environ, {
            "KESHER_MEDIA_MODE": "video_overview",
        }):
            res = pipeline.upload_only(slug=src["slug"], item_id=item_id, state=stale_state)
            self.assertEqual(res, 0)

    def test_codex_p1_short_publication_readiness(self):
        """P1 #2 Scenario D:
        Valid Short item (type=article_short, approved, technical_verified=True)
        must pass can_short_item_proceed_toward_publication and technical_publication_ready.
        Long predicate must return False.
        """
        short_item = make_item("short-valid-1", 1, status="approved", technical_verified=True)
        short_item["type"] = "article_short"
        short_item["visual_pipeline"] = "remotion-v4-notebooklm-short-motion-plan-v1"

        self.assertTrue(pipeline.can_short_item_proceed_toward_publication(short_item))
        self.assertTrue(pipeline.can_item_proceed_toward_publication(short_item))
        self.assertFalse(pipeline.can_long_item_proceed_toward_publication(short_item))
        self.assertTrue(reconcile.technical_publication_ready(short_item))

    def test_codex_p1_long_and_short_items_do_not_conflict_on_same_slug(self):
        """P1 #2 Scenario E:
        Long item and Short item coexist for the exact same slug + content_sha256.
        Long authority check must filter only Long items and not conflict with Short.
        Short must not be evaluated against video_overview constraints.
        """
        src = sample_source()
        long_item = make_item("long-attempt-1", 1, status="approved", technical_verified=True)
        long_item["type"] = "video_overview"

        short_item = make_item("short-attempt-1", 1, status="approved", technical_verified=True)
        short_item["type"] = "article_short"
        short_item["visual_pipeline"] = "remotion-v4-notebooklm-short-motion-plan-v1"

        state = {
            "version": 1,
            "state_revision": 2,
            "items": [long_item, short_item],
        }
        pipeline.save_state(state)

        # Long authority verification succeeds for long_item without ambiguity from short_item
        long_auth = pipeline.verify_single_upload_authority(
            state, src["slug"], src["content_sha256"], target_item_id="long-attempt-1"
        )
        self.assertEqual(long_auth["id"], "long-attempt-1")

        # Short item publication readiness is completely unaffected by Long
        self.assertTrue(pipeline.can_short_item_proceed_toward_publication(short_item))

    def test_codex_p1_prepare_upload_short_does_not_execute_long_ambiguity(self):
        """P1 #2 Scenario F:
        When preparing Short upload, verify_single_upload_authority (Long check)
        must NOT execute, and Short publication must proceed with advisory review.
        """
        src = sample_source()
        short_item = make_item("short-pub-1", 1, status="approved", technical_verified=True)
        short_item["type"] = "article_short"
        short_item["visual_pipeline"] = "remotion-v4-notebooklm-short-motion-plan-v1"
        short_item["source_mode"] = "independent"
        short_item["signature_verified"] = True
        short_item["signature_duration_seconds"] = 3.0

        state = {
            "version": 1,
            "state_revision": 3,
            "items": [short_item],
        }
        pipeline.save_state(state)

        outputs = {}
        with mock.patch.dict(os.environ, {
            "KESHER_MEDIA_MODE": "article_short",
            "TARGET_SLUG": src["slug"],
            "TARGET_CONTENT_SHA256": src["content_sha256"],
            "TARGET_ITEM_ID": "short-pub-1",
        }), mock.patch.object(reconcile, "current_source_snapshot", return_value=src), \
           mock.patch("scripts.kesher_e2e_delivery_guard._signature_verified", return_value=True), \
           mock.patch.object(reconcile, "workflow_output", lambda k, v: outputs.update({k: v})):
            code = reconcile.prepare_upload(src["slug"], src["content_sha256"], "short-pub-1")
            self.assertEqual(code, 0)
            self.assertEqual(outputs.get("ready"), "true")

    def test_codex_p1_unknown_media_type_fails_closed(self):
        """P1 #2 Scenario G:
        Any unknown media type must fail closed across all gates.
        """
        src = sample_source()
        unknown_item = {
            "id": "unknown-1",
            "type": "unsupported_media_type",
            "status": "approved",
            "technical_verified": True,
            "final_sha256": "f" * 64,
            "source": src,
        }
        self.assertFalse(pipeline.can_item_proceed_toward_publication(unknown_item))
        self.assertFalse(pipeline.can_long_item_proceed_toward_publication(unknown_item))
        self.assertFalse(pipeline.can_short_item_proceed_toward_publication(unknown_item))
        self.assertFalse(reconcile.technical_publication_ready(unknown_item))

        state = {"version": 1, "items": [unknown_item]}
        pipeline.save_state(state)
        with mock.patch.object(reconcile, "current_source_snapshot", return_value=src), \
             self.assertRaises(pipeline.PipelineError) as ctx:
            reconcile.prepare_upload(src["slug"], src["content_sha256"], "unknown-1")
        self.assertIn("UNKNOWN_MEDIA_TYPE", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
