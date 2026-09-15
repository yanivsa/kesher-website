import unittest

import scripts.kesher_content_controller_v6_runtime as v6


class KesherV6ShadowLearningTests(unittest.TestCase):
    def _state(self, *, strike=2, owner="jules", action="escalate_jules"):
        source = {"slug": "existing-article", "content_sha256": "a" * 64}
        return {
            "pipeline_id": "v5",
            "cycle": "2026-09-14",
            "source": source,
            "status": "long_video_running",
            "article": {"live": True, "url": "https://kesher.saharoni.com/blog/existing-article"},
            "long_video": {"verified": False, "youtube_url": None},
            "short": {"verified": False, "youtube_url": None},
            "interventions": {
                "v5|existing-article|" + "a" * 64 + "|long_video|STALLED": {
                    "pipeline_id": "v5",
                    "slug": "existing-article",
                    "content_sha256": "a" * 64,
                    "stage": "long_video",
                    "failure_signature": "STALLED",
                    "idempotency_key": "b" * 64,
                    "strike_count": strike,
                    "owner": owner,
                    "last_action": action,
                    "last_observed_at": "2026-09-14T11:00:00+00:00",
                }
            },
        }

    def test_shadow_report_recommends_current_owner_without_mutation_capability(self):
        fn = getattr(v6, "v5_incident_shadow_report", None)
        self.assertIsNotNone(fn)
        if fn is None:
            return
        report = fn(self._state())
        self.assertEqual(report["observed_pipeline_id"], "v5")
        self.assertEqual(report["strike"], 2)
        self.assertEqual(report["recommended_owner"], "jules")
        self.assertEqual(report["recommended_action"], "escalate_jules")
        self.assertEqual(report["source_identity"]["slug"], "existing-article")
        self.assertEqual(report["article_url"], "https://kesher.saharoni.com/blog/existing-article")
        self.assertFalse(report["production_dispatch_enabled"])
        self.assertFalse(report["article_dispatch_enabled"])
        self.assertFalse(report["provider_dispatch_enabled"])
        self.assertFalse(report["upload_enabled"])

    def test_shadow_report_sees_strike_three_as_direct_takeover(self):
        fn = getattr(v6, "v5_incident_shadow_report", None)
        self.assertIsNotNone(fn)
        if fn is None:
            return
        report = fn(self._state(strike=3, owner="direct", action="direct_takeover"))
        self.assertEqual(report["strike"], 3)
        self.assertEqual(report["recommended_owner"], "direct")
        self.assertEqual(report["recommended_action"], "direct_takeover")
        self.assertTrue(report["direct_takeover_required"])
        self.assertFalse(report["production_dispatch_enabled"])


if __name__ == "__main__":
    unittest.main()
