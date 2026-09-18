"""Durable worker claim/checkpoint boundary; no external work before its intent.

A caller receiving execute=False must reconcile the exact existing request.
An absent response is never permission to insert another provider job or upload.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .github import GitHubError, GitHubStateStore
from .identity import Identity, canonical_json, digest
from .state import PHASES, Claim, ClaimRejected, StateConflict, StateInvalid, claim_command, target_is_current, timestamp

PRIVATE_KEYS = {'token', 'access_token', 'refresh_token', 'id_token', 'secret', 'password', 'authorization',
                'cookie', 'cookies', 'storage_state', 'session_uri', 'session_url', 'api_key', 'client_secret'}


def public_evidence(value) -> None:
    """Capabilities live in encrypted storage referenced by hash, never here."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or key.lower().replace('-', '_') in PRIVATE_KEYS:
                raise StateInvalid('Credential/capability fields are forbidden in canonical evidence')
            public_evidence(nested)
    elif isinstance(value, list):
        for nested in value:
            public_evidence(nested)
    elif value is not None and not isinstance(value, (str, bool, int, float)):
        raise StateInvalid('Evidence must be JSON data')
    canonical_json(value)


def receipt_name(name: str) -> None:
    if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name):
        raise StateInvalid('Invalid checkpoint/effect name')


@dataclass(frozen=True)
class EffectDecision:
    execute: bool
    receipt: dict | None


class WorkerContext:
    def __init__(self, store: GitHubStateStore, command_id: str, run_id: str, target: Identity,
                 *, code_sha: str, now: Callable[[], str] | None = None):
        self.store = store
        self.command_id = command_id
        self.run_id = run_id
        self.target = target
        self.code_sha = code_sha
        self.now = now or (lambda: datetime.now(timezone.utc).isoformat())
        self._accepted = False

    def claim(self) -> Claim:
        def transition(state):
            return claim_command(state, self.command_id, self.run_id, self.target, code_sha=self.code_sha, now=self.now())

        # A lost claim response aborts execution. Only a positive durable CAS
        # receipt grants this process permission to start its first effect.
        receipt = self._update(transition, confirm_uncertain=False)
        self._accepted = receipt.execute
        return receipt

    def attach(self) -> None:
        """Resume a later step in the same run/attempt; effects still deduplicate."""
        self._owned(self.store.load().state, require_attached=False)
        self._accepted = True

    def _owned(self, state: dict, *, require_current: bool = False, require_attached: bool = True,
               allow_terminal: bool = False) -> dict:
        if require_attached and not self._accepted:
            raise ClaimRejected('Worker has no confirmed durable claim')
        row = state['commands'].get(self.command_id)
        if (row is None or row['target'] != self.target.to_dict() or row['code_sha'] != self.code_sha
                or (row['owner'] or {}).get('run_id') != self.run_id):
            raise ClaimRejected('Worker receipt does not own this exact source/kind/command/code')
        if not allow_terminal and row['outcome'] != 'pending':
            raise ClaimRejected('Worker command is terminal')
        if require_current and not target_is_current(state, self.target):
            raise ClaimRejected('Source was superseded; preserve receipts but stop new effects')
        return row

    def _update(self, transition, *, confirm_uncertain: bool = True):
        for attempt in range(3):
            loaded = self.store.load()
            proposed, result = transition(loaded.state)
            try:
                self.store.save(loaded, proposed)
                return result
            except StateConflict:
                if attempt == 2:
                    raise
                # Re-run the pure, exact-target transition on a NEW snapshot.
                # Never attach a stale complete document to the fresh blob SHA.
            except GitHubError as exc:
                if not exc.uncertain or not confirm_uncertain:
                    raise
                observed = self.store.load()
                confirmed, confirmed_result = transition(observed.state)
                if canonical_json(confirmed) == canonical_json(observed.state):
                    return confirmed_result
                raise
        raise AssertionError('Unreachable CAS loop')

    def begin_effect(self, name: str, request: dict) -> EffectDecision:
        receipt_name(name)
        public_evidence(request)
        if not isinstance(request, dict) or not request:
            raise StateInvalid('External effect requires an exact nonempty request')

        def transition(state):
            command = self._owned(state, require_current=True)
            request_sha = digest(request)
            existing = command['effects'].get(name)
            if existing is not None:
                if existing['request_sha256'] != request_sha:
                    raise StateInvalid('External effect payload changed; reconcile original request')
                return state, EffectDecision(False, copy.deepcopy(existing['receipt']))
            # Recovery creates a new command, not a new product. Its effect
            # fence spans all commands for the exact immutable media identity.
            prior = [(key, row['effects'][name]) for key, row in state['commands'].items()
                     if row['target'] == self.target.to_dict() and name in row['effects']]
            groups = {}
            for key, effect in prior:
                groups.setdefault(effect['request_sha256'], []).append((key, effect))
            for other_sha, effects in groups.items():
                if other_sha != request_sha and not any(effect['receipt'] is not None for _, effect in effects):
                    raise StateInvalid('Prior external creation is uncertain; reconcile before changing request')
            matches = groups.get(request_sha, [])
            receipts = {canonical_json(effect['receipt']): effect['receipt']
                        for _, effect in matches if effect['receipt'] is not None}
            if len(receipts) > 1:
                raise StateInvalid('Conflicting receipts for one external request; quarantine duplicates')
            adopted = copy.deepcopy(next(iter(receipts.values()), None))
            proposed = copy.deepcopy(state)
            now = timestamp(self.now())
            proposed['commands'][self.command_id]['effects'][name] = {
                'request': copy.deepcopy(request), 'request_sha256': request_sha, 'created_at': now, 'receipt': adopted,
                'reconciles_commands': sorted(key for key, _ in matches),
            }
            event = 'external_intent_adopted' if matches else 'external_intent'
            proposed['audit'].append({'at': now, 'event': event, 'command_id': self.command_id, 'effect': name})
            return proposed, EffectDecision(not matches, adopted)

        # If intent persistence was accepted but its response was lost, return
        # no execution permission. Reconciliation can later find its receipt.
        return self._update(transition, confirm_uncertain=False)

    def complete_effect(self, name: str, receipt: dict) -> None:
        receipt_name(name)
        public_evidence(receipt)
        if not isinstance(receipt, dict) or not receipt:
            raise StateInvalid('An external receipt must contain evidence')

        def transition(state):
            command = self._owned(state)
            effect = command['effects'].get(name)
            if effect is None:
                raise StateInvalid('External receipt has no durable request intent')
            if effect['receipt'] is not None:
                if effect['receipt'] != receipt:
                    raise StateInvalid('Conflicting external receipt; quarantine and reconcile')
                return state, None
            proposed = copy.deepcopy(state)
            proposed['commands'][self.command_id]['effects'][name]['receipt'] = copy.deepcopy(receipt)
            self._progress(proposed, 'external_receipt', name)
            return proposed, None

        self._update(transition)

    def checkpoint(self, name: str, evidence: dict, *, phase: str) -> None:
        receipt_name(name)
        public_evidence(evidence)
        if phase not in PHASES[2:-1] or not isinstance(evidence, dict) or not evidence:
            raise StateInvalid('Worker checkpoint needs evidence and cannot assert independent public verification')

        def transition(state):
            command = self._owned(state)
            existing = command['receipts'].get(name)
            if existing is not None:
                if existing['evidence'] != evidence or existing['phase'] != phase:
                    raise StateInvalid('Checkpoint evidence is immutable')
                return state, None
            proposed = copy.deepcopy(state)
            row = proposed['commands'][self.command_id]
            row['receipts'][name] = {'target': self.target.to_dict(), 'phase': phase,
                                    'evidence': copy.deepcopy(evidence), 'recorded_at': timestamp(self.now())}
            row['phase'] = PHASES[max(PHASES.index(phase), PHASES.index(command['phase']))]
            self._progress(proposed, 'worker_checkpoint', name)
            return proposed, None

        self._update(transition)

    def _progress(self, state: dict, event: str, name: str) -> None:
        command = state['commands'][self.command_id]
        semantic = {'phase': command['phase'],
                    'receipts': {key: {'phase': row['phase'], 'evidence': row['evidence']} for key, row in command['receipts'].items()},
                    'effects': {key: row['receipt'] for key, row in command['effects'].items() if row['receipt'] is not None}}
        fingerprint = digest(semantic)
        if command.get('progress_sha256') != fingerprint:
            command['progress_sha256'] = fingerprint
            command['last_meaningful_progress_at'] = timestamp(self.now())
            state['audit'].append({'at': self.now(), 'event': event, 'command_id': self.command_id, 'name': name})

    def finish(self, *, failure: dict | None = None) -> None:
        if failure is not None:
            public_evidence(failure)
            if not isinstance(failure, dict) or not failure.get('class'):
                raise StateInvalid('Failure requires a classified reason')
        outcome = 'failed' if failure is not None else 'succeeded'

        def transition(state):
            command = self._owned(state, allow_terminal=True)
            if command['outcome'] != 'pending':
                if command['outcome'] != outcome or command['failure'] != failure:
                    raise StateInvalid('Cannot change terminal worker result')
                return state, None
            if failure is None and not command['receipts']:
                raise StateInvalid('Worker success requires execution evidence')
            proposed = copy.deepcopy(state)
            proposed['commands'][self.command_id]['outcome'] = outcome
            proposed['commands'][self.command_id]['failure'] = copy.deepcopy(failure)
            proposed['audit'].append({'at': self.now(), 'event': 'worker_finished', 'command_id': self.command_id, 'outcome': outcome})
            return proposed, None

        self._update(transition)
