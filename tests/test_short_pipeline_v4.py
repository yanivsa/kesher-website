import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import kesher_short_pipeline_v4 as short


class ShortPipelineV4Tests(unittest.TestCase):
    def source(self):
        return {
            "slug": "how-to-talk",
            "title": "איך מדברים בלי להפוך כל שיחה לריב",
            "category": "זוגיות",
            "content_sha256": "a" * 64,
            "youtube_metadata": {
                "title": "איך מדברים בלי להפוך כל שיחה לריב",
                "description": "תיאור המאמר https://kesher.saharoni.com",
                "tags": ["זוגיות", "תקשורת"],
            },
        }

    def test_prompt_requests_one_complete_short_ready_hebrew_idea_without_duration_cap(self):
        prompt = short.generation_prompt(self.source())
        self.assertIn("קול של אישה ישראלית", prompt)
        self.assertIn("הרעיון השלם", prompt)
        self.assertIn("סיום טבעי", prompt)
        self.assertNotIn("45 עד 55 שניות", prompt)
        self.assertNotIn("55 השניות", prompt)

    def test_long_source_keeps_its_full_natural_duration(self):
        start, duration = short.short_window(132.0)
        self.assertEqual(start, 0.0)
        self.assertEqual(duration, 132.0)

    def test_valid_short_source_keeps_its_natural_duration(self):
        start, duration = short.short_window(44.25)
        self.assertEqual(start, 0.0)
        self.assertEqual(duration, 44.25)

    def test_short_source_keeps_its_full_duration_without_minimum(self):
        start, duration = short.short_window(12.5)
        self.assertEqual(start, 0.0)
        self.assertEqual(duration, 12.5)

    def test_vertical_technical_contract_accepts_exact_short(self):
        failures = short.short_technical_failures(
            {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 45.0}
        )
        self.assertEqual(failures, [])

    def test_vertical_technical_contract_accepts_long_vertical_media(self):
        failures = short.short_technical_failures(
            {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 132.0}
        )
        self.assertEqual(failures, [])

    def test_vertical_technical_contract_accepts_short_vertical_media(self):
        failures = short.short_technical_failures(
            {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 12.5}
        )
        self.assertEqual(failures, [])

    def test_short_v4_passes_generation_attempt_identity_to_voice_validator(self):
        media = {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 45.0}
        item = {
            "fresh_generation_attempt": 3,
            "source_mode": "direct-short",
            "signature_fullscreen": True,
            "signature_duration_seconds": 3.0,
            "signature_video_sha256": "s" * 64,
            "signature_verified": True,
        }
        with tempfile.NamedTemporaryFile(suffix=".mp4") as handle:
            video_path = Path(handle.name)
            with mock.patch.object(
                short.core,
                "validate_female_voice",
                return_value=(True, 129.0, "fallback accepted"),
            ) as validator:
                failures = short.short_technical_failures(media, video_path, item)

        validator.assert_called_once_with(video_path, item)
        self.assertEqual(failures, [])

    def test_vertical_technical_contract_rejects_horizontal_media(self):
        failures = short.short_technical_failures(
            {"codec": "h264", "audio_codec": "aac", "width": 1280, "height": 720, "duration": 90.0}
        )
        self.assertTrue(any("1080x1920" in failure for failure in failures))
        self.assertFalse(any("משך ה־Short" in failure for failure in failures))

    def test_signature_svg_is_staged_into_runtime_public_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            project_dir = root / "project"
            state_dir = root / "state"
            source = project_dir / "public" / "images" / "signature" / "signature-mask.svg"
            source.parent.mkdir(parents=True)
            state_dir.mkdir(parents=True)
            source.write_text("<svg>approved-signature</svg>", encoding="utf-8")

            with (
                mock.patch.object(short.core, "PROJECT_DIR", project_dir),
                mock.patch.object(short.core, "STATE_DIR", state_dir),
            ):
                runtime_name = short.prepare_signature_asset()

            self.assertEqual(runtime_name, "signature-mask.svg")
            self.assertEqual(
                (state_dir / runtime_name).read_text(encoding="utf-8"),
                "<svg>approved-signature</svg>",
            )

    def test_remotion_signature_end_card_uses_svg_image_not_video(self):
        source = (Path(short.core.PROJECT_DIR) / "src" / "remotion" / "ArticleShort.tsx").read_text(
            encoding="utf-8"
        )
        self.assertIn("signatureImageSrc", source)
        self.assertIn("FullScreenSignatureOutro", source)
        self.assertNotIn("signatureVideoSrc", source)

    def test_active_item_scopes_to_target_slug_when_multiple_active_exist(self):
        state = {
            "version": 1,
            "items": [
                {
                    "id": "item-old",
                    "status": "downloaded",
                    "uploaded": False,
                    "source": {"slug": "old-slug"},
                },
                {
                    "id": "item-new",
                    "status": "generating",
                    "uploaded": False,
                    "source": {"slug": "new-slug"},
                },
            ],
        }
        with self.assertRaises(short.core.PipelineError):
            short.core.active_item(state)

        target = short.core.active_item(state, slug="new-slug")
        self.assertIsNotNone(target)
        self.assertEqual(target["id"], "item-new")

        with mock.patch.dict(os.environ, {"DERIVE_SLUG": "new-slug"}):
            target_env = short.core.active_item(state)
            self.assertIsNotNone(target_env)
            self.assertEqual(target_env["id"], "item-new")

    def test_new_item_always_creates_direct_short_mode(self):
        item = short.new_item(self.source())
        self.assertEqual(item["type"], "article_short")
        self.assertEqual(item["source_mode"], "direct-short")

        with mock.patch.dict(os.environ, {"KESHER_SHORT_MODE": "derive"}):
            derived_item = short.new_item(self.source())
            self.assertEqual(derived_item["source_mode"], "direct-short")

    def test_short_technical_failures_rejects_overview_segment(self):
        media = {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 45.0}
        item = {
            "source_mode": "overview-segment",
            "signature_fullscreen": True,
            "signature_duration_seconds": 3.0,
            "signature_video_sha256": "f" * 64,
            "signature_verified": True,
        }
        failures = short.short_technical_failures(media, item=item)
        self.assertTrue(any("overview-segment" in err for err in failures))

    def test_short_technical_failures_validates_signature_video_properties(self):
        media = {"codec": "h264", "audio_codec": "aac", "width": 1080, "height": 1920, "duration": 45.0}
        valid_item = {
            "signature_fullscreen": True,
            "signature_duration_seconds": 3.0,
            "signature_video_sha256": "f" * 64,
            "signature_verified": True,
        }
        self.assertEqual(short.short_technical_failures(media, item=valid_item), [])

        missing_sha = dict(valid_item, signature_video_sha256="")
        self.assertTrue(any("signature_video_sha256" in err for err in short.short_technical_failures(media, item=missing_sha)))

        wrong_duration = dict(valid_item, signature_duration_seconds=5.0)
        self.assertTrue(any("משך סגיר החתימה" in err for err in short.short_technical_failures(media, item=wrong_duration)))

        not_fullscreen = dict(valid_item, signature_fullscreen=False)
        self.assertTrue(any("signature_fullscreen" in err for err in short.short_technical_failures(media, item=not_fullscreen)))

    def test_extract_signature_video_segment_cached(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            seg_file = state_dir / "test-item-signature-segment.mp4"
            seg_file.write_bytes(b"dummy video segment data")

            with mock.patch.object(short.core, "STATE_DIR", state_dir):
                path, sha = short.extract_signature_video_segment(state_dir / "dummy.mp4", "test-item")
                self.assertEqual(path, seg_file)
                self.assertEqual(sha, short.core.sha256_file(seg_file))


if __name__ == "__main__":
    unittest.main()
