from __future__ import annotations

import unittest

from scripts import kesher_video_upload_guard as guard


def approved_item(slug: str = "today", day: str = "2026-08-20") -> dict:
    final_sha = "f" * 64
    return {
        "id": f"video-{slug}",
        "status": "approved",
        "uploaded": False,
        "technical_verified": True,
        "israel_date": day,
        "source": {
            "slug": slug,
            "date": day,
            "content_sha256": "s" * 64,
        },
        "final_sha256": final_sha,
        "review_approved_for_sha256": final_sha,
        "manifest_sha256": "m" * 64,
        "transcript_sha256": "t" * 64,
        "source_file_sha256": "q" * 64,
        "visual_review_sha256": "v" * 64,
        "frame_sha256": {"frame-1.png": "a" * 64},
        "visual_review_status": "approved",
        "semantic_review_status": "approved",
        "metadata_review_status": "approved",
        "reviewed_at": "2026-08-20T04:00:00+00:00",
        "reviewer": {"type": "jules", "session": "sessions/review-1"},
    }


class VideoUploadGuardTests(unittest.TestCase):
    def test_exact_jules_approved_candidate_passes(self) -> None:
        guard.validate_candidate(approved_item())

    def test_missing_jules_identity_fails_closed(self) -> None:
        item = approved_item()
        item["reviewer"] = {"type": "manual", "session": "manual"}
        with self.assertRaisesRegex(guard.UploadGuardError, "authoritative Jules reviewer"):
            guard.validate_candidate(item)

    def test_changed_mp4_after_review_fails_closed(self) -> None:
        item = approved_item()
        item["final_sha256"] = "x" * 64
        with self.assertRaisesRegex(guard.UploadGuardError, "exact final MP4 SHA-256"):
            guard.validate_candidate(item)

    def test_rejected_gate_fails_closed(self) -> None:
        item = approved_item()
        item["status"] = "rejected"
        item["visual_review_status"] = "rejected"
        with self.assertRaises(guard.UploadGuardError):
            guard.validate_candidate(item)

    def test_oldest_unresolved_item_is_selected_deterministically(self) -> None:
        older = approved_item("older", "2026-08-18")
        newer = approved_item("newer", "2026-08-19")
        selected = guard.select_upload_candidate({"items": [newer, older]})
        self.assertEqual(selected["id"], "video-older")


if __name__ == "__main__":
    unittest.main()
