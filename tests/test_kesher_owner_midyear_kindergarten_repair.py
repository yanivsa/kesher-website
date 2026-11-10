import unittest
from scripts import kesher_owner_midyear_kindergarten_repair as repair
class MidyearRepairTests(unittest.TestCase):
    def test_exact_source_and_duration_repair(self):
        self.assertEqual(repair.ARCHIVE_ID,13796052703)
        self.assertEqual(len(repair.ARCHIVE_SHA),64)
        self.assertGreater((repair.CUT[1]-repair.CUT[0])/repair.RATE,3)
        self.assertIn(repair.CLOSING,repair.preview.source_scripts()["overview"][-1])
        self.assertEqual(len(repair.expected_names()),14)
    def test_cut_requires_silent_boundaries(self):
        import struct
        data=b"\0"*((repair.CUT[1]+1000)*2)
        self.assertEqual(len(repair.exact_cut(data)),(repair.CUT[1]-repair.CUT[0])*2)
        a=repair.CUT[0]*2
        loud=data[:a-500]+struct.pack("<h",3000)*500+data[a+500:]
        with self.assertRaisesRegex(ValueError,"CUT_NOT_SILENT"):
            repair.exact_cut(loud)
