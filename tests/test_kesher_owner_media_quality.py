"""Fail-closed KESHER OWNER media QA before the first canonical YouTube upload."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from scripts.kesher_runtime.media_worker import _publish, require_owner_media_quality
from scripts.kesher_runtime.state import StateInvalid


class OwnerMediaQualityGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.item = {
            "id": "media-" + "a" * 24,
            "type": "video_overview",
            "status": "pending_review",
            "technical_verified": True,
            "source": {"slug": "approved-topic", "content_sha256": "1" * 64},
            "final_sha256": "2" * 64,
            "manifest_sha256": "3" * 64,
            "transcript_sha256": "4" * 64,
            "visual_review_sha256": "5" * 64,
            "source_file_sha256": "6" * 64,
            "frame_sha256": {f"frames/frame-{n}.png": format(n, "x") * 64 for n in range(1, 9)},
        }
        self.approval = {
            "schema_version": 1,
            "source_slug": self.item["source"]["slug"],
            "content_sha256": self.item["source"]["content_sha256"],
            "media_kind": "overview",
            "media_item_id": self.item["id"],
            "final_sha256": self.item["final_sha256"],
            "manifest_sha256": self.item["manifest_sha256"],
            "transcript_sha256": self.item["transcript_sha256"],
            "visual_review_sha256": self.item["visual_review_sha256"],
            "source_file_sha256": self.item["source_file_sha256"],
            "frame_sha256": self.item["frame_sha256"],
            "reviewed_by": "OWNER",
            "reviewed_at": "2026-11-09T15:00:00Z",
            "checks": {
                "visual": "approved",
                "semantic": "approved",
                "audio": "approved",
                "metadata": "approved",
                "licensing": "approved",
            },
            "methods": {
                "visual": "full_motion_and_frames",
                "semantic": "research_vs_exact_transcript",
                "audio": "authorized_audio_tool_with_script_comparison",
            },
            "review_notes": {
                "visual": "נבדקו הפריימים והתנועה לכל אורך הסרטון ללא טקסט חופף.",
                "semantic": "התמלול המלא הושווה למחקרים עם ההסתייגויות הנדרשות.",
                "audio": "נבדק פס הקול האמיתי ולא רק השם של הקובץ המקורי.",
                "licensing": "רישיון השימוש בקול ובתמונות נבדק ואומת לשימוש מסחרי.",
            },
            "rights": {
                "commercial_use_permitted": True,
                "voice_license_url": "https://example.org/voice-license",
                "visual_license_url": "https://example.org/image-license",
            },
        }

    def write(self) -> None:
        (self.root / "approved-topic--overview.json").write_text(
            json.dumps(self.approval, ensure_ascii=False), encoding="utf-8"
        )

    def check(self) -> None:
        require_owner_media_quality(self.item, "overview", approval_root=self.root)

    def test_no_approval_means_quality_hold_not_implicit_pass(self) -> None:
        with self.assertRaisesRegex(StateInvalid, "EDITORIAL_QA_PENDING"):
            self.check()

    def test_exact_owner_approved_media_with_rights_passes(self) -> None:
        self.write()
        self.check()

    def test_refuses_jules_or_external_reviewer_and_unsupported_audio_method(self) -> None:
        self.approval["reviewed_by"] = "jules"
        self.write()
        with self.assertRaisesRegex(StateInvalid, "OWNER_ATTESTATION"):
            self.check()
        self.approval["reviewed_by"] = "OWNER"
        self.approval["methods"]["audio"] = "asr_only"
        self.write()
        with self.assertRaisesRegex(StateInvalid, "METHOD"):
            self.check()

    def test_refuses_any_editorial_hold_or_missing_licensing(self) -> None:
        self.approval["checks"]["semantic"] = "pending"
        self.write()
        with self.assertRaisesRegex(StateInvalid, "QA_HOLD"):
            self.check()
        self.approval["checks"]["semantic"] = "approved"
        self.approval["rights"]["commercial_use_permitted"] = False
        self.write()
        with self.assertRaisesRegex(StateInvalid, "LICENSE_HOLD"):
            self.check()
        self.approval["rights"]["commercial_use_permitted"] = True
        self.approval["rights"]["visual_license_url"] = ""
        self.write()
        with self.assertRaisesRegex(StateInvalid, "LICENSE_EVIDENCE"):
            self.check()

    def test_changed_binary_or_frame_or_source_rejects_stale_approval(self) -> None:
        self.write()
        for key, value in [("final_sha256", "b" * 64), ("visual_review_sha256", "c" * 64)]:
            changed = copy.deepcopy(self.item)
            changed[key] = value
            with self.assertRaisesRegex(StateInvalid, "EXACT_IDENTITY"):
                require_owner_media_quality(changed, "overview", approval_root=self.root)
        changed = copy.deepcopy(self.item)
        changed["frame_sha256"]["frames/frame-2.png"] = "d" * 64
        with self.assertRaisesRegex(StateInvalid, "FRAME_HASH"):
            require_owner_media_quality(changed, "overview", approval_root=self.root)
        changed = copy.deepcopy(self.item)
        changed["source"]["content_sha256"] = "f" * 64
        with self.assertRaisesRegex(StateInvalid, "EXACT_IDENTITY"):
            require_owner_media_quality(changed, "overview", approval_root=self.root)

    def test_no_path_traversal_or_wrong_media_kind(self) -> None:
        changed = copy.deepcopy(self.item)
        changed["source"]["slug"] = "../not-approved"
        with self.assertRaisesRegex(StateInvalid, "SOURCE_IDENTITY"):
            require_owner_media_quality(changed, "overview", approval_root=self.root)
        self.write()
        with self.assertRaisesRegex(StateInvalid, "MEDIA_KIND"):
            require_owner_media_quality(self.item, "short", approval_root=self.root)

    def test_canonical_publish_never_attempts_upload_without_qa(self) -> None:
        context = SimpleNamespace(target=SimpleNamespace(kind="overview", source=SimpleNamespace(slug="approved-topic")))
        state = SimpleNamespace(item=copy.deepcopy(self.item), context=context, persist=Mock())
        core = SimpleNamespace(
            STATE_DIR=self.root,
            ffprobe=lambda path: {"width": 1280, "height": 720, "duration": 100},
            upload_only=Mock(side_effect=AssertionError("UPLOAD MUST NOT OCCUR")),
        )
        guard = SimpleNamespace(_signature_verified=lambda item: True)
        with patch("scripts.kesher_runtime.media_worker.require_owner_media_quality",
                   side_effect=StateInvalid("EDITORIAL_QA_PENDING")):
            with self.assertRaisesRegex(StateInvalid, "EDITORIAL_QA_PENDING"):
                _publish(state, core, guard)
        core.upload_only.assert_not_called()
        state.persist.assert_not_called()
        self.assertEqual(state.item["status"], "pending_review")


if __name__ == "__main__":
    unittest.main()
