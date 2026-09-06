import unittest
from datetime import datetime, timezone

from scripts.kesher_intervention_policy import (
    DIRECT_TAKEOVER,
    FORCE_CONTROLLER_RECOVERY,
    OBSERVE_CONTROLLER,
    WAIT_AFTER_CONTROLLER_ACTION,
    durable_progress_fingerprint,
    mark_controller_action,
    observe_incident,
)


NOW = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)


class KesherInterventionPolicyTests(unittest.TestCase):
    def _progress(self, **overrides):
        progress = {
            "status": "generating",
            "slug": "late-singlehood-regrets",
            "content_sha256": "abc123",
            "task_id": "provider-1",
            "artifact_id": None,
            "youtube_url": None,
            "verified": False,
        }
        progress.update(overrides)
        return progress

    def test_three_distinct_checks_escalate_observe_recovery_takeover(self):
        state = {}
        kwargs = dict(
            state=state,
            pipeline_id="v5",
            slug="late-singlehood-regrets",
            content_sha256="abc123",
            stage="long_video",
            progress=self._progress(),
            now=NOW,
        )

        first = observe_incident(check_token="2026-09-06T12", controller_action_token=None, **kwargs)
        second = observe_incident(check_token="2026-09-06T13", controller_action_token=None, **kwargs)
        third = observe_incident(check_token="2026-09-06T14", controller_action_token=None, **kwargs)

        self.assertEqual((first.strike, first.action), (1, OBSERVE_CONTROLLER))
        self.assertEqual((second.strike, second.action), (2, FORCE_CONTROLLER_RECOVERY))
        self.assertEqual((third.strike, third.action), (3, DIRECT_TAKEOVER))

    def test_same_hour_poll_does_not_increment_strike(self):
        state = {}
        kwargs = dict(
            state=state,
            pipeline_id="v5",
            slug="late-singlehood-regrets",
            content_sha256="abc123",
            stage="short",
            progress=self._progress(status="rendering"),
            now=NOW,
            check_token="2026-09-06T12",
            controller_action_token=None,
        )
        first = observe_incident(**kwargs)
        repeated_poll = observe_incident(**kwargs)
        self.assertEqual(first.strike, 1)
        self.assertEqual(repeated_poll.strike, 1)
        self.assertEqual(repeated_poll.action, OBSERVE_CONTROLLER)

    def test_real_progress_resets_strikes(self):
        state = {}
        base = dict(
            state=state,
            pipeline_id="v5",
            slug="late-singlehood-regrets",
            content_sha256="abc123",
            stage="long_video",
            now=NOW,
            controller_action_token=None,
        )
        observe_incident(progress=self._progress(), check_token="h1", **base)
        observe_incident(progress=self._progress(), check_token="h2", **base)
        progressed = observe_incident(
            progress=self._progress(status="processing", artifact_id="artifact-7"),
            check_token="h3",
            **base,
        )
        self.assertEqual(progressed.strike, 0)
        self.assertTrue(progressed.progress_reset)

        stalled_again = observe_incident(
            progress=self._progress(status="processing", artifact_id="artifact-7"),
            check_token="h4",
            **base,
        )
        self.assertEqual((stalled_again.strike, stalled_again.action), (1, OBSERVE_CONTROLLER))

    def test_timestamp_and_workflow_success_are_not_durable_progress(self):
        first = self._progress(updated_at="2026-09-06T09:00:00Z", workflow_conclusion="failure")
        second = self._progress(updated_at="2026-09-06T10:00:00Z", workflow_conclusion="success")
        self.assertEqual(durable_progress_fingerprint(first), durable_progress_fingerprint(second))

    def test_controller_action_on_second_check_is_not_duplicated(self):
        state = {}
        base = dict(
            state=state,
            pipeline_id="v5",
            slug="late-singlehood-regrets",
            content_sha256="abc123",
            stage="short",
            progress=self._progress(status="rendering"),
            now=NOW,
        )
        observe_incident(check_token="h1", controller_action_token="recovery-0", **base)
        second = observe_incident(check_token="h2", controller_action_token="recovery-1", **base)
        self.assertEqual((second.strike, second.action), (2, WAIT_AFTER_CONTROLLER_ACTION))

    def test_forced_recovery_is_marked_so_same_check_cannot_dispatch_twice(self):
        state = {}
        base = dict(
            state=state,
            pipeline_id="v5",
            slug="late-singlehood-regrets",
            content_sha256="abc123",
            stage="short",
            progress=self._progress(status="rendering"),
            now=NOW,
        )
        observe_incident(check_token="h1", controller_action_token=None, **base)
        second = observe_incident(check_token="h2", controller_action_token=None, **base)
        self.assertEqual(second.action, FORCE_CONTROLLER_RECOVERY)
        mark_controller_action(state, incident_key=second.incident_key, action_token="dispatch-17", now=NOW)
        same_check = observe_incident(check_token="h2", controller_action_token="dispatch-17", **base)
        self.assertEqual((same_check.strike, same_check.action), (2, WAIT_AFTER_CONTROLLER_ACTION))

    def test_pipeline_sha_and_stage_are_isolated_incidents(self):
        state = {}
        common = dict(
            state=state,
            slug="late-singlehood-regrets",
            progress=self._progress(),
            now=NOW,
            controller_action_token=None,
        )
        v5 = observe_incident(
            pipeline_id="v5", content_sha256="abc123", stage="long_video", check_token="h1", **common
        )
        v6 = observe_incident(
            pipeline_id="v6", content_sha256="abc123", stage="long_video", check_token="h1", **common
        )
        other_sha = observe_incident(
            pipeline_id="v5", content_sha256="def456", stage="long_video", check_token="h1", **common
        )
        other_stage = observe_incident(
            pipeline_id="v5", content_sha256="abc123", stage="short", check_token="h1", **common
        )
        self.assertEqual([v5.strike, v6.strike, other_sha.strike, other_stage.strike], [1, 1, 1, 1])
        self.assertEqual(len(state["interventions"]), 4)


if __name__ == "__main__":
    unittest.main()
