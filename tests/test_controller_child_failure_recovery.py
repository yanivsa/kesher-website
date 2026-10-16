from __future__ import annotations

import unittest
from datetime import datetime
from unittest import mock
from zoneinfo import ZoneInfo

import scripts.kesher_content_controller_stabilized as stabilized
import scripts.kesher_content_controller as core

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


class ControllerChildFailureRecoveryTests(unittest.TestCase):
    def test_failed_child_does_not_dead_end_when_budget_remains(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        github.posts_on_main.return_value = []
        github.open_article_prs.return_value = []
        github.active_workflow_run.return_value = None

        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 16, 10, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )

        state = {
            "cycle": "2026-10-16",
            "status": "article_image_running",
            "schema_version": 5,
            "article": {
                "pr_number": 1130,
                "current_pr_head_sha": "3041e1b7c5c183dcb95eb95fd486c040f740bde5",
                "normalized_head_sha": "3041e1b7c5c183dcb95eb95fd486c040f740bde5",
                "normalization_status": "complete",
            },
            "image": {
                "status": "running",
                "run_id": 12345,
                "attempt_count": 1,
            },
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
        }

        # Mock child completion notification with failure
        child_env = {
            "trigger": "workflow_dispatch",
            "workflow": "Kesher Trusted Article Image",
            "run_id": "12345",
            "conclusion": "failure",
            "source_slug": "",
            "slot": "2026-10-16",
            "source_sha": "",
        }

        with mock.patch.object(controller, "state", return_value=state), \
             mock.patch.object(controller, "_child_notification_env", return_value=child_env), \
             mock.patch.object(controller, "_validate_child_notification", return_value=(True, "")), \
             mock.patch.object(controller, "_safe_save_controller_state"), \
             mock.patch.object(stabilized.v5.core.GitHubClient, "dispatch"):

            res_state, action = controller.tick()

        # The image status must NOT remain 'running'
        self.assertNotEqual(res_state["image"]["status"], "running")
        # Action must not be a dead-end wait without recording processed notification
        self.assertIn("Kesher Trusted Article Image:12345", res_state.get("processed_child_notifications", []))

    def test_failed_child_blocks_when_stage_budget_is_exhausted(self) -> None:
        github = mock.MagicMock()
        site = mock.MagicMock()
        controller = stabilized.StabilizedRuntimeV5Controller(
            now=datetime(2026, 10, 16, 10, 0, tzinfo=ISRAEL_TZ),
            github=github,
            site=site,
        )

        state = {
            "cycle": "2026-10-16",
            "status": "article_image_running",
            "schema_version": 5,
            "article": {"pr_number": 1130},
            "image": {
                "status": "running",
                "run_id": 12345,
                "attempt_count": 3,  # Max attempts reached
            },
        }

        child_env = {
            "trigger": "workflow_dispatch",
            "workflow": "Kesher Trusted Article Image",
            "run_id": "12345",
            "conclusion": "failure",
            "source_slug": "",
            "slot": "2026-10-16",
            "source_sha": "",
        }

        with mock.patch.object(controller, "state", return_value=state), \
             mock.patch.object(controller, "_child_notification_env", return_value=child_env), \
             mock.patch.object(controller, "_validate_child_notification", return_value=(True, "")), \
             mock.patch.object(controller, "_safe_save_controller_state"):

            res_state, action = controller.tick()

        self.assertEqual(action.kind, "blocked")
        self.assertIn("exhausted stage budget", action.reason)


if __name__ == "__main__":
    unittest.main()
