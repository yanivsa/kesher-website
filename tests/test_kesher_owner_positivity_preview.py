"""Bounded source, license-hold and media safety for direct OWNER positivity previews."""
import unittest
from pathlib import Path
from scripts import kesher_owner_positivity_preview as m

class PositivityOwnerPreview(unittest.TestCase):
    def test_exact_source_and_five_distinct_photo_hashes(self):
        scripts, evidence = m.source_check(public=False)
        self.assertEqual(len(scripts["overview"]), 5)
        self.assertEqual(len(scripts["short"]), 5)
        self.assertEqual(len(evidence["images"]), 5)
        self.assertEqual(m.SLUG, "positivity-resonance-marriage-micro-moments")
        self.assertEqual(m.SOURCE_SHA, "0f0aa3e55560774ca2fcb5c72a296cffda23ad29674530b54aa10be92b04f710")
        self.assertEqual(len({i["path"] for i in evidence["images"]}), 5)
        self.assertTrue(all(i["rights_status"] == "REVIEW_PENDING" for i in evidence["images"]))

    def test_scientific_limitations_are_spoken_not_unverified_promises(self):
        scripts=m.source_scripts()
        alltext=" ".join(scripts["overview"]+scripts["short"])
        for phrase in ("מאה חמישים וארבעה","שלוש עשרה שנים","שלושים שנה",
                       "קשר סטטיסטי","לא הוכחה","רק רעיון לתרגול"):
            self.assertIn(phrase,alltext)
        for bad in ("פי עשר","ניצולים מגירושים","עצב הוואגוס מופעל בכל חיוך"):
            self.assertNotIn(bad,alltext)

    def test_no_upload_path_or_external_creator(self):
        code=Path(m.__file__).read_text(encoding="utf-8")
        for forbidden in ("videos().insert(", "YOUTUBE_CLIENT_SECRET", "jules.run", "Descript"):
            self.assertNotIn(forbidden,code)
        self.assertIn('"uploaded":False',code)
        self.assertIn('"public":False',code)

    def test_photographic_visual_output_matches_native_aspect_ratios(self):
        from PIL import Image
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as root:
            source = Path(root)/"photo.jpg"
            source.write_bytes((m.ROOT/"public/images/generated/blog/couples-communication-life-transitions.jpg").read_bytes())
            for kind,dim in (("overview",(1280,720)),("short",(1080,1920))):
                target=Path(root)/(kind+".jpg")
                m.make_image(source,target,kind)
                self.assertEqual(Image.open(target).size,dim)

if __name__ == "__main__":
    unittest.main()
