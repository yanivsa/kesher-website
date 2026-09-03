from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / ".github" / "workflows" / "kesher-content-controller.yml"
PRODUCTION_CONTRACT = ROOT / "config" / "kesher-production-contract.json"
ARTICLE = ROOT / ".github" / "workflows" / "kesher-article-generation.yml"
SHORT = ROOT / ".github" / "workflows" / "kesher-short-v4.yml"
LEGACY_VIDEO = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
LEGACY_WEEKDAY = ROOT / ".github" / "workflows" / "jules-weekday-article.yml"
LEGACY_WEEKEND = ROOT / ".github" / "workflows" / "jules-weekend-article.yml"


def trigger_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("permissions:", 1)[0]


class SingleSchedulerPolicyTests(unittest.TestCase):
    def test_controller_is_the_only_scheduler_in_unified_content_pipeline(self):
        controller = trigger_block(CONTROLLER)
        article = trigger_block(ARTICLE)
        short = trigger_block(SHORT)
        legacy_video = trigger_block(LEGACY_VIDEO)
        self.assertIn("  schedule:", controller)
        self.assertNotIn("  schedule:", article)
        self.assertNotIn("  schedule:", short)
        self.assertNotIn("  schedule:", legacy_video)
        self.assertIn("workflow_dispatch:", article)
        self.assertIn("workflow_dispatch:", short)

    def test_superseded_article_scheduler_files_are_removed(self):
        self.assertFalse(LEGACY_WEEKDAY.exists())
        self.assertFalse(LEGACY_WEEKEND.exists())

    def test_controller_wakes_on_every_production_child_completion(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        for name in (
            "Kesher Article Generation",
            "Kesher Normalize Article PR",
            "Kesher Trusted Article Image",
            "Kesher Daily NotebookLM Video Overview",
            "Kesher Daily Article Short V4",
            "Deploy to Cloudflare Pages",
        ):
            self.assertIn(name, text)
        self.assertIn("types: [completed]", text)
        self.assertNotIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertNotIn('github.event.workflow_run.conclusion == "success"', text)

    def test_controller_ignores_only_pull_request_validation_completion(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.event != 'pull_request'", text)

    def test_heartbeat_is_recovery_only_and_runs_every_five_minutes(self):
        text = CONTROLLER.read_text(encoding="utf-8")
        self.assertIn('cron: "3,8,13,18,23,28,33,38,43,48,53,58 * * * *"', text)
        self.assertIn("Recovery heartbeat only", text)

    def test_production_contract_declares_five_minute_recovery_heartbeat(self):
        contract = json.loads(PRODUCTION_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["scheduler"]["heartbeat_minutes"], 5)

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

    def test_short_state_retains_exactly_three_snapshots_for_fourteen_days(self):
        text = SHORT.read_text(encoding="utf-8")
        self.assertIn("name: kesher-short-v4-state", text)
        self.assertIn("retention-days: 14", text)
        self.assertIn("Keep only the newest three Short V4 state artifacts", text)
        self.assertIn("| .[3:] | .[].id", text)
        self.assertNotIn("newest seven", text)
        self.assertNotIn("| .[7:]", text)


if __name__ == "__main__":
    unittest.main()
