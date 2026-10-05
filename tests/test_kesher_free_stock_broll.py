import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import kesher_free_stock_broll as broll


class FreeStockBrollTests(unittest.TestCase):
    def setUp(self):
        self.source = {
            "title": "למה הילד מתחיל את הבוקר במריבה?",
            "excerpt": "שגרת בוקר עם ילדים וקשב",
            "category": "הדרכת הורים",
            "slug": "adhd-morning-routine",
        }

    def test_query_uses_article_context(self):
        self.assertEqual(
            broll.build_stock_query(self.source),
            "school backpack shoes morning home close up",
        )

    def test_provider_credit_lines_only_include_used_free_sources(self):
        lines = broll.provider_credit_lines(
            [
                {"provider": "pexels"},
                {"provider": "pexels"},
                {"provider": "pixabay"},
                {"provider": "unknown"},
            ]
        )
        self.assertEqual(
            lines,
            [
                "קטעי וידאו משלימים מפקסלס: https://www.pexels.com/",
                "קטעי וידאו משלימים מפיקסאביי: https://pixabay.com/",
            ],
        )

    def test_pexels_parser_matches_documented_video_shape(self):
        with patch.object(broll.requests, "get") as request:
            response = request.return_value
            response.json.return_value = {
                "videos": [
                    {
                        "id": 123,
                        "url": "https://www.pexels.com/video/123/",
                        "user": {"name": "Creator"},
                        "video_files": [
                            {
                                "link": "https://cdn.example/landscape.mp4",
                                "file_type": "video/mp4",
                                "width": 1280,
                                "height": 720,
                            },
                            {
                                "link": "https://cdn.example/portrait.mp4",
                                "file_type": "video/mp4",
                                "width": 720,
                                "height": 1280,
                            },
                        ],
                    }
                ]
            }
            rows = broll._search_pexels(
                "free-key",
                "school backpack",
                "short_9_16",
                broll.time.monotonic() + 10,
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "pexels")
        self.assertEqual(rows[0]["download_url"], "https://cdn.example/portrait.mp4")
        self.assertEqual(rows[0]["creator"], "Creator")

    def test_pixabay_parser_matches_documented_video_shape(self):
        with patch.object(broll.requests, "get") as request:
            response = request.return_value
            response.json.return_value = {
                "hits": [
                    {
                        "id": 456,
                        "pageURL": "https://pixabay.com/videos/id-456/",
                        "user": "Creator",
                        "videos": {
                            "medium": {
                                "url": "https://cdn.example/landscape.mp4",
                                "width": 1280,
                                "height": 720,
                            },
                            "small": {
                                "url": "https://cdn.example/portrait.mp4",
                                "width": 720,
                                "height": 1280,
                            },
                        },
                    }
                ]
            }
            rows = broll._search_pixabay(
                "free-key",
                "school backpack",
                "overview_16_9",
                broll.time.monotonic() + 10,
            )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "pixabay")
        self.assertEqual(rows[0]["download_url"], "https://cdn.example/landscape.mp4")

    def test_pixabay_is_used_when_pexels_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            clip = state_dir / "clip.mp4"
            clip.write_bytes(b"x" * 4096)

            def provider_results(provider, *_args, **_kwargs):
                if provider == "pexels":
                    raise RuntimeError("rate limit")
                return [
                    {
                        "provider": "pixabay",
                        "id": "456",
                        "download_url": "https://cdn.example/clip.mp4",
                        "page_url": "https://pixabay.com/videos/id-456/",
                        "license_url": broll.PIXABAY_LICENSE_URL,
                        "creator": "Creator",
                    }
                ]

            with patch.dict(
                os.environ,
                {
                    "PEXELS_API_KEY": "free-key",
                    "PIXABAY_API_KEY": "backup-key",
                    "KESHER_BROLL_ENABLED": "true",
                },
                clear=False,
            ), patch.object(broll, "_provider_results", side_effect=provider_results), patch.object(
                broll, "_download_result", return_value=clip
            ):
                assets = broll.resolve_free_stock_broll(
                    state_dir=state_dir,
                    source=self.source,
                    source_identity="source-1",
                    duration_seconds=30,
                    profile="short_9_16",
                )
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["provider"], "pixabay")

    def test_missing_keys_is_clean_noop(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"PEXELS_API_KEY": "", "PIXABAY_API_KEY": "", "KESHER_BROLL_ENABLED": "true"},
            clear=False,
        ):
            result = broll.resolve_free_stock_broll(
                state_dir=Path(tmp),
                source=self.source,
                source_identity="source-1",
                duration_seconds=30,
                profile="short_9_16",
            )
        self.assertEqual(result, [])

    def test_kill_switch_is_clean_noop(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"PEXELS_API_KEY": "unused", "KESHER_BROLL_ENABLED": "false"},
            clear=False,
        ):
            result = broll.resolve_free_stock_broll(
                state_dir=Path(tmp),
                source=self.source,
                source_identity="source-1",
                duration_seconds=30,
                profile="short_9_16",
            )
        self.assertEqual(result, [])

    def test_provider_error_never_raises(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"PEXELS_API_KEY": "free-key", "PIXABAY_API_KEY": "", "KESHER_BROLL_ENABLED": "true"},
            clear=False,
        ), patch.object(broll, "_provider_results", side_effect=RuntimeError("rate limit")):
            result = broll.resolve_free_stock_broll(
                state_dir=Path(tmp),
                source=self.source,
                source_identity="source-1",
                duration_seconds=30,
                profile="short_9_16",
            )
        self.assertEqual(result, [])

    def test_short_caps_at_one_broll_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            clip = state_dir / "clip.mp4"
            clip.write_bytes(b"x" * 4096)
            results = [
                {
                    "provider": "pexels",
                    "id": str(index),
                    "download_url": f"https://example.invalid/{index}.mp4",
                    "page_url": f"https://www.pexels.com/video/{index}/",
                    "license_url": broll.PEXELS_LICENSE_URL,
                    "creator": "Example",
                }
                for index in range(3)
            ]
            with patch.dict(
                os.environ,
                {"PEXELS_API_KEY": "free-key", "PIXABAY_API_KEY": "backup-key", "KESHER_BROLL_ENABLED": "true"},
                clear=False,
            ), patch.object(broll, "_provider_results", return_value=results), patch.object(
                broll, "_download_result", return_value=clip
            ):
                assets = broll.resolve_free_stock_broll(
                    state_dir=state_dir,
                    source=self.source,
                    source_identity="source-1",
                    duration_seconds=30,
                    profile="short_9_16",
                )
        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0]["type"], "broll")
        self.assertEqual(assets[0]["provider"], "pexels")
        self.assertLessEqual(assets[0]["end"] - assets[0]["start"], 2.6)
        self.assertEqual(assets[0]["source_identity"], "source-1")

    def test_overview_caps_at_two_broll_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            clip = state_dir / "clip.mp4"
            clip.write_bytes(b"x" * 4096)
            results = [
                {
                    "provider": "pexels",
                    "id": str(index),
                    "download_url": f"https://example.invalid/{index}.mp4",
                    "page_url": f"https://www.pexels.com/video/{index}/",
                    "license_url": broll.PEXELS_LICENSE_URL,
                    "creator": "Example",
                }
                for index in range(4)
            ]
            with patch.dict(
                os.environ,
                {"PEXELS_API_KEY": "free-key", "PIXABAY_API_KEY": "", "KESHER_BROLL_ENABLED": "true"},
                clear=False,
            ), patch.object(broll, "_provider_results", return_value=results), patch.object(
                broll, "_download_result", return_value=clip
            ):
                assets = broll.resolve_free_stock_broll(
                    state_dir=state_dir,
                    source=self.source,
                    source_identity="source-1",
                    duration_seconds=120,
                    profile="overview_16_9",
                )
        self.assertEqual(len(assets), 2)
        self.assertTrue(all(asset["type"] == "broll" for asset in assets))
        self.assertTrue(all(asset["end"] <= 116.5 for asset in assets))


if __name__ == "__main__":
    unittest.main()
