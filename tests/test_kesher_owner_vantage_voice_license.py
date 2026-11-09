"""Fail-closed regression coverage for KESHER owner-only Short voice licensing."""
import unittest

from scripts.kesher_owner_vantage_short import VOICE, verify_voice_license


class VoiceLicenseGateTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {"voice": VOICE}
        self.approval = {
            "audio_review_pass": True,
            "visual_review_pass": True,
            "semantic_review_pass": True,
            "voice_license": {
                "voice_source": VOICE,
                "commercial_use_permitted": True,
                "license_evidence_url": "https://example.com/licenses/official-voice-terms",
            },
        }

    def test_valid_documented_exact_voice_passes(self):
        verify_voice_license(self.approval, self.manifest)

    def test_missing_license_fails_even_if_three_qa_checks_pass(self):
        del self.approval["voice_license"]
        with self.assertRaisesRegex(AssertionError, "VOICE_LICENSE_NOT_VERIFIED"):
            verify_voice_license(self.approval, self.manifest)

    def test_explicitly_unverified_license_fails(self):
        self.approval["voice_license"]["commercial_use_permitted"] = False
        with self.assertRaisesRegex(AssertionError, "VOICE_LICENSE_NOT_VERIFIED"):
            verify_voice_license(self.approval, self.manifest)

    def test_empty_evidence_url_fails(self):
        self.approval["voice_license"]["license_evidence_url"] = None
        with self.assertRaisesRegex(AssertionError, "VOICE_LICENSE_NOT_VERIFIED"):
            verify_voice_license(self.approval, self.manifest)

    def test_wrong_voice_fails(self):
        self.approval["voice_license"]["voice_source"] = "different-neural-voice"
        with self.assertRaisesRegex(AssertionError, "VOICE_LICENSE_NOT_VERIFIED"):
            verify_voice_license(self.approval, self.manifest)


if __name__ == "__main__":
    unittest.main()
