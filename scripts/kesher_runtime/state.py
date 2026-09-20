"""Pure canonical state and exact command transitions; persistence is always CAS."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime

from .identity import Identity, MediaIdentity, SlotIdentity, SourceIdentity, digest, identity_from_dict, require_sha

SCHEMA_VERSION = 6
PHASES = ('REQUESTED', 'ACCEPTED', 'STARTED', 'MEANINGFUL_PROGRESS', 'OUTPUT_CREATED',
          'TECHNICALLY_VALIDATED', 'UPLOAD_STARTED', 'UPLOADED', 'PROCESSED', 'PUBLISHED', 'PUBLICLY_VERIFIED')
COMMAND_OUTCOMES = {'pending', 'succeeded', 'failed', 'cancelled'}
IMMUTABLE_COMMAND_FIELDS = ('id', 'target', 'operation', 'ordinal', 'inputs', 'code_sha', 'created_at')
RESERVED_INPUTS = {'command_id', 'target_slug', 'target_content_sha256', 'target_kind', 'publication_slot', 'code_sha', 'identity'}


class StateInvalid(ValueError):
    pass


class StateConflict(RuntimeError):
    """Discard this plan and observe again; never rebind its stale payload."""


class CommandConflict(StateInvalid):
    pass


class ClaimRejected(StateInvalid):
    pass


def timestamp(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.utcoffset() is None:
            raise ValueError('timezone missing')
    except (ValueError, AttributeError, TypeError) as exc:
        raise StateInvalid('Expected timestamp with timezone') from exc
    return value


def new_state() -> dict:
    return {'schema_version': SCHEMA_VERSION, 'revision': 0, 'slots': {}, 'sources': {},
            'items': {}, 'commands': {}, 'incidents': {}, 'quarantine': [], 'audit': [], 'migration': {}}


def command_key(target: Identity, operation: str, ordinal: int) -> str:
    return 'command:' + digest({'target': target.to_dict(), 'operation': operation, 'ordinal': ordinal})


def target_is_current(state: dict, target: Identity) -> bool:
    active = state['slots'].get(target.slot, {}).get('source_key')
    if isinstance(target, SlotIdentity):
        return active is None
    source = target.source if isinstance(target, MediaIdentity) else target
    return active == source.key and source.key in state['sources']


def validate_state(state: dict) -> None:
    """Reject legacy/ambiguous state; only the explicit migration can import it."""
    if not isinstance(state, dict) or state.get('schema_version') != SCHEMA_VERSION:
        raise StateInvalid('STATE_SCHEMA_MIGRATION_REQUIRED')
    if type(state.get('revision')) is not int or state['revision'] < 0:
        raise StateInvalid('Invalid state revision')
    for name in ('slots', 'sources', 'items', 'commands', 'incidents', 'migration'):
        if not isinstance(state.get(name), dict):
            raise StateInvalid(f'Invalid state field {name}')
    for name in ('audit', 'quarantine'):
        if not isinstance(state.get(name), list):
            raise StateInvalid(f'Invalid state field {name}')
    try:
        for key, row in state['sources'].items():
            source = identity_from_dict(row['identity'])
            if not isinstance(source, SourceIdentity) or source.key != key:
                raise StateInvalid('Source key does not match immutable identity')
        for slot, row in state['slots'].items():
            SlotIdentity(slot)
            key = row.get('source_key')
            if key is not None and (key not in state['sources'] or state['sources'][key]['identity']['slot'] != slot):
                raise StateInvalid('Slot references a missing or different source')
        for key, row in state['items'].items():
            target = identity_from_dict(row['identity'])
            if not isinstance(target, MediaIdentity) or target.key != key or target.source.key not in state['sources']:
                raise StateInvalid('Media key/source does not match immutable identity')
        media_sequences = {}
        for key, row in state['commands'].items():
            target = identity_from_dict(row['target'])
            _validate_command_arguments(row['operation'], row['ordinal'], row['inputs'], row['code_sha'])
            if key != row['id'] or key != command_key(target, row['operation'], row['ordinal']):
                raise StateInvalid('Command key does not match immutable identity')
            timestamp(row['created_at'])
            if row['phase'] not in PHASES or row['outcome'] not in COMMAND_OUTCOMES:
                raise StateInvalid('Unknown command phase/outcome')
            owner = row['owner']
            if row['phase'] == 'REQUESTED' and owner is not None:
                raise StateInvalid('Unaccepted command cannot have an owner')
            if row['phase'] != 'REQUESTED':
                if not isinstance(owner, dict) or not isinstance(owner.get('run_id'), str) or not owner['run_id']:
                    raise StateInvalid('Accepted command requires its exact worker')
                timestamp(owner['claimed_at'])
            if not isinstance(row['receipts'], dict) or not isinstance(row['effects'], dict):
                raise StateInvalid('Command receipts/effects must be objects')
            if not isinstance(row['dispatch']['attempts'], list):
                raise StateInvalid('Dispatch attempts must be a list')
            for attempt in row['dispatch']['attempts']:
                timestamp(attempt['requested_at'])
                if not isinstance(attempt['workflow'], str) or attempt['inputs'] != {'command_id': key}:
                    raise StateInvalid('Dispatch attempt lost its exact command identity')
                if attempt['receipt'] is not None and not isinstance(attempt['receipt'], dict):
                    raise StateInvalid('Dispatch receipt must be an object')
            for name, receipt in row['receipts'].items():
                if receipt['target'] != target.to_dict() or receipt['phase'] not in PHASES:
                    raise StateInvalid('Checkpoint belongs to another target or unknown phase')
                timestamp(receipt['recorded_at'])
                if not isinstance(receipt['evidence'], dict) or not receipt['evidence']:
                    raise StateInvalid('Checkpoint lacks evidence')
                if name.startswith('media_state_'):
                    evidence = receipt['evidence']
                    sequence = evidence.get('sequence')
                    if (not isinstance(target, MediaIdentity) or type(sequence) is not int or sequence < 1
                            or name != 'media_state_' + digest(evidence)[:40]):
                        raise StateInvalid('Invalid canonical media snapshot sequence or digest')
                    sequences = media_sequences.setdefault(target.key, {})
                    if sequence in sequences and sequences[sequence] != evidence:
                        raise StateInvalid('Media recovery sequence cannot fork under concurrent workers')
                    sequences[sequence] = evidence
            for effect in row['effects'].values():
                timestamp(effect['created_at'])
                if not isinstance(effect['request'], dict) or effect['request_sha256'] != digest(effect['request']):
                    raise StateInvalid('External request digest mismatch')
                if effect['receipt'] is not None and not isinstance(effect['receipt'], dict):
                    raise StateInvalid('External receipt must be an object')
        for sequences in media_sequences.values():
            if len(sequences) != max(sequences):
                raise StateInvalid('Media recovery sequence has missing checkpoints')
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        if isinstance(exc, StateInvalid):
            raise
        raise StateInvalid('Malformed canonical state') from exc


def validate_transition(previous: dict, proposed: dict) -> None:
    validate_state(previous)
    validate_state(proposed)
    if proposed['revision'] != previous['revision']:
        raise StateInvalid('Only the CAS store increments revision')
    for key, row in previous['sources'].items():
        if key not in proposed['sources'] or proposed['sources'][key]['identity'] != row['identity']:
            raise StateInvalid('Cannot remove or rewrite immutable source')
    for key, row in previous['items'].items():
        if key not in proposed['items'] or proposed['items'][key]['identity'] != row['identity']:
            raise StateInvalid('Cannot remove or rewrite immutable media identity')
        _append_only(row['receipts'], proposed['items'][key]['receipts'], 'media receipts')
    for key, old in previous['commands'].items():
        new = proposed['commands'].get(key)
        if new is None or any(new[field] != old[field] for field in IMMUTABLE_COMMAND_FIELDS):
            raise StateInvalid('Cannot remove or rewrite command intent')
        if old['owner'] is not None and old['owner'] != new['owner']:
            raise StateInvalid('Cannot change an accepted command owner')
        if PHASES.index(new['phase']) < PHASES.index(old['phase']):
            raise StateInvalid('Cannot roll back lifecycle evidence')
        if old['outcome'] != 'pending' and new['outcome'] != old['outcome']:
            raise StateInvalid('Cannot reopen a terminal command')
        _append_only(old['receipts'], new['receipts'], 'command receipts')
        old_attempts = old['dispatch']['attempts']
        new_attempts = new['dispatch']['attempts']
        if len(new_attempts) < len(old_attempts):
            raise StateInvalid('Cannot erase dispatch history')
        for old_attempt, new_attempt in zip(old_attempts, new_attempts):
            if any(old_attempt[field] != new_attempt[field] for field in ('requested_at', 'workflow', 'inputs')):
                raise StateInvalid('Cannot rewrite dispatch intent')
            if old_attempt['receipt'] is not None and old_attempt['receipt'] != new_attempt['receipt']:
                raise StateInvalid('Cannot rewrite dispatch acknowledgement')
        for name, effect in old['effects'].items():
            updated = new['effects'].get(name)
            if updated is None or any(updated.get(field) != effect[field] for field in ('request', 'request_sha256', 'created_at', 'reconciles_commands')):
                raise StateInvalid('Cannot erase/rewrite external request intent')
            if effect.get('receipt') is not None and updated.get('receipt') != effect['receipt']:
                raise StateInvalid('Cannot erase/rewrite external request receipt')
    if proposed['audit'][:len(previous['audit'])] != previous['audit']:
        raise StateInvalid('Cannot erase/rewrite canonical audit history')


def _append_only(previous: dict, proposed: dict, label: str) -> None:
    if any(key not in proposed or proposed[key] != value for key, value in previous.items()):
        raise StateInvalid(f'Cannot erase/rewrite {label}')


def bind_source(state: dict, source: SourceIdentity, *, now: str, previous_source_key: str | None = None) -> dict:
    validate_state(state)
    timestamp(now)
    active = state['slots'].get(source.slot, {}).get('source_key')
    if active == source.key:
        return copy.deepcopy(state)
    if active != previous_source_key:
        raise StateInvalid('Source replacement requires the exact previously adopted source')
    proposed = copy.deepcopy(state)
    proposed['sources'].setdefault(source.key, {'identity': source.to_dict(), 'adopted_at': now, 'article': {}})
    slot = proposed['slots'].setdefault(source.slot, {})
    slot['source_key'] = source.key
    for kind in ('overview', 'short'):
        identity = MediaIdentity(source, kind)
        proposed['items'].setdefault(identity.key, {'identity': identity.to_dict(), 'phase': None, 'receipts': {}})
    proposed['audit'].append({'at': now, 'event': 'source_bound', 'source_key': source.key, 'previous_source_key': active})
    return proposed


def _validate_command_arguments(operation: str, ordinal: int, inputs: dict, code_sha: str) -> None:
    if not isinstance(operation, str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}', operation):
        raise StateInvalid('Invalid command operation')
    if type(ordinal) is not int or ordinal < 1:
        raise StateInvalid('Command ordinal must be a positive integer')
    if not isinstance(inputs, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in inputs.items()):
        raise StateInvalid('Workflow inputs must be string pairs')
    if RESERVED_INPUTS.intersection(inputs):
        raise StateInvalid('Workflow inputs cannot override canonical command identity')
    require_sha(code_sha, 40)


def plan_command(state: dict, target: Identity, operation: str, ordinal: int, inputs: dict,
                 *, code_sha: str, now: str) -> tuple[dict, str]:
    validate_state(state)
    _validate_command_arguments(operation, ordinal, inputs, code_sha)
    timestamp(now)
    if not target_is_current(state, target):
        raise CommandConflict('Source is superseded/unbound or article slot already adopted')
    key = command_key(target, operation, ordinal)
    existing = state['commands'].get(key)
    if existing is not None:
        if existing['inputs'] != inputs or existing['code_sha'] != code_sha:
            raise CommandConflict('Same command cannot change its payload or code')
        return copy.deepcopy(state), key
    for row in state['commands'].values():
        if row['target'] == target.to_dict() and row['outcome'] == 'pending':
            raise CommandConflict('An exact command is still pending; reconcile it before another attempt')
    proposed = copy.deepcopy(state)
    proposed['commands'][key] = {
        'id': key, 'target': target.to_dict(), 'operation': operation, 'ordinal': ordinal,
        'inputs': copy.deepcopy(inputs), 'code_sha': code_sha, 'created_at': now,
        'phase': 'REQUESTED', 'outcome': 'pending', 'owner': None,
        'dispatch': {'attempts': []}, 'receipts': {}, 'effects': {}, 'failure': None,
    }
    proposed['audit'].append({'at': now, 'event': 'command_requested', 'command_id': key})
    return proposed, key


@dataclass(frozen=True)
class Claim:
    execute: bool
    reason: str


def claim_command(state: dict, command_id: str, worker_run_id: str, expected_target: Identity,
                  *, code_sha: str, now: str) -> tuple[dict, Claim]:
    validate_state(state)
    timestamp(now)
    command = state['commands'].get(command_id)
    if command is None:
        raise ClaimRejected('Unknown command; workers cannot invent intent')
    if command['target'] != expected_target.to_dict() or command['code_sha'] != code_sha:
        raise ClaimRejected('Command source/kind/code revision mismatch')
    if not target_is_current(state, expected_target):
        raise ClaimRejected('Superseded source or article slot already adopted')
    if not isinstance(worker_run_id, str) or not worker_run_id:
        raise ClaimRejected('Worker must have an exact workflow run identity')
    if command['owner'] is not None or command['outcome'] != 'pending':
        return copy.deepcopy(state), Claim(False, 'Command already claimed or terminal')
    proposed = copy.deepcopy(state)
    proposed['commands'][command_id]['owner'] = {'run_id': worker_run_id, 'claimed_at': now}
    proposed['commands'][command_id]['phase'] = 'ACCEPTED'
    proposed['audit'].append({'at': now, 'event': 'command_accepted', 'command_id': command_id, 'worker_run_id': worker_run_id})
    return proposed, Claim(True, 'Exact command accepted')
