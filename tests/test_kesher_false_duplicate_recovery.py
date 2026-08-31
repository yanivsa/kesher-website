import copy
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_v3_best_effort as controller


TZ = ZoneInfo("Asia/Jerusalem")


class FakeGitHub:
    def __init__(self, state):
        self._state = copy.deepcopy(state)

    def load_controller_state(self):
        return copy.deepcopy(self._state)


class FalseDuplicateRecoveryTests(unittest.TestCase):
    def _blocked_state(self):
        return {
            "schema_version": 3,
            "cycle": "2026-08-31",
            "status": "blocked",
            "article": {
                "attempt_count": 3,
                "attempts": 3,
                "status": "exhausted",
                "last_error": {
                    "stage": "article",
                    "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
                },
                "last_worker_result": {
                    "slot": "2026-08-31",
                    "outcome": "DUPLICATE_ARTICLE_PRS",
                    "session_id": "",
                    "pr_url": "",
                },
            },
            "image": {},
            "video": {},
            "backlog": [{"cycle": "2026-08-30", "status": "blocked"}],
            "last_error": {
                "stage": "article",
                "code": "ARTICLE_ATTEMPTS_EXHAUSTED",
            },
            "history": [{"reason": "preexisting_history"}],
        }

    def test_false_duplicate_exhaustion_recovers_once_without_losing_backlog(self):
        github = FakeGitHub(self._blocked_state())
        instance = controller.BestEffortController(
            github,
            object(),
            now=datetime(2026, 8, 31, 10, 0, tzinfo=TZ),
        )

        state = instance.state()

        self.assertEqual(state["status"], "article_needed")
        self.assertEqual(state["article"]["attempt_count"], 0)
        self.assertEqual(state["article"]["attempts"], 0)
        self.assertEqual(state["article"]["status"], "pending")
        self.assertIsNone(state["last_error"])
        self.assertTrue(state["article"][controller.FALSE_DUPLICATE_RECOVERY_MARKER])
        self.assertEqual(state["backlog"], [{"cycle": "2026-08-30", "status": "blocked"}])
        self.assertEqual(state["history"][0]["reason"], "preexisting_history")
        self.assertEqual(state["history"][-1]["reason"], "slot_scoped_duplicate_guard_recovery")

    def test_does_not_reset_when_worker_created_a_session(self):
        payload = self._blocked_state()
        payload["article"]["last_worker_result"]["session_id"] = "sessions/123"
        github = FakeGitHub(payload)
        instance = controller.BestEffortController(
            github,
            object(),
            now=datetime(2026, 8, 31, 10, 0, tzinfo=TZ),
        )

        state = instance.state()

        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["article"]["attempt_count"], 3)
        self.assertNotIn(controller.FALSE_DUPLICATE_RECOVERY_MARKER, state["article"])


if __name__ == "__main__":
    unittest.main()
