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
        return {
            "id": item_id,
            "fresh_generation_attempt": attempt,
            "source": {"slug": "same-slug", "content_sha256": "same-hash"},
            "uploaded": uploaded,
            "status": status,
            "technical_verified": False,
            "final_mp4": f"{item_id}.mp4",
            "final_sha256": f"sha-{item_id}",
            "media": {"width": 1920, "height": 1080, "duration": 120},
            "review_notes": {"technical": note},
            "updated_at": f"2026-09-10T0{attempt}:00:00Z",
        }

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


if __name__ == "__main__":
    unittest.main()
