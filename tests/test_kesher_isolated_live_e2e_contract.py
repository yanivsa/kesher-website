from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


class KesherIsolatedLiveE2EContractTests(unittest.TestCase):
    def test_live_e2e_uses_authorized_isolated_article_session(self):
        text = workflow("kesher-live-e2e-test.yml")
        self.assertIn("test_mode=true", text)
        self.assertIn("gh pr reopen", text)
        self.assertIn("Resolve the one new article identity relative to main", text)
        self.assertIn("source_content_sha256", text)

    def test_live_e2e_runs_same_production_media_scripts_in_fresh_state_dirs(self):
        text = workflow("kesher-live-e2e-test.yml")
        self.assertIn("KESHER_E2E_LONG_STATE_DIR", text)
        self.assertIn("KESHER_E2E_SHORT_STATE_DIR", text)
        self.assertIn("KESHER_MEDIA_MODE: video_overview", text)
        self.assertIn("scripts/kesher_video_reconcile.py --prepare-generation", text)
        self.assertIn("scripts/kesher_daily_pipeline.py --max-wait-seconds", text)
        self.assertIn("scripts/kesher_daily_pipeline.py --upload-only", text)
        self.assertIn("--adopt-long-form-state", text)
        self.assertIn("scripts/kesher_short_pipeline_v4.py --max-wait-seconds", text)
        self.assertIn("scripts/kesher_short_pipeline_v4.py --upload-only", text)
        self.assertNotIn("Restore newest valid durable pipeline state", text)
        self.assertNotIn("Restore newest valid Short V4 durable state", text)

    def test_live_e2e_is_preview_only_and_never_merges_test_article(self):
        text = workflow("kesher-live-e2e-test.yml")
        self.assertIn("RUN_LIVE_E2E", text)
        self.assertIn("pages deploy dist --project-name=kesher-website --branch=", text)
        self.assertIn("LIVE_E2E_PREVIEW_URL", text)
        self.assertIn("Close isolated test article PR", text)
        self.assertNotIn("auto-merge-article-prs.yml", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotIn("Nudge the production Controller", text)
        self.assertNotIn("kesher-content-controller.yml", text)

    def test_live_e2e_requires_strict_public_media_evidence(self):
        text = workflow("kesher-live-e2e-test.yml")
        self.assertIn("verified_youtube_item", text)
        self.assertIn("short_public_portrait_verified", text)
        self.assertIn("technical_verified", text)
        self.assertIn("1080", text)
        self.assertIn("1920", text)
        self.assertIn("youtube.com/oembed", text)
        self.assertIn("LIVE_E2E_OVERVIEW_PUBLIC=true", text)
        self.assertIn("LIVE_E2E_SHORT_PUBLIC_PORTRAIT=true", text)

    def test_live_e2e_always_cleans_up_test_pr(self):
        text = workflow("kesher-live-e2e-test.yml")
        self.assertIn("if: ${{ always()", text)
        self.assertIn("gh pr close", text)
        self.assertIn("intentionally not merged into production", text)


if __name__ == "__main__":
    unittest.main()
