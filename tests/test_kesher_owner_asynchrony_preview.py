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
    def test_tall_portrait_not_crop_to_chin(self):
        from tempfile import TemporaryDirectory
        from PIL import Image, ImageDraw
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / "tall.jpg"
            out = Path(tmp) / "landscape.jpg"
            im = Image.new("RGB", (300, 900), "#ff0000")
            ImageDraw.Draw(im).rectangle((0, 450, 299, 899), fill="#0000ff")
            im.save(original, quality=95)
            m.make_image(original, out, "overview")
            reviewed = Image.open(out)
            self.assertEqual(reviewed.size, (1280, 720))
            top = reviewed.getpixel((640, 30))
            bottom = reviewed.getpixel((640, 690))
            self.assertGreater(top[0], top[2] * 2)
            self.assertGreater(bottom[2], bottom[0] * 2)
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
