import unittest
from pathlib import Path
from scripts import kesher_owner_separate_room_preview as p
class SeparateRoomPrivatePreviewTests(unittest.TestCase):
    def test_exact_source_and_photo_rights(self):
        scripts, provenance = p.source_check()
        self.assertEqual([len(scripts[k]) for k in p.KINDS], [6, 4])
        self.assertEqual(len(provenance["images"]), 10)
        self.assertEqual(provenance["dedup_evidence"]["candidates"], [])
        self.assertEqual(provenance["dedup_evidence"]["run_id"], 42920640111)
        self.assertTrue(all(x["commercial_use_permitted"] for x in provenance["images"]))
    def test_private_only(self):
        text = Path(p.__file__).read_text()
        for forbidden in ("videos().insert(", "videos().update(", "MediaFileUpload", "YOUTUBE_REFRESH_TOKEN", "edge_tts", "notebooklm"):
            self.assertNotIn(forbidden, text)
        self.assertIn('"uploaded": False, "public": False', text)
        self.assertIn("PENDING_GENUINE_INDEPENDENT_REVIEW", text)
