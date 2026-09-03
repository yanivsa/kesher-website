from __future__ import annotations

import importlib
import json
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller as core
from scripts import kesher_content_controller_v3_entry as v3
from scripts import kesher_content_controller_v3_best_effort as best_effort

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "kesher-production-contract.json"
CONTROLLER_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-content-controller.yml"
IMAGE_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-article-image.yml"


class DummySite:
    def get(self, url):
        return 404, ""


class DummyGithub:
    def __init__(self):
        self.saved = None
        self.video_state = {"version": 1, "items": []}

    def load_controller_state(self):
        return None

    def save_controller_state(self, state):
        self.saved = state

    def article_pr_image_ready(self, pr):
        return False, {}

    def active_image_run(self, pr_number):
        return None

    def newest_video_state(self):
        return self.video_state


class PipelineV3SelfAuditTests(unittest.TestCase):
    def test_schema_v3_has_explicit_required_fields_for_all_three_stages(self):
        state = v3.normalize_state(None, date(2026, 8, 21))
        self.assertEqual(state["schema_version"], 3)
        for stage in ("article", "image", "video"):
            self.assertIn(stage, state)
            for field in ("attempt_count", "status", "last_error", "next_retry_at", "run_id", "provider_id"):
                self.assertIn(field, state[stage], (stage, field))
            self.assertEqual(state[stage]["attempt_count"], 0)

    def test_schema_v2_migration_preserves_real_dispatch_count(self):
        old = {
            "schema_version": 2,
            "cycle": "2026-08-20",
            "status": "complete",
            "article": {"attempts": 4},
            "video": {"attempts": 1, "resume_dispatches": 5},
            "history": [],
        }
        state = v3.normalize_state(old, date(2026, 8, 20))
        self.assertEqual(state["schema_version"], 3)
        self.assertEqual(state["article"]["attempt_count"], 4)
        self.assertEqual(state["video"]["attempt_count"], 6)
        self.assertEqual(state["image"]["attempt_count"], 0)

    def test_every_controller_owned_stage_has_exactly_three_total_dispatches(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["retry"]["max_attempts_per_stage"], 3)
        self.assertEqual(contract["article"]["max_attempts"], 3)
        self.assertEqual(contract["image"]["max_attempts"], 3)
        self.assertEqual(contract["video"]["max_attempts_per_stage"], 3)
        self.assertEqual(v3.MAX_STAGE_ATTEMPTS, 3)

    def test_image_stage_dispatches_then_defers_without_blocking_article(self):
        github = DummyGithub()
        controller = best_effort.BestEffortController(
            github,
            DummySite(),
            now=datetime(2026, 8, 21, 9, 0, tzinfo=ZoneInfo("Asia/Jerusalem")),
        )
        state = v3.normalize_state(None, date(2026, 8, 21))
        pr = {"number": 99, "html_url": "https://example.test/pr/99"}
        with mock.patch.object(v3.core.GitHubClient, "dispatch", autospec=True) as dispatch:
            first = controller._handle_open_article_pr(state, pr)
            self.assertEqual(first.kind, "dispatch_image")
            self.assertEqual(state["image"]["attempt_count"], 1)
            state["image"]["attempt_count"] = 3
            state["status"] = "blocked"
            state["last_error"] = {"stage": "image", "code": "IMAGE_ATTEMPTS_EXHAUSTED"}
            second = controller._handle_open_article_pr(state, pr)
            self.assertEqual(second.kind, "wait")
            self.assertEqual(state["image"]["status"], "deferred")
            self.assertEqual(state["status"], "article_pr_open")
            self.assertIsNone(state["last_error"])
            self.assertEqual(dispatch.call_count, 1)

    def test_article_session_timeout_recovery_does_not_increment_attempt_count(self):
        github = DummyGithub()
        controller = best_effort.BestEffortController(
            github,
            DummySite(),
            now=datetime(2026, 8, 21, 15, 0, tzinfo=ZoneInfo("Asia/Jerusalem")),
        )
        state = v3.normalize_state(None, date(2026, 8, 21))
        state["article"]["attempt_count"] = 1
        state["article"]["last_jules_session_id"] = "sessions/123"
        state["article"]["last_error"] = {
            "stage": "article",
            "code": "JULES_TIMEOUT_SESSION_ACTIVE",
            "message": "timed out",
        }
        with mock.patch.object(v3.core.GitHubClient, "dispatch", autospec=True) as dispatch:
            controller._dispatch_budgeted(state, "article", "kesher-article-generation.yml", {"slot": "2026-08-21"})
        self.assertEqual(state["article"]["attempt_count"], 1)
        self.assertEqual(state["article"]["resume_dispatches"], 1)
        dispatch.assert_called_once()

    def test_exact_notebooklm_resume_does_not_consume_another_video_attempt(self):
        github = DummyGithub()
        github.video_state = {
            "version": 1,
            "items": [{
                "id": "video-oldest",
                "status": "generating",
                "uploaded": False,
                "source_id": "source-123",
                "task_id": "task-456",
                "artifact_id": "task-456",
                "created_at": "2026-08-21T12:00:00+00:00",
                "source": {"slug": "article", "date": "2026-08-21"},
            }],
        }
        controller = best_effort.BestEffortController(
            github,
            DummySite(),
            now=datetime(2026, 8, 21, 15, 0, tzinfo=ZoneInfo("Asia/Jerusalem")),
        )
        state = v3.normalize_state(None, date(2026, 8, 21))
        state["video"]["attempt_count"] = 1
        with mock.patch.object(v3.core.GitHubClient, "dispatch", autospec=True) as dispatch:
            controller._dispatch_budgeted(state, "video", core.VIDEO_WORKFLOW, {"operation": "full"})
        self.assertEqual(state["video"]["attempt_count"], 1)
        self.assertEqual(state["video"]["resume_dispatches"], 1)
        self.assertEqual(state["video"]["provider_id"], "task-456")
        self.assertEqual(state["video"]["source_id"], "source-123")
        self.assertEqual(state["video"]["artifact_id"], "task-456")
        dispatch.assert_called_once()

    def test_missing_provider_identity_is_a_real_video_attempt(self):
        github = DummyGithub()
        github.video_state = {
            "version": 1,
            "items": [{
                "id": "video-new",
                "status": "generating",
                "uploaded": False,
                "source_id": "source-123",
                "task_id": "",
                "artifact_id": "",
                "source": {"slug": "article", "date": "2026-08-21"},
            }],
        }
        controller = best_effort.BestEffortController(
            github,
            DummySite(),
            now=datetime(2026, 8, 21, 15, 0, tzinfo=ZoneInfo("Asia/Jerusalem")),
        )
        state = v3.normalize_state(None, date(2026, 8, 21))
        with mock.patch.object(v3.core.GitHubClient, "dispatch", autospec=True) as dispatch:
            controller._dispatch_budgeted(state, "video", core.VIDEO_WORKFLOW, {"operation": "full"})
        self.assertEqual(state["video"]["attempt_count"], 1)
        self.assertEqual(state["video"].get("resume_dispatches", 0), 0)
        dispatch.assert_called_once()

    def test_retry_backoff_is_five_then_fifteen_minutes(self):
        state = v3.normalize_state(None, date(2026, 8, 21))
        v3.record_stage_failure(state, "image", "X", "first", run_id=1)
        first = datetime.fromisoformat(state["image"]["next_retry_at"])
        self.assertEqual(state["image"]["same_failure_streak"], 1)
        v3.record_stage_failure(state, "image", "X", "second", run_id=2)
        second = datetime.fromisoformat(state["image"]["next_retry_at"])
        self.assertEqual(state["image"]["same_failure_streak"], 2)
        self.assertGreater((second - datetime.now(second.tzinfo)).total_seconds(), 13 * 60)
        self.assertLess((first - datetime.now(first.tzinfo)).total_seconds(), 6 * 60)

    def test_image_child_is_part_of_event_driven_controller_but_failures_still_defer(self):
        workflow = CONTROLLER_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Kesher Trusted Article Image", workflow)
        self.assertIn("scripts/kesher_content_controller_v5_runtime.py", workflow)
        self.assertNotIn("scripts/kesher_content_controller_v3_best_effort.py", workflow)
        self.assertIn('cron: "3,8,13,18,23,28,33,38,43,48,53,58 * * * *"', workflow)
        env = {
            "KESHER_TRIGGER_EVENT": "workflow_run",
            "KESHER_CHILD_WORKFLOW": "Kesher Trusted Article Image",
            "KESHER_CHILD_CONCLUSION": "failure",
        }
        self.assertTrue(v3.entry.failed_child_waits_for_heartbeat(env))

    def test_image_worker_has_no_independent_production_trigger(self):
        trigger = IMAGE_WORKFLOW.read_text(encoding="utf-8").split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch:", trigger)
        self.assertNotIn("pull_request_target:", trigger)
        self.assertNotIn("schedule:", trigger)

    def test_v3_guard_covers_article_video_and_deploy_dispatch_paths(self):
        source = (ROOT / "scripts" / "kesher_content_controller_v3_entry.py").read_text(encoding="utf-8")
        self.assertIn("workflow == core.ARTICLE_WORKFLOW", source)
        self.assertIn("workflow == core.VIDEO_WORKFLOW", source)
        self.assertIn("workflow == core.DEPLOY_WORKFLOW", source)
        self.assertIn("ARTICLE_DEPLOY_ATTEMPTS_EXHAUSTED", source)


if __name__ == "__main__":
    unittest.main()
