"""Targeted audio repair preserves all unrelated PCM and fails on non-silent cuts."""
import unittest
from scripts import kesher_owner_kindergarten_audio_repair as r

class KindergartenAudioRepairTests(unittest.TestCase):
    def test_splice_preserves_prefix_suffix_and_length(self):
        a,b=r.OVERVIEW_CUT; c,d=r.SHORT_CUT
        original=bytearray((b+1000)*2); short=bytearray((d+1000)*2)
        original[0:2]=b'\x01\x00'; original[-2:]=b'\x02\x00'
        short[(c+1000)*2:(c+1001)*2]=b'\x03\x00'
        output=r.splice(bytes(original),bytes(short))
        self.assertEqual(len(output),len(original))
        self.assertEqual(output[:a*2],original[:a*2])
        self.assertEqual(output[b*2:],original[b*2:])
        self.assertIn(b'\x03\x00',output[a*2:b*2])

    def test_non_silent_cut_fails_closed(self):
        a,b=r.OVERVIEW_CUT; c,d=r.SHORT_CUT
        original=bytearray((b+1000)*2); short=bytes((d+1000)*2)
        radius=r.RATE//200
        original[(a-radius)*2:(a+radius)*2]=b'\xff\x7f'*(radius*2)
        with self.assertRaisesRegex(ValueError,'CUT_NOT_SILENT'):
            r.splice(bytes(original),short)

if __name__=='__main__':
    unittest.main()
