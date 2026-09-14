import inspect
import unittest
from datetime import datetime, timezone

import scripts.kesher_intervention_policy as intervention


NOW = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)
FAILURE = "PROVIDER_STALLED:generation"


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

    def _observe(self, **kwargs):
        # Keep the RED test runnable against the previous API. Once the new
        # parameter exists, every behavior test exercises it explicitly.
        if "failure_signature" in inspect.signature(intervention.observe_incident).parameters:
            kwargs.setdefault("failure_signature", FAILURE)
        return intervention.observe_incident(**kwargs)

    def test_incident_identity_requires_failure_signature(self):
        parameters = inspect.signature(intervention.incident_key).parameters
        self.assertIn("failure_signature", parameters)

    def test_three_distinct_checks_escalate_controller_jules_direct(self):
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

        first = self._observe(check_token="2026-09-06T12", controller_action_token=None, **kwargs)
        second = self._observe(check_token="2026-09-06T13", controller_action_token=None, **kwargs)
        third = self._observe(check_token="2026-09-06T14", controller_action_token=None, **kwargs)

        self.assertEqual((first.strike, first.action), (1, intervention.OBSERVE_CONTROLLER))
        self.assertEqual((second.strike, second.action), (2, getattr(intervention, "ESCALATE_JULES", None)))
        self.assertEqual((third.strike, third.action), (3, intervention.DIRECT_TAKEOVER))

    def test_controller_action_does_not_suppress_second_hour_jules_escalation(self):
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
        first = self._observe(check_token="h1", controller_action_token=None, **base)
        intervention.mark_controller_action(
            state,
            incident_key=first.incident_key,
            action_token="controller-recovery-1",
            now=NOW,
        )
        second = self._observe(check_token="h2", controller_action_token="controller-recovery-1", **base)
        self.assertEqual((second.strike, second.action), (2, getattr(intervention, "ESCALATE_JULES", None)))

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
        first = self._observe(**kwargs)
        repeated_poll = self._observe(**kwargs)
        self.assertEqual(first.strike, 1)
        self.assertEqual(repeated_poll.strike, 1)
        self.assertEqual(repeated_poll.action, intervention.OBSERVE_CONTROLLER)

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
        self._observe(progress=self._progress(), check_token="h1", **base)
        self._observe(progress=self._progress(), check_token="h2", **base)
        progressed = self._observe(
            progress=self._progress(status="processing", artifact_id="artifact-7"),
            check_token="h3",
            **base,
        )
        self.assertEqual(progressed.strike, 0)
        self.assertTrue(progressed.progress_reset)

        stalled_again = self._observe(
            progress=self._progress(status="processing", artifact_id="artifact-7"),
            check_token="h4",
            **base,
        )
        self.assertEqual((stalled_again.strike, stalled_again.action), (1, intervention.OBSERVE_CONTROLLER))

    def test_timestamp_and_workflow_success_are_not_durable_progress(self):
        first = self._progress(updated_at="2026-09-06T09:00:00Z", workflow_conclusion="failure")
        second = self._progress(updated_at="2026-09-06T10:00:00Z", workflow_conclusion="success")
        self.assertEqual(
            intervention.durable_progress_fingerprint(first),
            intervention.durable_progress_fingerprint(second),
        )

    def test_failure_signature_change_starts_a_new_incident(self):
        self.assertIn("failure_signature", inspect.signature(intervention.observe_incident).parameters)
        if "failure_signature" not in inspect.signature(intervention.observe_incident).parameters:
            return
        state = {}
        common = dict(
            state=state,
            pipeline_id="v5",
            slug="late-singlehood-regrets",
            content_sha256="abc123",
            stage="long_video",
            progress=self._progress(),
            now=NOW,
            controller_action_token=None,
        )
        first = intervention.observe_incident(failure_signature="PROVIDER_STALLED", check_token="h1", **common)
        second = intervention.observe_incident(failure_signature="PROVIDER_STALLED", check_token="h2", **common)
        changed = intervention.observe_incident(failure_signature="YOUTUBE_PROCESSING_FAILED", check_token="h3", **common)
        self.assertEqual((first.strike, second.strike, changed.strike), (1, 2, 1))
        self.assertNotEqual(first.incident_key, changed.incident_key)

    def test_idempotency_key_is_stable_for_exact_incident_and_changes_with_failure(self):
        fn = getattr(intervention, "incident_idempotency_key", None)
        self.assertIsNotNone(fn)
        if fn is None:
            return
        common = dict(pipeline_id="v5", slug="slug", content_sha256="sha", stage="short")
        one = fn(failure_signature="SHORT_STALLED", **common)
        again = fn(failure_signature="SHORT_STALLED", **common)
        changed = fn(failure_signature="SHORT_UPLOAD_FAILED", **common)
        self.assertEqual(one, again)
        self.assertNotEqual(one, changed)
        self.assertRegex(one, r"^[0-9a-f]{64}$")

    def test_pipeline_sha_stage_and_failure_are_isolated_incidents(self):
        self.assertIn("failure_signature", inspect.signature(intervention.observe_incident).parameters)
        if "failure_signature" not in inspect.signature(intervention.observe_incident).parameters:
            return
        state = {}
        common = dict(
            state=state,
            slug="late-singlehood-regrets",
            progress=self._progress(),
            now=NOW,
            controller_action_token=None,
            check_token="h1",
        )
        rows = [
            intervention.observe_incident(pipeline_id="v5", content_sha256="abc123", stage="long_video", failure_signature="A", **common),
            intervention.observe_incident(pipeline_id="v6", content_sha256="abc123", stage="long_video", failure_signature="A", **common),
            intervention.observe_incident(pipeline_id="v5", content_sha256="def456", stage="long_video", failure_signature="A", **common),
            intervention.observe_incident(pipeline_id="v5", content_sha256="abc123", stage="short", failure_signature="A", **common),
            intervention.observe_incident(pipeline_id="v5", content_sha256="abc123", stage="long_video", failure_signature="B", **common),
        ]
        self.assertEqual([row.strike for row in rows], [1, 1, 1, 1, 1])
        self.assertEqual(len(state["interventions"]), 5)


if __name__ == "__main__":
    unittest.main()
