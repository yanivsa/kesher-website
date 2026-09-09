from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "kesher-production-contract.json"
JULES_POLICY = ROOT / ".github" / "prompts" / "jules-remotion-video-upgrade.md"


class MediaVoicePolicyContractTests(unittest.TestCase):
    def test_controller_contract_requires_three_female_attempts_then_male_fallback_for_both_products(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        policy = contract["video"]["voice_policy"]

        self.assertEqual(policy["preferred_voice"], "female")
        self.assertEqual(policy["female_attempts_before_fallback"], 3)
        self.assertEqual(policy["fallback_voice_after_failed_female_attempts"], "male")
        self.assertEqual(policy["applies_to"], ["video_overview", "short"])
        self.assertTrue(policy["retry_on_detected_male_before_fallback"])
        self.assertTrue(policy["accept_male_on_final_female_attempt"])
        self.assertTrue(policy["stop_voice_retries_after_fallback"])

    def test_jules_policy_matches_controller_voice_fallback_contract(self) -> None:
        text = JULES_POLICY.read_text(encoding="utf-8")

        required_phrases = (
            "Video Overview and Short",
            "attempts 1 and 2",
            "attempt 3",
            "male voice is an allowed fallback",
            "must not trigger a fourth generation solely because of voice gender",
        )
        for phrase in required_phrases:
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
