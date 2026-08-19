from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / ".github" / "workflows" / "kesher-content-controller.yml"
ARTICLE = ROOT / ".github" / "workflows" / "kesher-article-generation.yml"
VIDEO = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"


def trigger_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("permissions:", 1)[0]


class SingleSchedulerPolicyTests(unittest.TestCase):
    def test_controller_is_the_only_scheduler_in_unified_content_pipeline(self):
        controller = trigger_block(CONTROLLER)
        article = trigger_block(ARTICLE)
        video = trigger_block(VIDEO)
        self.assertIn("  schedule:", controller)
        self.assertNotIn("  schedule:", article)
        self.assertNotIn("  schedule:", video)
        self.assertIn("workflow_dispatch:", article)
        self.assertIn("workflow_dispatch:", video)

    def test_controller_wakes_on_child_completion(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        for name in (
            "Kesher Article Generation",
            "Kesher Daily NotebookLM Video Overview",
            "Deploy to Cloudflare Pages",
        ):
            self.assertIn(name, text)

    def test_controller_ignores_pull_request_validation_completion(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event != 'pull_request'", text)

    def test_legacy_article_schedulers_are_disabled_before_each_tick(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("jules-weekday-article.yml", text)
        self.assertIn("jules-weekend-article.yml", text)
        self.assertIn("/disable", text)

    def test_video_state_has_extended_recovery_retention(self):
        text = VIDEO.read_text(encoding="utf-8")
        self.assertIn("name: kesher-video-state", text)
        self.assertIn("retention-days: 14", text)


if __name__ == "__main__":
    unittest.main()
