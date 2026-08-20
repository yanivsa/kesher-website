from __future__ import annotations

import unittest

from scripts import kesher_video_upload_guard as guard


def technical_item(slug: str = "today", day: str = "2026-08-20") -> dict:
    return {
        "id": f"video-{slug}",
        "status": "pending_review",
        "uploaded": False,
        "technical_verified": True,
        "israel_date": day,
        "source": {
            "slug": slug,
            "date": day,
            "content_sha256": "s" * 64,
        },
        "final_sha256": "f" * 64,
        "manifest_sha256": "m" * 64,
        "transcript_sha256": "t" * 64,
        "source_file_sha256": "q" * 64,
        "visual_review_sha256": "v" * 64,
        "frame_sha256": {"frame-1.png": "a" * 64},
    }


class VideoUploadGuardTests(unittest.TestCase):
    def test_technically_verified_pending_review_candidate_passes(self) -> None:
        guard.validate_candidate(technical_item())

    def test_jules_rejection_is_advisory_and_does_not_block(self) -> None:
        item = technical_item()
        item["status"] = "rejected"
        item["visual_review_status"] = "rejected"
        item["reviewer"] = {"type": "jules", "session": "sessions/review-1"}
        guard.validate_candidate(item)

    def test_missing_jules_identity_does_not_block_technical_candidate(self) -> None:
        item = technical_item()
        item["status"] = "approved"
        item["reviewer"] = {"type": "manual", "session": "manual"}
        guard.validate_candidate(item)

    def test_missing_final_mp4_hash_fails_closed(self) -> None:
        item = technical_item()
        item["final_sha256"] = ""
        with self.assertRaisesRegex(guard.UploadGuardError, "final MP4 SHA-256"):
            guard.validate_candidate(item)

    def test_non_technical_candidate_fails_closed(self) -> None:
        item = technical_item()
        item["technical_verified"] = False
        with self.assertRaisesRegex(guard.UploadGuardError, "not technically verified"):
            guard.validate_candidate(item)

    def test_oldest_unresolved_item_is_selected_deterministically(self) -> None:
        older = technical_item("older", "2026-08-18")
        newer = technical_item("newer", "2026-08-19")
        selected = guard.select_upload_candidate({"items": [newer, older]})
        self.assertEqual(selected["id"], "video-older")


if __name__ == "__main__":
    unittest.main()
