#!/usr/bin/env python3
"""Safety primitives for the Kesher Master Supervisor.

This module is intentionally side-effect free. It defines durable incident
identity, semantic evidence hashing, idempotent recovery command identity and
an explicit action lifecycle. Live GitHub/Jules/V5 orchestration is layered on
top only after these primitives are proven in CI and shadow mode.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


@dataclass(frozen=True)
class IncidentIdentity:
    pipeline_id: str
    slug: str
    content_sha256: str
    stage: str

    @property
    def key(self) -> str:
        return "|".join(
            (
                str(self.pipeline_id).strip(),
                str(self.slug).strip(),
                str(self.content_sha256).strip(),
                str(self.stage).strip(),
            )
        )


@dataclass(frozen=True)
class EvidenceSnapshot:
    incident: IncidentIdentity
    failure_signature: str = ""
    item_id: str = ""
    task_id: str = ""
    artifact_id: str = ""
    workflow_run_id: str = ""
    observed_at: str = ""

    def semantic_payload(self) -> dict[str, str]:
        """Return only evidence that represents durable state/progress.

        Observation timestamps and workflow run identifiers are deliberately
        excluded. A heartbeat or rerun of the same exact failure is not durable
        progress and must not create a second recovery intent.
        """
        return {
            "incident": self.incident.key,
            "failure_signature": str(self.failure_signature).strip(),
            "item_id": str(self.item_id).strip(),
            "task_id": str(self.task_id).strip(),
            "artifact_id": str(self.artifact_id).strip(),
        }


def _stable_hash(payload: dict[str, str]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_evidence_hash(snapshot: EvidenceSnapshot) -> str:
    return _stable_hash(snapshot.semantic_payload())


class ActionLifecycle(str, Enum):
    PLANNED = "planned"
    ISSUED = "issued"
    ACKNOWLEDGED = "acknowledged"
    RUNNING = "running"
    VERIFIED = "verified"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


_ALLOWED_TRANSITIONS: dict[ActionLifecycle, frozenset[ActionLifecycle]] = {
    ActionLifecycle.PLANNED: frozenset({ActionLifecycle.ISSUED, ActionLifecycle.FAILED}),
    ActionLifecycle.ISSUED: frozenset({
        ActionLifecycle.ACKNOWLEDGED,
        ActionLifecycle.FAILED,
        ActionLifecycle.TIMED_OUT,
    }),
    ActionLifecycle.ACKNOWLEDGED: frozenset({
        ActionLifecycle.RUNNING,
        ActionLifecycle.VERIFIED,
        ActionLifecycle.FAILED,
        ActionLifecycle.TIMED_OUT,
    }),
    ActionLifecycle.RUNNING: frozenset({
        ActionLifecycle.VERIFIED,
        ActionLifecycle.FAILED,
        ActionLifecycle.TIMED_OUT,
    }),
    ActionLifecycle.VERIFIED: frozenset(),
    ActionLifecycle.FAILED: frozenset(),
    ActionLifecycle.TIMED_OUT: frozenset(),
}


def transition_action(current: ActionLifecycle, target: ActionLifecycle) -> ActionLifecycle:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid action lifecycle transition: {current.value} -> {target.value}")
    return target


@dataclass(frozen=True)
class RecoveryCommand:
    command_id: str
    incident: IncidentIdentity
    action: str
    evidence_hash: str
    item_id: str = ""
    task_id: str = ""
    artifact_id: str = ""

    @classmethod
    def build(
        cls,
        *,
        incident: IncidentIdentity,
        action: str,
        evidence_hash: str,
        item_id: str = "",
        task_id: str = "",
        artifact_id: str = "",
    ) -> "RecoveryCommand":
        payload = {
            "incident": incident.key,
            "action": str(action).strip(),
            "evidence_hash": str(evidence_hash).strip(),
            "item_id": str(item_id).strip(),
            "task_id": str(task_id).strip(),
            "artifact_id": str(artifact_id).strip(),
        }
        digest = _stable_hash(payload)
        return cls(
            command_id=f"ksr-{digest[:24]}",
            incident=incident,
            action=payload["action"],
            evidence_hash=payload["evidence_hash"],
            item_id=payload["item_id"],
            task_id=payload["task_id"],
            artifact_id=payload["artifact_id"],
        )


def command_precondition_status(
    command: RecoveryCommand,
    *,
    current_slug: str,
    current_content_sha256: str,
    completed_command_ids: Iterable[str],
    active_command_ids: Iterable[str],
) -> str:
    """Fail closed before a recovery command can produce an external side effect."""
    if (
        str(current_slug).strip() != command.incident.slug
        or str(current_content_sha256).strip() != command.incident.content_sha256
    ):
        return "stale_recovery_command_noop"

    completed = {str(value).strip() for value in completed_command_ids}
    if command.command_id in completed:
        return "already_completed_noop"

    active = {str(value).strip() for value in active_command_ids}
    if command.command_id in active:
        return "already_active_noop"

    return "ready"
