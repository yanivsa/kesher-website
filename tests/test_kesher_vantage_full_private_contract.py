"""Static and asset-bound guard for Vantage full private Overview candidate."""
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/kesher_vantage_full_private.py"
PLAN = ROOT / "research/kesher-vantage-overview-full-private-20261109.json"
SLUG = "vantage-sensitivity-sensitive-gifted-children"
SOURCE = "e264d2962b9028afc73463edcd2718b37539212762b0a72e35507d33dcb270ea"


class VantageFullPrivateTests(unittest.TestCase):
    def setUp(self):
        self.source = SCRIPT.read_text(encoding="utf-8")
        self.data = json.loads(PLAN.read_text(encoding="utf-8"))

    def test_compiles_without_creating_or_publishing_any_media(self):
        compile(self.source, str(SCRIPT), "exec")
        self.assertIn("no_publication", self.source)
        self.assertIn("PRIVATE_FULL_OVERVIEW_QA_CANDIDATE", self.source)
        self.assertIn('"youtube_uploaded":False', self.source)
        self.assertNotIn("videos().insert(", self.source)
        self.assertNotIn("YOUTUBE_REFRESH_TOKEN", self.source)
        self.assertNotIn("actions/workflows", self.source)

    def test_exact_article_identity_and_no_implicit_qa_pass(self):
        self.assertTrue(self.data["no_publication"])
        self.assertTrue(self.data["not_editorial_approval"])
        self.assertEqual("lnP5GltTLNk", self.data["existing_public_overview_id"])
        self.assertEqual({"slug": SLUG, "contentSha256": SOURCE}, self.data["sourceBinding"])
        self.assertEqual(SLUG, self.data["licensedPhotoStory"]["sourceSlug"])
        self.assertEqual(SOURCE, self.data["licensedPhotoStory"]["contentSha256"])
        self.assertIn("QUALITY_HOLD", self.data["editorial_rights_status"])

    def test_eight_original_local_immutable_images_and_provenance_holds(self):
        scenes = self.data["licensedPhotoStory"]["scenes"]
        self.assertEqual(8, len(scenes))
        self.assertEqual(8, len({x["assetPath"] for x in scenes}))
        for s in scenes:
            p = ROOT / "public" / s["assetPath"]
            self.assertTrue(p.is_file(), s["assetPath"])
            self.assertEqual(s["assetSha256"], hashlib.sha256(p.read_bytes()).hexdigest())
            self.assertTrue(s["licenseEvidenceUrl"].startswith("https://"))
            self.assertNotIn(s["rightsStatus"], ("approved", "QA_PASSED"))

    def test_script_scientifically_restrained_and_source_bound(self):
        scenes = self.data["licensedPhotoStory"]["scenes"]
        self.assertTrue(all(len(s["voiceText"].split()) >= 20 for s in scenes))
        all_text = " ".join(s["voiceText"] for s in scenes)
        for term in ("מייקל פלואס", "בלסקי", "בריונות", "בנים", "יותר מאלפיים",
                     "לא מוכיח", "אינה לבדה הוכחה", "לא הבטחה"):
            self.assertIn(term, all_text)
        source = (ROOT / "research/kesher-vantage-sensitivity-20261109.md").read_text(encoding="utf-8")
        for term in (SLUG, SOURCE):
            self.assertIn(term, source)

    def test_licensed_model_is_reused_and_full_audio_is_not_synthetic_tone(self):
        self.assertIn("kesher_owner_vantage_short", self.source)
        self.assertIn("voice.speak(output)", self.source)
        self.assertIn('audio_source', self.source)
        self.assertIn('"subjective_audition_status":"PENDING"', self.source)


if __name__ == "__main__":
    unittest.main()
