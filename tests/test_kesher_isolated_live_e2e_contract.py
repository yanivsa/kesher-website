from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


class KesherIsolatedLiveE2EContractTests(unittest.TestCase):
    def test_article_worker_can_keep_only_authorized_test_pr_open(self):
        text = workflow("kesher-article-generation.yml")
        self.assertIn("keep_test_pr_open:", text)
        self.assertIn("KESHER_KEEP_TEST_PR_OPEN", text)
        self.assertIn("KEEP_TEST_PR_OPEN_REQUIRES_TEST_MODE", text)
        self.assertIn("env.KESHER_KEEP_TEST_PR_OPEN != 'true'", text)

    def test_long_worker_supports_isolated_source_and_state_namespace(self):
        text = workflow("kesher-daily-video.yml")
        self.assertIn("source_ref:", text)
        self.assertIn("state_artifact_name:", text)
        self.assertIn("KESHER_SOURCE_REF", text)
        self.assertIn("KESHER_STATE_ARTIFACT", text)
        self.assertIn("ref: ${{ env.KESHER_SOURCE_REF }}", text)
        self.assertNotIn("name: kesher-video-state\n          path: ${{ env.KESHER_STATE_DIR }}", text)

    def test_short_worker_supports_isolated_source_and_both_state_namespaces(self):
        text = workflow("kesher-short-v4.yml")
        self.assertIn("source_ref:", text)
        self.assertIn("state_artifact_name:", text)
        self.assertIn("long_state_artifact_name:", text)
        self.assertIn("KESHER_SOURCE_REF", text)
        self.assertIn("KESHER_STATE_ARTIFACT", text)
        self.assertIn("KESHER_LONG_STATE_ARTIFACT", text)
        self.assertIn("ref: ${{ env.KESHER_SOURCE_REF }}", text)

    def test_live_e2e_is_preview_only_and_never_merges_test_article(self):
        text = workflow("kesher-live-e2e-test.yml")
        self.assertIn("test_mode=true", text)
        self.assertIn("keep_test_pr_open=true", text)
        self.assertIn("kesher-e2e-video-", text)
        self.assertIn("kesher-e2e-short-", text)
        self.assertIn("source_ref=", text)
        self.assertIn("state_artifact_name=", text)
        self.assertIn("long_state_artifact_name=", text)
        self.assertIn("pages deploy dist --project-name=kesher-website --branch=", text)
        self.assertIn("LIVE_E2E_PREVIEW_URL", text)
        self.assertIn("Close isolated test article PR", text)
        self.assertNotIn("auto-merge-article-prs.yml", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotIn("Refusing duplicate live E2E", text)
        self.assertNotIn("Nudge the production Controller", text)

    def test_production_defaults_remain_unchanged(self):
        long_text = workflow("kesher-daily-video.yml")
        short_text = workflow("kesher-short-v4.yml")
        self.assertRegex(long_text, r"source_ref:\s*\n\s+description:.*\n\s+required: false\s*\n\s+default: main")
        self.assertRegex(long_text, r"state_artifact_name:\s*\n\s+description:.*\n\s+required: false\s*\n\s+default: kesher-video-state")
        self.assertRegex(short_text, r"source_ref:\s*\n\s+description:.*\n\s+required: false\s*\n\s+default: main")
        self.assertRegex(short_text, r"state_artifact_name:\s*\n\s+description:.*\n\s+required: false\s*\n\s+default: kesher-short-v4-state")
        self.assertRegex(short_text, r"long_state_artifact_name:\s*\n\s+description:.*\n\s+required: false\s*\n\s+default: kesher-video-state")


if __name__ == "__main__":
    unittest.main()
