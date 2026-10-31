"""Provider-neutral, fail-closed intent contract for a Master-owned KESHER runtime.

This module does not observe providers, choose the next action, mutate state, or
dispatch workers.  It validates an explicit decision made by the external Master
against the exact main SHA and canonical state revision that decision observed.
"""
from __future__ import annotations

from dataclasses import dataclass

from .identity import Identity, require_sha
from .state import StateInvalid


# Article creation/settlement remain legacy controller/Jules operations during
# migration.  The Master creates article PRs directly and may only request the
# deterministic post-authoring operations below.
MASTER_OPERATIONS = frozenset({
    'normalize_article',
    'attach_image',
    'validate_article',
    'merge_article',
    'deploy_article',
    'publish',
    'reconcile',
    'rebuild',
    'repair_metadata',
})


@dataclass(frozen=True)
class MasterIntent:
    request_id: str
    expected_main_sha: str
    expected_state_revision: int
    target: Identity
    operation: str


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
    if not hasattr(intent.target, 'to_dict') or not hasattr(intent.target, 'key'):
        raise StateInvalid('MASTER_INTENT_TARGET_INVALID')
    return intent
