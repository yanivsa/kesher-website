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

    def test_recovery_rejects_wrong_archive_without_output(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            archive = root / "wrong.zip"
            archive.write_bytes(b"not the reviewed archive")
            with self.assertRaisesRegex(ValueError, "RECOVERY_ARCHIVE_IDENTITY_MISMATCH"):
                p.recover(archive, root / "output")
            self.assertFalse((root / "output").exists())
    def test_recovery_preserves_duration_gate_and_overview(self):
        self.assertEqual(p.RECOVERY_TEMPO, "0.86")
        self.assertEqual(p.RECOVERY_OVERVIEW_SHA, "4d53ae34495d49a7e91ef58148ff386437ff43b86e8a57f3e283c563bddc0e3a")
        self.assertGreater(25.262969 / float(p.RECOVERY_TEMPO), 28)
