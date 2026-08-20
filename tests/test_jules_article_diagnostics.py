from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import jules_article_diagnostics as diagnostics
from scripts import jules_article_runner_core as core


class JulesArticleDiagnosticsTests(unittest.TestCase):
    def test_configured_source_must_resolve_to_exact_repo_and_main(self):
        source = {
            "name": core.SOURCE,
            "githubRepo": {
                "owner": "yanivsa",
                "repo": "kesher-website",
                "defaultBranch": {"displayName": "main"},
                "branches": [{"displayName": "main"}],
            },
        }
        with mock.patch.object(core, "request_json", return_value=source) as request:
            result = diagnostics.validate_configured_source("key")

        self.assertTrue(result["main_available"])
        self.assertEqual(result["owner"], "yanivsa")
        self.assertEqual(result["repo"], "kesher-website")
        self.assertEqual(request.call_args.args[0], "GET")
        self.assertTrue(request.call_args.args[1].endswith(core.SOURCE))

    def test_source_mismatch_fails_closed(self):
        source = {
            "githubRepo": {
                "owner": "someone-else",
                "repo": "wrong-repo",
                "defaultBranch": {"displayName": "main"},
                "branches": [{"displayName": "main"}],
            }
        }
        with mock.patch.object(core, "request_json", return_value=source):
            with self.assertRaisesRegex(core.ArticleRunnerError, "configured Jules source resolved") as ctx:
                diagnostics.validate_configured_source("key")
        self.assertEqual(ctx.exception.code, "JULES_SOURCE_MISMATCH")

    def test_activity_inventory_follows_documented_pagination(self):
        first = {
            "activities": [{"id": "a1", "createTime": "2026-08-20T01:00:00Z"}],
            "nextPageToken": "next page/2",
        }
        second = {"activities": [{"id": "a2", "createTime": "2026-08-20T02:00:00Z"}]}
        with mock.patch.object(core, "request_json", side_effect=[first, second]) as request:
            rows = diagnostics.list_session_activities("key", "sessions/123")

        self.assertEqual([row["id"] for row in rows], ["a1", "a2"])
        self.assertEqual(request.call_count, 2)
        self.assertIn("pageToken=next+page%2F2", request.call_args_list[1].args[1])

    def test_activity_summary_reports_reason_and_change_set_without_patch_body(self):
        activities = [
            {
                "id": "a1",
                "createTime": "2026-08-20T01:00:00Z",
                "description": "Code changes ready",
                "artifacts": [{"changeSet": {"gitPatch": {"patch": "diff --git a/a b/a\n+secret-looking-body"}}}],
            },
            {
                "id": "a2",
                "createTime": "2026-08-20T02:00:00Z",
                "agentMessaged": {"agentMessage": "I could not submit the pull request because repository write access is unavailable."},
            },
        ]
        summary = diagnostics.summarize_activities(activities)

        self.assertEqual(summary["change_set_count"], 1)
        self.assertEqual(len(summary["change_set_fingerprints"]), 1)
        self.assertIn("could not submit", summary["last_agent_message"])
        self.assertNotIn("secret-looking-body", json.dumps(summary))

    def test_diagnostic_is_attached_to_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "result.json"
            path.write_text(
                json.dumps({"outcome": "COMPLETED_WITHOUT_PR", "message": "Jules completed without PR"}),
                encoding="utf-8",
            )
            diagnostics.attach_to_result(
                path,
                {
                    "source": {"owner": "yanivsa", "repo": "kesher-website", "main_available": True},
                    "activity_count": 7,
                    "change_set_count": 1,
                    "change_set_fingerprints": ["abc123"],
                    "last_agent_message": "PR creation was unavailable",
                    "last_progress": "",
                    "last_description": "",
                    "session_failed_reason": "",
                },
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["diagnostic"]["activity_count"], 7)
        self.assertEqual(payload["diagnostic"]["change_set_count"], 1)
        self.assertIn("PR creation was unavailable", payload["message"])


if __name__ == "__main__":
    unittest.main()
