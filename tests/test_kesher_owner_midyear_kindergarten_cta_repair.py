import unittest
from scripts import kesher_owner_midyear_kindergarten_cta_repair as repair
class MidyearCTARepairTests(unittest.TestCase):
    def test_exact_source_and_cta(self):
        scripts=repair.preview.source_scripts()
        self.assertIn(repair.OLD,scripts["overview"][-1])
        self.assertIn(repair.NEW,scripts["short"][-1])
        self.assertEqual(len(repair.expected_names()),27)
    def test_splice_preserves_outside_cut(self):
        a,b=repair.OVERVIEW_CUT;c,d=repair.SHORT_CUT
        original=b"\0"*((b+1000)*2);short=b"\0"*((d+1000)*2)
        self.assertEqual(repair.splice(original,short),original)
        import struct
        loud=short[:c*2-500]+struct.pack("<h",3000)*500+short[c*2+500:]
        with self.assertRaisesRegex(ValueError,"CUT_NOT_SILENT"):
            repair.splice(original,loud)
