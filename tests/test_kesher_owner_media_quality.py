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

    def test_dedup_batch_omission_recovered_by_exact_individual_read(self):
        from scripts import kesher_owner_reviewed_publish as p
        yt = Mock()
        a = {"id": "abcdefghijk", "snippet": {"channelId": p.CHANNEL}}
        b = {"id": "12345678901", "snippet": {"channelId": p.CHANNEL}}
        yt.videos.return_value.list.return_value.execute.side_effect = [
            {"items": [a]}, {"items": [b]},
        ]
        self.assertEqual(p.scan_video_records(yt, [a["id"], b["id"]]), [a, b])
        self.assertEqual(yt.videos.return_value.list.call_args_list[-1].kwargs,
                         {"part": "snippet,status", "id": b["id"]})

    def test_dedup_unresolved_individual_record_fails_closed(self):
        from scripts import kesher_owner_reviewed_publish as p
        yt = Mock()
        a = {"id": "abcdefghijk", "snippet": {"channelId": p.CHANNEL}}
        yt.videos.return_value.list.return_value.execute.side_effect = [
            {"items": [a]}, {"items": []},
        ]
        with self.assertRaisesRegex(RuntimeError, "INCOMPLETE_VIDEO_DEDUP_SCAN"):
            p.scan_video_records(yt, [a["id"], "12345678901"])

    def test_dedup_wrong_channel_or_duplicate_record_fails_closed(self):
        from scripts import kesher_owner_reviewed_publish as p
        yt = Mock()
        a = {"id": "abcdefghijk", "snippet": {"channelId": p.CHANNEL}}
        yt.videos.return_value.list.return_value.execute.return_value = {"items": [a, a]}
        with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_OR_DUPLICATE_VIDEO_RECORD"):
            p.scan_video_records(yt, [a["id"]])
        yt.videos.return_value.list.return_value.execute.return_value = {
            "items": [dict(a, snippet={"channelId": "wrong"})]}
        with self.assertRaisesRegex(RuntimeError, "UNEXPECTED_CHANNEL"):
            p.scan_video_records(yt, [a["id"]])

    def test_deleted_marker_requires_exact_channel_playlist_and_unavailable_status(self):
        from scripts import kesher_owner_reviewed_publish as p
        vid, playlist = "abcdefghijk", "UUx5fEFvdVf28HLAR2dFW64Q"
        row = {"contentDetails": {"videoId": vid}, "snippet": {
            "channelId": p.CHANNEL, "playlistId": playlist,
            "resourceId": {"kind": "youtube#video", "videoId": vid},
            "title": "Deleted video"}, "status": {"privacyStatus": "privacyStatusUnspecified"}}
        self.assertTrue(p.deleted_upload_marker(row, playlist))
        for key, value in (("title", "Private video"), ("videoOwnerChannelId", p.CHANNEL),
                           ("playlistId", "wrong"), ("channelId", "wrong")):
            changed = copy.deepcopy(row)
            changed["snippet"][key] = value
            self.assertFalse(p.deleted_upload_marker(changed, playlist))
        changed = copy.deepcopy(row)
        changed["status"]["privacyStatus"] = "private"
        self.assertFalse(p.deleted_upload_marker(changed, playlist))

    def test_confirmed_deleted_tombstone_accounted_but_unknown_missing_fails(self):
        from scripts import kesher_owner_reviewed_publish as p
        yt = Mock()
        a = {"id": "abcdefghijk", "snippet": {"channelId": p.CHANNEL}}
        b = "12345678901"
        yt.videos.return_value.list.return_value.execute.side_effect = [
            {"items": [a]}, {"items": []}]
        err = Exception("not found")
        err.resp = SimpleNamespace(status=404)
        err.content = json.dumps({"error": {"code": 404, "errors": [{
            "reason": "videoNotFound", "domain": "youtube.playlistItem", "location": "videoId"}]}}).encode()
        yt.playlistItems.return_value.list.return_value.execute.side_effect = err
        self.assertEqual(p.scan_video_records(yt, [a["id"], b], {b}, "uploads"), [a])
        yt.videos.return_value.list.return_value.execute.side_effect = [
            {"items": [a]}, {"items": []}]
        with self.assertRaisesRegex(RuntimeError, "INCOMPLETE_VIDEO_DEDUP_SCAN"):
            p.scan_video_records(yt, [a["id"], b], set(), "uploads")

    def test_deleted_marker_alone_and_generic_404_cannot_waive_missing(self):
        from scripts import kesher_owner_reviewed_publish as p
        yt = Mock()
        vid = "abcdefghijk"
        yt.videos.return_value.list.return_value.execute.side_effect = [
            {"items": []}, {"items": []}]
        err = Exception("generic 404")
        err.resp = SimpleNamespace(status=404)
        err.content = b'{"error":{"code":404,"errors":[{"reason":"playlistNotFound"}]}}'
        yt.playlistItems.return_value.list.return_value.execute.side_effect = err
        with self.assertRaisesRegex(RuntimeError, "INCOMPLETE_VIDEO_DEDUP_SCAN"):
            p.scan_video_records(yt, [vid], {vid}, "uploads")

    def test_productive_exact_repaired_source_and_metadata(self):
        from scripts import kesher_owner_reviewed_publish as p
        cfg = p.CONFIG[p.productive.SLUG]
        self.assertEqual(cfg["artifact"], 13757967291)
        self.assertEqual(cfg["canonical_sha"], p.productive.CANONICAL_SHA)
        self.assertIn("Adobe Firefly", p.metadata(cfg, "overview")["description"])
        self.assertNotIn("OpenAI", p.metadata(cfg, "overview")["description"])
        manifest = {"canonical_content_sha256": p.productive.CANONICAL_SHA,
                    "visual_repair": {"input_artifact_id": 13757158570,
                        "input_archive_sha256": p.productive.REPAIR_ARCHIVE_SHA,
                        "original_video_sha256": p.productive.REPAIR_SHORT_SHA,
                        "audio_packets_preserved": True,
                        "scene_frame_boundaries": [0,128,267,331,407,506,701,760],
                        "composition": "full_frame_9_16_editorial_focus_crops_no_blurred_padding",
                        "audio_packet_sha256": "92cba18305a9c229891f682279472716c489fc56228bbbcdafaeba9923466d9b"}}
        with patch.object(p.productive, "_audio_packets", return_value=manifest["visual_repair"]["audio_packet_sha256"]):
            p.validate_productive_repair(manifest, Path("short.mp4"), "short")
        with patch.object(p.productive, "_audio_packets", return_value="0"*64):
            with self.assertRaisesRegex(RuntimeError, "PRODUCTIVE_SHORT_AUDIO_PACKET_MISMATCH"):
                p.validate_productive_repair(manifest, Path("short.mp4"), "short")
        changed = copy.deepcopy(manifest)
        changed["visual_repair"]["composition"] = "blurred_padding"
        with self.assertRaisesRegex(RuntimeError, "PRODUCTIVE_SHORT_NATIVE_REPAIR_EVIDENCE_MISMATCH"):
            p.validate_productive_repair(changed, Path("short.mp4"), "short")
        changed = copy.deepcopy(manifest)
        changed["canonical_content_sha256"] = "0"*64
        with self.assertRaisesRegex(RuntimeError, "PRODUCTIVE_CANONICAL_MANIFEST_MISMATCH"):
            p.validate_productive_repair(changed, Path("short.mp4"), "short")

    def test_productive_archive_requires_asr_evidence(self):
        import hashlib
        import zipfile
        from scripts import kesher_owner_reviewed_publish as p
        cfg = dict(p.CONFIG[p.productive.SLUG])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "candidate.zip"
            names = {"asr-review.json"}
            for kind in p.KINDS:
                names.update((f"{kind}.mp4", f"{kind}-manifest.json",
                              f"{kind}-review-voice.wav", f"{kind}-visual-contact-sheet.jpg",
                              f"{kind}-asr.txt"))
                names.update(f"{kind}-frame-{i:02d}.jpg" for i in range(1,9))
            with zipfile.ZipFile(archive, "w") as z:
                for name in names:
                    z.writestr(name, b"test")
            cfg["zip_sha"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            out = root / "out"
            out.mkdir()
            p.archive_files(archive, out, cfg)
            self.assertEqual({x.name for x in out.iterdir()}, names)
            with zipfile.ZipFile(archive, "w") as z:
                for name in names - {"short-asr.txt"}:
                    z.writestr(name, b"test")
            cfg["zip_sha"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "ARTIFACT_FILE_SET_MISMATCH"):
                p.archive_files(archive, out, cfg)

    def test_7500_exact_repair_metadata_and_prefix_guard(self):
        from scripts import kesher_owner_reviewed_publish as p
        cfg = p.CONFIG[p.code7500.SLUG]
        self.assertEqual(cfg["artifact"], 13764754562)
        self.assertEqual(cfg["canonical_sha"], p.code7500.CANONICAL_SHA)
        self.assertEqual(p.metadata(cfg, "overview")["title"], "איך יודעים שהזוגיות במשבר? 5 סימנים שלא כדאי להתעלם מהם")
        short = p.metadata(cfg, "short", "abcdefghijk")
        self.assertEqual(short["title"], "זלזול בזוגיות: הסימן שהריב כבר לא רק על הנושא")
        self.assertIn("זלזול בזוגיות", short["tags"])
        self.assertIn("Adobe Firefly", short["description"])
        self.assertNotIn("OpenAI", short["description"])
        manifest = {"canonical_content_sha256": p.code7500.CANONICAL_SHA,
                    "composition": "native_full_frame_9_16_no_padding",
                    "targeted_repair": {
                        "input_artifact_id": p.code7500.REPAIR_ARTIFACT,
                        "input_archive_sha256": p.code7500.REPAIR_ARCHIVE_SHA,
                        "original_short_sha256": p.code7500.REPAIR_SHORT_SHA,
                        "overview_video_sha256": p.code7500.REPAIR_OVERVIEW_SHA,
                        "changed_scene_index": 3, "prefix_frames": 742,
                        "prefix_frame_hashes_sha256": "ff197c2b69ba719ff0ea31df1d475ff8c9bacf054045156711cc703a7bf6b7a8",
                        "prefix_aac_sha256": "1bc4f2e0ffb0499587ec017d47236d0185c3c1180d0c4b07a6fdff2a11846a9c",
                        "prefix_aac_bytes": 512016, "prefix_pixels_and_aac_preserved": True}}
        with patch.object(p, "sha", return_value=p.code7500.REPAIR_OVERVIEW_SHA):
            p.validate_7500_repair(manifest, Path("overview.mp4"), "overview")
        changed = copy.deepcopy(manifest)
        changed["targeted_repair"]["prefix_pixels_and_aac_preserved"] = False
        with self.assertRaisesRegex(RuntimeError, "7500_TARGETED_REPAIR_EVIDENCE_MISMATCH"):
            p.validate_7500_repair(changed, Path("short.mp4"), "short")
        changed = copy.deepcopy(manifest)
        changed["canonical_content_sha256"] = "0"*64
        with self.assertRaisesRegex(RuntimeError, "7500_CANONICAL_MANIFEST_MISMATCH"):
            p.validate_7500_repair(changed, Path("short.mp4"), "short")
        with patch.object(p, "sha", return_value="83df806140023ca39f515dc83a1a9efc52b0c9caf0056ab437251795e2240066"), \
             patch.object(p.code7500, "_frame_hashes", return_value=["changed"]*983), \
             patch.object(p.code7500, "_aac_packets", return_value=b"changed"):
            with self.assertRaisesRegex(RuntimeError, "7500_SHORT_REVIEWED_PREFIX_MISMATCH"):
                p.validate_7500_repair(manifest, Path("short.mp4"), "short")

    def test_7500_archive_requires_exact_asr_evidence(self):
        import hashlib
        import zipfile
        from scripts import kesher_owner_reviewed_publish as p
        cfg = dict(p.CONFIG[p.code7500.SLUG])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "candidate.zip"
            names = {"asr-review.json"}
            for kind in p.KINDS:
                names.update((f"{kind}.mp4", f"{kind}-manifest.json",
                              f"{kind}-review-voice.wav", f"{kind}-visual-contact-sheet.jpg",
                              f"{kind}-asr.txt"))
                names.update(f"{kind}-frame-{i:02d}.jpg" for i in range(1,9))
            with zipfile.ZipFile(archive, "w") as z:
                for name in names:
                    z.writestr(name, b"test")
            cfg["zip_sha"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            out = root / "out"
            out.mkdir()
            p.archive_files(archive, out, cfg)
            self.assertEqual({x.name for x in out.iterdir()}, names)
            with zipfile.ZipFile(archive, "w") as z:
                for name in names - {"short-asr.txt"}:
                    z.writestr(name, b"test")
            cfg["zip_sha"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError, "ARTIFACT_FILE_SET_MISMATCH"):
                p.archive_files(archive, out, cfg)

    def test_guarded_owner_publish_installs_photo_validation_dependency(self):
        from scripts import kesher_owner_reviewed_publish as p
        workflow = (p.ROOT / ".github/workflows/kesher-short-v4.yml").read_text(encoding="utf-8")
        step = workflow.split("- name: OWNER publish exact independently reviewed artifact, no generation", 1)[1].split("\n      - name:", 1)[0]
        self.assertIn("inputs.operation == 'owner_reviewed_publish'", step)
        self.assertIn("Pillow==11.3.0", step)
        self.assertIn("python -m unittest tests.test_kesher_owner_media_quality -v", step)
        self.assertIn("python -m scripts.kesher_owner_reviewed_publish", step)

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
