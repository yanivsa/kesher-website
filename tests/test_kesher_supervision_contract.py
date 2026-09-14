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

    def test_validated_supervision_policy_helper_is_available(self):
        helper = getattr(policy_module, "supervision_policy", None)
        self.assertIsNotNone(helper)
        if helper is None:
            return
        supervision = helper()
        self.assertEqual(supervision["escalation"], ["controller", "jules", "direct"])
        self.assertEqual(supervision["external_running_hard_timeout_minutes"], 90)


if __name__ == "__main__":
    unittest.main()
