from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / ".github" / "workflows" / "kesher-content-controller.yml"
ARTICLE = ROOT / ".github" / "workflows" / "kesher-article-generation.yml"
VIDEO = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
LEGACY_WEEKDAY = ROOT / ".github" / "workflows" / "jules-weekday-article.yml"
LEGACY_WEEKEND = ROOT / ".github" / "workflows" / "jules-weekend-article.yml"


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

    def test_superseded_article_scheduler_files_are_removed(self):
        self.assertFalse(LEGACY_WEEKDAY.exists())
        self.assertFalse(LEGACY_WEEKEND.exists())

    def test_controller_wakes_on_every_production_child_completion(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        for name in (
            "Kesher Article Generation",
            "Kesher Daily NotebookLM Video Overview",
            "Deploy to Cloudflare Pages",
        ):
            self.assertIn(name, text)
        self.assertIn("types: [completed]", text)
        self.assertNotIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertNotIn('github.event.workflow_run.conclusion == "success"', text)

    def test_controller_ignores_only_pull_request_validation_completion(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event != 'pull_request'", text)

    def test_heartbeat_is_recovery_only_and_runs_every_fifteen_minutes(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('cron: "3,18,33,48 * * * *"', text)
        self.assertIn("Recovery heartbeat only", text)

    def test_controller_has_no_runtime_scheduler_mutation(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertNotIn("/disable", text)
        self.assertNotIn("jules-weekday-article.yml", text)
        self.assertNotIn("jules-weekend-article.yml", text)

    def test_article_worker_is_single_attempt_and_persists_result(self):
        text = ARTICLE.read_text(encoding="utf-8")
        self.assertIn("Run exactly one autonomous Jules article text attempt", text)
        self.assertIn("python3 -u scripts/jules_article_runner_v3.py", text)
        self.assertIn("kesher-article-result-${{ github.run_id }}", text)
        self.assertIn("the controller owns retry/backoff", text)

    def test_video_state_retains_exactly_three_snapshots_for_fourteen_days(self):
        text = VIDEO.read_text(encoding="utf-8")
        self.assertIn("name: kesher-video-state", text)
        self.assertIn("retention-days: 14", text)
        self.assertIn("Keep the newest three durable state artifacts", text)
        self.assertIn("| .[3:] | .[].id", text)
        self.assertNotIn("newest seven", text)
        self.assertNotIn("| .[7:]", text)


if __name__ == "__main__":
    unittest.main()
