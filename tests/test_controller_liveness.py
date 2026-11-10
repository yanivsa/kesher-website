#!/usr/bin/env python3
"""Deterministic unit test suite for Controller Liveness Recovery.

Covers all production-readiness invariants specified in P1: CONTROLLER_LIVENESS:
1. 5-minute cron events missing for an extended period triggers recovery wake-up
2. Recovery dispatch occurs exactly once (idempotent)
3. Delayed workflow visibility suppresses duplicate dispatch (grace period)
4. Lost dispatch response or crash/restart reconciles cleanly
5. Existing active/queued controller run suppresses recovery
6. Exhausted/terminal cycle remains terminal (cannot resurrect)
7. Schema-6 / cutover authority rejects legacy recovery
8. Repeated watchdog ticks remain idempotent
9. Recovery budget is strictly bounded (max 3 per cycle)
10. Recovery inputs are empty, preserving article/image/Long/Short generation budgets
11. Fail-closed on foreign repository or unreadable/invalid state
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.kesher_runtime.controller_liveness import (
    CANONICAL_CONTROLLER_WORKFLOW,
    DEFAULT_REPO,
    DISPATCH_VISIBILITY_GRACE,
    FRESHNESS_WINDOW,
    MAX_RECOVERIES_PER_CYCLE,
    ControllerLivenessWatchdog,
    GitHubLivenessTransport,
    LivenessDecision,
    _iso,
    evaluate_liveness,
)


class MockTransport(GitHubLivenessTransport):
    def __init__(self, runs=None, state=None, remote_ledger=None):
        super().__init__(token="mock-token", repo=DEFAULT_REPO)
        self.runs = runs or []
        self.state = state
        self.dispatches: list[dict] = []
        self.should_fail_dispatch = False
        self.remote_ledger = remote_ledger if remote_ledger is not None else {}
        self.remote_ledger_sha: str = "blob-sha-init"

    def get_recent_runs(self, workflow_name="kesher-content-controller.yml", limit=10):
        return copy.deepcopy(self.runs)

    def dispatch_workflow(self, workflow_path, ref="main", inputs=None):
        if self.should_fail_dispatch:
            raise RuntimeError("MOCK_NETWORK_OR_API_FAILURE")
        self.dispatches.append({"workflow": workflow_path, "ref": ref, "inputs": inputs or {}})
        return True

    def get_controller_state_from_git(self, ref="automation-state"):
        return copy.deepcopy(self.state)

    def get_liveness_ledger(self, ref="automation-state"):
        return copy.deepcopy(self.remote_ledger), self.remote_ledger_sha

    def put_liveness_ledger(self, ledger, sha=None, ref="automation-state"):
        self.remote_ledger.clear()
        self.remote_ledger.update(copy.deepcopy(ledger))
        self.remote_ledger_sha = "blob-sha-updated"
        return self.remote_ledger_sha


class ControllerLivenessTests(unittest.TestCase):
    def setUp(self):
        self.base_time = datetime(2026, 10, 14, 12, 0, 0, tzinfo=timezone.utc)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ledger_file = Path(self.temp_dir.name) / "controller-liveness.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def valid_active_state(self, updated_at=None):
        return {
            "schema_version": 5,
            "cycle": "2026-10-14",
            "status": "in_progress",
            "updated_at": updated_at or _iso(self.base_time),
            "article": {"status": "in_progress"},
            "long_video": {"status": "pending"},
            "short": {"status": "pending"},
        }

    # 1. 5-minute cron events missing for an extended period
    def test_cron_events_missing_for_extended_period_triggers_recovery(self):
        # Controller was last updated 30 minutes ago, no runs since then
        stale_time = self.base_time - timedelta(minutes=30)
        state = self.valid_active_state(updated_at=_iso(stale_time))
        recent_runs = [
            {
                "databaseId": 1001,
                "status": "completed",
                "conclusion": "success",
                "createdAt": _iso(stale_time),
                "updatedAt": _iso(stale_time + timedelta(minutes=2)),
            }
        ]
        decision = evaluate_liveness(state, recent_runs, {}, self.base_time)

        self.assertEqual(decision.status, "LIVENESS_RECOVERY_REQUIRED")
        self.assertEqual(decision.action, "dispatch")
        self.assertEqual(decision.target_workflow, CANONICAL_CONTROLLER_WORKFLOW)
        self.assertEqual(decision.target_ref, "main")
        self.assertEqual(decision.target_inputs, {})

    # 2. Recovery dispatch exactly once
    def test_recovery_dispatch_exactly_once(self):
        stale_time = self.base_time - timedelta(minutes=25)
        state = self.valid_active_state(updated_at=_iso(stale_time))
        transport = MockTransport(runs=[], state=state)
        watchdog = ControllerLivenessWatchdog(
            repo=DEFAULT_REPO,
            ledger_path=self.ledger_file,
            transport=transport,
        )

        # First tick: should dispatch recovery
        report1 = watchdog.reconcile(now=self.base_time)
        self.assertEqual(report1["status"], "LIVENESS_RECOVERY_REQUIRED")
        self.assertTrue(report1["dispatched"])
        self.assertEqual(len(transport.dispatches), 1)

        # Second tick immediately after (e.g. 10s later): should NOT dispatch again (visibility grace active)
        report2 = watchdog.reconcile(now=self.base_time + timedelta(seconds=10))
        self.assertEqual(report2["status"], "LIVENESS_WAIT_DISPATCH_VISIBILITY")
        self.assertFalse(report2["dispatched"])
        self.assertEqual(len(transport.dispatches), 1)

    # 3. Delayed workflow visibility
    def test_delayed_workflow_visibility(self):
        # Ledger has an in-flight dispatch from 2 minutes ago
        dispatch_time = self.base_time - timedelta(minutes=2)
        ledger = {
            "current_intent": {
                "intent_id": "liveness-2026-10-14-1",
                "cycle": "2026-10-14",
                "created_at": _iso(dispatch_time),
                "status": "dispatched",
                "target_workflow": CANONICAL_CONTROLLER_WORKFLOW,
                "target_ref": "main",
                "inputs": {},
            }
        }
        stale_state = self.valid_active_state(updated_at=_iso(self.base_time - timedelta(minutes=30)))
        # GitHub runs API has not yet indexed the new run
        recent_runs = []

        decision = evaluate_liveness(stale_state, recent_runs, ledger, self.base_time)
        self.assertEqual(decision.status, "LIVENESS_WAIT_DISPATCH_VISIBILITY")
        self.assertIsNone(decision.action)
        self.assertEqual(decision.intent_id, "liveness-2026-10-14-1")

    # 4. Lost dispatch response / restart reconciles cleanly
    def test_lost_dispatch_response_or_restart_reconciles_when_run_appears(self):
        dispatch_time = self.base_time - timedelta(minutes=3)
        self.ledger_file.write_text(
            json.dumps(
                {
                    "current_intent": {
                        "intent_id": "liveness-2026-10-14-lost",
                        "cycle": "2026-10-14",
                        "created_at": _iso(dispatch_time),
                        "status": "dispatching",  # crashed before marking dispatched!
                    }
                }
            )
        )
        # On restart, the new run HAS appeared in actions/runs
        new_run_time = dispatch_time + timedelta(seconds=20)
        recent_runs = [
            {
                "databaseId": 2002,
                "status": "in_progress",
                "createdAt": _iso(new_run_time),
            }
        ]
        stale_state = self.valid_active_state(updated_at=_iso(self.base_time - timedelta(minutes=30)))
        transport = MockTransport(runs=recent_runs, state=stale_state)
        watchdog = ControllerLivenessWatchdog(
            repo=DEFAULT_REPO,
            ledger_path=self.ledger_file,
            transport=transport,
        )

        report = watchdog.reconcile(now=self.base_time)
        self.assertEqual(report["status"], "LIVENESS_OK_ACTIVE_RUN_PRESENT")
        self.assertFalse(report["dispatched"])

        # Intent should be reconciled in ledger
        reloaded_ledger = watchdog.load_ledger()
        self.assertIsNone(reloaded_ledger.get("current_intent"))
        self.assertEqual(len(reloaded_ledger.get("history", [])), 1)
        self.assertEqual(reloaded_ledger["history"][0]["status"], "reconciled")

    def test_completed_recovery_run_reconciles_and_marks_fresh(self):
        dispatch_time = self.base_time - timedelta(minutes=10)
        self.ledger_file.write_text(
            json.dumps(
                {
                    "current_intent": {
                        "intent_id": "liveness-2026-10-14-completed",
                        "cycle": "2026-10-14",
                        "created_at": _iso(dispatch_time),
                        "status": "dispatched",
                    }
                }
            )
        )
        completed_run_time = dispatch_time + timedelta(minutes=2)
        recent_runs = [
            {
                "databaseId": 2003,
                "status": "completed",
                "conclusion": "success",
                "createdAt": _iso(completed_run_time),
                "updatedAt": _iso(completed_run_time + timedelta(minutes=1)),
            }
        ]
        stale_state = self.valid_active_state(updated_at=_iso(self.base_time - timedelta(minutes=30)))
        transport = MockTransport(runs=recent_runs, state=stale_state)
        watchdog = ControllerLivenessWatchdog(
            repo=DEFAULT_REPO,
            ledger_path=self.ledger_file,
            transport=transport,
        )

        report = watchdog.reconcile(now=self.base_time)
        self.assertEqual(report["status"], "LIVENESS_OK_FRESH")
        self.assertFalse(report["dispatched"])

        reloaded_ledger = watchdog.load_ledger()
        self.assertIsNone(reloaded_ledger.get("current_intent"))
        self.assertEqual(len(reloaded_ledger.get("history", [])), 1)
        self.assertEqual(reloaded_ledger["history"][0]["status"], "reconciled")

    # 5. Existing active controller suppresses recovery
    def test_existing_active_controller_suppresses_recovery(self):
        stale_time = self.base_time - timedelta(minutes=45)
        state = self.valid_active_state(updated_at=_iso(stale_time))
        for status in ("queued", "in_progress", "waiting", "pending", "requested"):
            with self.subTest(status=status):
                recent_runs = [
                    {
                        "databaseId": 3003,
                        "status": status,
                        "createdAt": _iso(self.base_time - timedelta(minutes=2)),
                    }
                ]
                decision = evaluate_liveness(state, recent_runs, {}, self.base_time)
                self.assertEqual(decision.status, "LIVENESS_OK_ACTIVE_RUN_PRESENT")
                self.assertIsNone(decision.action)
                self.assertEqual(decision.active_run_id, 3003)

    # 6. Exhausted cycle remains terminal
    def test_exhausted_cycle_remains_terminal(self):
        stale_time = self.base_time - timedelta(hours=2)
        terminal_states = [
            {"cycle": "2026-10-14", "status": "blocked", "updated_at": _iso(stale_time), "schema_version": 5},
            {"cycle": "2026-10-14", "status": "completed", "updated_at": _iso(stale_time), "schema_version": 5},
            {"cycle": "2026-10-14", "status": "in_progress", "article": {"status": "exhausted"}, "updated_at": _iso(stale_time), "schema_version": 5},
            {"cycle": "2026-10-14", "status": "blocked", "article": {"status": "exhausted"}, "updated_at": _iso(stale_time), "schema_version": 5},
        ]
        for term_state in terminal_states:
            with self.subTest(term_state=term_state):
                decision = evaluate_liveness(term_state, [], {}, self.base_time)
                self.assertEqual(decision.status, "LIVENESS_OK_CYCLE_TERMINAL")
                self.assertIsNone(decision.action)

    # 7. Schema-6 / cutover authority rejects legacy recovery
    def test_schema6_cutover_authority_rejects_legacy_recovery(self):
        stale_time = self.base_time - timedelta(hours=1)
        cutover_states = [
            {"schema_version": 6, "cycle": "2026-10-14", "status": "in_progress", "updated_at": _iso(stale_time)},
            {"schema_version": 5, "cycle": "2026-10-14", "status": "in_progress", "handover": {"target": "v6"}, "updated_at": _iso(stale_time)},
            {"schema_version": 5, "cycle": "2026-10-14", "status": "in_progress", "github_exclusion": {}, "updated_at": _iso(stale_time)},
        ]
        for c_state in cutover_states:
            with self.subTest(c_state=c_state):
                decision = evaluate_liveness(c_state, [], {}, self.base_time)
                self.assertEqual(decision.status, "SCHEMA6_AUTHORITY_ACTIVE")
                self.assertIsNone(decision.action)

    # 8. Repeated watchdog ticks remain idempotent
    def test_repeated_watchdog_ticks_remain_idempotent(self):
        stale_time = self.base_time - timedelta(minutes=20)
        state = self.valid_active_state(updated_at=_iso(stale_time))
        transport = MockTransport(runs=[], state=state)
        watchdog = ControllerLivenessWatchdog(
            repo=DEFAULT_REPO,
            ledger_path=self.ledger_file,
            transport=transport,
        )

        # Tick 1: Dispatches recovery
        r1 = watchdog.reconcile(now=self.base_time)
        self.assertTrue(r1["dispatched"])
        self.assertEqual(len(transport.dispatches), 1)

        # Ticks 2, 3, 4 within 4 minutes: All wait for visibility
        for offset in (60, 120, 180):
            rx = watchdog.reconcile(now=self.base_time + timedelta(seconds=offset))
            self.assertEqual(rx["status"], "LIVENESS_WAIT_DISPATCH_VISIBILITY")
            self.assertFalse(rx["dispatched"])
            self.assertEqual(len(transport.dispatches), 1)

    # 9. Bounded recovery budget (max 3 per cycle)
    def test_liveness_recovery_budget_bounded(self):
        stale_time = self.base_time - timedelta(hours=2)
        state = self.valid_active_state(updated_at=_iso(stale_time))
        ledger = {
            "cycles": {
                "2026-10-14": {
                    "recovery_count": MAX_RECOVERIES_PER_CYCLE,
                    "last_recovery_at": _iso(self.base_time - timedelta(minutes=30)),
                }
            }
        }
        decision = evaluate_liveness(state, [], ledger, self.base_time)
        self.assertEqual(decision.status, "LIVENESS_RECOVERY_BUDGET_EXHAUSTED")
        self.assertIsNone(decision.action)

    # 10. Empty dispatch inputs preserve generation budget
    def test_liveness_recovery_passes_empty_inputs(self):
        stale_time = self.base_time - timedelta(minutes=25)
        state = self.valid_active_state(updated_at=_iso(stale_time))
        transport = MockTransport(runs=[], state=state)
        watchdog = ControllerLivenessWatchdog(
            repo=DEFAULT_REPO,
            ledger_path=self.ledger_file,
            transport=transport,
        )
        report = watchdog.reconcile(now=self.base_time)
        self.assertTrue(report["dispatched"])
        self.assertEqual(len(transport.dispatches), 1)
        dispatched_inputs = transport.dispatches[0]["inputs"]
        # Empty inputs guarantee no generation budget is consumed
        self.assertEqual(dispatched_inputs, {})

    # 11. Fail-closed on foreign repository or unreadable state
    def test_fail_closed_on_foreign_repo_or_invalid_state(self):
        state = self.valid_active_state()
        decision_foreign = evaluate_liveness(state, [], {}, self.base_time, current_repo="attacker/fake-repo")
        self.assertEqual(decision_foreign.status, "LIVENESS_REFUSED_FOREIGN_REPOSITORY")
        self.assertIsNone(decision_foreign.action)

        decision_none = evaluate_liveness(None, [], {}, self.base_time)
        self.assertEqual(decision_none.status, "LIVENESS_REFUSED_INVALID_STATE")
        self.assertIsNone(decision_none.action)

        decision_no_cycle = evaluate_liveness({"schema_version": 5}, [], {}, self.base_time)
        self.assertEqual(decision_no_cycle.status, "LIVENESS_REFUSED_INVALID_STATE")
        self.assertIsNone(decision_no_cycle.action)

    # 12. Remote ledger durability across VM crashes
    def test_remote_ledger_survives_vm_crash_and_prevents_duplicate_dispatch(self):
        """Instance A writes intent to remote ledger and dies; Instance B on a fresh VM
        (with empty filesystem) loads remote state, reconciles, and does NOT issue a duplicate POST/dispatch.
        """
        shared_remote_backend = {}
        stale_time = self.base_time - timedelta(minutes=25)
        state = self.valid_active_state(updated_at=_iso(stale_time))

        # VM A: starts, evaluates stale controller, writes intent remotely, and dispatches
        vm_a_dir = Path(self.temp_dir.name) / "vm_a"
        vm_a_dir.mkdir(parents=True, exist_ok=True)
        transport_a = MockTransport(runs=[], state=state, remote_ledger=shared_remote_backend)
        watchdog_a = ControllerLivenessWatchdog(
            repo=DEFAULT_REPO,
            ledger_path=vm_a_dir / "controller-liveness.json",
            transport=transport_a,
        )

        report_a = watchdog_a.reconcile(now=self.base_time)
        self.assertTrue(report_a["dispatched"])
        self.assertEqual(len(transport_a.dispatches), 1)
        self.assertIn("current_intent", shared_remote_backend)
        self.assertEqual(shared_remote_backend["current_intent"]["status"], "dispatched")

        # SIMULATE VM A CRASH: VM A disk is completely discarded!
        # VM B: Fresh runner VM starts up with empty disk!
        vm_b_dir = Path(self.temp_dir.name) / "vm_b"
        vm_b_dir.mkdir(parents=True, exist_ok=True)
        # Note: vm_b_dir / "controller-liveness.json" DOES NOT EXIST!
        self.assertFalse((vm_b_dir / "controller-liveness.json").exists())

        # Transport B accesses the same shared git repo (automation-state)
        # 2 minutes later: run has not appeared yet (delayed visibility)
        time_b = self.base_time + timedelta(minutes=2)
        transport_b = MockTransport(runs=[], state=state, remote_ledger=shared_remote_backend)
        # Dispatches list on transport_b is initially empty
        self.assertEqual(len(transport_b.dispatches), 0)

        watchdog_b = ControllerLivenessWatchdog(
            repo=DEFAULT_REPO,
            ledger_path=vm_b_dir / "controller-liveness.json",
            transport=transport_b,
        )

        # Watchdog B reconciles: loads remote ledger from automation-state,
        # detects active intent within visibility grace window, and suppresses dispatch!
        report_b = watchdog_b.reconcile(now=time_b)
        self.assertFalse(report_b["dispatched"])
        self.assertEqual(report_b["status"], "LIVENESS_WAIT_DISPATCH_VISIBILITY")
        # Critical verification: ZERO additional dispatches from VM B!
        self.assertEqual(len(transport_b.dispatches), 0)

    # 13. Pre-window wakes do not exhaust active pipeline recovery capacity
    def test_pre_window_wakes_do_not_exhaust_active_pipeline_recovery_capacity(self):
        # 05:00 Israel time (02:00 UTC) is before publication window (08:00 Israel time)
        pre_window_time = datetime(2026, 10, 14, 2, 0, 0, tzinfo=timezone.utc)
        # 09:00 Israel time (06:00 UTC) is during active publication window
        active_window_time = datetime(2026, 10, 14, 6, 0, 0, tzinfo=timezone.utc)

        state = self.valid_active_state(updated_at=_iso(pre_window_time - timedelta(hours=1)))
        ledger = {
            "cycles": {
                "2026-10-14": {
                    "pre_window_recovery_count": MAX_RECOVERIES_PER_CYCLE,
                    "active_window_recovery_count": 0,
                    "recovery_count": MAX_RECOVERIES_PER_CYCLE,
                    "last_recovery_at": _iso(pre_window_time - timedelta(minutes=20)),
                }
            }
        }

        # During pre-window, a 4th recovery is exhausted
        pre_decision = evaluate_liveness(state, [], ledger, pre_window_time)
        self.assertEqual(pre_decision.status, "LIVENESS_RECOVERY_BUDGET_EXHAUSTED")
        self.assertIn("pre-window", pre_decision.reason)

        # During active window, full recovery capacity remains (active_window_recovery_count is 0)
        active_decision = evaluate_liveness(state, [], ledger, active_window_time)
        self.assertEqual(active_decision.status, "LIVENESS_RECOVERY_REQUIRED")
        self.assertEqual(active_decision.action, "dispatch")


if __name__ == "__main__":
    unittest.main()
