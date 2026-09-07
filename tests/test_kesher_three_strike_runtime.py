import unittest
from datetime import datetime, timedelta, timezone

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

    def contents_json(self, path, ref):
        return []

    def open_article_prs(self, slot):
        return []

    def active_workflow_run(self, workflow, production_only=False):
        return {
            "id": self.run_id,
            "run_started_at": self.started_at.isoformat(),
            "created_at": self.started_at.isoformat(),
        }

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

    def test_prepublication_article_identity_is_stable_and_pipeline_scoped(self):
        source = _Harness._article_intervention_source("2026-09-06")
        self.assertEqual(source["slug"], "article-slot-2026-09-06")
        self.assertEqual(len(source["content_sha256"]), 64)
        int(source["content_sha256"], 16)


if __name__ == "__main__":
    unittest.main()
