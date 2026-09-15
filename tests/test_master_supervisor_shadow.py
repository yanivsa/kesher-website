from __future__ import annotations

import inspect
import unittest

from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_master_supervisor_shadow as shadow
from scripts.kesher_master_supervisor_shadow import build_shadow_report


def article() -> dict:
    return {
        "id": "shadow-article",
        "slug": "shadow-article",
        "title": "מאמר בדיקה",
        "date": "2026-09-15",
        "category": "זוגיות",
        "excerpt": "תקציר בדיקה משמעותי",
        "content": "<p>תוכן בדיקה מלא עבור זהות מקור יציבה.</p>",
    }


def source() -> dict[str, str]:
    return v5.article_source_identity(article())


def controller_state(*, status: str = "blocked", stage: str = "long_video", code: str = "VIDEO_ATTEMPTS_EXHAUSTED") -> dict:
    src = source()
    return {
        "schema_version": 5,
        "cycle": "2026-09-15",
        "status": status,
        "article": {
            "status": "complete",
            "live": True,
            "slug": src["slug"],
            "content_sha256": src["content_sha256"],
            "pr_number": 802,
        },
        "image": {"status": "complete"},
        "long_video": {"status": "exhausted", "item_id": "video-1"},
        "short": {"status": "pending"},
        "last_error": {"stage": stage, "code": code, "message": code},
    }


def exact_long(**updates) -> dict:
    src = source()
    row = {
        "id": "video-1",
        "source": src,
        "status": "rejected",
        "uploaded": False,
        "technical_verified": False,
        "signature_fullscreen": False,
        "task_id": "task-1",
        "artifact_id": "task-1",
        "source_id": "source-1",
    }
    row.update(updates)
    return row


class MasterSupervisorShadowTests(unittest.TestCase):
    def test_historical_829_rejected_signature_routes_exact_remotion_rebuild(self) -> None:
        report = build_shadow_report(
            controller_state=controller_state(),
            posts=[article()],
            video_state={"items": [exact_long()]},
            short_state={"items": []},
            observed_at="2026-09-16T00:00:00+00:00",
        )
        self.assertEqual(report["mode"], "shadow")
        self.assertEqual(report["failure_signature"], "OVERVIEW_SIGNATURE_FULLSCREEN_MISSING")
        self.assertEqual(report["proposed_action"], "rebuild_exact_overview")
        self.assertEqual(report["exact"]["item_id"], "video-1")
        self.assertFalse(report["would_dispatch"])
        self.assertTrue(report["incident_id"].endswith("|long_video"))

    def test_workflow_rerun_is_not_progress_or_new_recovery_intent(self) -> None:
        first = build_shadow_report(
            controller_state=controller_state(),
            posts=[article()],
            video_state={"items": [exact_long()]},
            short_state={"items": []},
            observed_at="2026-09-16T00:00:00+00:00",
            workflow_run_id="100",
        )
        second = build_shadow_report(
            controller_state=controller_state(),
            posts=[article()],
            video_state={"items": [exact_long()]},
            short_state={"items": []},
            observed_at="2026-09-16T00:10:00+00:00",
            workflow_run_id="101",
        )
        self.assertEqual(first["evidence_hash"], second["evidence_hash"])
        self.assertEqual(first["recovery_command_id"], second["recovery_command_id"])

    def test_technical_overview_without_upload_routes_exact_upload(self) -> None:
        state = controller_state(status="video_running", stage="long_video", code="")
        state["last_error"] = None
        row = exact_long(status="approved", technical_verified=True, signature_fullscreen=True)
        report = build_shadow_report(
            controller_state=state,
            posts=[article()],
            video_state={"items": [row]},
            short_state={"items": []},
        )
        self.assertEqual(report["failure_signature"], "YOUTUBE_UPLOAD_MISSING")
        self.assertEqual(report["proposed_action"], "retry_exact_upload")

    def test_verified_overview_without_short_routes_exact_short_continuation(self) -> None:
        state = controller_state(status="short_pending", stage="short", code="")
        state["last_error"] = None
        row = exact_long(
            status="uploaded",
            uploaded=True,
            technical_verified=True,
            signature_fullscreen=True,
            youtube_id="overview-1",
            youtube_url="https://youtu.be/overview-1",
            youtube_verification={
                "channel_id": v5.core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        )
        report = build_shadow_report(
            controller_state=state,
            posts=[article()],
            video_state={"items": [row]},
            short_state={"items": []},
        )
        self.assertEqual(report["failure_signature"], "SHORT_MISSING")
        self.assertEqual(report["proposed_action"], "continue_exact_short")

    def test_horizontal_short_routes_exact_short_rebuild(self) -> None:
        state = controller_state(status="short_running", stage="short", code="")
        state["last_error"] = None
        long_row = exact_long(
            status="uploaded",
            uploaded=True,
            technical_verified=True,
            signature_fullscreen=True,
            youtube_id="overview-1",
            youtube_url="https://youtu.be/overview-1",
            youtube_verification={
                "channel_id": v5.core.YOUTUBE_CHANNEL_ID,
                "privacy_status": "public",
                "processing_status": "succeeded",
            },
        )
        short_row = {
            "id": "short-1",
            "source": source(),
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "short-1",
            "youtube_url": "https://youtu.be/short-1",
            "media": {"width": 1920, "height": 1080},
        }
        report = build_shadow_report(
            controller_state=state,
            posts=[article()],
            video_state={"items": [long_row]},
            short_state={"items": [short_row]},
        )
        self.assertEqual(report["failure_signature"], "SHORT_NOT_PORTRAIT")
        self.assertEqual(report["proposed_action"], "rebuild_exact_short")
        self.assertEqual(report["exact"]["short_item_id"], "short-1")

    def test_image_guard_failure_repairs_same_pr(self) -> None:
        state = controller_state(stage="image", code="ARTICLE_IMAGE_GUARD_FAILED")
        state["image"] = {"status": "blocked"}
        report = build_shadow_report(
            controller_state=state,
            posts=[article()],
            video_state={"items": []},
            short_state={"items": []},
        )
        self.assertEqual(report["failure_signature"], "ARTICLE_IMAGE_GUARD_FAILED")
        self.assertEqual(report["proposed_action"], "repair_trusted_image_same_pr")
        self.assertEqual(report["exact"]["pr_number"], 802)

    def test_stale_controller_binding_routes_rebind_not_generation(self) -> None:
        state = controller_state(status="video_running", stage="long_video", code="")
        state["last_error"] = None
        state["long_video"].update({
            "item_id": "stale-video",
            "provider_id": "stale-task",
            "artifact_id": "stale-artifact",
            "source_id": "stale-source",
        })
        report = build_shadow_report(
            controller_state=state,
            posts=[article()],
            video_state={"items": [exact_long(status="generating", signature_fullscreen=None)]},
            short_state={"items": []},
        )
        self.assertEqual(report["failure_signature"], "STALE_SOURCE_BINDING")
        self.assertEqual(report["proposed_action"], "rebind_exact_source")
        self.assertNotEqual(report["proposed_action"], "generate_new_overview")

    def test_article_generation_without_authoritative_article_is_wait_only(self) -> None:
        state = {
            "schema_version": 5,
            "cycle": "2026-09-16",
            "status": "article_generating",
            "article": {"status": "running"},
            "image": {"status": "pending"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
            "last_error": None,
        }
        report = build_shadow_report(
            controller_state=state,
            posts=[],
            video_state={"items": []},
            short_state={"items": []},
        )
        self.assertEqual(report["status"], "waiting_for_authoritative_article")
        self.assertIsNone(report["incident_id"])
        self.assertIsNone(report["proposed_action"])
        self.assertFalse(report["would_dispatch"])

    def test_shadow_classifier_remains_side_effect_free_after_live_activation(self) -> None:
        source_text = inspect.getsource(shadow)
        self.assertNotIn("dispatch_workflow", source_text)
        self.assertNotIn("JULES_API_KEY", source_text)
        self.assertNotIn('method="POST"', source_text)
        self.assertNotIn('method="PUT"', source_text)
        report = build_shadow_report(
            controller_state=controller_state(),
            posts=[article()],
            video_state={"items": [exact_long()]},
            short_state={"items": []},
        )
        self.assertFalse(report["would_dispatch"])
        self.assertEqual(report["mode"], "shadow")


if __name__ == "__main__":
    unittest.main()
