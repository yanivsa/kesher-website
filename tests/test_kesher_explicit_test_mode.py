from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from scripts import jules_article_runner_v3 as runner


class KesherExplicitTestModeTests(unittest.TestCase):
    def test_normal_preflight_still_blocks_published_slot(self):
        with mock.patch.object(runner, "_load_local_posts", return_value=[{"date": "2026-09-06"}]), mock.patch.object(
            runner, "open_article_prs_for_slot"
        ) as open_prs, mock.patch.dict(os.environ, {"KESHER_TEST_MODE": "false"}, clear=False):
            self.assertEqual(runner.preflight("2026-09-06", "token"), "ARTICLE_ALREADY_PUBLISHED")
        open_prs.assert_not_called()

    def test_explicit_test_mode_bypasses_published_slot_and_open_same_slot_pr(self):
        with mock.patch.object(runner, "_load_local_posts", return_value=[{"date": "2026-09-06"}]), mock.patch.object(
            runner, "open_article_prs_for_slot", return_value=[{"number": 999}]
        ), mock.patch.dict(os.environ, {"KESHER_TEST_MODE": "true", "GITHUB_RUN_ID": "12345"}, clear=False):
            self.assertEqual(runner.preflight("2026-09-06", "token"), "READY")

    def test_test_prompt_explicitly_authorizes_duplicate_date_bypass(self):
        with mock.patch.dict(os.environ, {"KESHER_TEST_MODE": "true", "GITHUB_RUN_ID": "12345"}, clear=False):
            prompt = runner.build_prompt("2026-09-06", "POLICY")
        normalized = " ".join(prompt.split())
        self.assertIn("AUTHORIZED TEST MODE", prompt)
        self.assertIn("must not stop because an article or PR already exists for `2026-09-06`", normalized)
        self.assertIn("Create exactly one NEW test article", normalized)

    def test_test_session_identity_is_isolated_from_daily_slot(self):
        original = runner.core.slot_session_title
        try:
            with mock.patch.dict(os.environ, {"KESHER_TEST_MODE": "true", "GITHUB_RUN_ID": "12345"}, clear=False):
                runner.configure_test_session_identity("2026-09-06")
                self.assertEqual(
                    runner.core.slot_session_title("2026-09-06"),
                    "Kesher TEST article 2026-09-06 run-12345",
                )
        finally:
            runner.core.slot_session_title = original

    def test_article_workflow_exposes_test_mode_and_push_trigger(self):
        workflow = Path(".github/workflows/kesher-article-generation.yml").read_text(encoding="utf-8")
        self.assertIn("test_mode:", workflow)
        self.assertIn(".github/kesher-e2e-test-trigger.json", workflow)
        self.assertIn("KESHER_TEST_MODE", workflow)


if __name__ == "__main__":
    unittest.main()
