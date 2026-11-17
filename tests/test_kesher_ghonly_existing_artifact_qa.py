"""Hermetic source-bound provider read-only MP4 QA regression tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.kesher_runtime import ghonly_existing_artifact_qa as qa


class ExistingArtifactQAReadOnlyTests(unittest.TestCase):
    def test_all_targets_original_ids_are_unique_and_original_source_bound(self):
        self.assertEqual(len(qa.TARGETS), 4)
        self.assertEqual(len({row[4] for row in qa.TARGETS}), 4)
        self.assertTrue(all(len(row[3]) == 64 for row in qa.TARGETS))
        self.assertEqual({row[2] for row in qa.TARGETS}, {"long","short"})

    def test_one_completed_original_artifact_downloads_only_without_upload(self):
        row = qa.TARGETS[1]
        artifact_id = row[4]
        calls = []

        def command(args, **kwargs):
            calls.append(args)
            self.assertEqual(args[:3], ["notebooklm","download","video"])
            self.assertEqual(args[7], artifact_id)
            Path(args[3]).write_bytes(b"f" * 2048)
            return ""

        with tempfile.TemporaryDirectory() as folder,              patch.object(qa, "_safe_command", side_effect=command),              patch.object(qa, "_inspect", return_value={
                 "width":720, "height":1280,"duration_seconds":37,
                 "video_codec":"h264","audio_codec":"aac",
             }):
            result = qa.audit_one(row, {artifact_id:{"status":"completed"}}, Path(folder))
            self.assertTrue(result["technical_aspect_ratio_pass"])
            self.assertTrue(result["original_task_reused"])
            self.assertFalse(result["source_body_verified"])
            self.assertFalse(result["female_hebrew_voice_verified"])
            self.assertFalse(result["upload_authorized"])
            self.assertFalse(list(Path(folder).glob("*.mp4")))
            self.assertEqual(len(calls), 1)

    def test_long_ratio_and_wrong_source_will_not_grant_qa(self):
        row = qa.TARGETS[0]
        artifact_id = row[4]
        def command(args, **kwargs):
            Path(args[3]).write_bytes(b"x" * 1024)
            return ""
        with tempfile.TemporaryDirectory() as folder,              patch.object(qa, "_safe_command", side_effect=command),              patch.object(qa, "_inspect", return_value={
                 "width":1280,"height":720,"duration_seconds":220,
                 "video_codec":"h264","audio_codec":"aac",
             }):
            result = qa.audit_one(row, {artifact_id:{"status":"completed"}}, Path(folder))
        self.assertTrue(result["technical_aspect_ratio_pass"])
        self.assertFalse(result["visual_qa_verified"])
        self.assertFalse(result["licensing_verified"])
        self.assertFalse(result["generation_authorized"])

    def test_wrong_status_or_ambiguous_task_does_not_download(self):
        row = qa.TARGETS[0]
        with tempfile.TemporaryDirectory() as folder,              patch.object(qa, "_safe_command") as command:
            for record in ({}, {row[4]: {"status":"generating"}},
                           {row[4]: {"status":"rejected"}}):
                with self.assertRaisesRegex(qa.QAReadOnlyBlocked,
                                            "EXACT_PROVIDER_TASK_NOT_COMPLETED"):
                    qa.audit_one(row, record, Path(folder))
            command.assert_not_called()

    def test_no_provider_dispatch_or_youtube_in_source(self):
        s = Path("scripts/kesher_runtime/ghonly_existing_artifact_qa.py").read_text()
        flow = Path(".github/workflows/kesher-daily-video.yml").read_text()
        for forbidden in ("youtube_client(", "upload_only(", ".insert(",
                          "gh workflow run", "start_generation(", "POST", "mutation"):
            self.assertNotIn(forbidden, s)
        self.assertIn("GITHUB_WORKFLOW_REF", s)
        self.assertIn("inputs.operation == 'preflight'", flow)
        self.assertIn("ghonly_existing_artifact_qa", flow)


if __name__ == "__main__":
    unittest.main()
