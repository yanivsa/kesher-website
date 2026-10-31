"""Provider-neutral, fail-closed intent contract for a Master-owned KESHER runtime.

The Master chooses only an operation and immutable target. Exact worker inputs
are derived from the fresh revision-bound repository observation and canonical
Schema-6 state. Dispatch remains a separate outbox responsibility.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .controller import Observation, reconcile_facts
from .identity import Identity, MediaIdentity, SlotIdentity, SourceIdentity, digest, require_sha
from .media_state import next_generation_attempt, snapshots
from .policy import RULES
from .state import StateInvalid, plan_command, target_is_current, validate_state, validate_transition


MASTER_OPERATIONS = frozenset({
    'normalize_article', 'attach_image', 'validate_article', 'merge_article',
    'deploy_article', 'publish', 'reconcile', 'rebuild', 'repair_metadata',
})
ARTICLE_STAGE = {
    'normalize_article': 'normalize_required',
    'attach_image': 'image_required',
    'validate_article': 'ci_required',
    'merge_article': 'ready_to_merge',
}
ARCHIVE_FAILURES = {'OUTPUT_ARCHIVE_PENDING', 'OUTPUT_ARCHIVE_REBUILD'}


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
    if not isinstance(intent.inputs, dict):
        raise StateInvalid('MASTER_INTENT_INPUTS_INVALID')
    if intent.inputs:
        # Worker binding data is capability-sensitive. The caller may choose an
        # operation, never a PR/provider/deploy/generation identity.
        raise StateInvalid('MASTER_INTENT_INPUTS_FORBIDDEN')
    return intent


def _route_allowed(target: Identity, operation: str) -> bool:
    if isinstance(target, MediaIdentity):
        return operation in {'publish', 'reconcile', 'rebuild', 'repair_metadata'}
    if isinstance(target, SlotIdentity):
        return operation in ARTICLE_STAGE
    if isinstance(target, SourceIdentity):
        return operation == 'deploy_article'
    return False


def _observation_data(observation: Observation, *, main_sha: str, state_revision: int) -> dict:
    if not isinstance(observation, Observation):
        raise StateInvalid('MASTER_INTENT_OBSERVATION_INVALID')
    data = observation.value
    if data.get('state_revision') != state_revision:
        raise StateInvalid('MASTER_INTENT_STALE_STATE')
    if data.get('main_sha') != main_sha:
        raise StateInvalid('MASTER_INTENT_STALE_MAIN')
    if any(not isinstance(data.get(name), list) for name in ('publications', 'article_prs', 'runs')):
        raise StateInvalid('MASTER_INTENT_OBSERVATION_INVALID')
    return data


def _article_inputs(data: dict, target: SlotIdentity, operation: str) -> dict[str, str]:
    matches = [row for row in data['article_prs'] if row.get('slot') == target.slot]
    if len(matches) > 1:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_AMBIGUOUS')
    if len(matches) != 1:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    pr = matches[0]
    if pr.get('status') != ARTICLE_STAGE[operation]:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    try:
        require_sha(pr.get('head_sha'), 40)
    except (TypeError, ValueError) as exc:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_INVALID') from exc
    if type(pr.get('number')) is not int or pr['number'] < 1:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_INVALID')
    inputs = {'pr_number': str(pr['number']), 'pr_head_sha': pr['head_sha']}
    if operation in {'validate_article', 'merge_article'}:
        try:
            require_sha(pr.get('body_sha256'))
        except (TypeError, ValueError) as exc:
            raise StateInvalid('MASTER_INTENT_OBSERVATION_INVALID') from exc
        inputs.update(pr_body_sha256=pr['body_sha256'], validation_base_sha=data['main_sha'])
    return inputs


def _publication(data: dict, source: SourceIdentity) -> dict:
    matches = [row for row in data['publications']
               if row.get('source') == source.to_dict() and row.get('main_sha') == data['main_sha']]
    if len(matches) > 1:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_AMBIGUOUS')
    if len(matches) != 1:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    return matches[0]


def _media_inputs(state: dict, data: dict, target: MediaIdentity, operation: str) -> dict[str, str]:
    publication = _publication(data, target.source)
    media = (publication.get('media') or {}).get(target.kind)
    if not isinstance(media, dict) or media.get('status') not in {'absent', 'pending', 'failed', 'unknown', 'verified'}:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_INVALID')
    if media['status'] == 'verified':
        raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    history = snapshots(state, target)
    attempt = history[-1]['item'].get('fresh_generation_attempt', 1) if history else 1
    if type(attempt) is not int or attempt not in {1, 2, 3}:
        raise StateInvalid('MASTER_INTENT_OBSERVATION_INVALID')
    inputs = {'generation_attempt': str(attempt)}
    failure = media.get('failure_class')
    if operation == 'publish':
        if failure == 'PROVIDER_MEDIA_REJECTED':
            next_attempt = next_generation_attempt(state, target)
            if next_attempt is None:
                raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
            inputs['generation_attempt'] = str(next_attempt)
            if not history:
                raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
            inputs['rejected_snapshot_sha256'] = digest(history[-1])
        elif failure and RULES.get(failure) and RULES[failure].operation not in {'reconcile', 'publish'}:
            raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    else:
        rule = RULES.get(failure) if failure else None
        if rule is None or rule.operation != operation:
            raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    if failure in ARCHIVE_FAILURES:
        inputs['recovery_class'] = failure
    return inputs


def _derive_inputs(state: dict, data: dict, target: Identity, operation: str) -> dict[str, str]:
    if isinstance(target, SlotIdentity):
        return _article_inputs(data, target, operation)
    if not target_is_current(state, target):
        raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    source = target.source if isinstance(target, MediaIdentity) else target
    publication = _publication(data, source)
    source_row = state['sources'].get(source.key)
    if not isinstance(source_row, dict):
        raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    if isinstance(target, SourceIdentity):
        if (publication.get('article') or {}).get('status') == 'verified':
            raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
        return {'deploy_sha': data['main_sha']}
    if source_row.get('article', {}).get('phase') != 'PUBLICLY_VERIFIED':
        raise StateInvalid('MASTER_INTENT_OBSERVATION_MISMATCH')
    return _media_inputs(state, data, target, operation)


def plan_master_command(state: dict, intent: MasterIntent, *, main_sha: str,
                        observation: Observation, now: str) -> tuple[dict, str]:
    """Plan one exact command from fresh facts; never dispatch or perform provider effects."""
    validate_state(state)
    validate_master_intent(intent, main_sha=main_sha, state_revision=state['revision'])
    if not _route_allowed(intent.target, intent.operation):
        raise StateInvalid('MASTER_INTENT_ROUTE_FORBIDDEN')
    data = _observation_data(observation, main_sha=main_sha, state_revision=state['revision'])
    facts = reconcile_facts(state, observation, now=now)
    inputs = _derive_inputs(facts, data, intent.target, intent.operation)
    ordinals = [row['ordinal'] for row in facts['commands'].values()
                if row['target'] == intent.target.to_dict() and row['operation'] == intent.operation]
    ordinal = 1 + max(ordinals, default=0)
    proposed, command_id = plan_command(facts, intent.target, intent.operation, ordinal, inputs,
                                        code_sha=main_sha, now=now)
    proposed['audit'].append({'at': now, 'event': 'master_intent_planned',
                              'request_id': intent.request_id, 'command_id': command_id})
    validate_transition(state, proposed)
    return proposed, command_id
