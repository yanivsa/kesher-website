from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_video_reconcile as reconcile

TZ = ZoneInfo("Asia/Jerusalem")

def post(slug: str) -> dict:
    return {"id": slug, "slug": slug, "title": "כותרת יומית בעברית", "date": "2026-10-30", "category": "ייעוץ זוגי", "excerpt": "תקציר עברי שימושי", "content": "<p>תוכן עברי מלא ומעשי.</p>"}

class VideoRecoverySourceSelectedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state_dir = self.root / "state"
        self.posts_file = self.root / "posts.json"
        self.patchers = [
            mock.patch.object(pipeline, "STATE_DIR", self.state_dir),
            mock.patch.object(pipeline, "STATE_FILE", self.state_dir / "state.json"),
            mock.patch.object(pipeline, "POSTS_FILE", self.posts_file),
            mock.patch.object(pipeline, "israel_now", return_value=datetime(2026, 10, 30, 14, 0, tzinfo=TZ)),
        ]
        for patcher in self.patchers: patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers): patcher.stop()
        self.tmp.cleanup()

    def test_exact_source_selected_recovery_continues_same_item(self) -> None:
        row = post("shared-laughter-couples-intimacy")
        self.posts_file.write_text(json.dumps([row], ensure_ascii=False), encoding="utf-8")
        source = pipeline.source_metadata(row)
        item = pipeline.new_item(source)
        item.update({"type": "video_overview", "status": "source_selected"})
        pipeline.save_state({"version": 1, "items": [item], "updated_at": pipeline.utc_now()})
        output = self.root / "github-output.txt"
        with mock.patch.dict(os.environ, {"KESHER_MEDIA_MODE":"video_overview","TARGET_ITEM_ID":item["id"],"TARGET_CONTENT_SHA256":source["content_sha256"],"GITHUB_OUTPUT":str(output),"OPERATION":"recovery","KESHER_RECOVERY_MODE":"true"}, clear=False):
            self.assertEqual(reconcile.prepare_generation(source["slug"]), 0)
        self.assertIn("skip_generation=false", output.read_text(encoding="utf-8"))
        saved = pipeline.load_state()["items"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["id"], item["id"])
        self.assertEqual(saved[0]["status"], "source_selected")

if __name__ == "__main__": unittest.main()
