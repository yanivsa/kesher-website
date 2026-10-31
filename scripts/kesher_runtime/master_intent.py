"""Provider-neutral, fail-closed intent contract for a Master-owned KESHER runtime.

The Master chooses an action. This module validates that explicit decision against
the exact main SHA and canonical state revision it observed, then creates only a
canonical command intent. Dispatch remains a separate outbox responsibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .identity import Identity, MediaIdentity, SlotIdentity, SourceIdentity, require_sha
from .state import StateInvalid, plan_command, validate_state


MASTER_OPERATIONS = frozenset({
    'normalize_article', 'attach_image', 'validate_article', 'merge_article',
    'deploy_article', 'publish', 'reconcile', 'rebuild', 'repair_metadata',
})


@dataclass(frozen=True)
class MasterIntent:
    request_id: str
    expected_main_sha: str
    expected_state_revision: int
    target: Identity
    operation: str
    inputs: dict[str, str] = field(default_factory=dict)


def validate_master_intent(intent: MasterIntent, *, main_sha: str, state_revision: int) -> MasterIntent:
    """Validate freshness and authority boundaries before any command is planned."""
    if not isinstance(intent, MasterIntent):
        raise StateInvalid('MASTER_INTENT_MALFORMED')
    if not isinstance(intent.request_id, str) or not intent.request_id.strip() or len(intent.request_id) > 200:
        raise StateInvalid('MASTER_INTENT_REQUEST_ID_INVALID')
    try:
        require_sha(intent.expected_main_sha, 40)
        require_sha(main_sha, 40)
    except (TypeError, ValueError) as exc:
        raise StateInvalid('MASTER_INTENT_MAIN_SHA_INVALID') from exc
    if intent.expected_main_sha != main_sha:
        raise StateInvalid('MASTER_INTENT_STALE_MAIN')
    if (type(intent.expected_state_revision) is not int or type(state_revision) is not int
            or intent.expected_state_revision < 0 or state_revision < 0):
        raise StateInvalid('MASTER_INTENT_STATE_REVISION_INVALID')
    if intent.expected_state_revision != state_revision:
        raise StateInvalid('MASTER_INTENT_STALE_STATE')
    if intent.operation not in MASTER_OPERATIONS:
        raise StateInvalid('MASTER_INTENT_OPERATION_FORBIDDEN')
    if not isinstance(intent.target, (SlotIdentity, SourceIdentity, MediaIdentity)):
        raise StateInvalid('MASTER_INTENT_TARGET_INVALID')
    if not isinstance(intent.inputs, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                  for k, v in intent.inputs.items()):
        raise StateInvalid('MASTER_INTENT_INPUTS_INVALID')
    return intent


def _route_allowed(target: Identity, operation: str) -> bool:
    if isinstance(target, MediaIdentity):
        return operation in {'publish', 'reconcile', 'rebuild', 'repair_metadata'}
    if isinstance(target, SlotIdentity):
        return operation in {'normalize_article', 'attach_image', 'validate_article', 'merge_article'}
    if isinstance(target, SourceIdentity):
        return operation == 'deploy_article'
    return False


def plan_master_command(state: dict, intent: MasterIntent, *, main_sha: str, now: str) -> tuple[dict, str]:
    """Persistable command plan only; never dispatch or perform provider effects."""
    validate_state(state)
    validate_master_intent(intent, main_sha=main_sha, state_revision=state['revision'])
    if not _route_allowed(intent.target, intent.operation):
        raise StateInvalid('MASTER_INTENT_ROUTE_FORBIDDEN')
    ordinals = [row['ordinal'] for row in state['commands'].values()
                if row['target'] == intent.target.to_dict() and row['operation'] == intent.operation]
    ordinal = 1 + max(ordinals, default=0)
    return plan_command(state, intent.target, intent.operation, ordinal, intent.inputs,
                        code_sha=main_sha, now=now)
