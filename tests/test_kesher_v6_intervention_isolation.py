import unittest
from datetime import datetime, timezone

from scripts.kesher_content_controller_v6_runtime import (
    ARTIFACT_NAMESPACE,
    CANARY_MODE_SHADOW,
    PIPELINE_ID,
    STATE_REF,
    V6InterventionReconciler,
    shadow_canary_report,
)
from scripts.kesher_intervention_policy import DIRECT_TAKEOVER, FORCE_CONTROLLER_RECOVERY, OBSERVE_CONTROLLER


class KesherV6InterventionIsolationTests(unittest.TestCase):
    def test_v6_has_isolated_identity_and_state_namespace(self):
        self.assertEqual(PIPELINE_ID, "v6")
        self.assertEqual(STATE_REF, "automation-state-v6")
        self.assertEqual(ARTIFACT_NAMESPACE, "kesher-v6")

    def test_v6_shadow_canary_is_bound_to_exact_identity_and_cannot_dispatch(self):
        report = shadow_canary_report(
            slug="existing-article",
            content_sha256="exact-content-sha",
            stage="long_video",
            progress={"status": "complete", "youtube_url": "https://youtu.be/example"},
        )

        self.assertEqual(report["canary_mode"], CANARY_MODE_SHADOW)
        self.assertEqual(report["identity"], {
            "slug": "existing-article",
            "content_sha256": "exact-content-sha",
            "stage": "long_video",
        })
        self.assertFalse(report["production_dispatch_enabled"])
        self.assertFalse(report["article_dispatch_enabled"])
        self.assertFalse(report["provider_dispatch_enabled"])
        self.assertFalse(report["upload_enabled"])

    def test_v6_shadow_canary_fails_closed_without_exact_identity(self):
        for field, kwargs in (
            ("slug", {"slug": "", "content_sha256": "sha", "stage": "short"}),
            ("content_sha256", {"slug": "slug", "content_sha256": "", "stage": "short"}),
            ("stage", {"slug": "slug", "content_sha256": "sha", "stage": ""}),
        ):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, field):
                    shadow_canary_report(**kwargs)

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

    def test_v6_article_stage_uses_the_same_bounded_takeover_contract(self):
        state = {}
        reconciler = V6InterventionReconciler(state)
        progress = {
            "stage": "article",
            "status": "article_session",
            "slug": "article-slot-2026-09-06",
            "content_sha256": "prepub-sha",
            "task_id": "v6-jules-session",
            "source_id": "jules-fingerprint-1",
        }
        now = datetime(2026, 9, 6, 9, 0, tzinfo=timezone.utc)

        one = reconciler.observe(
            slug=progress["slug"], content_sha256=progress["content_sha256"], stage="article",
            progress=progress, check_token="h1", controller_action_token=None, now=now,
        )
        two = reconciler.observe(
            slug=progress["slug"], content_sha256=progress["content_sha256"], stage="article",
            progress=progress, check_token="h2", controller_action_token=None, now=now,
        )
        three = reconciler.observe(
            slug=progress["slug"], content_sha256=progress["content_sha256"], stage="article",
            progress=progress, check_token="h3", controller_action_token=None, now=now,
        )
        self.assertEqual((one.action, two.action, three.action), (
            OBSERVE_CONTROLLER, FORCE_CONTROLLER_RECOVERY, DIRECT_TAKEOVER
        ))
        self.assertIn("v6|article-slot-2026-09-06|prepub-sha|article", state["interventions"])


if __name__ == "__main__":
    unittest.main()
