"""Unit tests for the Kesher Publish Request workflow and Cloud Publisher."""

import json
import unittest
from pathlib import Path
import yaml

import scripts.kesher_cloud_publisher as publisher


class PublishRequestWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow_path = Path(".github/workflows/kesher-publish-request.yml")

    def test_workflow_file_exists_and_schema(self):
        self.assertTrue(self.workflow_path.is_file())
        content = yaml.safe_load(self.workflow_path.read_text(encoding="utf-8"))
        self.assertEqual(content.get("name"), "Kesher Publish Request")
        on_block = content.get("on") or content.get(True) or {}
        self.assertIn("workflow_dispatch", on_block)

        inputs = on_block["workflow_dispatch"]["inputs"]
        self.assertIn("action", inputs)
        allowed_actions = inputs["action"]["options"]
        for expected in ("daily", "run_now", "resume", "audit", "repair"):
            self.assertIn(expected, allowed_actions)

        # Single Scheduler policy: Must NOT contain any schedule triggers
        self.assertNotIn("schedule", on_block)
        self.assertNotIn("push", on_block)

    def test_client_headers(self):
        client = publisher.GitHubActionsClient("dummy_token", "yanivsa/kesher-website")
        headers = client._headers()
        self.assertEqual(headers["Authorization"], "Bearer dummy_token")
        self.assertEqual(headers["X-GitHub-Api-Version"], "2022-11-28")

    def test_handle_audit_slot(self):
        res = publisher.handle_audit("2026-11-21")
        self.assertEqual(res["action"], "audit")
        self.assertEqual(res["slot"], "2026-11-21")
        self.assertTrue(res["contract_complete"])
        self.assertEqual(res["status"], "success")

    def test_handle_daily_already_complete_guarantee(self):
        res = publisher.handle_daily("2026-11-21", client=None, dry_run=True)
        self.assertEqual(res["action"], "daily")
        self.assertEqual(res["slot"], "2026-11-21")
        self.assertEqual(res["status"], "already_complete")
        self.assertTrue(res["contract_complete"])

    def test_supervisor_audit_requires_exact_slug(self):
        from unittest.mock import patch, Mock

        payload = {
            "delivery": {
                "complete": True,
                "article_count": 1,
                "triads": [{"slug": "another-article", "complete": True}],
            },
            "controller_health": {"direct_takeover_required": False},
        }
        with patch.object(publisher.subprocess, "run", return_value=Mock(
            stdout=json.dumps(payload), stderr="", returncode=0,
        )):
            audit = publisher.run_supervisor_audit("2026-11-21", target_slug="requested-article")
            self.assertFalse(audit["complete"])
            audit_ok = publisher.run_supervisor_audit("2026-11-21", target_slug="another-article")
            self.assertTrue(audit_ok["complete"])

    def test_supervisor_audit_refuses_empty_success(self):
        from unittest.mock import patch, Mock

        payload = {"delivery": {"complete": True, "article_count": 0, "triads": []}}
        with patch.object(publisher.subprocess, "run", return_value=Mock(
            stdout=json.dumps(payload), stderr="", returncode=0,
        )):
            self.assertFalse(publisher.run_supervisor_audit("2026-11-22")["complete"])

    def test_get_latest_run_does_not_adopt_stale_or_ambiguous_dispatch(self):
        from unittest.mock import patch, Mock

        client = publisher.GitHubActionsClient("dummy_token")
        def response(rows):
            return Mock(__enter__=Mock(return_value=Mock(
                read=Mock(return_value=json.dumps({"workflow_runs": rows}).encode("utf-8"))
            )), __exit__=Mock(return_value=False))

        start = "2026-11-22T05:27:52+00:00"
        with patch.object(publisher.urllib.request, "urlopen", return_value=response([
            {"id": 111, "created_at": "2026-11-21T00:00:00Z", "event": "workflow_dispatch"},
        ])):
            self.assertIsNone(client.get_latest_run("kesher-daily-video.yml", start))

        rows = [
            {"id": 222, "created_at": "2026-11-22T05:27:53Z", "event": "workflow_dispatch"},
            {"id": 333, "created_at": "2026-11-22T05:27:54Z", "event": "workflow_dispatch"},
        ]
        with patch.object(publisher.urllib.request, "urlopen", return_value=response(rows)):
            with self.assertRaisesRegex(RuntimeError, "AMBIGUOUS_WORKFLOW_DISPATCH"):
                client.get_latest_run("kesher-daily-video.yml", start)

    def test_handle_run_now_dry_run(self):
        res = publisher.handle_run_now("2026-11-21", client=None, dry_run=True)
        self.assertEqual(res["action"], "run_now")
        self.assertEqual(res["status"], "dry_run_success")
        self.assertTrue(res["slug"])
        self.assertTrue(res["article_url"].startswith("https://kesher.saharoni.com/blog/"))


if __name__ == "__main__":
    unittest.main()
