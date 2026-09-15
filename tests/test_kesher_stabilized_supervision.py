import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_intervention_policy as intervention


class _GitHub:
    def __init__(self):
        self.saved = []

    def save_controller_state(self, state):
        self.saved.append(state.copy())


class KesherStabilizedSupervisionTests(unittest.TestCase):
    def _controller(self):
        controller = object.__new__(stabilized.StabilizedRuntimeV5Controller)
        controller.github = _GitHub()
        controller.now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
        return controller

    def _state(self):
        slug = "school-readiness"
        sha = "a" * 64
        failure = "LONG_VIDEO_NO_DURABLE_PROGRESS"
        key = intervention.incident_key(
            pipeline_id="v5",
            slug=slug,
            content_sha256=sha,
            stage="long_video",
            failure_signature=failure,
        )
        idem = intervention.incident_idempotency_key(
            pipeline_id="v5",
            slug=slug,
            content_sha256=sha,
            stage="long_video",
            failure_signature=failure,
        )
        return key, {
            "pipeline_id": "v5",
            "cycle": "2026-09-14",
            "status": "long_video_running",
            "history": [],
            "source": {"slug": slug, "content_sha256": sha},
            "article": {"status": "complete"},
            "long_video": {
                "status": "generating",
                "task_id": "task-1",
                "provider_id": "task-1",
                "artifact_id": "artifact-1",
                "source_id": "source-1",
            },
            "short": {},
            "interventions": {
                key: {
                    "pipeline_id": "v5",
                    "slug": slug,
                    "content_sha256": sha,
                    "stage": "long_video",
                    "failure_signature": failure,
                    "idempotency_key": idem,
                    "strike_count": 2,
                    "owner": "jules",
                    "last_action": intervention.ESCALATE_JULES,
                    "last_observed_at": "2026-09-14T12:00:00+00:00",
                }
            },
        }

    def test_s2_handoff_acquires_one_exact_jules_session_and_persists_it(self):
        controller = self._controller()
        key, state = self._state()
        with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}, clear=False), patch.object(
            stabilized.incident_repair,
            "acquire_or_nudge_session",
            return_value="sessions/repair-1",
        ) as acquire:
            action = controller._handoff_to_jules(state)

        self.assertEqual(action.kind, "jules_incident_repair")
        acquire.assert_called_once()
        incident = state["interventions"][key]
        self.assertEqual(incident["owner"], "jules")
        self.assertEqual(incident["jules_repair"]["session_id"], "sessions/repair-1")
        self.assertTrue(controller.github.saved)

    def test_existing_persisted_jules_session_prevents_second_handoff(self):
        controller = self._controller()
        key, state = self._state()
        state["interventions"][key]["jules_repair"] = {
            "session_id": "sessions/repair-1",
            "idempotency_key": state["interventions"][key]["idempotency_key"],
        }
        with patch.object(stabilized.incident_repair, "acquire_or_nudge_session") as acquire:
            action = controller._handoff_to_jules(state)
        self.assertIsNone(action)
        acquire.assert_not_called()


if __name__ == "__main__":
    unittest.main()
