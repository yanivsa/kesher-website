from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import jules_article_runner_v4 as runner


class KesherCustomTopicBriefTests(unittest.TestCase):
    def test_prompt_binds_jules_to_owner_topic(self):
        brief = "כתבה על בני נוער ו-AI מנקודת המבט של מנחת הורים"
        with mock.patch.dict(os.environ, {"KESHER_ARTICLE_TOPIC_BRIEF": brief, "KESHER_ARTICLE_TOPIC_BRIEF_FILE": ""}, clear=False):
            prompt = runner.build_prompt("2026-09-26", "POLICY")
        normalized = " ".join(prompt.split())
        self.assertIn("OWNER-SUPPLIED TOPIC BRIEF", prompt)
        self.assertIn(brief, prompt)
        self.assertIn("authoritative subject constraint", normalized)
        self.assertIn("shopping/product-recommendation trust", normalized)

    def test_topic_brief_file_is_supported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "brief.txt"
            path.write_text("נושא מותאם אישית\n", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {"KESHER_ARTICLE_TOPIC_BRIEF_FILE": str(path), "KESHER_ARTICLE_TOPIC_BRIEF": ""},
                clear=False,
            ):
                self.assertEqual(runner.load_owner_topic_brief(), "נושא מותאם אישית")

    def test_workflow_exposes_dispatch_and_repo_trigger(self):
        workflow = Path(".github/workflows/kesher-article-generation.yml").read_text(encoding="utf-8")
        self.assertIn("topic_brief:", workflow)
        self.assertIn(".github/kesher-topic-request.json", workflow)
        self.assertIn("KESHER_ARTICLE_TOPIC_BRIEF_FILE", workflow)


if __name__ == "__main__":
    unittest.main()
