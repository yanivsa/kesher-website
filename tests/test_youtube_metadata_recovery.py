from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kesher_daily_pipeline.py"
SPEC = importlib.util.spec_from_file_location("kesher_daily_pipeline_metadata_recovery", MODULE_PATH)
pipeline = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(pipeline)


class YoutubeMetadataRecoveryTest(unittest.TestCase):
    def _item(self) -> dict:
        source = {
            "date": "2026-10-15",
            "slug": "returning-to-israel-relationship-struggles",
            "content_sha256": "f" * 64,
            "title": "חוזרים לארץ אחרי רילוקיישן?",
            "excerpt": "חזרה לישראל יכולה לטלטל את הזוגיות.",
            "canonical_url": "https://kesher.saharoni.com/blog/returning-to-israel-relationship-struggles",
            "category": "זוגיות",
            "subcategory": "זוגיות בעלייה ורילוקיישן",
        }
        expected = pipeline.publication_metadata(source, "short")
        return {
            "id": "video-20261015-short",
            "type": "article_short",
            "source": source,
            "youtube_id": "OVWw2wu0LOo",
            "youtube_metadata": expected,
            "enhancement_assets_used": [],
        }

    def test_repairs_same_persisted_video_metadata_without_new_insert(self) -> None:
        item = self._item()
        expected = item["youtube_metadata"]
        wrong = {
            "id": item["youtube_id"],
            "snippet": {
                "channelId": pipeline.YOUTUBE_CHANNEL_ID,
                "title": expected["title"],
                "description": expected["description"],
                "tags": ["שגוי"],
                "categoryId": "22",
                "defaultLanguage": "he",
                "defaultAudioLanguage": "he",
            },
        }
        corrected = {
            "id": item["youtube_id"],
            "snippet": {
                **wrong["snippet"],
                "tags": expected["tags"],
            },
        }
        response = mock.Mock(status_code=200)
        with mock.patch.object(
            pipeline, "youtube_get", side_effect=[{"items": [wrong]}, {"items": [corrected]}]
        ), mock.patch.object(pipeline.requests, "put", return_value=response) as put:
            row = pipeline.repair_persisted_youtube_metadata(item, "token")

        self.assertEqual(row["id"], item["youtube_id"])
        put.assert_called_once()
        args, kwargs = put.call_args
        self.assertEqual(args[0], "https://www.googleapis.com/youtube/v3/videos")
        self.assertEqual(kwargs["params"], {"part": "snippet"})
        self.assertEqual(kwargs["json"]["id"], item["youtube_id"])
        self.assertEqual(kwargs["json"]["snippet"]["tags"], expected["tags"])
        self.assertEqual(kwargs["json"]["snippet"]["title"], expected["title"])
        self.assertEqual(kwargs["json"]["snippet"]["description"], expected["description"])

    def test_refuses_metadata_repair_for_wrong_channel(self) -> None:
        item = self._item()
        wrong_channel = {
            "id": item["youtube_id"],
            "snippet": {
                "channelId": "other-channel",
                "title": item["youtube_metadata"]["title"],
                "description": item["youtube_metadata"]["description"],
                "tags": ["שגוי"],
                "categoryId": "22",
            },
        }
        with mock.patch.object(pipeline, "youtube_get", return_value={"items": [wrong_channel]}), mock.patch.object(
            pipeline.requests, "put"
        ) as put:
            with self.assertRaisesRegex(pipeline.PipelineError, "wrong YouTube channel"):
                pipeline.repair_persisted_youtube_metadata(item, "token")
        put.assert_not_called()


if __name__ == "__main__":
    unittest.main()
