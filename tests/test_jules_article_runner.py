from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import jules_article_runner as runner


class JulesArticleRunnerTests(unittest.TestCase):
    def test_policy_loader_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.md"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(runner.ArticleRunnerError):
                runner.load_policy(path)

    def test_prompt_injects_authoritative_policy_and_slot(self):
        marker = "UNIQUE_POLICY_MARKER_20260819"
        prompt = runner.build_prompt("2026-08-19", marker)
        self.assertIn(marker, prompt)
        self.assertIn("2026-08-19", prompt)
        self.assertIn("BEGIN AUTHORITATIVE ARTICLE POLICY", prompt)
        self.assertIn("Article publication runs MUST NOT create a video", prompt)
        self.assertIn("Publish Kesher article:", prompt)
        self.assertIn("Never ask the user", prompt)

    def test_slot_duplicate_detection_is_exact(self):
        posts = [
            {"id": "a", "date": "2026-08-18"},
            {"id": "b", "date": "2026-08-19"},
        ]
        self.assertTrue(runner.article_exists_for_slot(posts, "2026-08-19"))
        self.assertFalse(runner.article_exists_for_slot(posts, "2026-08-20"))

    def test_runtime_prompt_is_short_task_wrapper_not_policy_duplication(self):
        policy = "POLICY_BODY_SENTINEL"
        prompt = runner.build_prompt("2026-08-19", policy)
        self.assertEqual(prompt.count(policy), 1)
        self.assertLess(len(prompt.replace(policy, "")), 2500)


if __name__ == "__main__":
    unittest.main()
