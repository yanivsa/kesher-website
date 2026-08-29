import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / ".github" / "scripts" / "kesher_task_supervisor.py"
spec = importlib.util.spec_from_file_location("kesher_task_supervisor", MODULE_PATH)
supervisor = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = supervisor
spec.loader.exec_module(supervisor)


class KesherTaskSupervisorTests(unittest.TestCase):
    def test_issue_refs(self):
        text = "Fixes #574; references #575 and plain #576"
        self.assertEqual(supervisor.issue_ref_numbers(text), {574, 575})
        self.assertEqual(supervisor.any_ref_numbers(text), {574, 575, 576})

    def test_gate_requires_verify(self):
        state = supervisor.gate_state({
            "lint": {"id": 1, "status": "completed", "conclusion": "success"},
        })
        self.assertEqual(state.state, "missing")

    def test_gate_rejects_failed_check(self):
        state = supervisor.gate_state({
            "verify": {"id": 1, "status": "completed", "conclusion": "success"},
            "e2e": {"id": 2, "status": "completed", "conclusion": "failure"},
        })
        self.assertEqual(state.state, "failed")
        self.assertIn("e2e=failure", state.detail)

    def test_gate_accepts_green_checks(self):
        state = supervisor.gate_state({
            "verify": {"id": 1, "status": "completed", "conclusion": "success"},
            "stability": {"id": 2, "status": "completed", "conclusion": "success"},
        })
        self.assertEqual(state.state, "green")

    def test_scope_blocks_unrelated_workflow_churn(self):
        issue = {"title": "Fix Hebrew copy", "body": ""}
        files = [{"filename": "src/App.tsx"}, {"filename": ".github/workflows/deploy.yml"}]
        state = supervisor.scope_gate(issue, files)
        self.assertEqual(state.state, "failed")

    def test_scope_allows_workflow_issue(self):
        issue = {"title": "Repair workflow controller", "body": "Fix GitHub Actions controller"}
        files = [{"filename": ".github/workflows/deploy.yml"}]
        state = supervisor.scope_gate(issue, files)
        self.assertEqual(state.state, "green")

    def test_session_matches_issue(self):
        session = {
            "title": "[Kesher Supervisor] Issue #574",
            "prompt": "repair",
            "sourceContext": {"source": "sources/github/yanivsa/kesher-website"},
            "outputs": [],
        }
        self.assertTrue(supervisor.repo_session(session))
        self.assertTrue(supervisor.session_mentions(session, 574, set()))

    def test_human_blocker_marker(self):
        activities = [{"agentMessaged": {"agentMessage": "HUMAN_BLOCKER: enable 2FA"}}]
        self.assertEqual(supervisor.human_blocker(activities), "enable 2FA")

    def test_live_urls_falls_back_to_home(self):
        issue = {"body": "No URL here"}
        pr = {"body": ""}
        self.assertEqual(supervisor.live_urls(issue, pr), ["https://kesher.saharoni.com/"])


if __name__ == "__main__":
    unittest.main()
