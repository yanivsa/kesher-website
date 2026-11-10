import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import kesher_short_pipeline_v4 as short
from tests.test_media_provenance_contract import bound_short


class ShortPipelineV4Tests(unittest.TestCase):
    def source(self):
        return {
            "slug": "how-to-talk",
            "title": "איך מדברים בלי להפוך כל שיחה לריב",
            "category": "זוגיות",
            "excerpt": "תיאור קצר",
            "canonical_url": "https://kesher.saharoni.com/blog/how-to-talk",
            "content_sha256": "a" * 64,
            "youtube_metadata": {
                "title": "איך מדברים בלי להפוך כל שיחה לריב",
                "description": "תיאור המאמר\n\nלקריאת המאמר המלא:\nhttps://kesher.saharoni.com/blog/how-to-talk\n\nלאתר קשר:\nhttps://kesher.saharoni.com\n\nלתיאום פגישה:\nhttps://kesher.saharoni.com/appointment",
                "tags": ["זוגיות", "תקשורת"],
            },
        }

    def test_prompt_requests_one_complete_short_ready_hebrew_idea_without_duration_cap(self):
        prompt = short.generation_prompt(self.source())
        self.assertIn("כל הקריינות, מתחילת הסרטון ועד סופו, בקול נשי בלבד", prompt)
        self.assertIn("אין להשתמש בקול גברי", prompt)
        self.assertIn("תזכורת מחייבת: הקריינות כולה בקול נשי ישראלי בלבד", prompt)
        self.assertIn("סרטון אנכי ביחס 9:16", prompt)
        self.assertIn("אין ליצור סקירת וידאו אופקית", prompt)
        self.assertIn("אסור להשתמש ברקע מטושטש", prompt)
        self.assertIn("קומפוזיציה אנכית חדה", prompt)
        self.assertIn("הרעיון השלם", prompt)
        self.assertIn("סיום טבעי", prompt)
        self.assertNotIn("45 עד 55 שניות", prompt)
        self.assertNotIn("55 השניות", prompt)


    def test_short_uses_distinct_title_tags_and_hook(self):
        source = self.source()
        source["short_youtube_metadata"] = {
            "title": "מריבות בזוגיות: שלושה סימנים שהוויכוח יצא משליטה",
            "description": source["youtube_metadata"]["description"],
            "tags": ["זוגיות", "מריבות בזוגיות", "איך לריב נכון"],
        }
        source["short_title"] = source["short_youtube_metadata"]["title"]
        source["short_hook"] = "כששני אנשים נלחמים על ההגה — אף אחד כבר לא מנווט את הקשר."
        item = short.new_item(source)
        self.assertEqual(item["youtube_metadata"]["title"], source["short_youtube_metadata"]["title"])
        self.assertIn("מריבות בזוגיות", item["youtube_metadata"]["tags"])
        prompt = short.generation_prompt(item["source"])
        self.assertIn(source["short_hook"], prompt)
        self.assertIn(source["short_title"], prompt)

    def test_new_item_requires_native_provider_short_and_three_links(self):
        item = short.new_item(self.source())
        self.assertEqual(item["provider_video_format"], "short")
        self.assertTrue(item["provider_native_short"])
        lines = [line.strip() for line in item["youtube_metadata"]["description"].splitlines() if line.strip()]
        self.assertIn("https://kesher.saharoni.com/blog/how-to-talk", lines)
        self.assertIn("https://kesher.saharoni.com", lines)
        self.assertIn("https://kesher.saharoni.com/appointment", lines)

    def test_repair_youtube_metadata_updates_stale_recovered_item_links(self):
        item = short.new_item(self.source())
        item["youtube_metadata"]["description"] = "תיאור ישן ללא קישורים"
        metadata = short.repair_youtube_metadata(item)
        lines = [line.strip() for line in metadata["description"].splitlines() if line.strip()]
        self.assertIn("https://kesher.saharoni.com/blog/how-to-talk", lines)
        self.assertIn("https://kesher.saharoni.com", lines)
        self.assertIn("https://kesher.saharoni.com/appointment", lines)


    def test_repair_youtube_metadata_adds_credit_only_for_used_stock(self):
        item = short.new_item(self.source())
        item["enhancement_assets_used"] = [{"provider": "pexels", "type": "broll"}]
        metadata = short.repair_youtube_metadata(item)
        lines = [line.strip() for line in metadata["description"].splitlines() if line.strip()]
        self.assertIn("קטעי וידאו משלימים מפקסלס: https://www.pexels.com/", lines)
        short.core.require_hebrew(metadata["description"], "YouTube description", allow_url=True)

    def test_short_generation_has_no_landscape_explainer_fallback(self):
        source = (Path(short.core.PROJECT_DIR) / "scripts" / "kesher_short_pipeline_v4.py").read_text(encoding="utf-8")
        self.assertIn('provider_format = "short"', source)
        self.assertNotIn('provider_format = "short" if', source)

    def test_native_provider_gate_rejects_landscape_or_long_form_identity(self):
        valid = {"provider_video_format": "short", "provider_native_short": True}
        valid["fresh_generation_attempt"] = 1
        self.assertEqual(short.native_provider_short_failures({"width": 1080, "height": 1920}, valid), [])
        self.assertTrue(short.native_provider_short_failures({"width": 1920, "height": 1080}, valid))
        fallback = dict(valid, fresh_generation_attempt=3, provider_video_format="explainer", provider_native_short=False)
        fallback_failures = short.native_provider_short_failures({"width": 1920, "height": 1080}, fallback)
        self.assertTrue(any("landscape fallback is forbidden" in err for err in fallback_failures))
        reused = dict(fallback, shared_provider_identity=True)
        self.assertTrue(any("Video Overview provider identity" in err for err in short.native_provider_short_failures({"width": 1080, "height": 1920}, reused)))

    def test_signature_component_keeps_branded_background_inside_timeline(self):
        source = (Path(short.core.PROJECT_DIR) / "src" / "remotion" / "components" / "FullScreenSignatureOutro.tsx").read_text(encoding="utf-8")
        self.assertIn("linear-gradient(135deg, #18281f 0%, #0d1712 100%)", source)
        self.assertNotIn("rgba(13,23,18,0.05)", source)

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
        item = bound_short(45.0)
        item["fresh_generation_attempt"] = 3
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

    @mock.patch.dict(os.environ, {'KESHER_MEDIA_MODE': 'article_short'})
    def test_active_item_scopes_to_target_slug_when_multiple_active_exist(self):
        state = {
            "version": 1,
            "items": [
                {
                    "id": "item-old",
                    "type": "article_short",
                    "status": "downloaded",
                    "uploaded": False,
                    "source": {"slug": "old-slug"},
                },
                {
                    "id": "item-new",
                    "type": "article_short",
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
        self.assertEqual(item["provider_video_format"], "short")
        self.assertTrue(item["provider_native_short"])

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
        valid_item = bound_short(45.0)
        self.assertEqual(short.short_technical_failures(media, item=valid_item), [])

        missing_sha = dict(valid_item, signature_video_sha256="")
        self.assertTrue(any("signature_video_sha256" in err for err in short.short_technical_failures(media, item=missing_sha)))

        wrong_duration = dict(valid_item, signature_duration_seconds=5.0)
        self.assertTrue(any("משך סגיר החתימה" in err for err in short.short_technical_failures(media, item=wrong_duration)))

        not_fullscreen = dict(valid_item, signature_fullscreen=False)
        self.assertEqual(short.short_technical_failures(media, item=not_fullscreen), [])
        appended_outro = dict(valid_item, signature_overlay=False)
        self.assertTrue(any("signature_provenance" in err for err in short.short_technical_failures(media, item=appended_outro)))

    def test_cached_signature_cannot_replace_missing_current_final(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            seg_file = state_dir / "test-item-signature-segment.mp4"
            seg_file.write_bytes(b"dummy video segment data")

            with mock.patch.object(short.core, "STATE_DIR", state_dir):
                with self.assertRaises(short.core.PipelineError):
                    short.extract_signature_video_segment(state_dir / "dummy.mp4", "test-item")


if __name__ == "__main__":
    unittest.main()
