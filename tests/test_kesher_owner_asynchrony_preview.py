"""Hermetic identity and no-publish OWNER tests."""
import unittest
from pathlib import Path
from scripts import kesher_owner_asynchrony_preview as m

class OwnerAsynchronyPreview(unittest.TestCase):
    def test_source_and_three_original_photos(self):
        scripts, photos = m.source_check(public=False)
        self.assertEqual(len(scripts["overview"]), 5)
        self.assertEqual(len(scripts["short"]), 5)
        self.assertEqual(len(photos["images"]), 3)
        self.assertEqual(m.SOURCE_SHA, "7b6ae2e8dc3182d798edbf19c2d95e576b02ab093c5e2bf04bad91113a716a00")
    def test_preview_is_nonpublishing(self):
        src = Path(m.__file__).read_text(encoding="utf-8")
        for value in ("YOUTUBE_CLIENT_SECRET","youtube.upload","videos().insert(","owner_publish"):
            self.assertNotIn(value,src)
    def test_evidence_safe_hebrew_scripts(self):
        scripts=m.source_scripts()
        text="\n".join(scripts["overview"]+scripts["short"])
        self.assertIn("מחוננות אינה גורמת בהכרח",text)
        self.assertIn("מותר לכעוס, אסור לשבור",text)
        for phrase in ("פי עשר","המחקר מוכיח שכולם","עשרות אחוזים"):
            self.assertNotIn(phrase,text)

if __name__=="__main__":
    unittest.main()
