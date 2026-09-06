import unittest
from datetime import datetime, timezone

from scripts.kesher_content_controller_v6_runtime import (
    ARTIFACT_NAMESPACE,
    PIPELINE_ID,
    STATE_REF,
    V6InterventionReconciler,
)
from scripts.kesher_intervention_policy import DIRECT_TAKEOVER, FORCE_CONTROLLER_RECOVERY, OBSERVE_CONTROLLER


class KesherV6InterventionIsolationTests(unittest.TestCase):
    def test_v6_has_isolated_identity_and_state_namespace(self):
        self.assertEqual(PIPELINE_ID, "v6")
        self.assertEqual(STATE_REF, "automation-state-v6")
        self.assertEqual(ARTIFACT_NAMESPACE, "kesher-v6")

    def test_v6_uses_same_three_check_contract_without_sharing_v5_incident(self):
        state = {}
        reconciler = V6InterventionReconciler(state)
        progress = {
            "status": "generating",
            "slug": "v6-article",
            "content_sha256": "v6sha",
            "task_id": "v6-provider-1",
        }
        now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)

        one = reconciler.observe(
            slug="v6-article", content_sha256="v6sha", stage="long_video",
            progress=progress, check_token="h1", controller_action_token=None, now=now,
        )
        two = reconciler.observe(
            slug="v6-article", content_sha256="v6sha", stage="long_video",
            progress=progress, check_token="h2", controller_action_token=None, now=now,
        )
        three = reconciler.observe(
            slug="v6-article", content_sha256="v6sha", stage="long_video",
            progress=progress, check_token="h3", controller_action_token=None, now=now,
        )

        self.assertEqual((one.action, two.action, three.action), (
            OBSERVE_CONTROLLER, FORCE_CONTROLLER_RECOVERY, DIRECT_TAKEOVER
        ))
        self.assertIn("v6|v6-article|v6sha|long_video", state["interventions"])
        self.assertNotIn("v5|v6-article|v6sha|long_video", state["interventions"])


if __name__ == "__main__":
    unittest.main()
