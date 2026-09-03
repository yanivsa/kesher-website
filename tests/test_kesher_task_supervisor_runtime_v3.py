import importlib.util
import inspect
import pathlib
import sys
import unittest
from unittest import mock

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / ".github" / "scripts" / "kesher_task_supervisor_runtime_v3.py"
spec = importlib.util.spec_from_file_location("kesher_task_supervisor_runtime_v3", MODULE_PATH)
runtime_v3 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = runtime_v3
spec.loader.exec_module(runtime_v3)


class KesherTaskSupervisorAdaptiveRecoveryTests(unittest.TestCase):
    def test_fingerprint_is_stable_across_head_and_url_changes(self):
        reason = "PR #582 final QA"
        a = runtime_v3._adaptive_recovery_key(
            "Issue #575 PR #582 current HEAD abcdef123456 still has the same Hebrew blocker https://example.test/a",
            reason,
            "generated-text",
        )
        b = runtime_v3._adaptive_recovery_key(
            "Issue #575 PR #582 current HEAD fedcba654321 still has the same Hebrew blocker https://example.test/b",
            reason,
            "generated-text",
        )
        self.assertEqual(a, b)

    def test_fingerprint_changes_when_normalized_blocker_detail_changes(self):
        reason = "PR #22 scope repair"
        a = runtime_v3._adaptive_recovery_key(
            "Issue #1 PR #22 branch contains unrelated workflow files",
            reason,
            "branch-contamination",
        )
        b = runtime_v3._adaptive_recovery_key(
            "Issue #1 PR #22 branch contains an unrelated binary artifact",
            reason,
            "branch-contamination",
        )
        self.assertNotEqual(a, b)

    def test_new_head_deescalates_to_stage_one(self):
        key = "issue-1-pr-2-generated-text-fp-abc"
        activities = [
            {
                "createTime": "2026-08-30T06:00:00Z",
                "userMessaged": {
                    "userMessage": f"{runtime_v3.runtime_v2.RECOVERY_MARKER} key={key} stage=4 head=aaaaaaa"
                },
            },
            {
                "createTime": "2026-08-30T06:05:00Z",
                "agentMessaged": {"agentMessage": "I pushed a corrected head."},
            },
        ]
        stage, may_send, _, takeover = runtime_v3._marker_state(
            activities, key, "bbbbbbb", initial_stage=3
        )
        self.assertEqual(stage, 1)
        self.assertTrue(may_send)
        self.assertFalse(takeover)

    def test_same_head_advances_only_after_agent_response(self):
        key = "issue-1-pr-2-generic-fp-abc"
        waiting = [
            {
                "createTime": "2026-08-30T06:00:00Z",
                "userMessaged": {
                    "userMessage": f"{runtime_v3.runtime_v2.RECOVERY_MARKER} key={key} stage=2 head=aaaaaaa"
                },
            }
        ]
        stage, may_send, _, takeover = runtime_v3._marker_state(waiting, key, "aaaaaaa")
        self.assertEqual(stage, 2)
        self.assertFalse(may_send)
        self.assertFalse(takeover)

        responded = waiting + [
            {
                "createTime": "2026-08-30T06:05:00Z",
                "agentMessaged": {"agentMessage": "Attempt completed without a new head."},
            }
        ]
        stage, may_send, _, takeover = runtime_v3._marker_state(responded, key, "aaaaaaa")
        self.assertEqual(stage, 3)
        self.assertTrue(may_send)
        self.assertFalse(takeover)

    def test_stage_five_response_becomes_takeover_not_stage_five_loop(self):
        key = "issue-594-pr-na-generic-fp-abc"
        activities = [
            {
                "createTime": "2026-08-30T06:00:00Z",
                "userMessaged": {
                    "userMessage": f"{runtime_v3.runtime_v2.RECOVERY_MARKER} key={key} stage=5 head=aaaaaaa"
                },
            },
            {
                "createTime": "2026-08-30T06:05:00Z",
                "agentMessaged": {"agentMessage": "Stage five failed to produce progress."},
            },
        ]
        stage, may_send, _, takeover = runtime_v3._marker_state(activities, key, "aaaaaaa")
        self.assertEqual(stage, 5)
        self.assertFalse(may_send)
        self.assertTrue(takeover)

    def test_human_blocker_halts_wrapper_before_retry(self):
        session = {"name": "sessions/123"}
        activities = [
            {
                "createTime": "2026-08-30T06:00:00Z",
                "agentMessaged": {"agentMessage": "HUMAN_BLOCKER: complete secure authentication"},
            }
        ]
        with mock.patch.object(runtime_v3.base, "jules_activities", return_value=activities), mock.patch.object(
            runtime_v3.runtime_v2, "_send_with_transient_jules_retry"
        ) as send:
            result = runtime_v3.send_to_session_with_adaptive_recovery(
                session, "Issue #1 recovery", reason="Issue #1 failed-session recovery"
            )
        self.assertFalse(result)
        send.assert_not_called()

    def test_pending_ci_remains_non_mutating_in_inherited_processor(self):
        source = inspect.getsource(runtime_v3.runtime_v2.runtime.ORIGINAL_PROCESS_ISSUE)
        self.assertIn('if ci.state == "pending":', source)
        pending_block = source.split('if ci.state == "pending":', 1)[1].split('if ci.state == "failed":', 1)[0]
        self.assertIn("return", pending_block)
        self.assertNotIn("send_to_session", pending_block)

    def test_takeover_comment_is_deduplicated(self):
        session = {"name": "sessions/123"}
        key = "issue-594-pr-na-generic-fp-deadbeef"
        marker = f"<!-- {runtime_v3.TAKEOVER_COMMENT_MARKER} fingerprint={key} -->"
        with mock.patch.object(runtime_v3.base, "get_issue_comments", return_value=[{"body": marker}]), mock.patch.object(
            runtime_v3.base, "comment_issue"
        ) as comment:
            changed = runtime_v3._record_takeover(session, key, "test recovery")
        self.assertFalse(changed)
        comment.assert_not_called()


if __name__ == "__main__":
    unittest.main()
