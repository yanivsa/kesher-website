"""Offline ASR review integrity, no model invocation or upload in unit tests."""
import unittest
from pathlib import Path
from scripts import kesher_owner_positivity_asr as asr
from scripts import kesher_owner_positivity_preview as owner

class OwnerPositivityAsrTests(unittest.TestCase):
    def test_script_similarity_returns_consistent_hebrew_only(self):
        self.assertEqual(asr.similarity("שלום, עולם!", "שלום עולם"),1.0)
        self.assertEqual(asr.similarity("yes","שלום"),0.0)
    def test_no_hidden_publishing_path(self):
        text=Path(asr.__file__).read_text(encoding="utf-8")
        for marker in ("YOUTUBE_REFRESH_TOKEN","youtube.upload","videos().insert(","owner_publish"):
            self.assertNotIn(marker,text)
    def test_source_is_exact(self):
        self.assertEqual(owner.SLUG,"positivity-resonance-marriage-micro-moments")
        self.assertEqual(owner.SOURCE_SHA,"6bb5723bbadc7b78725e4cdb477857e7194cca47c1140f27d1c4f3921b6e2d5f")

if __name__=="__main__": unittest.main()
