from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.kesher_master_supervisor import (
    ActionLifecycle,
    EvidenceSnapshot,
    IncidentIdentity,
    RecoveryCommand,
    command_precondition_status,
    semantic_evidence_hash,
    transition_action,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "config" / "kesher-production-contract.json"


class MasterSupervisorFoundationTests(unittest.TestCase):
    def test_incident_identity_is_stable_across_symptom_changes_and_cycle_rollover(self) -> None:
        first = IncidentIdentity(
            pipeline_id="v5",
            slug="returning-to-israel-after-relocation-relationship",
            content_sha256="abc123",
            stage="long_video",
        )
        second = IncidentIdentity(
            pipeline_id="v5",
            slug="returning-to-israel-after-relocation-relationship",
            content_sha256="abc123",
            stage="long_video",
        )
        self.assertEqual(first.key, second.key)
        self.assertEqual(first.key, "v5|returning-to-israel-after-relocation-relationship|abc123|long_video")

    def test_semantic_evidence_hash_ignores_observation_time_but_tracks_real_state(self) -> None:
        base = EvidenceSnapshot(
            incident=IncidentIdentity("v5", "slug-a", "hash-a", "long_video"),
            failure_signature="OVERVIEW_SIGNATURE_FULLSCREEN_MISSING",
            item_id="video-1",
            task_id="task-1",
            artifact_id="artifact-1",
            workflow_run_id="100",
            observed_at="2026-09-16T00:00:00+00:00",
        )
        later = EvidenceSnapshot(
            incident=base.incident,
            failure_signature=base.failure_signature,
            item_id=base.item_id,
            task_id=base.task_id,
            artifact_id=base.artifact_id,
            workflow_run_id=base.workflow_run_id,
            observed_at="2026-09-16T00:10:00+00:00",
        )
        changed = EvidenceSnapshot(
            incident=base.incident,
            failure_signature="YOUTUBE_UPLOAD_MISSING",
            item_id=base.item_id,
            task_id=base.task_id,
            artifact_id=base.artifact_id,
            workflow_run_id=base.workflow_run_id,
            observed_at=base.observed_at,
        )
        self.assertEqual(semantic_evidence_hash(base), semantic_evidence_hash(later))
        self.assertNotEqual(semantic_evidence_hash(base), semantic_evidence_hash(changed))

    def test_recovery_command_id_is_deterministic_for_exact_intent(self) -> None:
        incident = IncidentIdentity("v5", "slug-a", "hash-a", "long_video")
        evidence = EvidenceSnapshot(
            incident=incident,
            failure_signature="OVERVIEW_SIGNATURE_FULLSCREEN_MISSING",
            item_id="video-1",
            observed_at="2026-09-16T00:00:00+00:00",
        )
        first = RecoveryCommand.build(
            incident=incident,
            action="rebuild_exact_overview",
            evidence_hash=semantic_evidence_hash(evidence),
            item_id="video-1",
        )
        second = RecoveryCommand.build(
            incident=incident,
            action="rebuild_exact_overview",
            evidence_hash=semantic_evidence_hash(evidence),
            item_id="video-1",
        )
        self.assertEqual(first.command_id, second.command_id)
        self.assertTrue(first.command_id.startswith("ksr-"))

    def test_stale_or_duplicate_command_is_noop_before_dispatch(self) -> None:
        incident = IncidentIdentity("v5", "slug-a", "hash-a", "long_video")
        command = RecoveryCommand.build(
            incident=incident,
            action="rebuild_exact_overview",
            evidence_hash="evidence-1",
            item_id="video-1",
        )
        self.assertEqual(
            command_precondition_status(
                command,
                current_slug="slug-b",
                current_content_sha256="hash-b",
                completed_command_ids=set(),
                active_command_ids=set(),
            ),
            "stale_recovery_command_noop",
        )
        self.assertEqual(
            command_precondition_status(
                command,
                current_slug="slug-a",
                current_content_sha256="hash-a",
                completed_command_ids={command.command_id},
                active_command_ids=set(),
            ),
            "already_completed_noop",
        )
        self.assertEqual(
            command_precondition_status(
                command,
                current_slug="slug-a",
                current_content_sha256="hash-a",
                completed_command_ids=set(),
                active_command_ids={command.command_id},
            ),
            "already_active_noop",
        )

    def test_action_lifecycle_rejects_skipping_verification(self) -> None:
        self.assertEqual(
            transition_action(ActionLifecycle.PLANNED, ActionLifecycle.ISSUED),
            ActionLifecycle.ISSUED,
        )
        self.assertEqual(
            transition_action(ActionLifecycle.ISSUED, ActionLifecycle.ACKNOWLEDGED),
            ActionLifecycle.ACKNOWLEDGED,
        )
        self.assertEqual(
            transition_action(ActionLifecycle.ACKNOWLEDGED, ActionLifecycle.RUNNING),
            ActionLifecycle.RUNNING,
        )
        self.assertEqual(
            transition_action(ActionLifecycle.RUNNING, ActionLifecycle.VERIFIED),
            ActionLifecycle.VERIFIED,
        )
        with self.assertRaises(ValueError):
            transition_action(ActionLifecycle.PLANNED, ActionLifecycle.VERIFIED)

    def test_production_contract_assigns_single_writer_and_master_escalation_ownership(self) -> None:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        supervisor = contract["supervisor"]
        self.assertEqual(supervisor["production_state_writer"], "kesher-content-controller-v5")
        self.assertEqual(supervisor["escalation_owner"], "kesher-master-supervisor")
        self.assertEqual(supervisor["state_ref"], "automation-supervisor-state")
        self.assertTrue(supervisor["recovery_commands"]["idempotent"])
        self.assertTrue(supervisor["recovery_commands"]["stale_commands_noop"])
        self.assertEqual(
            supervisor["action_lifecycle"],
            ["planned", "issued", "acknowledged", "running", "verified", "failed", "timed_out"],
        )
        self.assertTrue(contract["invariants"]["master_is_only_escalation_owner_when_live"])
        self.assertTrue(contract["invariants"]["supervisor_never_writes_production_state"])


if __name__ == "__main__":
    unittest.main()
