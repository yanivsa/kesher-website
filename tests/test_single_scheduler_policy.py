from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / ".github" / "workflows" / "kesher-content-controller.yml"
ARTICLE = ROOT / ".github" / "workflows" / "kesher-article-generation.yml"
VIDEO = ROOT / ".github" / "workflows" / "kesher-daily-video.yml"
ENTRY = ROOT / "scripts" / "kesher_content_controller_entry.py"
POLICY = ROOT / "config" / "kesher-automation-policy.json"
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

    def test_child_completion_is_observable_but_failed_child_waits_for_heartbeat(self):
        workflow = CONTROLLER.read_text(encoding="utf-8")
        entry = ENTRY.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", workflow)
        self.assertIn("types: [completed]", workflow)
        self.assertIn("KESHER_CHILD_CONCLUSION", workflow)
        self.assertIn("failed_child_waits_for_heartbeat", entry)
        self.assertIn("failed child deferred to recovery heartbeat", entry)
        self.assertIn('variables.get("KESHER_TRIGGER_EVENT") == "workflow_run"', entry)

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
        self.assertIn("Run exactly one autonomous Jules article attempt", text)
        self.assertIn("kesher-article-result-${{ github.run_id }}", text)
        self.assertIn("the controller owns retry/backoff", text)

    def test_technically_verified_video_uses_advisory_publication_hook(self):
        entry = ENTRY.read_text(encoding="utf-8")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertIn("advisory_video_publication_ready", entry)
        self.assertIn("controller.mandatory_video_review_approved = advisory_video_publication_ready", entry)
        self.assertEqual(policy["video"]["publication_gate"], "technical")
        self.assertTrue(policy["video"]["jules_is_advisory"])

    def test_video_state_keeps_durable_14_day_recovery_window(self):
        text = VIDEO.read_text(encoding="utf-8")
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertIn("name: kesher-video-state", text)
        self.assertIn("retention-days: 14", text)
        self.assertGreaterEqual(int(policy["video"]["durable_state_artifacts_to_keep"]), 3)


if __name__ == "__main__":
    unittest.main()
