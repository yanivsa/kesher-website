from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kesher_daily_pipeline.py"
SPEC = importlib.util.spec_from_file_location("kesher_daily_pipeline_pending_evidence_test", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pipeline)


class PendingEvidenceRepairTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_dir = self.root / "state"
        self.patches = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_dir / "state.json"),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    def test_pending_review_with_missing_immutable_evidence_can_be_revalidated(self) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        raw = self.state_dir / "item-notebooklm.mp4"
        raw.write_bytes(b"authoritative-notebooklm-video")
        item = {
            "id": "video-pending-evidence",
            "status": "pending_review",
            "technical_verified": True,
            "visual_review_status": "approved",
            "semantic_review_status": "approved",
            "metadata_review_status": "approved",
            "review_notes": {"technical": "אומת טכנית", "visual": "אושר", "semantic": "אושר", "metadata": "אושר"},
            "raw_mp4": raw.name,
            "raw_sha256": pipeline.sha256_file(raw),
            "notebook_id": pipeline.NOTEBOOK_ID,
            "source_id": "source-1",
            "task_id": "artifact-1",
            "artifact_id": "artifact-1",
            "source": {"slug": "article", "content_sha256": "a" * 64, "title": "כותרת", "category": "זוגיות"},
            "youtube_metadata": {"title": "כותרת", "description": "תיאור https://kesher.saharoni.com", "tags": ["זוגיות"]},
            "uploaded": False,
        }
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})

        with mock.patch.object(pipeline, "validate_and_manifest") as validate:
            pipeline.rebuild_rejected_with_remotion(item["id"])

        saved = pipeline.load_state()["items"][0]
        self.assertEqual(saved["status"], "downloaded")
        self.assertFalse(saved["technical_verified"])
        self.assertEqual(saved["evidence_history"][0]["status"], "pending_review")
        validate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
