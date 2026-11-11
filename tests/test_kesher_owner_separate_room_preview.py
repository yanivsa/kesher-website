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

    def test_exact_targeted_review_windows_and_identity(self):
        self.assertEqual(len(p.scene_windows("overview", 71.5175)), 6)
        self.assertEqual(len(p.scene_windows("short", 29.00175)), 4)
        self.assertEqual(p.scene_windows("short", 29.00175)[1], (4.68, 13.84))
        with self.assertRaisesRegex(ValueError, "INVALID_EXACT_SCENE_WINDOWS"):
            p.scene_windows("short", 20)
        self.assertEqual(p.FINAL_VIDEO_SHA["overview"], p.RECOVERY_OVERVIEW_SHA)
        self.assertEqual(len(p.IVRIT_REV), 40)

    def test_pronunciation_repair_preserves_unaffected_pcm(self):
        import numpy as np
        from scripts import kesher_owner_separate_room_pronunciation_repair as r
        original=np.zeros(5000,dtype="<i2")
        original[10:20]=123
        replacement=np.full(1000,200,dtype="<i2")
        edited=r.splice(original,[(2000,3000,replacement)])
        self.assertTrue(np.array_equal(edited[:2000],original[:2000]))
        self.assertTrue(np.array_equal(edited[3000:],original[3000:]))
        self.assertEqual(len(r.cut_samples("overview",3153920)),8)
        self.assertEqual(len(r.cut_samples("short",1278976)),4)
        with self.assertRaisesRegex(ValueError,"INVALID_REPAIR_CUTS"):
            r.cut_samples("short",100)
