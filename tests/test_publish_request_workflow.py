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

    def test_handle_run_now_dry_run(self):
        res = publisher.handle_run_now("2026-11-21", client=None, dry_run=True)
        self.assertEqual(res["action"], "run_now")
        self.assertEqual(res["status"], "dry_run_success")
        self.assertTrue(res["slug"])
        self.assertTrue(res["article_url"].startswith("https://kesher.saharoni.com/blog/"))


if __name__ == "__main__":
    unittest.main()
