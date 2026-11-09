"""Strict exact-license provenance and attribution gates for the OWNER Short."""
import unittest
from scripts.kesher_owner_vantage_short import VOICE, verify_voice_license

MODEL = "notmax123/BlueTTS2.5-onnx"
MODEL_URL = "https://huggingface.co/notmax123/BlueTTS2.5-onnx"
CORPUS_URL = "https://www.openslr.org/141/"


class VoiceLicenseGateTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "voice": VOICE,
            "voice_provenance": {
                "model_repo": MODEL,
                "model_revision": "f" * 40,
                "weights_license": "MIT",
                "weights_license_url": MODEL_URL,
                "voice_preset": "libri_female_6147",
                "reference_license": "CC BY 4.0",
                "reference_license_url": CORPUS_URL,
                "g2p_model": "notmax123/RenikudPlus",
                "g2p_license": "Apache-2.0",
                "g2p_revision": "d" * 40,
            },
        }
        self.approval = {
            "audio_review_pass": True,
            "visual_review_pass": True,
            "semantic_review_pass": True,
            "voice_license": {
                "voice_source": VOICE,
                "commercial_use_permitted": True,
                "attribution_in_description": True,
                "model_repo": MODEL,
                "model_license": "MIT",
                "license_evidence_url": MODEL_URL,
                "voice_reference_corpus": "LibriTTS-R train-clean-100",
                "reference_license": "CC BY 4.0",
                "reference_license_url": CORPUS_URL,
            },
        }

    def assert_blocked(self):
        with self.assertRaisesRegex(AssertionError, "VOICE_LICENSE_NOT_VERIFIED"):
            verify_voice_license(self.approval, self.manifest)

    def test_valid_licensed_exact_voice_passes(self):
        verify_voice_license(self.approval, self.manifest)

    def test_missing_license_fails_even_when_audio_visual_semantic_pass(self):
        self.approval.pop("voice_license")
        self.assert_blocked()

    def test_explicitly_unverified_license_fails(self):
        self.approval["voice_license"]["commercial_use_permitted"] = False
        self.assert_blocked()

    def test_missing_license_evidence_fails(self):
        self.approval["voice_license"]["license_evidence_url"] = None
        self.assert_blocked()

    def test_wrong_or_unlicensed_voice_fails(self):
        self.approval["voice_license"]["voice_source"] = "he-IL-HilaNeural"
        self.assert_blocked()

    def test_wrong_model_provenance_fails(self):
        self.manifest["voice_provenance"]["model_repo"] = "unauthorized/fork"
        self.assert_blocked()

    def test_wrong_or_missing_reference_license_fails(self):
        self.approval["voice_license"]["reference_license"] = "CC BY NC"
        self.assert_blocked()

    def test_missing_cc_by_attribution_fails(self):
        self.approval["voice_license"]["attribution_in_description"] = False
        self.assert_blocked()

    def test_unpinned_model_revision_fails(self):
        self.manifest["voice_provenance"]["model_revision"] = "main"
        self.assert_blocked()


    def test_missing_pinned_g2p_weights_fails(self):
        self.manifest["voice_provenance"]["g2p_revision"] = None
        self.assert_blocked()

    def test_unapproved_g2p_weights_fails(self):
        self.manifest["voice_provenance"]["g2p_license"] = "unknown"
        self.assert_blocked()

if __name__ == "__main__":
    unittest.main()
