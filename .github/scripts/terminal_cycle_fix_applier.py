from __future__ import annotations

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = ROOT / "tests" / "test_kesher_content_controller.py"
CORE_PATH = ROOT / "scripts" / "kesher_content_controller.py"

TEST_NAME = "test_terminal_merge_budget_tombstone_blocks_stale_jules_recovery"
TEST_MARKER = "    def test_preserved_jules_timeout_immediately_redispatches_same_slot_recovery(self):\n"
TEST_BLOCK = '''    def test_terminal_merge_budget_tombstone_blocks_stale_jules_recovery(self):
        gh = FakeGitHub()
        gh.saved_state = controller.new_cycle_state(self.now().date())
        # Reproduce production after a terminal cycle was accidentally revived:
        # mutable status says running, while merge_dispatch_count is the durable
        # proof that this article cycle already exhausted its terminal budget.
        gh.saved_state["status"] = "article_generating"
        gh.saved_state["article"].update({
            "status": "running",
            "attempts": 1,
            "attempt_count": 2,
            "run_id": 43,
            "processed_run_id": 41,
            "merge_dispatch_count": 6,
        })
        gh.runs[43] = {"id": 43, "status": "completed", "conclusion": "failure"}
        gh.article_results[43] = {
            "schema_version": 1,
            "slot": "2026-08-19",
            "outcome": "JULES_TIMEOUT_SESSION_ACTIVE",
            "retryable": True,
            "message": "session preserved",
            "session_id": "sessions/43",
        }

        state, action = self.make(gh).tick()

        self.assertEqual(action.kind, "blocked")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["article"]["status"], "exhausted")
        self.assertEqual(state["last_error"]["code"], "ARTICLE_ATTEMPTS_EXHAUSTED")
        self.assertEqual(gh.dispatches, [])

'''

CORE_OLD = '''        if not todays:
            if not self.article_slot_open():
'''
CORE_NEW = '''        if not todays:
            # A terminal article budget is a durable tombstone for this cycle.
            # Child workflow wake-ups must never replay an older retryable worker
            # result after auto-merge/article attempts were already exhausted.
            # A real same-day article, reconciled above, still takes precedence.
            article_state = state.get("article") if isinstance(state.get("article"), dict) else {}
            last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
            terminal_article_exhausted = bool(
                article_state.get("status") == "exhausted"
                or int(article_state.get("merge_dispatch_count") or 0) >= 3
                or (
                    state.get("status") == "blocked"
                    and last_error.get("stage") == "article"
                    and last_error.get("code") == "ARTICLE_ATTEMPTS_EXHAUSTED"
                )
            )
            if terminal_article_exhausted:
                message = "article cycle has durable terminal attempt exhaustion; stale worker recovery is forbidden"
                already_terminal = bool(
                    state.get("status") == "blocked"
                    and article_state.get("status") == "exhausted"
                    and last_error.get("stage") == "article"
                    and last_error.get("code") == "ARTICLE_ATTEMPTS_EXHAUSTED"
                )
                article_state["status"] = "exhausted"
                state["article"] = article_state
                if not already_terminal:
                    block(state, "article", "ARTICLE_ATTEMPTS_EXHAUSTED", message)
                return Action("blocked", message)

            if not self.article_slot_open():
'''


def run(*args: str, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout, end="")
    if expect_success and proc.returncode != 0:
        raise SystemExit(proc.returncode)
    return proc


def main() -> int:
    tests = TEST_PATH.read_text(encoding="utf-8")
    if TEST_NAME not in tests:
        if TEST_MARKER not in tests:
            raise SystemExit("regression insertion marker missing")
        TEST_PATH.write_text(tests.replace(TEST_MARKER, TEST_BLOCK + TEST_MARKER, 1), encoding="utf-8")

    red = run(
        sys.executable,
        "-m",
        "unittest",
        f"tests.test_kesher_content_controller.ControllerTests.{TEST_NAME}",
        "-v",
        expect_success=False,
    )
    if red.returncode == 0:
        raise SystemExit("regression unexpectedly passed before fix")
    print("RED_CONFIRMED: stale Jules result resurrects terminal cycle before fix")

    core = CORE_PATH.read_text(encoding="utf-8")
    if "durable terminal attempt exhaustion" not in core:
        if CORE_OLD not in core:
            raise SystemExit("controller insertion marker missing")
        CORE_PATH.write_text(core.replace(CORE_OLD, CORE_NEW, 1), encoding="utf-8")

    run(
        sys.executable,
        "-m",
        "unittest",
        f"tests.test_kesher_content_controller.ControllerTests.{TEST_NAME}",
        "tests.test_kesher_content_controller.ControllerTests.test_preserved_jules_timeout_immediately_redispatches_same_slot_recovery",
        "-v",
    )
    run(sys.executable, "-m", "unittest", "tests.test_kesher_content_controller", "-v")
    print("GREEN_CONFIRMED: terminal tombstone blocks stale recovery and legitimate recovery still works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
