import importlib.util
import pathlib
import sys
import unittest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / ".github" / "scripts" / "kesher_task_supervisor_runtime_v2.py"
spec = importlib.util.spec_from_file_location("kesher_task_supervisor_runtime_v2", MODULE_PATH)
runtime_v2 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = runtime_v2
spec.loader.exec_module(runtime_v2)


class KesherTaskSupervisorRecoveryTests(unittest.TestCase):
    def test_first_recovery_starts_at_stage_one(self):
        stage, may_send, _ = runtime_v2._recovery_state([], "issue-1-pr-2-generic")
        self.assertEqual(stage, 1)
        self.assertTrue(may_send)

    def test_does_not_advance_until_jules_responds(self):
        key = "issue-1-pr-2-generic"
        activities = [
            {
                "createTime": "2026-08-30T06:00:00Z",
                "userMessaged": {
                    "userMessage": f"{runtime_v2.RECOVERY_MARKER} key={key} stage=1"
                },
            }
        ]
        stage, may_send, _ = runtime_v2._recovery_state(activities, key)
        self.assertEqual(stage, 1)
        self.assertFalse(may_send)

    def test_advances_after_jules_response(self):
        key = "issue-1-pr-2-generic"
        activities = [
            {
                "createTime": "2026-08-30T06:00:00Z",
                "userMessaged": {
                    "userMessage": f"{runtime_v2.RECOVERY_MARKER} key={key} stage=1"
                },
            },
            {
                "createTime": "2026-08-30T06:05:00Z",
                "agentMessaged": {"agentMessage": "I tried a focused repair."},
            },
        ]
        stage, may_send, recent = runtime_v2._recovery_state(activities, key)
        self.assertEqual(stage, 2)
        self.assertTrue(may_send)
        self.assertIn("focused repair", recent[-1])

    def test_stage_caps_at_five_and_can_continue_on_new_evidence(self):
        key = "issue-1-pr-2-generic"
        activities = []
        for stage in range(1, 6):
            activities.extend(
                [
                    {
                        "createTime": f"2026-08-30T0{stage}:00:00Z",
                        "userMessaged": {
                            "userMessage": f"{runtime_v2.RECOVERY_MARKER} key={key} stage={stage}"
                        },
                    },
                    {
                        "createTime": f"2026-08-30T0{stage}:05:00Z",
                        "agentMessaged": {"agentMessage": f"attempt {stage}"},
                    },
                ]
            )
        stage, may_send, _ = runtime_v2._recovery_state(activities, key)
        self.assertEqual(stage, 5)
        self.assertTrue(may_send)

    def test_legacy_attempts_can_seed_stage_three(self):
        key = "issue-1-pr-2-generated-text"
        activities = [
            {
                "createTime": "2026-08-30T04:00:00Z",
                "userMessaged": {"userMessage": "Fix צמצום חרדי and regenerate."},
            },
            {
                "createTime": "2026-08-30T05:00:00Z",
                "userMessaged": {"userMessage": "The same occurrence remains; regenerate from source."},
            },
        ]
        count = runtime_v2._legacy_attempt_count(activities, "generated-text")
        self.assertGreaterEqual(count, 2)
        stage, may_send, _ = runtime_v2._recovery_state(
            activities, key, initial_stage=min(3, 1 + count)
        )
        self.assertEqual(stage, 3)
        self.assertTrue(may_send)

    def test_branch_contamination_pattern_changes_strategy(self):
        kind = runtime_v2._recovery_kind("PR is dirty, mergeable=false, unrelated changed files")
        self.assertEqual(kind, "branch-contamination")
        strategy = runtime_v2._pattern_strategy(kind)
        self.assertIn("reconstruct the SAME branch", strategy)
        self.assertIn("allowlist", strategy)

    def test_generated_text_pattern_repairs_source_of_truth(self):
        kind = runtime_v2._recovery_kind("same string צמצום חרדי remains after regenerate")
        self.assertEqual(kind, "generated-text")
        strategy = runtime_v2._pattern_strategy(kind)
        self.assertIn("source of truth", strategy)
        self.assertIn("zero bad occurrences", strategy)

    def test_first_final_qa_is_plain_but_recurring_qa_enters_recovery(self):
        self.assertFalse(runtime_v2._should_use_recovery("PR #22 final QA", []))
        activities = [
            {
                "createTime": "2026-08-30T06:00:00Z",
                "userMessaged": {
                    "userMessage": f"{runtime_v2.base.QA_REQUEST} PR #22 HEAD abc123"
                },
            }
        ]
        self.assertTrue(runtime_v2._should_use_recovery("PR #22 final QA", activities))
        self.assertTrue(runtime_v2._should_use_recovery("PR #22 scope repair", []))

    def test_history_can_classify_recurring_qa_as_generated_text(self):
        history = "Previous attempt still contains צמצום חרדי after regenerate"
        kind = runtime_v2._recovery_kind(f"PR #582 final QA\n{history}")
        self.assertEqual(kind, "generated-text")


if __name__ == "__main__":
    unittest.main()
