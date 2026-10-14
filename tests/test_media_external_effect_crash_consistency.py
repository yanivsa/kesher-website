#!/usr/bin/env python3
"""Regressions for P1: MEDIA_EXTERNAL_EFFECT_CRASH_CONSISTENCY.

Verifies crash-safety on pre-cutover Schema-5 NotebookLM and YouTube external effects:
1. Crash immediately after NotebookLM source acceptance does not create duplicate source
2. Crash after NotebookLM generation acceptance does not trigger second fresh generation
3. Lost YouTube resumable-session response reconciles or fails closed without duplicate session
4. Crash after final upload acceptance but before local video_id save recovers video_id without re-upload
5. Restart/reconcile recovers exact provider identity or fails closed
6. Uncertain-effect state refuses a second fresh generation or upload
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.kesher_daily_pipeline import (
    PipelineError,
    add_source,
    legacy_external_effect,
    reconcile_legacy_effect,
    start_generation,
)


class MediaExternalEffectCrashConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "media-state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_crash_after_notebooklm_source_acceptance_recovers_or_fails_closed(self):
        state = {"version": 1, "items": []}
        item = {"id": "video-test-1", "source": {"title": "Test Title"}}
        state["items"].append(item)
        request = {"notebook_id": "nb-123", "title": "Test Title", "body_sha256": "abc"}

        call_count = 0

        def create_source():
            nonlocal call_count
            call_count += 1
            return {"source_id": "src-accepted-1"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            # Normal first execution succeeds
            receipt = legacy_external_effect(state, item, "provider_source", request, create_source)
            self.assertEqual(receipt["source_id"], "src-accepted-1")
            self.assertEqual(call_count, 1)

            # Re-running with completed effect reuses receipt WITHOUT calling provider again
            receipt2 = legacy_external_effect(state, item, "provider_source", request, create_source)
            self.assertEqual(receipt2["source_id"], "src-accepted-1")
            self.assertEqual(call_count, 1)

    def test_crash_with_unreconciled_intent_fails_closed_without_second_call(self):
        state = {"version": 1, "items": []}
        item = {
            "id": "video-test-crash",
            "source": {"title": "Test Title"},
            "external_effects": {
                "provider_source": {
                    "status": "intent",  # crashed after intent save!
                    "request": {"notebook_id": "nb-123", "title": "Test Title"},
                }
            },
        }
        state["items"].append(item)
        request = {"notebook_id": "nb-123", "title": "Test Title"}

        call_count = 0

        def create_source():
            nonlocal call_count
            call_count += 1
            return {"source_id": "src-duplicate"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            with self.assertRaisesRegex(PipelineError, "EXTERNAL_RESULT_UNCERTAIN"):
                legacy_external_effect(state, item, "provider_source", request, create_source)
            # Provider was NEVER called a second time!
            self.assertEqual(call_count, 0)

    def test_reconciles_known_source_id_after_crash(self):
        state = {"version": 1, "items": []}
        item = {
            "id": "video-test-crash-reconciled",
            "source_id": "src-existing-99",  # recovered provider identity
            "source": {"title": "Test Title"},
            "external_effects": {
                "provider_source": {
                    "status": "intent",
                    "request": {"notebook_id": "nb-123", "title": "Test Title"},
                }
            },
        }
        state["items"].append(item)
        request = {"notebook_id": "nb-123", "title": "Test Title"}

        call_count = 0

        def create_source():
            nonlocal call_count
            call_count += 1
            return {"source_id": "src-duplicate"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            receipt = legacy_external_effect(state, item, "provider_source", request, create_source)
            self.assertEqual(receipt["source_id"], "src-existing-99")
            self.assertEqual(call_count, 0)

    def test_crash_after_notebooklm_generation_acceptance_fails_closed(self):
        state = {"version": 1, "items": []}
        item = {
            "id": "video-test-gen-crash",
            "source_id": "src-1",
            "external_effects": {
                "provider_generation": {
                    "status": "intent",
                    "request": {"notebook_id": "nb-123", "source_id": "src-1"},
                }
            },
        }
        state["items"].append(item)
        request = {"notebook_id": "nb-123", "source_id": "src-1"}

        call_count = 0

        def create_generation():
            nonlocal call_count
            call_count += 1
            return {"task_id": "task-dup", "artifact_id": "task-dup"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            with self.assertRaisesRegex(PipelineError, "EXTERNAL_RESULT_UNCERTAIN"):
                legacy_external_effect(state, item, "provider_generation", request, create_generation)
            self.assertEqual(call_count, 0)

    def test_lost_youtube_session_response_reconciles_existing_uri(self):
        state = {"version": 1, "items": []}
        item = {
            "id": "video-test-yt-session",
            "upload_session_uri": "https://upload.youtube.com/resumable/session-abc",
            "external_effects": {
                "youtube_session": {
                    "status": "intent",
                    "request": {"metadata": {"title": "Title"}},
                }
            },
        }
        state["items"].append(item)
        request = {"metadata": {"title": "Title"}}

        call_count = 0

        def create_session():
            nonlocal call_count
            call_count += 1
            return {"location": "https://upload.youtube.com/resumable/session-dup"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            receipt = legacy_external_effect(state, item, "youtube_session", request, create_session)
            self.assertEqual(receipt["location"], "https://upload.youtube.com/resumable/session-abc")
            self.assertEqual(call_count, 0)

    def test_crash_after_final_upload_acceptance_recovers_video_id(self):
        state = {"version": 1, "items": []}
        item = {
            "id": "video-test-yt-upload",
            "youtube_id": "yt-video-12345",
            "external_effects": {
                "youtube_upload_bytes": {
                    "status": "intent",
                    "request": {"session_uri": "uri-1", "offset": 0, "size": 1000},
                }
            },
        }
        state["items"].append(item)
        request = {"session_uri": "uri-1", "offset": 0, "size": 1000}

        call_count = 0

        def do_upload():
            nonlocal call_count
            call_count += 1
            return {"video_id": "yt-video-dup"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            receipt = legacy_external_effect(state, item, "youtube_upload_bytes", request, do_upload)
            self.assertEqual(receipt["video_id"], "yt-video-12345")
            self.assertEqual(call_count, 0)


if __name__ == "__main__":
    unittest.main()
