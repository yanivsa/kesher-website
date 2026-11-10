import unittest
from pathlib import Path
from scripts.kesher_owner_positivity_youtube_probe import SLUG,SHA,CHANNEL,KIND_MARKERS,MIDYEAR_SLUG,MIDYEAR_SHA,MIDYEAR_BODY_SHA,midyear_candidates
class PositivityYoutubeReadOnlyTests(unittest.TestCase):
    def test_bound_identity(self):
        self.assertEqual(SLUG,"positivity-resonance-marriage-micro-moments")
        self.assertEqual(SHA,"6bb5723bbadc7b78725e4cdb477857e7194cca47c1140f27d1c4f3921b6e2d5f")
        self.assertEqual(CHANNEL,"UCx5fEFvdVf28HLAR2dFW64Q")
        self.assertEqual(len(KIND_MARKERS),2)
    def test_midyear_exact_and_legacy_candidates(self):
        self.assertEqual(MIDYEAR_SLUG, "changing-kindergarten-midyear")
        self.assertEqual(MIDYEAR_SHA, "5b0d6c5e8ba2c7fb001d1b7944a4abca1dbe4d5b0248889466dca4225e393a1a")
        def record(vid, title, desc, privacy="public"):
            return {"id": vid, "snippet": {"channelId": CHANNEL, "title": title, "description": desc}, "status": {"privacyStatus": privacy}}
        rows = [record("abcdefghijk", "מעבר לגן באמצע השנה", ""),
                record("bcdefghijkl", "כותרת אחרת", "https://kesher.saharoni.com/blog/" + MIDYEAR_SLUG, "private"),
                record("cdefghijklm", "מעבר לגן עירייה", "transition-to-municipal-kindergarten"),
                record("defghijklmn", "כותרת ישנה", "content_sha256=" + MIDYEAR_BODY_SHA)]
        result = midyear_candidates(rows)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["public_id"], "abcdefghijk")
        self.assertIsNone(result[1]["public_id"])
        self.assertIsNone(result[1]["title"])
        self.assertEqual(len(result[1]["id_fingerprint"]), 12)
        self.assertEqual(result[2]["public_id"], "defghijklmn")
        rows[0]["snippet"]["channelId"] = "wrong"
        with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_CHANNEL"):
            midyear_candidates(rows)

    def test_read_only_source(self):
        source=Path("scripts/kesher_owner_positivity_youtube_probe.py").read_text()
        for forbidden in ("videos().insert(", "videos().update(", "videos().delete(", "MediaFileUpload", "upload_only(", "workflow_dispatch", "https://www.googleapis.com/upload"):
            self.assertNotIn(forbidden,source)
if __name__=="__main__": unittest.main()
