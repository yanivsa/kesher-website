"""One command-bound workflow outbox, with bounded safe redelivery.

HTTP acknowledgement is not worker acceptance. Only the worker's CAS claim is.
Redelivery uses the same command ID and never authorizes another external effect.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from .github import GitHubError, GitHubStateStore
from .identity import MediaIdentity, SlotIdentity, identity_from_dict
from .state import StateConflict, StateInvalid, target_is_current, timestamp

MAX_DISPATCH_ATTEMPTS = 3
DISPATCH_GRACE_SECONDS = 600
ACCEPTANCE_TIMEOUT_SECONDS = 1800
ACTIVE_RUN_STATUSES = {'queued', 'in_progress', 'waiting', 'requested', 'pending'}


@dataclass(frozen=True)
class ObservedRuns:
    workflow: str
    rows: tuple[dict, ...]
    observed_at: str


@dataclass(frozen=True)
class DispatchResult:
    status: str
    reason: str


def workflow_for(command: dict) -> str:
    target = identity_from_dict(command['target'])
    operation = command['operation']
    if isinstance(target, MediaIdentity) and operation in {'publish', 'reconcile', 'rebuild', 'repair_metadata'}:
        return 'kesher-short-v4.yml' if target.kind == 'short' else 'kesher-daily-video.yml'
    if isinstance(target, SlotIdentity) and operation == 'create_article':
        return 'kesher-article-generation.yml'
    routes = {'normalize_article': 'normalize-article-pr.yml', 'attach_image': 'kesher-article-image.yml',
              'deploy_article': 'deploy.yml'}
    if command['target']['type'] == 'source' and operation in routes:
        return routes[operation]
    raise StateInvalid('No authorized worker route for this target/operation')


def exact_runs(observed: ObservedRuns, command: dict) -> list[dict]:
    workflow = workflow_for(command)
    if observed.workflow != workflow:
        raise StateInvalid('Observed workflow differs from command route')
    return [row for row in observed.rows
            if row.get('display_title') == 'kesher-command:' + command['id']
            and str(row.get('path') or '').split('@')[0] == '.github/workflows/' + workflow
            and row.get('head_branch') == 'main' and row.get('event') == 'workflow_dispatch']


def _seconds(after: str, before: str) -> float:
    timestamp(after)
    timestamp(before)
    return (datetime.fromisoformat(after.replace('Z', '+00:00')) - datetime.fromisoformat(before.replace('Z', '+00:00'))).total_seconds()


def _record_receipt(store: GitHubStateStore, command_id: str, attempt: int, receipt: dict) -> None:
    for retry in range(3):
        loaded = store.load()
        state = loaded.state
        attempts = state['commands'][command_id]['dispatch']['attempts']
        if attempt >= len(attempts):
            raise StateInvalid('Dispatch receipt has no durable attempt')
        if attempts[attempt]['receipt'] is not None:
            if attempts[attempt]['receipt'] != receipt:
                raise StateInvalid('Conflicting dispatch receipt')
            return
        attempts[attempt]['receipt'] = receipt
        try:
            store.save(loaded, state)
            return
        except StateConflict:
            if retry == 2:
                raise


def deliver_command(store: GitHubStateStore, command_id: str, observed: ObservedRuns,
                    dispatch: Callable[[str, dict], None], *, now: str, trusted_main_sha: str) -> DispatchResult:
    if not 0 <= _seconds(now, observed.observed_at) <= 60:
        raise StateInvalid('Workflow observation is stale or from the future')
    loaded = store.load()
    state = loaded.state
    command = state['commands'].get(command_id)
    if command is None:
        raise StateInvalid('Cannot dispatch a command without persisted intent')
    if command['outcome'] != 'pending':
        return DispatchResult('terminal', 'Command has a terminal worker result; reconcile the product separately')
    if command['owner'] is not None:
        return DispatchResult('claimed', 'Exact worker claim already exists')
    if command['code_sha'] != trusted_main_sha:
        return DispatchResult('code_changed', 'Replan under current trusted code without changing source identity')
    if not target_is_current(state, identity_from_dict(command['target'])):
        return DispatchResult('superseded', 'Source changed before worker acceptance')
    runs = exact_runs(observed, command)
    if any(row.get('status') in ACTIVE_RUN_STATUSES for row in runs):
        if _seconds(now, command['created_at']) >= ACCEPTANCE_TIMEOUT_SECONDS:
            return DispatchResult('repair_required', 'WORKER_ACCEPTANCE_STALLED: reconcile/cancel exact unclaimed run before retry')
        return DispatchResult('waiting', 'Exact command workflow exists; await its claim or terminal result')
    if any(row.get('status') != 'completed' for row in runs):
        return DispatchResult('repair_required', 'WORKER_STATE_UNKNOWN: no new dispatch until exact run state is understood')
    if any(row.get('status') == 'completed' and row.get('conclusion') == 'success' for row in runs):
        return DispatchResult('repair_required', 'WORKER_RECEIPT_MISSING: successful workflow never claimed command')
    attempts = command['dispatch']['attempts']
    if attempts and _seconds(now, attempts[-1]['requested_at']) < DISPATCH_GRACE_SECONDS:
        return DispatchResult('waiting', 'Reconcile uncertain dispatch before bounded redelivery')
    if max(len(attempts), len(runs)) >= MAX_DISPATCH_ATTEMPTS:
        return DispatchResult('repair_required', 'DISPATCH_ATTEMPTS_EXHAUSTED: repair the worker/route, preserve intent')
    workflow = workflow_for(command)
    inputs = {'command_id': command_id}
    index = len(attempts)
    proposed = copy.deepcopy(state)
    proposed['commands'][command_id]['dispatch']['attempts'].append({
        'requested_at': timestamp(now), 'workflow': workflow, 'inputs': inputs, 'receipt': None,
    })
    proposed['audit'].append({'at': now, 'event': 'dispatch_intent', 'command_id': command_id, 'attempt': index + 1})
    # Do not retry this stale plan after a CAS conflict. No HTTP mutation may
    # happen unless the exact intent write succeeded.
    store.save(loaded, proposed)
    try:
        dispatch(workflow, inputs)
    except GitHubError as exc:
        status = 'uncertain' if exc.uncertain else 'rejected'
        _record_receipt(store, command_id, index, {'status': status, 'http_status': exc.status})
        return DispatchResult(status, 'Reconcile exact command before any retry')
    _record_receipt(store, command_id, index, {'status': 'acknowledged', 'http_status': 204})
    return DispatchResult('dispatched', 'Dispatch acknowledged; worker acceptance and product completion remain separate')
