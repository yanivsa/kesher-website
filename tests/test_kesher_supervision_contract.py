import unittest

import scripts.kesher_automation_policy as policy_module


class KesherSupervisionContractTests(unittest.TestCase):
    def test_production_contract_declares_fixed_supervision_policy(self):
        policy = policy_module.load_policy()
        supervision = policy.get("supervision")
        self.assertIsInstance(supervision, dict)
        self.assertEqual(supervision.get("incident_fingerprint_version"), 2)
        self.assertEqual(supervision.get("strike_interval_minutes"), 60)
        self.assertEqual(supervision.get("external_running_hard_timeout_minutes"), 90)
        self.assertEqual(supervision.get("escalation"), ["controller", "jules", "direct"])
        self.assertEqual(
            supervision.get("stage_sla_minutes"),
            {"article": 60, "long_video": 90, "short": 90},
        )
        self.assertEqual(
            supervision.get("prompt_versions"),
            {"controller_recovery": 1, "jules_incident_repair": 1},
        )
        self.assertTrue(supervision.get("actionable_safe_work_must_execute"))
        self.assertFalse(supervision.get("report_only_when_action_available"))
        self.assertTrue(supervision.get("direct_takeover_requires_action_before_report"))
        self.assertTrue(supervision.get("post_repair_recovery_required"))
        image_failure = supervision.get("article_image_guard_failure")
        self.assertEqual(image_failure.get("action"), "repair_same_pr_or_dispatch_trusted_image")
        self.assertFalse(image_failure.get("duplicate_article_or_pr_allowed"))
        self.assertFalse(image_failure.get("waiting_without_action_allowed"))

    def test_validated_supervision_policy_helper_is_available(self):
        helper = getattr(policy_module, "supervision_policy", None)
        self.assertIsNotNone(helper)
        if helper is None:
            return
        supervision = helper()
        self.assertEqual(supervision["escalation"], ["controller", "jules", "direct"])
        self.assertEqual(supervision["external_running_hard_timeout_minutes"], 90)
        self.assertTrue(supervision["actionable_safe_work_must_execute"])
        self.assertFalse(supervision["report_only_when_action_available"])


if __name__ == "__main__":
    unittest.main()
