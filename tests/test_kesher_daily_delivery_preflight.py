"""Regressions for the read-only KESHER daily delivery preflight."""
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

from scripts.kesher_runtime.delivery_preflight import audit, live_article, source_for_date

ISRAEL = ZoneInfo("Asia/Jerusalem")


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "src/data").mkdir(parents=True)
        (self.root / "public/images").mkdir(parents=True)
        (self.root / "public/images/photo.jpg").write_bytes(b"valid-photo-bytes")
        self.post = dict(id="daily-article", slug="daily-article", date="2026-11-16",
                         title="מה עושים כשהילד לחוץ?", content="מאמר בעברית", image="/images/photo.jpg")
        self.write("posts.json", [self.post])
        self.write("postsRecent.json", [])
        self.mapping({"daily-article": {"youtubeId": "AxFKFx1pAWU"}})

    def write(self, name, value):
        (self.root / "src/data" / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf8")

    def mapping(self, obj):
        (self.root / "src/data/articleVideos.json").write_text(json.dumps(obj), encoding="utf8")

    def test_source_catalogs_are_both_searched(self):
        result = audit(self.root, datetime(2026, 11, 16, 9, 30, tzinfo=ISRAEL))
        self.assertEqual(result["slug"], "daily-article")
        self.assertEqual(result["short"], "UNVERIFIED_EXTERNAL")
        self.assertNotEqual(result["status"], "BLOCKED")

    def test_exact_duplicate_catalog_copy_is_not_second_article(self):
        self.write("postsRecent.json", [self.post])
        post, reason = source_for_date(self.root, "2026-11-16")
        self.assertEqual(post["id"], "daily-article")
        self.assertIsNone(reason)

    def test_conflicting_catalog_rejected(self):
        self.write("postsRecent.json", [{**self.post, "content": "תוכן אחר"}])
        _, reason = source_for_date(self.root, "2026-11-16")
        self.assertEqual(reason, "CONFLICTING_CATALOG_ENTRIES")

    def test_duplicate_slug_rejected(self):
        self.write("postsRecent.json", [{**self.post, "id": "another-article", "slug": "another-article"}])
        self.assertEqual(audit(self.root, datetime(2026, 11, 16, 10, tzinfo=ISRAEL))["status"], "BLOCKED")

    def test_missing_early_article_is_pending_but_after_nine_blocked(self):
        self.write("posts.json", [])
        self.assertEqual(audit(self.root, datetime(2026, 11, 16, 0, 30, tzinfo=ISRAEL))["status"], "PENDING")
        self.assertEqual(audit(self.root, datetime(2026, 11, 16, 9, 30, tzinfo=ISRAEL))["status"], "BLOCKED")

    def test_missing_hero_fails_closed(self):
        (self.root / "public/images/photo.jpg").unlink()
        self.assertEqual(audit(self.root, datetime(2026, 11, 16, 10, tzinfo=ISRAEL))["article"], "HERO_MISSING_OR_INVALID")

    def test_missing_long_mapping_requires_action(self):
        self.mapping({})
        result = audit(self.root, datetime(2026, 11, 16, 10, tzinfo=ISRAEL))
        self.assertEqual(result["long"], "NO_VERIFIED_MAPPING")
        self.assertEqual(result["status"], "ACTION_REQUIRED")

    def test_html_lazy_player_facade_is_an_embedded_player(self):
        response = Mock(status=200)
        response.read.return_value = ("<h2>מעדיפים לצפות?</h2><a href='https://www.youtube.com/watch?v=AxFKFx1pAWU'>צפה</a>").encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock(return_value=response)
        self.assertEqual(live_article("https://kesher.saharoni.com/blog/daily-article", "AxFKFx1pAWU", opener=opener), "LIVE_LONG_FACADE_OK")

    def test_wrong_video_id_cannot_pass_embed(self):
        response = Mock(status=200)
        response.read.return_value = "<h2>מעדיפים לצפות?</h2><a href='https://youtube.com/watch?v=WRONG111111'>צפה</a>".encode()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        self.assertEqual(live_article("https://kesher.saharoni.com/blog/daily-article", "AxFKFx1pAWU", opener=Mock(return_value=response)), "LIVE_LONG_FACADE_MISSING")

    def test_path_traversal_hero_is_blocked(self):
        self.write("posts.json", [{**self.post, "image": "/images/../../secrets"}])
        self.assertEqual(audit(self.root, datetime(2026, 11, 16, 10, tzinfo=ISRAEL))["article"], "HERO_MISSING_OR_INVALID")


if __name__ == "__main__":
    unittest.main()
