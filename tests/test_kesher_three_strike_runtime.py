import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from scripts import kesher_content_controller_v5 as v5
from scripts.kesher_three_strike_runtime import ThreeStrikeMediaInterventionMixin


class _FakeGitHub:
    def __init__(self, started_at):
        self.started_at = started_at
        self.run_id = 101
        self.nudges = []
        self.cancels = []
        self.dispatches = []
        self.fingerprint = "jules-fingerprint-1"
        self.video_state = {"version": 1, "items": []}
        self.short_state = {"version": 1, "items": []}
        self.active_runs = {}

    def contents_json(self, path, ref):
        return []

    def open_article_prs(self, slot):
        return []

    def active_workflow_run(self, workflow, production_only=False):
        if workflow in self.active_runs:
            return self.active_runs[workflow]
        if workflow == v5.core.ARTICLE_WORKFLOW:
            return {
                "id": self.run_id,
                "run_started_at": self.started_at.isoformat(),
                "created_at": self.started_at.isoformat(),
            }
        return None

    def newest_video_state(self):
        return self.video_state

    def newest_short_state(self):
        return self.short_state

    def article_session_snapshot(self, slot):
        return {
            "session_id": "sessions/article-1",
            "fingerprint": self.fingerprint,
        }

    def nudge_article_session(self, session_id):
        self.nudges.append(session_id)

    def cancel_workflow_run(self, run_id):
        self.cancels.append(run_id)

    def dispatch(self, workflow, inputs):
        self.dispatches.append((workflow, inputs))
        self.run_id += 1

    def save_controller_state(self, state):
        return None


class _Harness(ThreeStrikeMediaInterventionMixin):
    PIPELINE_ID = "v5"

    def __init__(self, now):
        self.now = now
        self.github = _FakeGitHub(now - timedelta(hours=2))

    @staticmethod
    def _watchdog_candidate(snapshot, source):
        rows = [
            row
            for row in v5._exact_items(snapshot, source)
            if str(row.get("status") or "") in {"source_selected", "source_added", "generating"}
            and row.get("uploaded") is not True
        ]
        return v5._newest(rows)

    def _recover_long_video(self, state, source, item):
        self.github.dispatch(v5.LONG_VIDEO_WORKFLOW, {"operation": "full", "target_item_id": item.get("id")})
        return v5.core.Action("long_video_watchdog_recover", "resumed same long-form provider identity")

    def _recover_short(self, state, source, item, long_item):
        self.github.dispatch(v5.SHORT_WORKFLOW, {"operation": "derive", "derive_long_item_id": long_item.get("id")})
        return v5.core.Action("short_watchdog_recover", "resumed same short provider identity")


class KesherThreeStrikeRuntimeTests(unittest.TestCase):
    def _state(self):
        return {
            "cycle": "2026-09-06",
            "status": "article_generating",
            "history": [],
            "article": {
                "status": "running",
                "run_id": 101,
            },
        }

    def test_article_controller_acts_on_first_stall_then_direct_takeover_on_third_hour(self):
        state = self._state()
        harness = _Harness(datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc))

        first = harness._article_watchdog(state)
        self.assertEqual(first.kind, "article_watchdog_nudge")
        self.assertEqual(harness.github.nudges, ["sessions/article-1"])
        incident = next(iter(state["interventions"].values()))
        self.assertEqual(incident["strike_count"], 1)
        self.assertTrue(incident["controller_action_observed"])

        harness.now = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)
        second = harness._article_watchdog(state)
        self.assertEqual(second.kind, "article_watchdog_restart")
        self.assertEqual(len(harness.github.cancels), 1)
        incident = next(iter(state["interventions"].values()))
        self.assertEqual(incident["strike_count"], 2)

        harness.now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
        third = harness._article_watchdog(state)
        self.assertEqual(third.kind, "direct_takeover_required")
        self.assertTrue(state["direct_takeover_required"]["required"])
        self.assertEqual(state["direct_takeover_required"]["stage"], "article")
        self.assertEqual(len(harness.github.nudges), 1, "Strike 3 must not send another Jules nudge")

    def test_real_jules_fingerprint_progress_clears_article_takeover_sequence(self):
        state = self._state()
        harness = _Harness(datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc))
        harness._article_watchdog(state)
        incident_key = next(iter(state["interventions"]))

        harness.github.fingerprint = "jules-fingerprint-2"
        harness.now = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)
        action = harness._article_watchdog(state)

        self.assertEqual(action.kind, "wait")
        self.assertEqual(state["interventions"][incident_key]["strike_count"], 0)
        self.assertNotIn("direct_takeover_required", state)

    def test_media_watchdog_hard_timeout_interventions_across_hourly_tokens(self):
        source = {"slug": "dating-burnout", "content_sha256": "a" * 64}
        start = datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc)
        item = {
            "id": "item-attempt-3",
            "task_id": "task-uuid-1",
            "artifact_id": "task-uuid-1",
            "source": source,
            "status": "generating",
            "generation_started_at": start.isoformat(),
            "created_at": start.isoformat(),
            "last_provider_status": "pending",
            "uploaded": False,
        }
        harness = _Harness(start + timedelta(minutes=91))  # > 45 min hard timeout, hour 08:31 UTC
        harness.github.video_state = {"version": 1, "items": [item]}
        state = {
            "cycle": "2026-09-06",
            "status": "article_live",
            "history": [],
            "long_video": v5.v3._stage_template(),
            "short": v5.v3._stage_template(),
        }

        # Requirement A: Hard timeout calls intervention tracking
        # Requirement B: Hard timeout does not leave strike_count=0
        first = harness._media_watchdog_preflight(state, source)
        self.assertEqual(first.kind, "blocked")
        incident = next(iter(state["interventions"].values()))
        self.assertEqual(incident["strike_count"], 1)
        self.assertEqual(state["last_error"]["code"], "LONG_VIDEO_PROVIDER_HARD_TIMEOUT")

        # Requirement C: Multiple heartbeat ticks in the same hour do not increment strikes
        harness.now += timedelta(minutes=5)  # 08:36 UTC (same Asia/Jerusalem hour 11:xx)
        second = harness._media_watchdog_preflight(state, source)
        self.assertEqual(second.kind, "blocked")
        incident = next(iter(state["interventions"].values()))
        self.assertEqual(incident["strike_count"], 1)

        # Requirement D: Next hourly token advances strike state
        harness.now = start + timedelta(hours=2, minutes=31)  # 09:31 UTC (next hour)
        third = harness._media_watchdog_preflight(state, source)
        self.assertEqual(third.kind, "blocked")
        incident = next(iter(state["interventions"].values()))
        self.assertEqual(incident["strike_count"], 2)

        # Requirement E: Third hourly token triggers direct_takeover_required
        harness.now = start + timedelta(hours=3, minutes=31)  # 10:31 UTC (3rd hour)
        fourth = harness._media_watchdog_preflight(state, source)
        self.assertEqual(fourth.kind, "direct_takeover_required")
        self.assertTrue(state["direct_takeover_required"]["required"])
        self.assertEqual(state["direct_takeover_required"]["stage"], "long_video")

    def test_media_durable_progress_resets_intervention_strikes(self):
        source = {"slug": "dating-burnout", "content_sha256": "a" * 64}
        start = datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc)
        item = {
            "id": "item-attempt-3",
            "task_id": "task-uuid-1",
            "artifact_id": "task-uuid-1",
            "source": source,
            "status": "generating",
            "generation_started_at": start.isoformat(),
            "created_at": start.isoformat(),
            "last_provider_status": "pending",
            "uploaded": False,
        }
        harness = _Harness(start + timedelta(minutes=91))
        harness.github.video_state = {"version": 1, "items": [item]}
        state = {
            "cycle": "2026-09-06",
            "status": "article_live",
            "history": [],
            "long_video": v5.v3._stage_template(),
            "short": v5.v3._stage_template(),
        }
        harness._media_watchdog_preflight(state, source)
        incident_key = next(iter(state["interventions"]))
        self.assertEqual(state["interventions"][incident_key]["strike_count"], 1)

        # Durable progress: media resolution rendered
        item["media"] = {"width": 1920, "height": 1080}
        harness.now += timedelta(minutes=5)
        action = harness._media_watchdog_preflight(state, source)
        self.assertEqual(action.kind, "wait")
        self.assertEqual(state["interventions"][incident_key]["strike_count"], 0)
        self.assertNotIn("direct_takeover_required", state)

    def test_media_watchdog_hard_timeout_promotes_fallback_candidate(self):
        source = {"slug": "dating-burnout", "content_sha256": "a" * 64}
        start = datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc)
        second = {
            "id": "item-attempt-2",
            "fresh_generation_attempt": 2,
            "source": source,
            "status": "rejected",
            "technical_verified": False,
            "final_mp4": "item-attempt-2.mp4",
            "final_sha256": "sha-2",
            "media": {"width": 1920, "height": 1080, "duration": 120},
            "review_notes": {"technical": "נפסל טכנית: Detected male voice pitch (129.0 Hz < 155 Hz threshold); Israeli female voice required"},
            "uploaded": False,
            "updated_at": "2026-09-06T08:00:00Z",
        }
        third = {
            "id": "item-attempt-3",
            "fresh_generation_attempt": 3,
            "task_id": "task-uuid-3",
            "source": source,
            "status": "generating",
            "generation_started_at": start.isoformat(),
            "created_at": start.isoformat(),
            "last_provider_status": "pending",
            "uploaded": False,
            "updated_at": "2026-09-06T08:30:00Z",
        }
        harness = _Harness(start + timedelta(minutes=91))
        harness.github.video_state = {"version": 1, "items": [second, third]}
        state = {
            "cycle": "2026-09-06",
            "status": "article_live",
            "history": [],
            "long_video": v5.v3._stage_template(),
            "short": v5.v3._stage_template(),
        }
        action = harness._media_watchdog_preflight(state, source)
        self.assertEqual(action.kind, "long_video_watchdog_recover")
        self.assertEqual(len(harness.github.dispatches), 1)
        wf, inputs = harness.github.dispatches[0]
        self.assertEqual(wf, v5.LONG_VIDEO_WORKFLOW)
        self.assertEqual(inputs.get("target_item_id"), "item-attempt-2")

    def test_media_blocked_state_does_not_oscillate_to_article_live(self):
        from scripts.kesher_content_controller_stabilized import StabilizedRuntimeV5Controller

        class MockSite:
            def get(self, url):
                return (200, "<html><head><title>why-cant-i-find-a-relationship</title><meta name=\"article-content-sha256\" content=\"60a0e246\"></head><body><h1>why-cant-i-find-a-relationship</h1></body></html>")

        gh = _FakeGitHub(datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc))
        ctrl = StabilizedRuntimeV5Controller(gh, MockSite(), now=datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc))

        state = {
            "cycle": "2026-10-16",
            "status": "blocked",
            "article": {"slug": "why-cant-i-find-a-relationship", "title": "why-cant-i-find-a-relationship", "quality_content_sha256": "60a0e246"},
            "long_video": {"status": "blocked"},
            "last_error": {"stage": "long_video", "code": "LONG_VIDEO_PROVIDER_HARD_TIMEOUT"},
            "history": [],
        }

        with mock.patch("scripts.kesher_content_controller.article_is_public", return_value=True):
            is_pub, action = ctrl._ensure_article_public_and_deployed(state)

        self.assertTrue(is_pub)
        self.assertIsNone(action)
        # Status MUST remain blocked, NOT oscillate to article_live!
        self.assertEqual(state.get("status"), "blocked")

    def test_dispatch_allows_recovery_with_target_item_id_even_at_attempt_limit(self):
        from scripts.kesher_content_controller_stabilized import StabilizedRuntimeV5Controller
        gh = _FakeGitHub(datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc))
        ctrl = StabilizedRuntimeV5Controller(gh, None, now=datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc))

        state = {
            "cycle": "2026-10-16",
            "long_video": {"attempt_count": 3, "status": "blocked"},
            "pending_dispatches": {},
            "history": [],
        }
        ctrl._active_state_ref = state

        # When target_item_id is provided, recovery dispatch MUST be permitted even at attempt limit
        recovery_inputs = {"operation": "full", "target_item_id": "item-attempt-3"}
        dispatched = []
        ctrl._guarded_dispatch(state, v5.LONG_VIDEO_WORKFLOW, recovery_inputs, lambda wf, inp: dispatched.append((wf, inp)))
        self.assertEqual(len(dispatched), 1)

        # But a fresh generation without target_item_id MUST still be rejected
        fresh_inputs = {"operation": "full"}
        with self.assertRaises(v5.core.ControllerError) as ctx:
            ctrl._guarded_dispatch(state, v5.LONG_VIDEO_WORKFLOW, fresh_inputs, lambda wf, inp: dispatched.append((wf, inp)))
        self.assertIn("VIDEO_ATTEMPTS_EXHAUSTED", str(ctx.exception))

    def test_repeated_heartbeat_is_idempotent(self):
        source = {"slug": "dating-burnout", "content_sha256": "a" * 64}
        start = datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc)
        item = {
            "id": "item-attempt-3",
            "task_id": "task-uuid-1",
            "artifact_id": "task-uuid-1",
            "source": source,
            "status": "generating",
            "generation_started_at": start.isoformat(),
            "created_at": start.isoformat(),
            "last_provider_status": "pending",
            "uploaded": False,
        }
        harness = _Harness(start + timedelta(minutes=10))  # Not timed out yet (< 15 min idle)
        harness.github.video_state = {"version": 1, "items": [item]}
        state = {
            "cycle": "2026-09-06",
            "status": "article_live",
            "history": [],
            "long_video": v5.v3._stage_template(),
            "short": v5.v3._stage_template(),
        }

        # First tick returns wait
        action1 = harness._media_watchdog_preflight(state, source)
        self.assertEqual(action1.kind, "wait")
        self.assertEqual(len(harness.github.dispatches), 0)

        # Second tick 5 min later with unchanged state returns identical wait, no dispatches
        harness.now += timedelta(minutes=2)
        action2 = harness._media_watchdog_preflight(state, source)
        self.assertEqual(action2.kind, "wait")
        self.assertEqual(len(harness.github.dispatches), 0)

    def test_persisted_youtube_id_prevents_duplicate_upload(self):
        source = {"slug": "dating-burnout", "content_sha256": "a" * 64}
        start = datetime(2026, 9, 6, 7, 0, tzinfo=timezone.utc)
        item = {
            "id": "item-attempt-3",
            "task_id": "task-uuid-1",
            "artifact_id": "task-uuid-1",
            "source": source,
            "status": "uploaded",
            "uploaded": True,
            "youtube_id": "6j-doosfuRk",
            "youtube_url": "https://youtu.be/6j-doosfuRk",
            "technical_verified": True,
            "created_at": start.isoformat(),
        }
        harness = _Harness(start + timedelta(minutes=30))
        harness.github.video_state = {"version": 1, "items": [item]}
        state = {
            "cycle": "2026-09-06",
            "status": "article_live",
            "history": [],
            "long_video": v5.v3._stage_template(),
            "short": v5.v3._stage_template(),
        }

        # Item is already uploaded with YouTube ID; watchdog preflight does NOT dispatch long video
        action = harness._media_watchdog_preflight(state, source)
        # Should either be None (long verified, moves to short) or not dispatch long
        self.assertEqual(len(harness.github.dispatches), 0)


if __name__ == "__main__":
    unittest.main()
