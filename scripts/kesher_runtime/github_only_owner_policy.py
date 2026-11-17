"""Pure, fail-closed GitHub-only owner-ledger decision policy.

This module is intentionally NOT wired to production. A future reviewed
controller must persist decisions with exact Git-ref CAS, reconcile external
task identities, and prove exclusive dispatch authority before side effects.
No local or in-memory decision is an ownership fence.
"""
from __future__ import annotations

import hashlib
import json
import re


class OwnerLedgerBlocked(ValueError):
    """No safe new external dispatch may occur."""


_SHA = re.compile(r"[0-9a-f]{40}")
_HASH = re.compile(r"[0-9a-f]{64}")
_ALLOWED = frozenset({"article", "notebooklm_long", "youtube_long",
                      "notebooklm_short", "youtube_short", "website"})


def command_identity(*, slot: str, source_sha256: str, operation: str, ordinal: int = 1) -> str:
    """Stable identity for one immutable source/operation/attempt."""
    if not isinstance(slot, str) or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", slot):
        raise OwnerLedgerBlocked("INVALID_SLOT")
    if not isinstance(source_sha256, str) or not _HASH.fullmatch(source_sha256):
        raise OwnerLedgerBlocked("INVALID_SOURCE_HASH")
    if operation not in _ALLOWED or type(ordinal) is not int or ordinal < 1:
        raise OwnerLedgerBlocked("INVALID_OPERATION")
    canonical = json.dumps([slot, source_sha256, operation, ordinal],
                           separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def plan_dispatch(*, ledger: dict, expected_epoch: str, reviewed_main_sha: str,
                  command_id: str, observed_provider_tasks: dict,
                  pending_github_runs: list) -> str:
    """Return NOOP or CLAIM_REQUIRED; never grant dispatch authority.

    Caller MUST first CAS a durable CLAIMED receipt on automation-state, then
    re-read ownership and reconcile the exact provider task before any API call.
    Unknown/pending provider tasks, incomplete inventories and competing runs
    are hard blockers, not opportunities to retry.
    """
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1:
        raise OwnerLedgerBlocked("LEDGER_NOT_MIGRATED")
    if not isinstance(expected_epoch, str) or not expected_epoch:
        raise OwnerLedgerBlocked("EPOCH_MISSING")
    if ledger.get("epoch") != expected_epoch or ledger.get("owner") != "github-only":
        raise OwnerLedgerBlocked("OWNER_EPOCH_MISMATCH")
    if not isinstance(reviewed_main_sha, str) or not _SHA.fullmatch(reviewed_main_sha):
        raise OwnerLedgerBlocked("INVALID_REVIEWED_SHA")
    if ledger.get("reviewed_main_sha") != reviewed_main_sha:
        raise OwnerLedgerBlocked("REVIEWED_MAIN_CHANGED")
    if ledger.get("activation") != "PROTECTED_VERIFIED":
        raise OwnerLedgerBlocked("PROTECTED_ACTIVATION_REQUIRED")
    if ledger.get("inventory_complete") is not True:
        raise OwnerLedgerBlocked("INCOMPLETE_INVENTORY")
    if not isinstance(command_id, str) or not _HASH.fullmatch(command_id):
        raise OwnerLedgerBlocked("INVALID_COMMAND_ID")
    if not isinstance(observed_provider_tasks, dict) or not isinstance(pending_github_runs, list):
        raise OwnerLedgerBlocked("UNKNOWN_TASK_INVENTORY")
    if pending_github_runs:
        raise OwnerLedgerBlocked("COMPETING_GITHUB_RUN")
    if any(v not in ("completed", "rejected", "cancelled") for v in observed_provider_tasks.values()):
        raise OwnerLedgerBlocked("UNRECONCILED_PROVIDER_TASK")
    commands = ledger.get("commands")
    if not isinstance(commands, dict):
        raise OwnerLedgerBlocked("MISSING_COMMAND_JOURNAL")
    previous = commands.get(command_id)
    if previous is not None:
        if previous.get("phase") in ("CLAIMED", "DISPATCH_UNKNOWN", "WAITING_PROVIDER",
                                      "OUTPUT_CREATED", "PUBLISHED", "DONE"):
            return "NOOP"
        raise OwnerLedgerBlocked("EXISTING_COMMAND_REQUIRES_RECONCILIATION")
    return "CLAIM_REQUIRED"
