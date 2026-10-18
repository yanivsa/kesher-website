import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import kesher_final_attempt_fallback as fallback


class FinalAttemptFallbackTests(unittest.TestCase):
    def _item(self, item_id, attempt, *, voice_only=True, uploaded=False, status="rejected"):
        note = (
            "נפסל טכנית: Detected male voice pitch (129.0 Hz < 155 Hz threshold); Israeli female voice required"
            if voice_only
            else "נפסל טכנית: יחס התמונה 1080x1920 אינו יחס אופקי טבעי 16:9"
        )
        final_sha = hashlib.sha256(b"x" * 2048).hexdigest()
        src = {"slug": "same-slug", "content_sha256": "same-hash"}
        manifest = {
            "item_id": item_id,
            "source": src,
            "final_mp4": f"{item_id}.mp4",
            "final_sha256": final_sha,
            "raw_sha256": "r" * 64,
            "failure_signature": "wrong_narrator_gender" if voice_only else "invalid_aspect_ratio",
            "rejection_reasons": ["Detected male voice pitch (129.0 Hz < 155 Hz threshold); Israeli female voice required"] if voice_only else ["יחס התמונה 1080x1920 אינו יחס אופקי טבעי 16:9"],
            "media": {
                "codec": "h264",
                "audio_codec": "aac",
                "width": 1920 if voice_only else 1080,
                "height": 1080 if voice_only else 1920,
                "duration": 120.0,
            },
            "content_duration_seconds": 120.0,
            "signature_overlay": True,
            "signature_asset_sha256": "s" * 64,
            "youtube_metadata": {
                "title": "Title",
                "description": "Description",
                "tags": ["tag"],
            },
            "visual_pipeline": "remotion-v1-notebooklm-audio",
        }
        return {
            "id": item_id,
            "fresh_generation_attempt": attempt,
            "source": src,
            "uploaded": uploaded,
            "status": status,
            "technical_verified": False,
            "final_mp4": f"{item_id}.mp4",
            "final_sha256": final_sha,
            "media": {"codec": "h264", "audio_codec": "aac", "width": 1920, "height": 1080, "duration": 120.0},
            "review_notes": {"technical": note},
            "manifest": manifest,
            "failure_signature": manifest["failure_signature"],
            "updated_at": f"2026-09-10T0{attempt}:00:00Z",
        }

    def setUp(self):
        super().setUp()
        self.fallback_gate_patcher = mock.patch.object(fallback, "FALLBACK_PROMOTION_ENABLED", True)
        self.fallback_gate_patcher.start()

    def tearDown(self):
        self.fallback_gate_patcher.stop()
        super().tearDown()

    def test_production_default_refuses_fallback(self):
        with mock.patch.object(fallback, "FALLBACK_PROMOTION_ENABLED", False):
            self.assertFalse(fallback.is_fallback_promotion_enabled())
            state = {"version": 1, "items": [self._item("first", 1), self._item("second", 2), self._item("third", 3, voice_only=False)]}
            chosen = fallback.promote_last_usable_after_third_attempt(state)
            self.assertIsNone(chosen)

    def test_third_attempt_failure_promotes_latest_usable_same_source_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            first = self._item("first", 1)
            second = self._item("second", 2)
            third = self._item("third", 3, voice_only=False)
            for row in (first, second, third):
                (state_dir / row["final_mp4"]).write_bytes(b"x" * 2048)
            state = {"version": 1, "items": [first, second, third]}
            with mock.patch.object(fallback, "STATE_DIR", state_dir):
                chosen = fallback.promote_last_usable_after_third_attempt(state)

            self.assertIs(chosen, second)
            self.assertTrue(second["technical_verified"])
            self.assertEqual(second["status"], "pending_review")
            self.assertTrue(second["final_attempt_fallback"])
            self.assertEqual(second["voice_gate_waived_after_attempt"], 3)
            self.assertEqual(third["status"], "superseded")

    def test_does_nothing_before_third_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            first = self._item("first", 1)
            second = self._item("second", 2)
            for row in (first, second):
                (state_dir / row["final_mp4"]).write_bytes(b"x" * 2048)
            state = {"version": 1, "items": [first, second]}
            with mock.patch.object(fallback, "STATE_DIR", state_dir):
                chosen = fallback.promote_last_usable_after_third_attempt(state)
            self.assertIsNone(chosen)

    def test_never_reuses_other_source_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            third = self._item("third", 3, voice_only=False)
            other = self._item("other", 2)
            other["source"]["content_sha256"] = "other-hash"
            for row in (third, other):
                (state_dir / row["final_mp4"]).write_bytes(b"x" * 2048)
            state = {"version": 1, "items": [other, third]}
            with mock.patch.object(fallback, "STATE_DIR", state_dir):
                chosen = fallback.promote_last_usable_after_third_attempt(state)
            self.assertIsNone(chosen)

    def test_never_runs_after_public_upload_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            previous = self._item("previous", 2)
            third = self._item("third", 3, voice_only=False)
            public = self._item("public", 1, uploaded=True, status="uploaded")
            for row in (previous, third, public):
                (state_dir / row["final_mp4"]).write_bytes(b"x" * 2048)
            state = {"version": 1, "items": [previous, third, public]}
            with mock.patch.object(fallback, "STATE_DIR", state_dir):
                chosen = fallback.promote_last_usable_after_third_attempt(state)
            self.assertIsNone(chosen)

    def test_unrelated_technical_rejection_not_promoted(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            # Attempt 2 has an unrelated technical failure (bad aspect ratio, not voice pitch)
            second = self._item("second", 2, voice_only=False)
            third = self._item("third", 3, voice_only=False)
            for row in (second, third):
                (state_dir / row["final_mp4"]).write_bytes(b"x" * 2048)
            state = {"version": 1, "items": [second, third]}
            with mock.patch.object(fallback, "STATE_DIR", state_dir):
                chosen = fallback.promote_last_usable_after_third_attempt(state)
            self.assertIsNone(chosen)

    def test_ordinary_pending_attempt3_does_not_trigger_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            second = self._item("second", 2, voice_only=True)
            third = self._item("third", 3, status="generating")
            for row in (second, third):
                (state_dir / row["final_mp4"]).write_bytes(b"x" * 2048)
            state = {"version": 1, "items": [second, third]}
            with mock.patch.object(fallback, "STATE_DIR", state_dir):
                # When allow_pending_abandonment is False, ordinary pending does NOT promote
                chosen = fallback.promote_last_usable_after_third_attempt(state, allow_pending_abandonment=False)
                self.assertIsNone(chosen)

                # When explicitly allowed (e.g. hard timeout abandonment), it can promote
                chosen_allowed = fallback.promote_last_usable_after_third_attempt(state, allow_pending_abandonment=True)
                self.assertIs(chosen_allowed, second)

    def test_no_new_generation_created_on_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            first = self._item("first", 1)
            second = self._item("second", 2)
            third = self._item("third", 3, voice_only=False)
            for row in (first, second, third):
                (state_dir / row["final_mp4"]).write_bytes(b"x" * 2048)
            state = {"version": 1, "items": [first, second, third]}
            original_item_count = len(state["items"])
            with mock.patch.object(fallback, "STATE_DIR", state_dir):
                chosen = fallback.promote_last_usable_after_third_attempt(state)

            self.assertIs(chosen, second)
            self.assertEqual(len(state["items"]), original_item_count, "Promotion must not create any new item in items list")

    def test_find_usable_candidate_without_local_file(self):
        second = self._item("second", 2, voice_only=True)
        third = {
            "id": "third",
            "fresh_generation_attempt": 3,
            "source": {"slug": "same-slug", "content_sha256": "same-hash"},
            "status": "generating",
            "uploaded": False,
        }
        state = {"version": 1, "items": [second, third]}

        # Without requiring file on disk, remote controller inspects metadata candidate
        candidate = fallback.find_usable_candidate(state, "same-slug", "same-hash", require_file=False)
        self.assertIs(candidate, second)

        # Mismatched source hash returns None
        mismatch = fallback.find_usable_candidate(state, "same-slug", "other-hash", require_file=False)
        self.assertIsNone(mismatch)


if __name__ == "__main__":
    unittest.main()
