import importlib
import importlib.util
import unittest
from unittest.mock import patch


MODULE = "scripts.kesher_jules_incident_repair"


class KesherJulesIncidentRepairTests(unittest.TestCase):
    def _module(self):
        spec = importlib.util.find_spec(MODULE)
        self.assertIsNotNone(spec, "Jules incident repair adapter must exist")
        return importlib.import_module(MODULE)

    def test_deterministic_session_title_uses_incident_idempotency_key(self):
        module = self._module()
        title = module.incident_session_title("a" * 64)
        self.assertEqual(title, "Kesher incident " + "a" * 16)

    def test_prompt_is_exact_identity_bound_and_forbids_duplicate_generation(self):
        module = self._module()
        prompt = module.build_repair_prompt(
            pipeline_id="v5",
            slug="school-readiness",
            content_sha256="b" * 64,
            stage="long_video",
            failure_signature="NOTEBOOKLM_PROVIDER_STALLED",
            idempotency_key="c" * 64,
            evidence={
                "source_id": "source-1",
                "task_id": "task-1",
                "artifact_id": "artifact-1",
            },
        )
        self.assertIn("school-readiness", prompt)
        self.assertIn("NOTEBOOKLM_PROVIDER_STALLED", prompt)
        self.assertIn("source-1", prompt)
        self.assertIn("task-1", prompt)
        self.assertIn("artifact-1", prompt)
        self.assertIn("Do NOT create a new article", prompt)
        self.assertIn("Do NOT start a new NotebookLM provider generation", prompt)
        self.assertIn("Do NOT upload a new YouTube video", prompt)
        self.assertIn("at most ONE repair PR", prompt)

    def test_reuses_one_existing_active_exact_incident_session(self):
        module = self._module()
        existing = {
            "name": "sessions/existing-1",
            "title": module.incident_session_title("d" * 64),
            "state": "IN_PROGRESS",
        }
        with patch.object(module, "list_exact_incident_sessions", return_value=[existing]), patch.object(
            module, "send_message"
        ) as send, patch.object(module, "create_session") as create:
            session = module.acquire_or_nudge_session(
                api_key="key",
                idempotency_key="d" * 64,
                prompt="repair exact incident",
            )
        self.assertEqual(session, "sessions/existing-1")
        send.assert_called_once()
        create.assert_not_called()

    def test_recovers_completed_exact_session_without_creating_or_nudging(self):
        module = self._module()
        existing = {
            "name": "sessions/completed-1",
            "title": module.incident_session_title("f" * 64),
            "state": "COMPLETED",
        }
        with patch.object(module, "list_exact_incident_sessions", return_value=[existing]), patch.object(
            module, "send_message"
        ) as send, patch.object(module, "create_session") as create:
            session = module.acquire_or_nudge_session(
                api_key="key",
                idempotency_key="f" * 64,
                prompt="repair exact incident",
            )
        self.assertEqual(session, "sessions/completed-1")
        send.assert_not_called()
        create.assert_not_called()

    def test_recovers_terminal_failure_exact_session_without_second_creation(self):
        module = self._module()
        existing = {
            "name": "sessions/failed-1",
            "title": module.incident_session_title("1" * 64),
            "state": "FAILED",
        }
        with patch.object(module, "list_exact_incident_sessions", return_value=[existing]), patch.object(
            module, "send_message"
        ) as send, patch.object(module, "create_session") as create:
            session = module.acquire_or_nudge_session(
                api_key="key",
                idempotency_key="1" * 64,
                prompt="repair exact incident",
            )
        self.assertEqual(session, "sessions/failed-1")
        send.assert_not_called()
        create.assert_not_called()

    def test_duplicate_exact_incident_sessions_fail_closed_even_if_one_is_terminal(self):
        module = self._module()
        title = module.incident_session_title("e" * 64)
        rows = [
            {"name": "sessions/one", "title": title, "state": "COMPLETED"},
            {"name": "sessions/two", "title": title, "state": "IN_PROGRESS"},
        ]
        with patch.object(module, "list_exact_incident_sessions", return_value=rows):
            with self.assertRaisesRegex(module.IncidentRepairError, "duplicate"):
                module.acquire_or_nudge_session(
                    api_key="key",
                    idempotency_key="e" * 64,
                    prompt="repair exact incident",
                )


if __name__ == "__main__":
    unittest.main()
