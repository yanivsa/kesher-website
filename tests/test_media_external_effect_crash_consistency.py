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
        """Model real failure window: pre-crash durable state has NO youtube_id.
        Provider accepted the upload, VM died before local receipt save.
        Fresh VM starts with empty disk, queries provider/session, recovers video ID without duplicate upload.
        """
        state = {"version": 1, "items": []}
        item = {
            "id": "video-test-yt-upload",
            # Note: youtube_id is NOT present in item before crash!
            "upload_session_uri": "https://upload.youtube.com/resumable/session-abc",
            "external_effects": {
                "youtube_upload_bytes": {
                    "status": "intent",
                    "request": {"session_uri": "https://upload.youtube.com/resumable/session-abc", "offset": 0, "size": 1000},
                }
            },
        }
        state["items"].append(item)
        request = {"session_uri": "https://upload.youtube.com/resumable/session-abc", "offset": 0, "size": 1000}

        call_count = 0

        def do_upload():
            nonlocal call_count
            call_count += 1
            return {"video_id": "yt-video-dup"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"), \
             mock.patch("scripts.kesher_daily_pipeline.youtube_access_token", return_value="dummy-token"), \
             mock.patch("scripts.kesher_daily_pipeline.resume_upload_status", return_value={"offset": 1000, "video_id": "yt-video-12345"}) as mock_resume:
            receipt = legacy_external_effect(state, item, "youtube_upload_bytes", request, do_upload)
            self.assertEqual(receipt["video_id"], "yt-video-12345")
            self.assertEqual(call_count, 0)
            mock_resume.assert_called_once_with("https://upload.youtube.com/resumable/session-abc", "dummy-token", 1000)

    def test_crash_after_final_upload_incomplete_fails_closed(self):
        """When provider session reports incomplete and video ID is absent, fail closed."""
        state = {"version": 1, "items": []}
        item = {
            "id": "video-test-yt-upload-incomplete",
            "upload_session_uri": "https://upload.youtube.com/resumable/session-inc",
            "external_effects": {
                "youtube_upload_bytes": {
                    "status": "intent",
                    "request": {"session_uri": "https://upload.youtube.com/resumable/session-inc", "offset": 0, "size": 1000},
                }
            },
        }
        state["items"].append(item)
        request = {"session_uri": "https://upload.youtube.com/resumable/session-inc", "offset": 0, "size": 1000}

        call_count = 0

        def do_upload():
            nonlocal call_count
            call_count += 1
            return {"video_id": "yt-video-dup"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"), \
             mock.patch("scripts.kesher_daily_pipeline.youtube_access_token", return_value="dummy-token"), \
             mock.patch("scripts.kesher_daily_pipeline.resume_upload_status", return_value={"offset": 500, "video_id": None}):
            with self.assertRaisesRegex(PipelineError, "EXTERNAL_RESULT_UNCERTAIN"):
                legacy_external_effect(state, item, "youtube_upload_bytes", request, do_upload)
            self.assertEqual(call_count, 0)

    def test_remote_intent_survives_vm_crash_and_prevents_duplicate_mutation(self):
        """Instance A persists intent remotely and dies; Instance B starts with empty filesystem,
        loads remote intent, and makes NO second NotebookLM/YouTube mutation.
        """
        from scripts import kesher_daily_pipeline as pipe
        pipe._REMOTE_MEDIA_INTENT_STORE.clear()

        # Instance A: runs on VM A, persists intent and dies (SIGKILL / power loss)
        # In a real hard crash, the intent is written ahead to remote storage before provider call,
        # and the VM dies before any response or failure can be recorded.
        request = {"notebook_id": "nb-999", "title": "Title A"}
        pipe._persist_remote_media_intent(
            "video-vm-crash-test",
            "provider_source",
            {"status": "intent", "request": copy.deepcopy(request), "started_at": pipe.utc_now()},
        )

        # Instance B: Fresh VM starts with empty disk! No local external_effects on item_b!
        state_b = {"version": 1, "items": []}
        item_b = {"id": "video-vm-crash-test", "source": {"title": "Title A"}}
        # Note: item_b has NO local "external_effects" key!
        self.assertNotIn("external_effects", item_b)
        state_b["items"].append(item_b)

        call_count_b = 0

        def second_attempt():
            nonlocal call_count_b
            call_count_b += 1
            return {"source_id": "duplicate-source-id"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            # When legacy_external_effect is invoked on Instance B, it loads remote intent
            # and fails closed because intent is uncertain, REFUSING any second mutation!
            with self.assertRaisesRegex(PipelineError, "EXTERNAL_RESULT_UNCERTAIN"):
                pipe.legacy_external_effect(state_b, item_b, "provider_source", request, second_attempt)

            # Verification: Instance B made ZERO duplicate mutations!
            self.assertEqual(call_count_b, 0)

    def test_remote_intent_completed_survives_vm_crash_and_returns_receipt(self):
        """Instance A persists completed receipt remotely; Instance B starts with empty disk,
        loads remote receipt, and returns it without any second provider mutation.
        """
        from scripts import kesher_daily_pipeline as pipe
        pipe._REMOTE_MEDIA_INTENT_STORE.clear()

        # Instance A: succeeds and persists receipt
        state_a = {"version": 1, "items": []}
        item_a = {"id": "video-vm-completed-test", "source": {"title": "Title C"}}
        state_a["items"].append(item_a)
        request = {"notebook_id": "nb-999", "title": "Title C"}

        call_count_a = 0

        def create_source_a():
            nonlocal call_count_a
            call_count_a += 1
            return {"source_id": "source-authoritative-99"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            receipt_a = pipe.legacy_external_effect(state_a, item_a, "provider_source", request, create_source_a)
            self.assertEqual(receipt_a["source_id"], "source-authoritative-99")
            self.assertEqual(call_count_a, 1)

        # Instance B: starts on fresh VM with empty disk
        state_b = {"version": 1, "items": []}
        item_b = {"id": "video-vm-completed-test", "source": {"title": "Title C"}}
        state_b["items"].append(item_b)

        call_count_b = 0

        def create_source_b():
            nonlocal call_count_b
            call_count_b += 1
            return {"source_id": "source-duplicate-b"}

        with mock.patch("scripts.kesher_daily_pipeline.save_state"):
            receipt_b = pipe.legacy_external_effect(state_b, item_b, "provider_source", request, create_source_b)
            self.assertEqual(receipt_b["source_id"], "source-authoritative-99")
            # Never called provider a second time!
            self.assertEqual(call_count_b, 0)


if __name__ == "__main__":
    unittest.main()
