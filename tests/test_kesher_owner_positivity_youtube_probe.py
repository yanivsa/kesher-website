import unittest
from pathlib import Path
from scripts.kesher_owner_positivity_youtube_probe import SLUG,SHA,CHANNEL,KIND_MARKERS
class PositivityYoutubeReadOnlyTests(unittest.TestCase):
    def test_bound_identity(self):
        self.assertEqual(SLUG,"positivity-resonance-marriage-micro-moments")
        self.assertEqual(SHA,"6bb5723bbadc7b78725e4cdb477857e7194cca47c1140f27d1c4f3921b6e2d5f")
        self.assertEqual(CHANNEL,"UCx5fEFvdVf28HLAR2dFW64Q")
        self.assertEqual(len(KIND_MARKERS),2)
    def test_read_only_source(self):
        source=Path("scripts/kesher_owner_positivity_youtube_probe.py").read_text()
        for forbidden in ("videos().insert(", "videos().update(", "videos().delete(", "MediaFileUpload", "upload_only(", "workflow_dispatch", "https://www.googleapis.com/upload"):
            self.assertNotIn(forbidden,source)
if __name__=="__main__": unittest.main()
