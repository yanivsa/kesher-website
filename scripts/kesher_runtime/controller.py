"""Single deterministic decision owner for article, media and recovery.

This module is pure apart from run_tick's CAS/write-before-dispatch boundary.
Observation adapters supply fresh independent product evidence, not worker flags.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass

from .identity import Identity, MediaIdentity, SlotIdentity, SourceIdentity, canonical_json, digest, identity_from_dict, require_sha
from .media_state import snapshots
from .policy import RULES, Rule, due_after, record_incident, seconds
from .state import StateConflict, StateInvalid, bind_source, plan_command, target_is_current, timestamp, validate_state, validate_transition

OBSERVATION_MAX_AGE = 300
VERIFICATION_MAX_AGE = 600


@dataclass(frozen=True, init=False)
class Observation:
    """Immutable read snapshot so caller mutation cannot change a decided plan."""
    _encoded: str

    def __init__(self, value: dict):
        object.__setattr__(self, '_encoded', canonical_json(value))

    @property
    def value(self) -> dict:
        return json.loads(self._encoded)


@dataclass(frozen=True)
class Decision:
    state: dict
    command_id: str | None
    reason: str


def _commands(state: dict, target: Identity) -> list[dict]:
    return sorted((row for row in state['commands'].values() if row['target'] == target.to_dict()),
                  key=lambda row: (row['created_at'], row['id']))


def _pending(state: dict, target: Identity) -> dict | None:
    rows = [row for row in _commands(state, target) if row['outcome'] == 'pending']
    if len(rows) > 1:
        raise StateInvalid('Multiple pending commands own the same exact target')
    return rows[0] if rows else None


def _verification(row: dict, target: Identity, *, now: str, main_sha: str) -> dict | None:
    status = row.get('status')
    if status not in {'verified', 'absent', 'pending', 'failed', 'unknown'}:
        raise StateInvalid('Unknown independent product observation')
    if status != 'verified':
        return None
    evidence = row.get('evidence') or {}
    version = 2 if isinstance(target, SourceIdentity) else 1
    if (evidence.get('identity') != target.to_dict() or evidence.get('verifier_version') != version
            or not isinstance(evidence.get('public_url'), str) or not evidence['public_url'].startswith('https://')
            or not 0 <= seconds(now, evidence.get('verified_at')) <= VERIFICATION_MAX_AGE):
        raise StateInvalid('Public receipt must be fresh and bind the complete source/kind identity')
    if isinstance(target, SourceIdentity) and evidence.get('deploy_sha') != main_sha:
        raise StateInvalid('Article verification does not bind the observed deployed source revision')
    return evidence


def _record_verification(row: dict, observation: dict, target: Identity, *, now: str, main_sha: str) -> bool:
    evidence = _verification(observation, target, now=now, main_sha=main_sha)
    row['status'] = observation['status']
    row['phase'] = 'PUBLICLY_VERIFIED' if evidence else None
    if evidence:
        # Rechecking identical reality refreshes validity, not semantic progress.
        semantic = {key: value for key, value in evidence.items() if key != 'verified_at'}
        key = 'public:' + digest(semantic)
        row.setdefault('receipts', {}).setdefault(key, semantic)
        row['verification'] = {'receipt': key, 'verified_at': evidence['verified_at']}
    else:
        row.pop('verification', None)
    return evidence is not None


def _settle_commands(state: dict, observation: dict, *, now: str) -> None:
    runs = observation['runs']
    for command in state['commands'].values():
        if command['outcome'] != 'pending':
            continue
        target = identity_from_dict(command['target'])
        owner = command['owner']
        if owner is None:
            if command['code_sha'] != observation['main_sha'] or not target_is_current(state, target):
                # CAS cancellation wins against a concurrent claim; the loser must reload.
                command['outcome'] = 'cancelled'
                command['failure'] = {'class': 'CODE_CHANGED' if target_is_current(state, target) else 'SOURCE_SUPERSEDED'}
            elif command['dispatch']['attempts'] and seconds(now, command['created_at']) >= 1800:
                command['dispatch']['blocked_reason'] = 'WORKER_ACCEPTANCE_STALLED'
                record_incident(state, target, command['operation'], 'WORKER_ACCEPTANCE_STALLED', now=now,
                                evidence={'command_id': command['id'], 'dispatch_attempts': len(command['dispatch']['attempts'])})
            continue
        exact = [run for run in runs if run.get('command_id') == command['id']
                 and run.get('run_id') == owner['run_id'] and run.get('code_sha') == command['code_sha']]
        if len(exact) > 1:
            raise StateInvalid('Conflicting exact worker observations')
        if not exact or exact[0].get('status') != 'completed':
            if seconds(now, command.get('last_meaningful_progress_at') or owner['claimed_at']) >= 7200:
                record_incident(state, target, command['operation'], 'WORKER_STALLED', now=now,
                                evidence={'command_id': command['id'], 'run_id': owner['run_id']})
            continue  # An in-flight or unknown worker retains ownership; never steal it.
        result = command['receipts'].get('execution_result', {}).get('evidence')
        if exact[0].get('conclusion') == 'success' and result:
            command['outcome'] = 'succeeded'
        else:
            command['outcome'] = 'failed'
            command['failure'] = {'class': 'WORKER_RECEIPT_MISSING' if exact[0].get('conclusion') == 'success' else 'WORKER_FAILED'}
        state['audit'].append({'at': now, 'event': 'terminal_worker_reconciled', 'command_id': command['id'],
                               'run_id': owner['run_id'], 'outcome': command['outcome']})


def _progress(state: dict, target: Identity, tracker: dict, *, now: str) -> None:
    history = snapshots(state, target) if isinstance(target, MediaIdentity) else []
    item = history[-1]['item'] if history else None
    effects = {name + ':' + effect['request_sha256']: effect['receipt'] for command in _commands(state, target)
               for name, effect in command['effects'].items() if effect['receipt'] is not None}
    article_heads = sorted({canonical_json(row['receipts']['article_progress']['evidence'])
                            for row in _commands(state, target) if 'article_progress' in row['receipts']})
    # Execution bookkeeping and repeated waiting receipts cannot reset stall time.
    fingerprint = digest({'item': item, 'external_receipts': effects, 'article_heads': article_heads})
    if tracker.get('progress_sha256') != fingerprint:
        tracker['progress_sha256'] = fingerprint
        tracker['last_meaningful_progress_at'] = now


def _eligible(state: dict, target: Identity, observation: dict, tracker: dict, *, now: str,
              default_operation: str, inputs: dict | None = None) -> tuple[Identity, str, dict] | None:
    if observation['status'] == 'verified':
        tracker.pop('unknown_since', None)
        return None
    if observation['status'] == 'unknown':
        tracker.setdefault('unknown_since', now)
        if seconds(now, tracker['unknown_since']) >= 43200:
            record_incident(state, target, default_operation, 'OBSERVATION_UNAVAILABLE', now=now)
        return None
    tracker.pop('unknown_since', None)
    if _pending(state, target):
        return None
    commands = _commands(state, target)
    _progress(state, target, tracker, now=now)
    if isinstance(target, (SlotIdentity, SourceIdentity)):
        # Article stages and successive exact PR heads do not share a retry
        # budget. A completed Jules poll must not delay trusted image attachment.
        commands = [row for row in commands if row['operation'] == default_operation
                    and row['inputs'] == (inputs or {})]
    if isinstance(target, SourceIdentity):
        current_input = digest({'operation': default_operation, 'inputs': inputs or {}})
        if tracker.get('deployment_input_sha256') != current_input:
            tracker['deployment_input_sha256'] = current_input
            tracker['last_meaningful_progress_at'] = now
    failure_class = observation.get('failure_class')
    last = commands[-1] if commands else None
    if not failure_class and last:
        result = last['receipts'].get('execution_result', {}).get('evidence') or {}
        if last['outcome'] == 'failed':
            failure_class = (last['failure'] or {}).get('class') or 'WORKER_FAILED'
        elif result.get('status') == 'waiting':
            failure_class = result.get('failure_class') or 'PROVIDER_PENDING'
        elif last['outcome'] == 'succeeded':
            failure_class = 'PUBLIC_PROCESSING_PENDING'
    if observation['status'] == 'pending' and not failure_class:
        failure_class = 'PROVIDER_PENDING'
    if failure_class:
        rule = RULES.get(failure_class, Rule(None, 0))
        operation = default_operation if rule.operation == 'reconcile' and not isinstance(target, MediaIdentity) else rule.operation
        archive_recovery = isinstance(target, MediaIdentity) and failure_class in {'OUTPUT_ARCHIVE_PENDING', 'OUTPUT_ARCHIVE_REBUILD'}
        attempts = sum(1 for row in commands if row['operation'] == operation and row['outcome'] != 'cancelled'
                       and (not archive_recovery or row['inputs'].get('recovery_class') == failure_class))
        if isinstance(target, SourceIdentity) and failure_class == 'DEPLOY_FAILED':
            from .article_deploy import deployment_intents
            attempts = sum(row['code_sha'] == inputs['deploy_sha'] for row in deployment_intents(state))
        elif isinstance(target, SourceIdentity) and failure_class == 'DEPLOY_ARCHIVE_REBUILD':
            from .deployment_artifact import effect_key
            attempts = len({effect['request_sha256'] for row in commands
                            if (effect := row['effects'].get(effect_key(inputs['deploy_sha'])))})
        if (rule.operation is None or attempts >= rule.attempts
                or seconds(now, tracker['last_meaningful_progress_at']) >= rule.deadline_seconds):
            record_incident(state, target, default_operation, failure_class, now=now,
                            external_blocker=observation.get('external_blocker'),
                            evidence={'attempts': attempts, 'last_command_id': last['id'] if last else None})
            return None
        if last and last['outcome'] != 'cancelled':
            last_time = last.get('last_meaningful_progress_at') or last['created_at']
            delay = rule.delays[min(max(0, attempts - 1), len(rule.delays) - 1)]
            tracker['next_action_at'] = due_after(last_time, delay)
            if seconds(now, tracker['next_action_at']) < 0:
                return None
    else:
        operation = default_operation
    tracker.pop('next_action_at', None)
    payload = dict(inputs or {})
    if isinstance(target, MediaIdentity):
        history = snapshots(state, target)
        payload['generation_attempt'] = str(history[-1]['item'].get('fresh_generation_attempt', 1) if history else 1)
        if failure_class in {'OUTPUT_ARCHIVE_PENDING', 'OUTPUT_ARCHIVE_REBUILD'}:
            payload['recovery_class'] = failure_class
    return target, operation, payload


def reconcile(state: dict, observed: Observation, *, now: str) -> Decision:
    validate_state(state)
    timestamp(now)
    data = observed.value
    if 'state_revision' in data and data['state_revision'] != state['revision']:
        raise StateConflict('Canonical state changed during observation; discard this plan')
    require_sha(data.get('main_sha'), 40)
    SlotIdentity(data.get('current_slot'))
    if not 0 <= seconds(now, data.get('observed_at')) <= OBSERVATION_MAX_AGE:
        raise StateInvalid('Controller observation is stale or from the future')
    if any(not isinstance(data.get(field), list) for field in ('publications', 'runs', 'article_prs')):
        raise StateInvalid('Incomplete controller observation')
    proposed = copy.deepcopy(state)
    candidates = {}
    blocked = set()
    for entry in data['publications']:
        source = identity_from_dict(entry['source'])
        if not isinstance(source, SourceIdentity) or entry.get('main_sha') != data['main_sha'] or source.slot > data['current_slot']:
            raise StateInvalid('Publication must come from observed authoritative main and an eligible slot')
        candidates.setdefault(source.slot, []).append(entry)
    for slot, entries in candidates.items():
        if len(entries) != 1:
            record_incident(proposed, SlotIdentity(slot), 'article', 'SOURCE_AMBIGUOUS', now=now,
                            evidence={'source_keys': sorted(identity_from_dict(row['source']).key for row in entries)})
            blocked.add(slot)
            if slot in proposed['slots']:
                proposed['slots'][slot].update(blocked='SOURCE_AMBIGUOUS', complete=False)
            continue
        source = identity_from_dict(entries[0]['source'])
        previous = proposed['slots'].get(slot, {}).get('source_key')
        # Replacement is explicit and preserves every old media identity/receipt.
        proposed = bind_source(proposed, source, now=now, previous_source_key=previous)
        proposed['slots'][slot].pop('blocked', None)
        proposed['slots'][slot]['observed_at'] = data['observed_at']
    from .article_merge_observer import reconcile_merge_effects
    reconcile_merge_effects(proposed, data.get('merge_effects', []), main_sha=data['main_sha'], now=now)
    _settle_commands(proposed, data, now=now)
    eligible = []
    for slot in sorted(candidates, reverse=True):
        if slot in blocked:
            continue
        entry = candidates[slot][0]
        source = identity_from_dict(entry['source'])
        source_row = proposed['sources'][source.key]
        article_verified = _record_verification(source_row['article'], entry['article'], source, now=now, main_sha=data['main_sha'])
        verified = [article_verified]
        if not article_verified:
            action = _eligible(proposed, source, entry['article'], source_row.setdefault('recovery', {}),
                               now=now, default_operation='deploy_article', inputs={'deploy_sha': data['main_sha']})
            if action:
                eligible.append(action)
        for kind in ('overview', 'short'):
            target = MediaIdentity(source, kind)
            row = proposed['items'][target.key]
            result = entry['media'][kind]
            technical = result.get('technical_evidence')
            if technical is not None:
                if technical.get('schema_version') != 1 or technical.get('identity') != target.to_dict():
                    raise StateInvalid('Independent technical receipt belongs to another target')
                for field in ('output_sha256', 'verifier_sha256', 'raw_sha256', 'final_sha256', 'audio_sha256'):
                    require_sha(technical.get(field))
                if type(technical.get('final_size_bytes')) is not int or technical['final_size_bytes'] <= 0:
                    raise StateInvalid('Independent technical receipt has invalid file size')
                row['receipts'].setdefault('technical:' + digest(technical), technical)
            verified.append(_record_verification(row, result, target, now=now, main_sha=data['main_sha']))
            if article_verified:
                action = _eligible(proposed, target, result, row.setdefault('recovery', {}), now=now, default_operation='publish')
                if action:
                    eligible.append(action)
        slot_row = proposed['slots'][slot]
        slot_row['complete'] = all(verified)
        if slot_row['complete']:
            for incident in proposed['incidents'].values():
                if incident['target'].get('slot') == slot and incident['target'].get('content_sha256') == source.content_sha256:
                    incident['status'] = 'resolved'
                    incident.setdefault('resolved_at', now)
    # Pre-merge article work belongs to the slot. The immutable source is only
    # adopted from main, after normalization/image/CI/merge finish.
    prs = {}
    for pr in data['article_prs']:
        slot = SlotIdentity(pr['slot']).slot
        if slot > data['current_slot']:
            continue
        require_sha(pr['head_sha'], 40)
        if type(pr.get('number')) is not int or pr['number'] < 1:
            raise StateInvalid('Article PR must have exact repository number/head')
        prs.setdefault(slot, []).append(pr)
    missing_slots = data.get('missing_slots', [])
    for slot in missing_slots:
        SlotIdentity(slot)
        if slot > data['current_slot']:
            raise StateInvalid('Missing historical source has a future slot')
    for slot in sorted({data['current_slot'], *prs.keys(), *missing_slots}):
        if slot in candidates or slot in blocked:
            continue
        target = SlotIdentity(slot)
        matches = prs.get(slot, [])
        if len(matches) > 1:
            record_incident(proposed, target, 'article', 'DUPLICATE_PR', now=now,
                            evidence={'pull_requests': sorted(row['number'] for row in matches)})
            proposed['slots'].setdefault(slot, {}).update(blocked='DUPLICATE_PR', complete=False)
            continue
        row = proposed['slots'].setdefault(slot, {})
        row['observed_at'] = data['observed_at']
        row.pop('blocked', None)
        if row.get('source_key'):
            # An adopted article disappearing from main is an incident, never
            # permission to create a replacement under another identity.
            record_incident(proposed, target, 'article', 'SOURCE_MISSING', now=now)
            row['complete'] = False
            continue
        if matches:
            pr = matches[0]
            row['article_pr'] = {'number': pr['number'], 'head_sha': pr['head_sha']}
            semantic = digest({**row['article_pr'], 'status': pr['status'], 'body_sha256': pr.get('body_sha256'),
                               'validation_base_sha': data['main_sha'] if pr['status'].startswith('ci_') else None})
            if row.get('article_progress_sha256') != semantic:
                row['article_progress_sha256'] = semantic
                row['article_last_progress_at'] = now
            operation = {'normalize_required': 'normalize_article', 'image_required': 'attach_image', 'ci_required': 'validate_article',
                         'ready_to_merge': 'merge_article'}.get(pr['status'])
            if operation or pr['status'] == 'ci_failed':
                settled = any(command['outcome'] == 'succeeded'
                              and command['operation'] in {'create_article', 'settle_article'}
                              and (receipt := command['receipts'].get('article_pr_settled', {}).get('evidence'))
                              and receipt.get('number') == pr['number'] and receipt.get('head_sha') == pr['head_sha']
                              for command in _commands(proposed, target))
                if not settled:
                    operation = 'settle_article'
            if operation:
                inputs = {'pr_number': str(pr['number']), 'pr_head_sha': pr['head_sha']}
                if operation in {'validate_article', 'merge_article'}:
                    inputs.update(pr_body_sha256=pr.get('body_sha256', digest('')), validation_base_sha=data['main_sha'])
                action = _eligible(proposed, target, {'status': 'absent'}, row.setdefault('recovery', {}),
                                   now=now, default_operation=operation,
                                   inputs=inputs)
                if action:
                    eligible.append(action)
            elif pr['status'] == 'ci_failed':
                record_incident(proposed, target, 'article', 'CI_FAILED', now=now, evidence=row['article_pr'])
            elif seconds(now, row['article_last_progress_at']) >= 43200:
                record_incident(proposed, target, 'article', 'ARTICLE_PR_STALLED', now=now, evidence=row['article_pr'])
            continue
        if slot == data['current_slot'] and data.get('article_creation_allowed') is False:
            continue
        action = _eligible(proposed, target, {'status': 'absent'}, row.setdefault('recovery', {}),
                           now=now, default_operation='create_article')
        if action:
            eligible.append(action)
    current = [action for action in eligible if action[0].slot == data['current_slot']]
    backlog = sorted((action for action in eligible if action[0].slot != data['current_slot']), key=lambda action: action[0].slot)
    scheduler = proposed.setdefault('scheduler', {})
    lane = 'backlog' if backlog and (not current or scheduler.get('last_lane') == 'current') else 'current'
    choices = backlog if lane == 'backlog' else current
    command_id = None
    if choices:
        target, operation, inputs = choices[0]
        ordinal = 1 + max((row['ordinal'] for row in _commands(proposed, target) if row['operation'] == operation), default=0)
        proposed, command_id = plan_command(proposed, target, operation, ordinal, inputs, code_sha=data['main_sha'], now=now)
        scheduler = proposed.setdefault('scheduler', {})
        scheduler['last_lane'] = lane
    else:
        # An already persisted unclaimed intent can be delivered by the outbox;
        # another scheduler cannot create another one for the same target.
        pending = [row for row in proposed['commands'].values() if row['outcome'] == 'pending' and row['owner'] is None
                   and not row['dispatch'].get('blocked_reason')
                   and target_is_current(proposed, identity_from_dict(row['target']))]
        if pending:
            command_id = min(pending, key=lambda row: (row['created_at'], row['id']))['id']
    validate_transition(state, proposed)
    return Decision(proposed, command_id, 'exact_command' if command_id else 'waiting_or_complete')


def run_tick(store, observed: Observation, *, now: str, dispatch) -> Decision:
    loaded = store.load()
    decision = reconcile(loaded.state, observed, now=now)
    store.save(loaded, decision.state)
    if decision.command_id:
        dispatch(decision.command_id)
    return decision
