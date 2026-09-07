from __future__ import annotations

import unittest

from scripts import kesher_video_upload_guard as guard


def technical_item(slug: str = "today", day: str = "2026-08-20", status: str = "approved") -> dict:
    return {
        "id": f"video-{slug}",
        "status": status,
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
        "visual_review_status": "approved",
        "semantic_review_status": "approved",
        "metadata_review_status": "approved",
        "reviewed_at": "2026-08-20T04:00:00+00:00",
        "reviewer": {"type": "jules", "session": "sessions/review-1"},
    }


class VideoUploadGuardTests(unittest.TestCase):
    def test_technically_verified_candidate_passes(self) -> None:
        guard.validate_candidate(technical_item())

    def test_missing_jules_identity_does_not_block(self) -> None:
        item = technical_item(status="pending_review")
        item.pop("reviewer", None)
        item.pop("reviewed_at", None)
        guard.validate_candidate(item)

    def test_changed_mp4_does_not_require_review_rebinding(self) -> None:
        item = technical_item()
        item["final_sha256"] = "x" * 64
        guard.validate_candidate(item)

    def test_jules_rejected_candidate_still_passes_when_technically_verified(self) -> None:
        item = technical_item(status="rejected")
        item["visual_review_status"] = "rejected"
        guard.validate_candidate(item)

    def test_missing_final_sha_fails_closed(self) -> None:
        item = technical_item()
        item["final_sha256"] = ""
        with self.assertRaisesRegex(guard.UploadGuardError, "no final MP4 SHA-256"):
            guard.validate_candidate(item)

    def test_technical_failure_fails_closed(self) -> None:
        item = technical_item()
        item["technical_verified"] = False
        with self.assertRaisesRegex(guard.UploadGuardError, "not technically verified"):
            guard.validate_candidate(item)

    def test_oldest_unresolved_item_is_selected_deterministically(self) -> None:
        older = technical_item("older", "2026-08-18")
        newer = technical_item("newer", "2026-08-19")
        selected = guard.select_upload_candidate({"items": [newer, older]})
        self.assertEqual(selected["id"], "video-older")


    def test_short_candidate_passes_with_verified_signature_video(self) -> None:
        item = technical_item()
        item.update({
            "type": "article_short",
            "source_mode": "direct-short",
            "signature_verified": True,
            "signature_fullscreen": True,
            "signature_duration_seconds": 3.0,
            "signature_video_sha256": "v" * 64,
        })
        guard.validate_candidate(item)

    def test_short_candidate_fails_closed_when_derived_from_overview_segment(self) -> None:
        item = technical_item()
        item.update({
            "type": "article_short",
            "source_mode": "overview-segment",
            "signature_verified": True,
            "signature_fullscreen": True,
            "signature_duration_seconds": 3.0,
            "signature_video_sha256": "v" * 64,
        })
        with self.assertRaisesRegex(guard.UploadGuardError, "derived from overview-segment"):
            guard.validate_candidate(item)

    def test_short_candidate_fails_closed_when_svg_only_or_missing_signature_video(self) -> None:
        item = technical_item()
        item.update({
            "type": "article_short",
            "source_mode": "direct-short",
            "signature_verified": True,
            "signature_asset": "signature-mask.svg",
            "signature_sha256": "s" * 64,
        })
        with self.assertRaisesRegex(guard.UploadGuardError, "lacks verified 3.0s full-screen video signature"):
            guard.validate_candidate(item)


if __name__ == "__main__":
    unittest.main()
