from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_video_reconcile as reconcile


class TargetSlugModeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.state_dir = root / "state"
        self.posts_file = root / "posts.json"
        row = {
            "id": "current",
            "slug": "current",
            "title": "כותרת",
            "date": "2026-09-10",
            "category": "הנחיית הורים",
            "excerpt": "תקציר",
            "content": "<p>תוכן</p>",
        }
        self.posts_file.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
        self.patchers = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_dir / "state.json"),
            mock.patch.object(pipeline, "POSTS_FILE", self.posts_file),
        ]
        for patcher in self.patchers:
            patcher.start()
        pipeline.save_state({"version": 1, "items": [], "updated_at": pipeline.utc_now()})

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tmp.cleanup()

    def test_target_slug_in_long_form_mode_does_not_create_short_item(self) -> None:
        with mock.patch.dict(os.environ, {"KESHER_MEDIA_MODE": "video_overview"}, clear=False):
            self.assertEqual(reconcile.prepare_generation("current"), 0)
        items = pipeline.load_state()["items"]
        self.assertEqual(items, [], "Long-form reconciliation must defer targeted item creation to kesher_daily_pipeline")

    def test_target_slug_in_short_mode_still_initializes_direct_short(self) -> None:
        with mock.patch.dict(os.environ, {"KESHER_MEDIA_MODE": "article_short"}, clear=False):
            self.assertEqual(reconcile.prepare_generation("current"), 0)
        item = pipeline.load_state()["items"][0]
        self.assertEqual(item["type"], "article_short")
        self.assertEqual(item["source_mode"], "direct-short")


if __name__ == "__main__":
    unittest.main()
