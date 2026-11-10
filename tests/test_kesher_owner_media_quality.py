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


class OwnerReviewedPublishTests(unittest.TestCase):
    def test_exact_source_and_metadata(self):
        from scripts import kesher_owner_reviewed_publish as p
        for slug, cfg in p.CONFIG.items():
            self.assertIs(p.source_config(slug, cfg["canonical_sha"]), cfg)
            with self.assertRaises(RuntimeError):
                p.source_config(slug, cfg["module"].SOURCE_SHA)
            self.assertIn("content_sha256=" + cfg["canonical_sha"], p.metadata(cfg, "overview")["description"])
            with self.assertRaises(RuntimeError):
                p.source_config(slug, "0" * 64)
            overview = p.metadata(cfg, "overview")
            short = p.metadata(cfg, "short", "abcdefghijk")
            self.assertIn(cfg["module"].ARTICLE, overview["description"])
            self.assertIn(cfg["module"].ARTICLE, short["description"])
            self.assertIn("https://creativecommons.org/licenses/by/4.0/", short["description"])
            self.assertIn("https://www.youtube.com/watch?v=abcdefghijk", short["description"])
            with self.assertRaises(RuntimeError):
                p.metadata(cfg, "short")

    def test_recompute_both_hashes_from_exact_committed_post(self):
        from scripts import kesher_owner_reviewed_publish as p
        for cfg in p.CONFIG.values():
            post = p.verify_source_binding(cfg)
            for key in ("title", "excerpt", "content"):
                changed = dict(post)
                changed[key] += " שינוי"
                with self.assertRaisesRegex(RuntimeError, "CANONICAL_SOURCE_BINDING_MISMATCH"):
                    p.verify_source_binding(cfg, changed)

    def test_legacy_body_hash_is_not_a_public_identity(self):
        from scripts import kesher_owner_reviewed_publish as p
        cfg = p.CONFIG[p.gifted.SLUG]
        meta = p.metadata(cfg, "overview")
        meta["description"] = meta["description"].replace(cfg["canonical_sha"], cfg["module"].SOURCE_SHA)
        with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_EXISTING_SOURCE_VIDEO"):
            p.classify(cfg, [{"id": "abcdefghijk", "snippet": dict(meta, channelId=p.CHANNEL)}])

    def test_dedup_exact_ambiguous_and_duplicate(self):
        from scripts import kesher_owner_reviewed_publish as p
        cfg = p.CONFIG[p.gifted.SLUG]
        meta = p.metadata(cfg, "overview")
        row = {"id": "abcdefghijk", "snippet": dict(meta, channelId=p.CHANNEL)}
        self.assertEqual(p.classify(cfg, [row]), {"overview": row})
        with self.assertRaises(RuntimeError):
            p.classify(cfg, [row, dict(row, id="12345678901")])
        ambiguous = {"id": "12345678901", "snippet": {
            "channelId": p.CHANNEL, "description": cfg["module"].ARTICLE}}
        with self.assertRaises(RuntimeError):
            p.classify(cfg, [ambiguous])

    def test_wrong_archive_digest_fails_before_extraction(self):
        from scripts import kesher_owner_reviewed_publish as p
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "wrong.zip"
            archive.write_bytes(b"not the reviewed artifact")
            with self.assertRaisesRegex(RuntimeError, "ARTIFACT_DIGEST_MISMATCH"):
                p.archive_files(archive, root, p.CONFIG[p.gifted.SLUG])
            self.assertEqual(list(root.iterdir()), [archive])


if __name__ == "__main__":
    unittest.main()
