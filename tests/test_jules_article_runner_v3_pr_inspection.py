from __future__ import annotations

import base64
import json
import unittest
from unittest import mock

from scripts import jules_article_runner_v3 as v3


class JulesArticleRunnerV3PrInspectionTests(unittest.TestCase):
    def test_prior_day_pr_does_not_block_when_contents_api_omits_inline_content(self):
        prior_posts = [
            {
                "id": "relationship-code-7500",
                "date": "2026-10-03",
                "title": "קוד 7500 בזוגיות",
                "content": "<p>תוכן</p>",
            }
        ]
        encoded = base64.b64encode(
            (json.dumps(prior_posts, ensure_ascii=False) + "\n").encode("utf-8")
        ).decode("ascii")

        def fake_request(method, url, headers, body=None, **kwargs):
            if url.endswith("/pulls?state=open&per_page=100"):
                return [
                    {
                        "number": 997,
                        "title": "Publish Kesher article: קוד 7500 בזוגיות",
                        "head": {"sha": "head997"},
                    }
                ]
            if url.endswith("/pulls/997/files?per_page=100"):
                return [
                    {
                        "filename": "src/data/posts.json",
                        "sha": "postsblob997",
                    }
                ]
            if "/contents/src/data/posts.json?ref=" in url:
                # GitHub may omit inline content for a contents response.
                return {
                    "name": "posts.json",
                    "sha": "postsblob997",
                    "encoding": "none",
                    "content": "",
                }
            if url.endswith("/git/blobs/postsblob997"):
                return {
                    "sha": "postsblob997",
                    "encoding": "base64",
                    "content": encoded,
                }
            raise AssertionError(f"unexpected request: {method} {url}")

        with mock.patch.object(v3.core, "request_json", side_effect=fake_request):
            matches = v3.open_article_prs_for_slot("token", "2026-10-04")

        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
