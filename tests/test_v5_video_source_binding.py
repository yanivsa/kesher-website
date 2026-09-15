from __future__ import annotations

import copy
import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_content_controller_v5 as v5
from tests.test_v5_shared_video_controller import FakeGitHub, FakeSite, article


TZ = ZoneInfo("Asia/Jerusalem")


class V5VideoSourceBindingTests(unittest.TestCase):
    def test_current_cycle_long_video_dispatch_binds_authoritative_slug_even_with_stale_provider_backlog(self):
        gh = FakeGitHub()
        stale_source = v5.article_source_identity(article("stale-article"))
        gh.long_state["items"] = [{
            "id": "video-stale",
            "status": "generating",
            "uploaded": False,
            "source": copy.deepcopy(stale_source),
            "source_id": "source-stale",
            "task_id": "task-stale",
            "artifact_id": "task-stale",
            "created_at": "2026-08-18T10:00:00Z",
        }]
        controller = stabilized.StabilizedRuntimeV5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 19, 19, 0, tzinfo=TZ),
        )

        with mock.patch.object(stabilized.quality, "article_violations", return_value=[]), mock.patch.object(
            controller, "_overview_evidence_preflight", return_value=None
        ), mock.patch.object(
            controller, "_verified_long_from_artifact_history", return_value=None
        ):
            state, action = controller.tick()

        self.assertEqual(action.kind, "dispatch_long_video")
        self.assertEqual(
            gh.dispatches,
            [(v5.LONG_VIDEO_WORKFLOW, {"operation": "full", "target_slug": "today-article"})],
        )
        self.assertEqual(state["article"]["slug"], "today-article")
        self.assertEqual(state["long_video"]["attempt_count"], 1)
        self.assertIsNone(state["long_video"].get("provider_id"))
        self.assertIsNone(state["long_video"].get("artifact_id"))
        self.assertIsNone(state["long_video"].get("source_id"))
        self.assertNotEqual(state["long_video"].get("item_id"), "video-stale")

    def test_proven_stale_source_binding_exhaustion_resets_once_for_exact_current_item(self):
        gh = FakeGitHub()
        controller = stabilized.StabilizedRuntimeV5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 19, 19, 0, tzinfo=TZ),
        )
        source = v5.article_source_identity(article())
        stale_source = v5.article_source_identity(article("stale-article"))
        gh.long_state["items"] = [
            {
                "id": "video-stale",
                "status": "generating",
                "uploaded": False,
                "source": copy.deepcopy(stale_source),
                "source_id": "source-stale",
                "task_id": "task-stale",
                "artifact_id": "task-stale",
            },
            {
                "id": "video-current",
                "status": "pending_review",
                "uploaded": False,
                "source": copy.deepcopy(source),
                "source_id": "source-current",
                "task_id": "task-current",
                "artifact_id": "task-current",
            },
        ]

        initial = controller.state()
        initial["status"] = "blocked"
        initial["last_error"] = {
            "stage": "long_video",
            "code": "VIDEO_ATTEMPTS_EXHAUSTED",
            "message": "historical stale binding exhausted budget",
        }
        initial["long_video"].update({
            "attempt_count": 3,
            "status": "exhausted",
            "run_id": 99,
            "processed_run_id": 99,
            "item_id": "video-stale",
            "provider_id": "task-stale",
            "artifact_id": "task-stale",
            "source_id": "source-stale",
            "resume_dispatches": 5,
            "watchdog": {"identity": "current", "last_progress_at": "old"},
        })
        gh.saved_state = copy.deepcopy(initial)

        recovered = controller.state()
        long_video = recovered["long_video"]
        self.assertEqual(recovered["status"], "article_live")
        self.assertIsNone(recovered["last_error"])
        self.assertTrue(long_video["source_binding_exhaustion_recovery_applied"])
        self.assertEqual(long_video["attempt_count"], 0)
        self.assertEqual(long_video["status"], "pending")
        self.assertIsNone(long_video["item_id"])
        self.assertIsNone(long_video["provider_id"])
        self.assertIsNone(long_video["artifact_id"])
        self.assertIsNone(long_video["source_id"])
        self.assertNotIn("watchdog", long_video)
        self.assertEqual(
            long_video["source_binding_recovery_previous"]["item_id"],
            "video-stale",
        )
        recovery_events = [
            row for row in recovered["history"]
            if row.get("reason") == "source_binding_exhaustion_recovery"
        ]
        self.assertEqual(len(recovery_events), 1)
        self.assertEqual(recovery_events[0]["details"]["exact_item_id"], "video-current")

        gh.saved_state = copy.deepcopy(recovered)
        recovered_again = controller.state()
        recovery_events_again = [
            row for row in recovered_again["history"]
            if row.get("reason") == "source_binding_exhaustion_recovery"
        ]
        self.assertEqual(len(recovery_events_again), 1)
        self.assertEqual(recovered_again["long_video"]["attempt_count"], 0)

    def test_legitimate_exact_source_exhaustion_is_not_reset(self):
        gh = FakeGitHub()
        controller = stabilized.StabilizedRuntimeV5Controller(
            gh,
            FakeSite(),
            now=datetime(2026, 8, 19, 19, 0, tzinfo=TZ),
        )
        source = v5.article_source_identity(article())
        gh.long_state["items"] = [{
            "id": "video-current",
            "status": "pending_review",
            "uploaded": False,
            "source": copy.deepcopy(source),
            "source_id": "source-current",
            "task_id": "task-current",
            "artifact_id": "task-current",
        }]
        initial = controller.state()
        initial["status"] = "blocked"
        initial["last_error"] = {
            "stage": "long_video",
            "code": "VIDEO_ATTEMPTS_EXHAUSTED",
            "message": "real current-source exhaustion",
        }
        initial["long_video"].update({
            "attempt_count": 3,
            "status": "exhausted",
            "item_id": "video-current",
            "provider_id": "task-current",
            "artifact_id": "task-current",
            "source_id": "source-current",
        })
        gh.saved_state = initial

        unchanged = controller.state()
        self.assertEqual(unchanged["status"], "blocked")
        self.assertEqual(unchanged["long_video"]["attempt_count"], 3)
        self.assertNotIn("source_binding_exhaustion_recovery_applied", unchanged["long_video"])


if __name__ == "__main__":
    unittest.main()
