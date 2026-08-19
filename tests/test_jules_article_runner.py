from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import jules_article_runner as runner


class JulesArticleRunnerTests(unittest.TestCase):
    def test_current_policy_manifest_is_valid(self):
        policy = runner.load_policy()
        self.assertTrue(policy.startswith("# עדכון מחייב למדיניות מאמרי קשר"))
        meta = json.loads(runner.POLICY_META_PATH.read_text(encoding="utf-8"))
        self.assertEqual(meta["policy_version"], runner.ARTICLE_POLICY_VERSION)
        self.assertEqual(
            meta["git_blob_sha1"],
            runner.git_blob_sha1(runner.POLICY_PATH.read_bytes()),
        )

    def test_policy_loader_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.md"
            path.write_text("", encoding="utf-8")
            with self.assertRaises(runner.ArticleRunnerError):
                runner.load_policy(path)

    def test_policy_loader_rejects_content_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "policy.md"
            meta = root / "policy.meta.json"
            path.write_text("מדיניות תקינה", encoding="utf-8")
            meta.write_text(
                json.dumps(
                    {
                        "policy_version": runner.ARTICLE_POLICY_VERSION,
                        "git_blob_sha1": "0" * 40,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.ArticleRunnerError, "content drift"):
                runner.load_policy(path, meta)

    def test_policy_loader_rejects_version_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "policy.md"
            meta = root / "policy.meta.json"
            raw = "מדיניות תקינה".encode("utf-8")
            path.write_bytes(raw)
            meta.write_text(
                json.dumps(
                    {
                        "policy_version": runner.ARTICLE_POLICY_VERSION + 1,
                        "git_blob_sha1": runner.git_blob_sha1(raw),
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.ArticleRunnerError, "version mismatch"):
                runner.load_policy(path, meta)

    def test_prompt_injects_authoritative_policy_and_slot(self):
        marker = "UNIQUE_POLICY_MARKER_20260819"
        prompt = runner.build_prompt("2026-08-19", marker)
        self.assertIn(marker, prompt)
        self.assertIn("2026-08-19", prompt)
        self.assertIn("Article policy version: `1`", prompt)
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
        self.assertLess(len(prompt.replace(policy, "")), 2600)


if __name__ == "__main__":
    unittest.main()
