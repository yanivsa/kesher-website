"""Master-owned KESHER intent planning over canonical Schema-6 state.

The Master chooses the operation. This module binds that choice to fresh repository
observations, derives all worker inputs, persists one immutable canonical command,
and never accepts arbitrary worker payloads from the caller.
"""
from __future__ import annotations

import re

from .controller import Decision, Observation, reconcile_facts
from .identity import MediaIdentity, SlotIdentity, SourceIdentity, identity_from_dict, require_sha
from .media_state import snapshots
from .policy import RULES
from .state import StateConflict, StateInvalid, plan_command, validate_state, validate_transition

REQUEST_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
SLOT_OPERATIONS = {
    'normalize_article': 'normalize_required',
    'attach_image': 'image_required',
    'validate_article': 'ci_required',
    'merge_article': 'ready_to_merge',
}
MEDIA_OPERATIONS = {'publish', 'reconcile', 'rebuild', 'repair_metadata'}


def _request(value: dict):
    if not isinstance(value, dict) or set(value) != {
            'request_id', 'expected_main_sha', 'expected_state_revision', 'target', 'operation'}:
        raise StateInvalid('MASTER_INTENT_REQUEST_INVALID')
    request_id = value['request_id']
    if not isinstance(request_id, str) or not REQUEST_ID.fullmatch(request_id):
        raise StateInvalid('MASTER_INTENT_REQUEST_ID_INVALID')
    if type(value['expected_state_revision']) is not int or value['expected_state_revision'] < 0:
        raise StateInvalid('MASTER_INTENT_REVISION_INVALID')
    require_sha(value['expected_main_sha'], 40)
    target = identity_from_dict(value['target'])
    operation = value['operation']
    if not isinstance(operation, str):
        raise StateInvalid('MASTER_INTENT_OPERATION_INVALID')
    if isinstance(target, SlotIdentity) and operation not in SLOT_OPERATIONS:
        raise StateInvalid('MASTER_INTENT_OPERATION_NOT_ALLOWED')
    if isinstance(target, SourceIdentity) and operation != 'deploy_article':
        raise StateInvalid('MASTER_INTENT_OPERATION_NOT_ALLOWED')
    if isinstance(target, MediaIdentity) and operation not in MEDIA_OPERATIONS:
        raise StateInvalid('MASTER_INTENT_OPERATION_NOT_ALLOWED')
    return request_id, target, operation


def _article_inputs(data: dict, target: SlotIdentity, operation: str) -> dict:
    matches = [row for row in data['article_prs'] if row.get('slot') == target.slot]
    if len(matches) != 1:
        raise StateInvalid('MASTER_INTENT_ARTICLE_PR_AMBIGUOUS')
    pr = matches[0]
    if pr.get('status') != SLOT_OPERATIONS[operation]:
        raise StateInvalid('MASTER_INTENT_STAGE_MISMATCH')
    require_sha(pr.get('head_sha'), 40)
    if type(pr.get('number')) is not int or pr['number'] < 1:
        raise StateInvalid('MASTER_INTENT_ARTICLE_PR_INVALID')
    inputs = {'pr_number': str(pr['number']), 'pr_head_sha': pr['head_sha']}
    if operation in {'validate_article', 'merge_article'}:
        require_sha(pr.get('body_sha256'))
        inputs.update(pr_body_sha256=pr['body_sha256'], validation_base_sha=data['main_sha'])
    return inputs


def _publication(data: dict, source: SourceIdentity) -> dict:
    matches = [row for row in data['publications'] if row.get('source') == source.to_dict()]
    if len(matches) != 1:
        raise StateInvalid('MASTER_INTENT_SOURCE_OBSERVATION_AMBIGUOUS')
    return matches[0]


def _derive_inputs(state: dict, data: dict, target, operation: str) -> dict:
    if isinstance(target, SlotIdentity):
        return _article_inputs(data, target, operation)
    bound = state['slots'].get(target.slot, {}).get('source_key')
    source = target.source if isinstance(target, MediaIdentity) else target
    if bound != source.key or source.key not in state['sources']:
        raise StateInvalid('MASTER_INTENT_SOURCE_NOT_CURRENT')
    publication = _publication(data, source)
    if isinstance(target, SourceIdentity):
        if state['sources'][source.key]['article'].get('phase') == 'PUBLICLY_VERIFIED':
            raise StateInvalid('MASTER_INTENT_ARTICLE_ALREADY_VERIFIED')
        return {'deploy_sha': data['main_sha']}
    if state['sources'][source.key]['article'].get('phase') != 'PUBLICLY_VERIFIED':
        raise StateInvalid('MASTER_INTENT_ARTICLE_NOT_VERIFIED')
    result = publication['media'][target.kind]
    if result.get('status') == 'verified':
        raise StateInvalid('MASTER_INTENT_MEDIA_ALREADY_VERIFIED')
    history = snapshots(state, target)
    generation_attempt = str(history[-1]['item'].get('fresh_generation_attempt', 1) if history else 1)
    inputs = {'generation_attempt': generation_attempt}
    if operation != 'publish':
        failure = result.get('failure_class')
        rule = RULES.get(failure) if failure else None
        if rule is None or rule.operation != operation:
            raise StateInvalid('MASTER_INTENT_RECOVERY_STAGE_MISMATCH')
    return inputs


def plan_master_intent(state: dict, observed: Observation, request: dict, *, now: str) -> Decision:
    validate_state(state)
    request_id, target, operation = _request(request)
    data = observed.value
    if request['expected_state_revision'] != state['revision']:
        raise StateConflict('MASTER_INTENT_STALE_STATE')
    if request['expected_main_sha'] != data.get('main_sha'):
        raise StateConflict('MASTER_INTENT_STALE_MAIN')
    facts = reconcile_facts(state, observed, now=now)
    inputs = _derive_inputs(facts, data, target, operation)
    ordinal = 1 + max((row['ordinal'] for row in facts['commands'].values()
                       if row['target'] == target.to_dict() and row['operation'] == operation), default=0)
    proposed, command_id = plan_command(
        facts, target, operation, ordinal, inputs, code_sha=data['main_sha'], now=now)
    proposed['audit'].append({
        'at': now, 'event': 'master_intent_planned', 'request_id': request_id, 'command_id': command_id})
    validate_transition(state, proposed)
    return Decision(proposed, command_id, 'master_intent')
