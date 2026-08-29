import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / ".github" / "scripts" / "kesher_task_supervisor_runtime.py"
spec = importlib.util.spec_from_file_location("kesher_task_supervisor_runtime", MODULE_PATH)
runtime = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = runtime
spec.loader.exec_module(runtime)


class KesherTaskSupervisorRuntimeTests(unittest.TestCase):
    def test_excludes_openclaw_issue(self):
        issue = {"title": "OpenClaw recovery", "body": "Tailscale and OCI helper"}
        self.assertFalse(runtime.is_kesher_issue(issue))

    def test_includes_kesher_marketing_issue(self):
        issue = {"title": "Competitor Ads Research", "body": "Israeli couples therapy advertisers"}
        self.assertTrue(runtime.is_kesher_issue(issue))

    def test_excludes_dependabot_pr(self):
        pr = {"title": "chore(deps): bump vite", "body": "Kesher dependency", "user": {"login": "dependabot[bot]"}}
        self.assertFalse(runtime.is_kesher_pr(pr))

    def test_includes_unlinked_kesher_article_pr(self):
        pr = {"title": "Publish Kesher article: example", "body": "No issue reference", "user": {"login": "yanivsa"}}
        self.assertTrue(runtime.is_kesher_pr(pr))

    def test_includes_synthetic_workflow_incident(self):
        issue = {"title": "workflow failure", "body": "<!-- kesher-supervisor-workflow-failure:123 -->"}
        self.assertTrue(runtime.is_kesher_issue(issue))

    def test_orphan_pr_marker(self):
        issue = {"body": "<!-- kesher-supervisor-orphan-pr:579 -->"}
        self.assertEqual(runtime.orphan_pr_number(issue), 579)

    def test_detects_phone_video_verification_as_human_only(self):
        issue = {"title": "Google Business Profile", "body": "Complete continuous phone video verification"}
        self.assertTrue(runtime.is_human_only_issue(issue))

    def test_push_deploy_observation_does_not_dispatch(self):
        before = runtime.datetime.now(runtime.timezone.utc)
        marker = runtime.observe_push_deploy()
        self.assertLess(marker, before)
        self.assertIn("duplicate deploy dispatch suppressed", runtime.base.meaningful_changes[-1])

    def test_latest_agent_signature_is_stable(self):
        activities = [{"agentMessaged": {"agentMessage": "same result"}}]
        a = runtime.latest_agent_signature({"name": "sessions/1"}, activities)
        b = runtime.latest_agent_signature({"name": "sessions/1"}, activities)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
