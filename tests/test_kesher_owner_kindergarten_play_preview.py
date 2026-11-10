"""Direct private kindergarten media source and visual contract."""
import unittest
from scripts import kesher_owner_kindergarten_play_preview as preview

class KindergartenPlayPrivatePreviewTests(unittest.TestCase):
    def test_exact_source_and_photo_bytes(self):
        scripts, provenance = preview.source_check(public=False)
        self.assertEqual(provenance["content_sha256"], preview.SOURCE_SHA)
        self.assertEqual(provenance["canonical_content_sha256"], preview.SOURCE_SHA)
        self.assertEqual(provenance["article_body_sha256"], preview.BODY_SHA)
        self.assertNotEqual(preview.SOURCE_SHA, preview.BODY_SHA)
        self.assertEqual(len(scripts["overview"]), 6)
        self.assertEqual(len(scripts["short"]), 4)
        self.assertEqual([x["dimensions"] for x in provenance["images"][3:]], [[1080, 1920], [1080, 1920]])
        self.assertEqual(len({x["sha256"] for x in provenance["images"]}), 5)

    def test_research_caveat_and_referral_are_in_actual_scripts(self):
        scripts = preview.source_scripts()
        self.assertIn("לא אבחנה", " ".join(scripts["overview"]))
        for kind in preview.SOURCE_KINDS:
            self.assertIn("רופא הילדים", " ".join(scripts[kind]))
            self.assertIn("בתיאור", " ".join(scripts[kind]))

if __name__ == "__main__":
    unittest.main()
