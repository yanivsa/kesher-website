from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import kesher_daily_pipeline as pipeline


class VideoVoiceFallbackRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_dir = self.root / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "state.json"
        self.patches = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_file),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patches):
            patcher.stop()
        self.temporary.cleanup()

    @staticmethod
    def source() -> dict:
        return {
            "id": "voice-fallback",
            "slug": "voice-fallback",
            "title": "בדיקת התאוששות קול",
            "category": "הדרכת הורים",
            "content_sha256": "a" * 64,
            "canonical_url": "https://kesher.saharoni.com/blog/voice-fallback",
            "youtube_metadata": {
                "title": "בדיקת התאוששות קול",
                "description": "בדיקת התאוששות קול\nhttps://kesher.saharoni.com/blog/voice-fallback\nhttps://kesher.saharoni.com\nhttps://kesher.saharoni.com/appointment",
                "tags": ["הדרכת הורים"],
            },
        }

    def test_new_item_persists_explicit_generation_attempt(self) -> None:
        with mock.patch.dict(os.environ, {"KESHER_FRESH_GENERATION_ATTEMPT": "3"}, clear=False):
            item = pipeline.new_item(self.source())
        self.assertEqual(item["fresh_generation_attempt"], 3)

    def test_wrong_voice_rebuild_revalidates_same_artifact_on_final_attempt(self) -> None:
        source = self.source()
        raw = self.state_dir / "original-notebooklm.mp4"
        raw.write_bytes(b"same-provider-artifact")
        item = pipeline.new_item(source)
        item.update(
            {
                "id": "video-existing",
                "status": "rejected",
                "technical_verified": False,
                "failure_signature": "wrong_narrator_gender",
                "failure_fingerprint": "wrong_narrator_gender:prompt:source",
                "notebook_id": "notebook",
                "source_id": "source-existing",
                "task_id": "task-existing",
                "artifact_id": "task-existing",
                "raw_mp4": raw.name,
                "raw_sha256": pipeline.sha256_file(raw),
                "review_notes": {
                    "technical": "נפסל טכנית: Detected male voice pitch",
                    "visual": "",
                    "semantic": "",
                    "metadata": "",
                },
            }
        )
        state = {"version": 1, "items": [item], "updated_at": pipeline.utc_now()}
        pipeline.save_state(state)

        observed: dict[str, object] = {}

        def fake_validate(saved_state: dict, saved_item: dict, raw_path: Path) -> None:
            observed["artifact_id"] = saved_item["artifact_id"]
            observed["task_id"] = saved_item["task_id"]
            observed["attempt"] = saved_item.get("fresh_generation_attempt")
            observed["raw_path"] = raw_path.name
            saved_item["technical_verified"] = True
            saved_item["status"] = "pending_review"
            pipeline.save_state(saved_state)

        with mock.patch.dict(os.environ, {"KESHER_FRESH_GENERATION_ATTEMPT": "3"}, clear=False), mock.patch.object(
            pipeline, "validate_and_manifest", side_effect=fake_validate
        ):
            pipeline.rebuild_rejected_with_remotion("video-existing")

        self.assertEqual(observed["artifact_id"], "task-existing")
        self.assertEqual(observed["task_id"], "task-existing")
        self.assertEqual(observed["attempt"], 3)
        self.assertEqual(observed["raw_path"], raw.name)
