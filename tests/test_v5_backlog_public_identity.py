from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_v5 as v5
from scripts import kesher_content_controller_v5_runtime as runtime
from tests.test_v5_shared_video_controller import FakeGitHub, article

TZ = ZoneInfo("Asia/Jerusalem")


class V5BacklogPublicIdentityTests(unittest.TestCase):
    def _post(self) -> dict:
        post = article("backlog-strict-public-gate")
        post.update({
            "title": "מאמר היסטורי לאימות קשיח",
            "date": "2026-08-19",
            "category": "זוגיות",
            "excerpt": "תקציר בדיקה",
            "content": "<p>תוכן מלא בעברית לצורך בדיקת זהות ציבורית קשיחה.</p>",
            "controllerManaged": True,
        })
        return post

    def test_title_only_public_page_cannot_unlock_backlog_media(self):
        gh = FakeGitHub()
        post = self._post()
        gh.posts = [post]

        class TitleOnlySite:
            def get(self, url):
                return 200, "<html><h1>מאמר היסטורי לאימות קשיח</h1></html>"

        controller = runtime.RuntimeV5Controller(
            gh,
            TitleOnlySite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )
        state = {
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {"slug": "backlog-strict-public-gate"},
            }]
        }

        row, source = controller._published_backlog_source(state)

        self.assertIsNone(row)
        self.assertIsNone(source)

    def test_matching_signed_sha_marker_unlocks_exact_backlog_source(self):
        gh = FakeGitHub()
        post = self._post()
        gh.posts = [post]
        expected = v5.article_source_identity(post)

        class SignedSite:
            def get(self, url):
                return 200, (
                    "<html><head>"
                    f"<meta name=\"kesher:content-sha256\" content=\"{expected['content_sha256']}\">"
                    "</head><body><h1>מאמר היסטורי לאימות קשיח</h1></body></html>"
                )

        controller = runtime.RuntimeV5Controller(
            gh,
            SignedSite(),
            now=datetime(2026, 8, 20, 0, 40, tzinfo=TZ),
        )
        state = {
            "backlog": [{
                "cycle": "2026-08-19",
                "article": {
                    "slug": expected["slug"],
                    "quality_content_sha256": expected["content_sha256"],
                },
            }]
        }

        row, source = controller._published_backlog_source(state)

        self.assertIsNotNone(row)
        self.assertEqual(source["slug"], expected["slug"])
        self.assertEqual(source["content_sha256"], expected["content_sha256"])


if __name__ == "__main__":
    unittest.main()
