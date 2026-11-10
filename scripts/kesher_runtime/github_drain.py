"""Bounded Actions retirement subordinate to a caller-owned real Git epoch.

No CLI or live invocation exists here. ``journal`` loads and CAS-saves the SAME
automation-state document; only github_exclusion.drains may change. ``authority``
freshly proves ownership and returns its exact epoch before every read/write.
``registered`` supplies the complete reviewed, identity-bound candidate inventory
(including all retained missing-YAML IDs); it is not a safety classification.

GitHub disables return no CAS revision. Cancel accepts a run ID, not an attempt;
we bind and recheck its latest attempt under the independently owned fence.
Neither acknowledgment is terminal proof. At most one Actions mutation occurs
per step. An ambiguous cancel intent is never replayed, including after a crash.
"""
import copy
import re

from .authority_topology import (ACTIVE_RUN_STATUSES, GitHubAuthorityObserver,
                                 WORKFLOW_STATES, authority_path, run_identity,
                                 run_snapshot, workflow_snapshot, REGISTERED_SYSTEM_PATHS)
from .github import GitHubError
from .identity import digest
from .state import StateInvalid


def _action(action):
    if (not isinstance(action, dict) or set(action) - {'outcome', 'status'}
            or action.get('outcome') not in {'intent', 'acknowledged', 'uncertain', 'denied'}
            or 'status' in action and action['status'] is not None and type(action['status']) is not int
            or action.get('outcome') in {'intent', 'acknowledged'} and set(action) != {'outcome'}):
        raise StateInvalid('GITHUB_DRAIN_INVALID_EFFECT_RECEIPT')


def _validate_drains(drains):
    if not isinstance(drains, dict): raise StateInvalid('GITHUB_DRAIN_INVALID_LEDGER')
    for key, entry in drains.items():
        if (not isinstance(entry, dict) or set(entry) != {'workflow_id', 'workflow_path', 'epoch',
                'observed_disabled', 'disable', 'runs', 'proof'}
                or type(entry['workflow_id']) is not int or entry['workflow_id'] < 1
                or key != str(entry['workflow_id']) or not isinstance(entry['workflow_path'], str)
                or not (entry['workflow_path'].startswith('.github/workflows/') or
                        entry['workflow_path'] in REGISTERED_SYSTEM_PATHS)
                or not isinstance(entry['epoch'], str) or not entry['epoch']
                or type(entry['observed_disabled']) is not bool or not isinstance(entry['runs'], dict)
                or not isinstance(entry['disable'], dict) or set(entry['disable']) != {'attempts'}
                or not isinstance(entry['disable']['attempts'], list) or len(entry['disable']['attempts']) > 2):
            raise StateInvalid('GITHUB_DRAIN_INVALID_LEDGER')
        authority_path(entry['workflow_path'])
        for action in entry['disable']['attempts']: _action(action)
        for run_key, row in entry['runs'].items():
            if not isinstance(row, dict) or set(row) != {'identity', 'status', 'conclusion', 'cancel'}:
                raise StateInvalid('GITHUB_DRAIN_INVALID_RUN_RECEIPT')
            exact = row['identity']
            if (not isinstance(exact, dict) or set(exact) not in
                    ({'id', 'run_attempt', 'workflow_id', 'path'}, {'id', 'run_attempt', 'workflow_id', 'path', 'head_sha'})
                    or exact['workflow_id'] != entry['workflow_id'] or exact['path'] != entry['workflow_path']
                    or run_key != f"{exact['id']}:{exact['run_attempt']}"
                    or run_identity(dict(exact, status=row['status'], conclusion=row['conclusion'])) != exact):
                raise StateInvalid('GITHUB_DRAIN_INVALID_RUN_RECEIPT')
            if row['cancel'] is not None: _action(row['cancel'])
        proof = entry['proof']
        if proof is not None:
            expected_runs = [dict(row['identity'], status=row['status'], conclusion=row['conclusion'])
                             for _, row in sorted(entry['runs'].items())]
            if (not isinstance(proof, dict) or set(proof) != {'status', 'epoch', 'workflow_id',
                    'workflow_path', 'state', 'runs', 'readback_sha256'}
                    or proof['status'] != 'drained' or proof['state'] != 'disabled_manually'
                    or any(proof[field] != entry[field] for field in ('workflow_id', 'workflow_path', 'epoch'))
                    or not entry['observed_disabled'] or proof['runs'] != expected_runs
                    or any(row['status'] != 'completed' for row in entry['runs'].values())
                    or not isinstance(proof['readback_sha256'], str)
                    or not re.fullmatch('[a-f0-9]{64}', proof['readback_sha256'])):
                raise StateInvalid('GITHUB_DRAIN_INVALID_TERMINAL_PROOF')


def _effect_transition(old, new):
    if old == new: return
    if old is None and new == {'outcome': 'intent'}: return
    if old == {'outcome': 'intent'} and new is not None and new['outcome'] in {'acknowledged', 'uncertain', 'denied'}:
        return
    raise StateInvalid('GITHUB_DRAIN_EFFECT_REPLAY_OR_ERASURE')


def validate_drain_transition(old, new):
    """Validate two *drains mappings*, for the same-document journal CAS gate.

    The root adapter separately enforces the exact Git epoch, immutable ledger
    metadata and every other document byte. Effects, discovered run identities,
    terminal receipts and certified proofs cannot be erased or rewritten.
    """
    try:
        _validate_drains(old); _validate_drains(new)
        if not set(old) <= set(new): raise StateInvalid('GITHUB_DRAIN_LEDGER_ERASURE')
        for key, before in old.items():
            after = new[key]
            if (any(before[field] != after[field] for field in ('workflow_id', 'workflow_path', 'epoch'))
                    or before['observed_disabled'] and not after['observed_disabled']
                    or before['proof'] is not None and before != after):
                raise StateInvalid('GITHUB_DRAIN_NONMONOTONIC_LEDGER')
            a, b = before['disable']['attempts'], after['disable']['attempts']
            if len(b) not in {len(a), len(a)+1}: raise StateInvalid('GITHUB_DRAIN_EFFECT_ERASURE')
            for previous, proposed in zip(a, b): _effect_transition(previous, proposed)
            if len(b) > len(a) and b[-1] != {'outcome': 'intent'}:
                raise StateInvalid('GITHUB_DRAIN_DISABLE_INTENT_REQUIRED')
            if not set(before['runs']) <= set(after['runs']): raise StateInvalid('GITHUB_DRAIN_RUN_ERASURE')
            for run_key, row in before['runs'].items():
                proposed = after['runs'][run_key]
                if (row['identity'] != proposed['identity'] or row['status'] == 'completed'
                        and (proposed['status'] != 'completed' or row['conclusion'] != proposed['conclusion'])):
                    raise StateInvalid('GITHUB_DRAIN_RUN_RECEIPT_REWRITE')
                _effect_transition(row['cancel'], proposed['cancel'])
            for run_key in set(after['runs']) - set(before['runs']):
                row = after['runs'][run_key]
                if row['status'] not in ACTIVE_RUN_STATUSES or row['cancel'] is not None:
                    raise StateInvalid('GITHUB_DRAIN_DISCOVERY_REQUIRED')
        for key in set(new) - set(old):
            entry = new[key]
            if (entry['proof'] is not None or entry['disable']['attempts']
                    or any(row['status'] not in ACTIVE_RUN_STATUSES or row['cancel'] is not None
                           for row in entry['runs'].values())):
                raise StateInvalid('GITHUB_DRAIN_INITIAL_OBSERVATION_REQUIRED')
    except (KeyError, TypeError, ValueError) as exc:
        raise StateInvalid('GITHUB_DRAIN_INVALID_LEDGER') from exc


class GithubDrain:
    def __init__(self, github, repo, *, journal, authority, registered):
        if not callable(authority) or not callable(registered):
            raise StateInvalid('GITHUB_DRAIN_TRUSTED_AUTHORITY_REQUIRED')
        self.github, self.repo, self.journal = github, repo, journal
        self.authority, self.registered = authority, registered
        self.api = '/repos/' + repo
        self.epoch = None

    def _owned(self):
        epoch = self.authority()
        if not isinstance(epoch, str) or not epoch or self.epoch is not None and self.epoch != epoch:
            raise StateInvalid('GITHUB_DRAIN_EPOCH_CHANGED')
        self.epoch = epoch
        return epoch

    def _request(self, method, path):
        self._owned()
        return self.github.request(method, path)

    def _inventory(self):
        self._owned()
        known = self.registered()
        if (not isinstance(known, list) or not known
                or any(not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] < 1
                       or not isinstance(row.get('path'), str) for row in known)
                or len({row['id'] for row in known}) != len(known)
                or len({row['path'] for row in known}) != len(known)):
            raise StateInvalid('GITHUB_DRAIN_REGISTERED_INVENTORY_INVALID')
        expected = {row['id']: row['path'] for row in known}
        # A small read-only port ensures every paginated GET reasserts the epoch.
        outer = self
        class Reader:
            def request(self, method, path): return outer._request(method, path)
        observer = GitHubAuthorityObserver(Reader(), self.repo, '.', fence=None)
        rows = observer.pages('actions/workflows', 'workflows')
        self._known(rows, expected)
        runs = observer.active_inventory(rows)
        fresh = observer.pages('actions/workflows', 'workflows')
        self._known(fresh, expected)
        if workflow_snapshot(rows) != workflow_snapshot(fresh):
            raise StateInvalid('GITHUB_DRAIN_WORKFLOW_CHANGED_DURING_INVENTORY')
        return {'workflows': fresh, 'active_runs': runs}

    @staticmethod
    def _known(rows, expected):
        if (len(rows) != len(expected) or any(row.get('state') not in WORKFLOW_STATES
                or type(row.get('id')) is not int or expected.get(row['id']) != row.get('path') for row in rows)
                or len({row['id'] for row in rows}) != len(rows)
                or len({row['path'] for row in rows}) != len(rows)):
            raise StateInvalid('GITHUB_DRAIN_UNKNOWN_REGISTERED_IDENTITY')

    def _load(self):
        self._owned(); loaded = self.journal.load()
        exclusion = loaded.state.get('github_exclusion')
        if (not isinstance(exclusion, dict) or exclusion.get('epoch') != self.epoch
                or not isinstance(exclusion.get('drains', {}), dict)):
            raise StateInvalid('GITHUB_DRAIN_JOURNAL_EPOCH_MISMATCH')
        return loaded

    def _save(self, loaded, workflow_id, entry):
        self._owned()
        proposed = copy.deepcopy(loaded.state)
        proposed['github_exclusion'].setdefault('drains', {})[str(workflow_id)] = copy.deepcopy(entry)
        validate_drain_transition(loaded.state['github_exclusion'].get('drains', {}),
                                  proposed['github_exclusion']['drains'])
        # Any lost CAS response aborts this invocation before the Actions effect.
        return self.journal.save(loaded, proposed)

    def _entry(self, loaded, workflow_id, workflow_path):
        entry = loaded.state['github_exclusion'].get('drains', {}).get(str(workflow_id))
        if entry is not None:
            validate_drain_transition({str(workflow_id): entry}, {str(workflow_id): entry})
            if (entry.get('workflow_id') != workflow_id or entry.get('workflow_path') != workflow_path
                    or entry.get('epoch') != self.epoch or type(entry.get('observed_disabled')) is not bool
                    or not isinstance(entry.get('runs'), dict)
                    or not isinstance(entry.get('disable', {}).get('attempts'), list)):
                raise StateInvalid('GITHUB_DRAIN_JOURNAL_IDENTITY_MISMATCH')
            for key, row in entry['runs'].items():
                exact = row['identity']
                if (key != f"{exact['id']}:{exact['run_attempt']}" or exact['workflow_id'] != workflow_id
                        or exact['path'] != workflow_path
                        or run_identity(dict(exact, status=row['status'], conclusion=row['conclusion'])) != exact):
                    raise StateInvalid('GITHUB_DRAIN_JOURNAL_RUN_MISMATCH')
        return copy.deepcopy(entry)

    @staticmethod
    def _target(inventory, workflow_id, workflow_path, entry=None):
        row = next((row for row in inventory['workflows'] if row['id'] == workflow_id), None)
        if row is None or row['path'] != workflow_path:
            raise StateInvalid('GITHUB_DRAIN_TARGET_INVALID')
        if entry and (entry['observed_disabled'] or entry['proof']) and row['state'] != 'disabled_manually':
            raise StateInvalid('GITHUB_DRAIN_WORKFLOW_REENABLED')
        if row['state'] not in {'active', 'disabled_manually'}:
            raise StateInvalid('GITHUB_DRAIN_EXACT_MANUAL_DISABLE_REQUIRED')
        return row

    @staticmethod
    def _remember(entry, inventory):
        changed = False
        for run in inventory['active_runs']:
            if run['workflow_id'] != entry['workflow_id']: continue
            exact = run_identity(run); key = f"{exact['id']}:{exact['run_attempt']}"
            if key in entry['runs']:
                previous = entry['runs'][key]
                if previous['identity'] != exact or previous['status'] == 'completed':
                    raise StateInvalid('GITHUB_DRAIN_RUN_IDENTITY_CHANGED')
            else:
                if entry['proof']: raise StateInvalid('GITHUB_DRAIN_RUN_AFTER_PROOF')
                entry['runs'][key] = {'identity': exact, 'status': run['status'],
                                      'conclusion': None, 'cancel': None}
                changed = True
        return changed

    def _attempt(self, record):
        exact = record['identity']
        run = self._request('GET', self.api + f"/actions/runs/{exact['id']}/attempts/{exact['run_attempt']}")
        if run_identity(run) != exact:
            raise StateInvalid('GITHUB_DRAIN_EXACT_ATTEMPT_MISMATCH')
        if record['status'] == 'completed' and (run['status'] != 'completed' or run['conclusion'] != record['conclusion']):
            raise StateInvalid('GITHUB_DRAIN_TERMINAL_ATTEMPT_CHANGED')
        return run

    @staticmethod
    def _pending(workflow_id, workflow_path):
        return {'status': 'pending', 'workflow_id': workflow_id, 'workflow_path': workflow_path}

    def step(self, workflow_id, workflow_path):
        self._owned()
        loaded = self._load(); entry = self._entry(loaded, workflow_id, workflow_path)
        inventory = self._inventory()
        workflow = self._target(inventory, workflow_id, workflow_path, entry)
        pending = self._pending(workflow_id, workflow_path)
        if entry is None:
            entry = {'workflow_id': workflow_id, 'workflow_path': workflow_path, 'epoch': self.epoch,
                     'observed_disabled': workflow['state'] == 'disabled_manually',
                     'disable': {'attempts': []}, 'runs': {}, 'proof': None}
            self._remember(entry, inventory); self._save(loaded, workflow_id, entry)
            return pending
        if entry['proof']:
            return self.observe(workflow_id, workflow_path)
        if workflow['state'] == 'active':
            attempts = entry['disable']['attempts']
            if attempts and attempts[-1]['outcome'] == 'acknowledged':
                raise StateInvalid('GITHUB_DRAIN_WORKFLOW_REENABLED')
            if len(attempts) >= 2 or attempts and attempts[-1]['outcome'] == 'denied':
                return pending
            # Fresh active read permits one bounded idempotent disable reconcile.
            # It is never a workflow-revision CAS or exclusivity proof.
            attempts.append({'outcome': 'intent'})
            loaded = self._save(loaded, workflow_id, entry)
            try:
                self._request('PUT', self.api + f'/actions/workflows/{workflow_id}/disable')
                attempts[-1]['outcome'] = 'acknowledged'
            except GitHubError as exc:
                attempts[-1]['outcome'] = 'uncertain' if exc.uncertain else 'denied'
                attempts[-1]['status'] = exc.status
            self._save(loaded, workflow_id, entry)
            return pending
        changed = self._remember(entry, inventory)
        if not entry['observed_disabled']:
            entry['observed_disabled'] = True; changed = True
        if changed: loaded = self._save(loaded, workflow_id, entry)
        waiting = False
        for key in sorted(entry['runs']):
            record = entry['runs'][key]; run = self._attempt(record)
            if record['status'] != run['status'] or record['conclusion'] != run.get('conclusion'):
                record.update(status=run['status'], conclusion=run.get('conclusion'))
                loaded = self._save(loaded, workflow_id, entry)
            if run['status'] == 'completed': continue
            waiting = True
            if record['cancel'] is not None: continue  # durable intent/ambiguity is never replayed
            latest = self._request('GET', self.api + f"/actions/runs/{run['id']}")
            current = run_identity(latest)
            if current != record['identity']:
                if (current['id'] == run['id'] and current['workflow_id'] == workflow_id
                        and current['path'] == workflow_path and current['run_attempt'] > run['run_attempt']):
                    continue  # enumerate/adopt the newer exact attempt on the next invocation
                raise StateInvalid('GITHUB_DRAIN_CANCEL_IDENTITY_CHANGED')
            if latest['status'] == 'completed': continue  # poll terminal exact attempt again next invocation
            record['cancel'] = {'outcome': 'intent'}
            loaded = self._save(loaded, workflow_id, entry)
            try:
                self._request('POST', self.api + f"/actions/runs/{run['id']}/cancel")
                record['cancel']['outcome'] = 'acknowledged'
            except GitHubError as exc:
                record['cancel'].update(outcome='uncertain' if exc.uncertain else 'denied', status=exc.status)
            self._save(loaded, workflow_id, entry)
            return pending
        if waiting: return pending
        readbacks = []
        for _ in range(2):
            fresh = self._inventory(); current = self._target(fresh, workflow_id, workflow_path, entry)
            new = self._remember(entry, fresh)
            if new: loaded = self._save(loaded, workflow_id, entry)
            if any(run['workflow_id'] == workflow_id for run in fresh['active_runs']): return pending
            readbacks.append({'workflow': current, 'registered': workflow_snapshot(fresh['workflows']),
                              'active_runs': run_snapshot(fresh['active_runs'])})
        self._owned()
        proof = {'status': 'drained', 'epoch': self.epoch, 'workflow_id': workflow_id,
                 'workflow_path': workflow_path, 'state': 'disabled_manually',
                 'runs': [dict(row['identity'], status=row['status'], conclusion=row['conclusion'])
                          for _, row in sorted(entry['runs'].items())], 'readback_sha256': digest(readbacks)}
        entry['proof'] = proof
        self._save(loaded, workflow_id, entry)
        return copy.deepcopy(proof)

    def observe(self, workflow_id, workflow_path):
        """Read-only recertification after PREPARED freezes the drain ledger."""
        return self.observe_many([(workflow_id,workflow_path)])[0]

    def observe_many(self, targets):
        """Two fresh complete inventories certify all targets in one read batch.

        Each journal entry and recorded exact run attempt is still revalidated;
        no inventory or proof is cached across invocations. A new registration,
        re-enable or active attempt on ANY target rejects the entire batch.
        """
        loaded=self._load();entries=[]
        if len({wid for wid,_ in targets})!=len(targets):
            raise StateInvalid('GITHUB_DRAIN_TARGET_INVALID')
        for workflow_id,workflow_path in targets:
            entry=self._entry(loaded,workflow_id,workflow_path)
            if not entry or not entry['proof'] or not entry['observed_disabled']:
                raise StateInvalid('GITHUB_DRAIN_PROOF_REQUIRED')
            entries.append(entry)
        for _ in range(2):
            inventory = self._inventory()
            for entry in entries:
                workflow_id,workflow_path=entry['workflow_id'],entry['workflow_path']
                self._target(inventory,workflow_id,workflow_path,entry)
                if any(run['workflow_id']==workflow_id for run in inventory['active_runs']):
                    raise StateInvalid('GITHUB_DRAIN_RUN_AFTER_PROOF')
                for row in entry['runs'].values():
                    if row['status']!='completed' or self._attempt(row)['status']!='completed':
                        raise StateInvalid('GITHUB_DRAIN_TERMINAL_PROOF_REQUIRED')
        self._owned()
        return [copy.deepcopy(entry['proof']) for entry in entries]

    observe_drained = observe
