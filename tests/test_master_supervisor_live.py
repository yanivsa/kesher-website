from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.kesher_master_supervisor_live import (
    SUPERVISOR_STATE_PATH,
    SUPERVISOR_STATE_REF,
    SupervisorCasConflict,
    SupervisorStateStore,
    build_incident_packet,
    direct_dispatch_spec,
    incident_fingerprint,
    mark_command_acknowledged,
    mark_command_failed,
    new_supervisor_state,
    prepare_escalation,
    record_resolution,
    should_hold_external_running,
)


ROOT = Path(__file__).resolve().parents[1]
MASTER_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-master-supervisor.yml"
LEGACY_WORKFLOW = ROOT / ".github" / "workflows" / "kesher-task-supervisor-controller.yml"
CONTRACT = ROOT / "config" / "kesher-production-contract.json"


def incident_report(*, signature: str = "OVERVIEW_SIGNATURE_FULLSCREEN_MISSING", action: str = "rebuild_exact_overview", stage: str = "long_video") -> dict:
    return {
        "mode": "live",
        "status": "incident_detected",
        "incident_id": f"v5|slug-a|hash-a|{stage}",
        "failure_signature": signature,
        "evidence_hash": "evidence-a",
        "proposed_action": action,
        "exact": {
            "slug": "slug-a",
            "content_sha256": "hash-a",
            "item_id": "video-1",
            "task_id": "task-1",
            "artifact_id": "artifact-1",
            "short_item_id": "short-1",
            "pr_number": 802,
        },
    }


class FakeStoreApi:
    def __init__(self) -> None:
        self.state = None
        self.sha = None
        self.conflict = False
        self.saved_expected_sha = None

    def load_state_blob(self, ref: str, path: str):
        return self.state, self.sha

    def save_state_blob(self, ref: str, path: str, state: dict, expected_sha: str | None):
        self.saved_expected_sha = expected_sha
        if self.conflict:
            raise SupervisorCasConflict("simulated conflict")
        self.state = json.loads(json.dumps(state))
        self.sha = "sha-next"
        return self.sha


class MasterSupervisorLiveTests(unittest.TestCase):
    def test_supervisor_state_is_separate_from_production_state(self) -> None:
        self.assertEqual(SUPERVISOR_STATE_REF, "automation-supervisor-state")
        self.assertEqual(SUPERVISOR_STATE_PATH, ".kesher-master-supervisor/state.json")
        self.assertNotEqual(SUPERVISOR_STATE_REF, "automation-state")

    def test_first_incident_is_s1_controller_and_persists_command_before_side_effect(self) -> None:
        state = new_supervisor_state()
        updated, decision = prepare_escalation(
            state,
            incident_report(),
            now="2026-09-16T00:00:00+00:00",
            prior_action_terminal=False,
        )
        self.assertEqual(decision["stage"], "S1")
        self.assertEqual(decision["executor"], "controller")
        self.assertTrue(decision["execute_now"])
        fp = incident_fingerprint(incident_report())
        self.assertEqual(updated["incidents"][fp]["strike"], 1)
        command = updated["commands"][decision["command_id"]]
        self.assertEqual(command["lifecycle"], "issued")
        self.assertEqual(command["proposed_action"], "rebuild_exact_overview")

    def test_crash_after_state_persist_never_blindly_reissues_same_command(self) -> None:
        state, first = prepare_escalation(
            new_supervisor_state(),
            incident_report(),
            now="2026-09-16T00:00:00+00:00",
            prior_action_terminal=False,
        )
        reloaded = json.loads(json.dumps(state))
        again, second = prepare_escalation(
            reloaded,
            incident_report(),
            now="2026-09-16T00:01:00+00:00",
            prior_action_terminal=False,
        )
        self.assertEqual(second["stage"], "WAIT")
        self.assertFalse(second["execute_now"])
        self.assertEqual(first["command_id"], again["incidents"][incident_fingerprint(incident_report())]["active_command_id"])

    def test_same_failure_after_terminal_s1_escalates_to_s2_jules_then_s3_direct(self) -> None:
        state, s1 = prepare_escalation(new_supervisor_state(), incident_report(), now="2026-09-16T00:00:00+00:00", prior_action_terminal=False)
        state = mark_command_failed(state, s1["command_id"], "controller completed but incident persisted", at="2026-09-16T00:10:00+00:00")
        state, s2 = prepare_escalation(state, incident_report(), now="2026-09-16T00:10:01+00:00", prior_action_terminal=True)
        self.assertEqual((s2["stage"], s2["executor"]), ("S2", "jules"))
        self.assertEqual(state["incidents"][incident_fingerprint(incident_report())]["strike"], 2)

        state = mark_command_failed(state, s2["command_id"], "Jules completed without convergence", at="2026-09-16T00:30:00+00:00")
        state, s3 = prepare_escalation(state, incident_report(), now="2026-09-16T00:30:01+00:00", prior_action_terminal=True)
        self.assertEqual((s3["stage"], s3["executor"]), ("S3", "direct"))
        self.assertEqual(state["incidents"][incident_fingerprint(incident_report())]["strike"], 3)

    def test_fourth_same_failure_fails_closed_to_human_blocker(self) -> None:
        state, s1 = prepare_escalation(new_supervisor_state(), incident_report(), now="2026-09-16T00:00:00+00:00", prior_action_terminal=False)
        state = mark_command_failed(state, s1["command_id"], "failed", at="2026-09-16T00:01:00+00:00")
        state, s2 = prepare_escalation(state, incident_report(), now="2026-09-16T00:01:01+00:00", prior_action_terminal=True)
        state = mark_command_failed(state, s2["command_id"], "failed", at="2026-09-16T00:02:00+00:00")
        state, s3 = prepare_escalation(state, incident_report(), now="2026-09-16T00:02:01+00:00", prior_action_terminal=True)
        state = mark_command_failed(state, s3["command_id"], "failed", at="2026-09-16T00:03:00+00:00")
        state, final = prepare_escalation(state, incident_report(), now="2026-09-16T00:03:01+00:00", prior_action_terminal=True)
        self.assertEqual(final["stage"], "HUMAN_BLOCKER")
        self.assertFalse(final["execute_now"])
        self.assertEqual(state["incidents"][incident_fingerprint(incident_report())]["status"], "human_blocker")

    def test_new_failure_signature_is_a_new_incident_not_strike_four(self) -> None:
        first = incident_report()
        state, s1 = prepare_escalation(new_supervisor_state(), first, now="2026-09-16T00:00:00+00:00", prior_action_terminal=False)
        state = mark_command_failed(state, s1["command_id"], "failed", at="2026-09-16T00:01:00+00:00")
        changed = incident_report(signature="YOUTUBE_UPLOAD_MISSING", action="retry_exact_upload")
        state, decision = prepare_escalation(state, changed, now="2026-09-16T00:02:00+00:00", prior_action_terminal=False)
        self.assertEqual(decision["stage"], "S1")
        self.assertEqual(state["incidents"][incident_fingerprint(changed)]["strike"], 1)

    def test_resolution_verifies_active_command_and_closes_incident(self) -> None:
        state, decision = prepare_escalation(new_supervisor_state(), incident_report(), now="2026-09-16T00:00:00+00:00", prior_action_terminal=False)
        state = mark_command_acknowledged(state, decision["command_id"], {"run_id": "123"}, at="2026-09-16T00:00:05+00:00")
        state = record_resolution(state, incident_report(), at="2026-09-16T00:05:00+00:00")
        fp = incident_fingerprint(incident_report())
        self.assertEqual(state["incidents"][fp]["status"], "resolved")
        self.assertEqual(state["commands"][decision["command_id"]]["lifecycle"], "verified")

    def test_external_provider_running_has_bounded_90_minute_exception(self) -> None:
        started = datetime(2026, 9, 16, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(should_hold_external_running(started.isoformat(), (started + timedelta(minutes=89)).isoformat()))
        self.assertFalse(should_hold_external_running(started.isoformat(), (started + timedelta(minutes=91)).isoformat()))

    def test_incident_packet_is_prepared_for_jules_instead_of_reasking_it_to_diagnose(self) -> None:
        packet = build_incident_packet(incident_report(), strike=2, command_id="ksr-test")
        self.assertEqual(packet["incident_id"], incident_report()["incident_id"])
        self.assertEqual(packet["failure_signature"], "OVERVIEW_SIGNATURE_FULLSCREEN_MISSING")
        self.assertEqual(packet["exact"]["item_id"], "video-1")
        self.assertIn("definition_of_done", packet)
        self.assertTrue(packet["constraints"]["reuse_existing_session_pr"])
        self.assertTrue(packet["constraints"]["no_duplicate_generation_upload"])

    def test_direct_dispatch_specs_are_exact_and_never_fresh_generation(self) -> None:
        report = incident_report()
        spec = direct_dispatch_spec(report)
        self.assertEqual(spec["workflow"], "kesher-daily-video.yml")
        self.assertEqual(spec["inputs"]["operation"], "rebuild")
        self.assertEqual(spec["inputs"]["rebuild_item_id"], "video-1")
        self.assertEqual(spec["inputs"]["target_slug"], "slug-a")

        upload = incident_report(signature="YOUTUBE_UPLOAD_MISSING", action="retry_exact_upload")
        self.assertEqual(direct_dispatch_spec(upload)["inputs"]["operation"], "upload")

        short = incident_report(signature="SHORT_MISSING", action="continue_exact_short", stage="short")
        short_spec = direct_dispatch_spec(short)
        self.assertEqual(short_spec["workflow"], "kesher-short-v4.yml")
        self.assertEqual(short_spec["inputs"]["operation"], "derive")
        self.assertEqual(short_spec["inputs"]["derive_long_item_id"], "video-1")

    def test_cas_store_uses_expected_blob_sha_and_propagates_conflict(self) -> None:
        api = FakeStoreApi()
        api.state = new_supervisor_state()
        api.sha = "sha-old"
        store = SupervisorStateStore(api)
        state, sha = store.load()
        self.assertEqual(sha, "sha-old")
        store.save(state, expected_sha=sha)
        self.assertEqual(api.saved_expected_sha, "sha-old")
        api.conflict = True
        with self.assertRaises(SupervisorCasConflict):
            store.save(state, expected_sha="sha-next")

    def test_workflow_switches_live_and_legacy_mutating_supervisor_is_disabled(self) -> None:
        master = MASTER_WORKFLOW.read_text(encoding="utf-8")
        legacy = LEGACY_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("name: Kesher Master Supervisor", master)
        self.assertNotIn("name: Kesher Master Supervisor Shadow", master)
        self.assertIn("contents: write", master)
        self.assertIn("actions: write", master)
        self.assertIn("pull-requests: write", master)
        self.assertIn("checks: read", master)
        self.assertIn("JULES_API_KEY", master)
        self.assertIn("--live", master)
        self.assertIn("group: kesher-master-supervisor", master)
        self.assertNotIn("schedule:", legacy)
        self.assertNotIn("JULES_API_KEY", legacy)

    def test_contract_declares_live_s1_s2_s3_and_single_escalation_owner(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        supervisor = contract["supervisor"]
        self.assertEqual(supervisor["mode"], "live_s1_s2_s3")
        self.assertEqual(supervisor["state_ref"], SUPERVISOR_STATE_REF)
        self.assertEqual(supervisor["state_path"], SUPERVISOR_STATE_PATH)
        self.assertEqual(supervisor["escalation"]["S1"], "controller")
        self.assertEqual(supervisor["escalation"]["S2"], "jules")
        self.assertEqual(supervisor["escalation"]["S3"], "direct")
        self.assertTrue(contract["invariants"]["legacy_task_supervisor_live_mutations_disabled"])


if __name__ == "__main__":
    unittest.main()
