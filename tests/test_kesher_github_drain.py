"""Offline service fixtures: canceled acknowledgment does not stop a run."""
import copy
import unittest
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from scripts.kesher_runtime.github import GitHubError
from scripts.kesher_runtime.state import StateConflict, StateInvalid


PATH = '.github/workflows/removed.yml'


class Journal:
    def __init__(self):
        self.document = {'schema_version': 5, 'github_exclusion': {'epoch': 'epoch-one', 'drains': {}}}
        self.revision = 0
        self.writes = []
        self.drop = False
        self.reject = False

    def load(self):
        return SimpleNamespace(state=copy.deepcopy(self.document), revision=self.revision)

    def save(self, loaded, proposed):
        if self.reject or loaded.revision != self.revision:
            raise StateConflict('exact journal CAS rejected')
        self.document = copy.deepcopy(proposed); self.revision += 1
        self.writes.append(copy.deepcopy(proposed))
        if self.drop:
            self.drop = False
            raise GitHubError(None, 'lost CAS acknowledgment', uncertain=True)
        return self.load()


class Actions:
    def __init__(self, journal):
        self.journal = journal
        self.workflows = [{'id': 9, 'path': PATH, 'state': 'active'}]
        self.runs = {}
        self.calls = []
        self.disable_drop = self.cancel_drop = False
        self.cancel_denied = False
        self.hook = None
        self.crash_after_disable = False

    def run(self, identity=42, attempt=1, status='queued'):
        row = {'id': identity, 'run_attempt': attempt, 'workflow_id': 9,
               'path': PATH, 'head_sha': 'a'*40, 'status': status,
               'conclusion': 'success' if status == 'completed' else None}
        self.runs[(identity, attempt)] = row
        return row

    def request(self, method, path, body=None):
        self.calls.append((method, path))
        if self.hook: self.hook(method, path)
        tail = urlsplit(path).path.removeprefix('/repos/owner/repo')
        query = parse_qs(urlsplit(path).query)
        if method == 'GET' and tail == '/actions/workflows':
            return {'total_count': len(self.workflows), 'workflows': copy.deepcopy(self.workflows)}
        if method == 'GET' and tail == '/actions/workflows/9':
            return copy.deepcopy(self.workflows[0])
        if method == 'GET' and tail == '/actions/runs':
            latest = {identity: max(attempt for run, attempt in self.runs if run == identity)
                      for identity, _ in self.runs}
            rows = [row for (identity, attempt), row in self.runs.items()
                    if latest[identity] == attempt and row['status'] == query['status'][0]]
            return {'total_count': len(rows), 'workflow_runs': copy.deepcopy(rows)}
        if method == 'GET' and tail.startswith('/actions/runs/'):
            fields = tail.split('/'); identity = int(fields[3])
            attempt = int(fields[5]) if len(fields) > 4 else max(a for i, a in self.runs if i == identity)
            return copy.deepcopy(self.runs[(identity, attempt)])
        entry = self.journal.document['github_exclusion']['drains']['9']
        if method == 'PUT' and tail == '/actions/workflows/9/disable':
            assert entry['disable']['attempts'] and entry['disable']['attempts'][-1]['outcome'] == 'intent'
            self.workflows[0]['state'] = 'disabled_manually'
            if self.crash_after_disable:
                self.crash_after_disable = False
                raise KeyboardInterrupt('runner crashed after effect')
            if self.disable_drop:
                self.disable_drop = False
                raise GitHubError(None, 'disable acknowledgment lost', uncertain=True)
            return {}
        if method == 'POST' and tail.endswith('/cancel'):
            identity = int(tail.split('/')[3])
            attempt = max(a for i, a in self.runs if i == identity)
            assert entry['runs'][f'{identity}:{attempt}']['cancel']['outcome'] == 'intent'
            if self.cancel_denied: raise GitHubError(403, 'cancel not permitted')
            if self.cancel_drop:
                self.cancel_drop = False
                raise GitHubError(None, 'cancel acknowledgment lost', uncertain=True)
            return {}  # accepted request remains queued/running until explicit service readback
        raise AssertionError((method, path))


class GithubDrainTests(unittest.TestCase):
    def setUp(self):
        self.journal = Journal(); self.github = Actions(self.journal)
        self.owned = True

    def authority(self):
        if not self.owned: raise StateConflict('another epoch owns exact Git ref')
        return 'epoch-one'

    def drain(self):
        from scripts.kesher_runtime.github_drain import GithubDrain
        return GithubDrain(self.github, 'owner/repo', journal=self.journal,
                           authority=self.authority, registered=lambda: [{'id':9, 'path':PATH}])

    def step(self): return self.drain().step(9, PATH)

    def until(self, status='drained', limit=12):
        for _ in range(limit):
            result = self.step()
            if result['status'] == status: return result
        self.fail(f'did not reach {status} in bounded fixture steps')

    def mutations(self, suffix): return [c for c in self.github.calls if c[0] != 'GET' and c[1].endswith(suffix)]

    def test_disabled_empty_workflow_requires_all_five_fresh_status_readbacks(self):
        self.github.workflows[0]['state'] = 'disabled_manually'
        proof = self.until()
        self.assertEqual(proof['workflow_id'], 9); self.assertEqual(proof['workflow_path'], PATH)
        self.assertEqual(proof['state'], 'disabled_manually'); self.assertEqual(proof['runs'], [])
        self.assertTrue(proof['readback_sha256'])
        for status in ('queued','in_progress','waiting','pending','requested'):
            self.assertGreaterEqual(sum('status='+status+'&' in path for _, path in self.github.calls), 2)

    def test_cancel_ack_is_never_terminal_for_each_active_status(self):
        for status in ('queued','in_progress','waiting','pending','requested'):
            with self.subTest(status=status):
                self.setUp(); self.github.run(status=status)
                for _ in range(6): self.assertEqual(self.step()['status'], 'pending')
                self.assertEqual(len(self.mutations('/cancel')), 1)
                self.github.runs[(42,1)].update(status='completed', conclusion='cancelled')
                proof = self.until()
                self.assertEqual(proof['runs'][0]['run_attempt'], 1)
                self.assertEqual(proof['runs'][0]['status'], 'completed')

    def test_lost_disable_reconciles_fresh_runner_without_repeat(self):
        self.github.disable_drop = True
        self.until()
        self.assertEqual(len(self.mutations('/disable')), 1)

    def test_lost_cancel_stays_pending_and_never_repeats_on_fresh_runner(self):
        self.github.cancel_drop = True; self.github.run(status='in_progress')
        for _ in range(8): self.assertEqual(self.step()['status'], 'pending')
        self.assertEqual(len(self.mutations('/cancel')), 1)
        self.github.runs[(42,1)].update(status='completed', conclusion='cancelled')
        self.until(); self.assertEqual(len(self.mutations('/cancel')), 1)

    def test_running_run_finishing_naturally_requires_terminal_attempt_readback(self):
        self.github.cancel_denied = True; self.github.run(status='in_progress')
        for _ in range(6): self.assertEqual(self.step()['status'], 'pending')
        self.github.runs[(42,1)].update(status='completed', conclusion='success')
        proof = self.until()
        self.assertEqual(proof['runs'][0]['conclusion'], 'success')
        self.assertTrue(any('/attempts/1' in path for _, path in self.github.calls))

    def test_crash_after_disable_before_readback_recovers_durable_intent(self):
        self.github.crash_after_disable = True
        self.step()
        with self.assertRaises(KeyboardInterrupt): self.step()
        self.until(); self.assertEqual(len(self.mutations('/disable')), 1)

    def test_intent_cas_loss_or_rejection_prevents_effect_until_fresh_load(self):
        self.journal.drop = True
        with self.assertRaises(GitHubError): self.step()
        self.assertEqual(self.mutations('/disable'), [])
        self.until(); self.assertEqual(len(self.mutations('/disable')), 1)
        self.setUp(); self.journal.reject = True
        with self.assertRaises(StateConflict): self.step()
        self.assertEqual(self.mutations('/disable'), [])

    def test_known_ambiguous_intent_after_crash_is_not_repeated(self):
        self.github.workflows[0]['state'] = 'disabled_manually'; self.github.run()
        for _ in range(5): self.step()
        entry = self.journal.document['github_exclusion']['drains']['9']
        entry['runs']['42:1']['cancel']['outcome'] = 'intent'
        for _ in range(4): self.assertEqual(self.step()['status'], 'pending')
        self.assertEqual(len(self.mutations('/cancel')), 1)

    def test_queued_run_created_in_final_inventory_prevents_drain_proof(self):
        self.github.workflows[0]['state'] = 'disabled_manually'
        self.step()
        seen = 0
        def create(method, path):
            nonlocal seen
            if 'status=queued&' in path:
                seen += 1
                if seen == 2: self.github.run(identity=43)
        self.github.hook = create
        self.assertEqual(self.step()['status'], 'pending')
        self.assertIsNone(self.journal.document['github_exclusion']['drains']['9']['proof'])
        self.github.hook = None
        for _ in range(4): self.step()
        self.assertEqual(len(self.mutations('/cancel')), 1)
        self.github.runs[(43,1)].update(status='completed', conclusion='cancelled')
        self.until()

    def test_reenable_during_drain_and_after_proof_fail_closed(self):
        self.github.workflows[0]['state'] = 'disabled_manually'; self.github.run()
        for _ in range(4): self.step()
        self.github.workflows[0]['state'] = 'active'
        with self.assertRaisesRegex(StateInvalid, 'REENABLED'): self.step()
        self.setUp(); self.until(); self.github.workflows[0]['state'] = 'active'
        with self.assertRaisesRegex(StateInvalid, 'REENABLED'): self.step()

    def test_reenabled_after_acknowledged_disable_before_readback_is_refused(self):
        self.step(); self.step()
        self.assertEqual(len(self.mutations('/disable')), 1)
        self.github.workflows[0]['state'] = 'active'
        with self.assertRaisesRegex(StateInvalid, 'REENABLED'): self.step()
        self.assertEqual(len(self.mutations('/disable')), 1)

    def test_unknown_registration_appearing_mid_inventory_refuses_proof(self):
        self.github.workflows[0]['state'] = 'disabled_manually'; self.step()
        def add(method, path):
            if 'status=pending&' in path and len(self.github.workflows) == 1:
                self.github.workflows.append({'id':10,'path':'.github/workflows/unknown.yml','state':'active'})
        self.github.hook = add
        with self.assertRaises(StateInvalid): self.step()
        self.assertIsNone(self.journal.document['github_exclusion']['drains']['9']['proof'])

    def test_mismatched_workflow_id_path_and_unknown_run_refuse(self):
        for changed in ({'id':10}, {'path':'.github/workflows/other.yml'}):
            with self.subTest(changed=changed):
                self.setUp(); self.github.workflows[0].update(changed)
                with self.assertRaises(StateInvalid): self.step()
                self.assertEqual(self.mutations('/disable'), [])
        self.setUp(); self.github.workflows[0]['state']='disabled_manually'
        self.github.run()['workflow_id'] = 99
        with self.assertRaises(StateInvalid): self.step()

    def test_rerun_attempt_and_missing_terminal_conclusion_cannot_bless_old_proof(self):
        self.github.workflows[0]['state'] = 'disabled_manually'; self.github.run()
        for _ in range(5): self.step()
        self.github.runs[(42,1)].update(status='completed', conclusion='success')
        self.github.run(attempt=2, status='queued')
        for _ in range(5): self.assertEqual(self.step()['status'], 'pending')
        self.assertEqual(len(self.mutations('/cancel')), 2)
        self.github.runs[(42,2)].update(status='completed', conclusion=None)
        with self.assertRaises(StateInvalid): self.step()

    def test_loss_of_authority_prevents_any_mutation(self):
        self.owned = False
        with self.assertRaises(StateConflict): self.step()
        self.assertEqual(self.github.calls, [])

    def test_readonly_recognition_polls_persisted_exact_attempts_without_writes(self):
        self.github.workflows[0]['state'] = 'disabled_manually'; self.github.run()
        for _ in range(4): self.step()
        self.github.runs[(42,1)].update(status='completed', conclusion='success')
        expected = self.until(); before = self.journal.revision
        self.assertEqual(self.drain().observe_drained(9, PATH), expected)
        self.assertEqual(self.journal.revision, before)
        self.github.runs[(42,1)]['conclusion'] = 'failure'
        with self.assertRaises(StateInvalid): self.drain().observe_drained(9, PATH)

    def test_drain_transition_preserves_all_intents_terminal_receipts_and_proof(self):
        from scripts.kesher_runtime.github_drain import validate_drain_transition
        self.github.workflows[0]['state'] = 'disabled_manually'; self.github.run()
        for _ in range(4): self.step()
        self.github.runs[(42,1)].update(status='completed', conclusion='success')
        self.until()
        ledgers = [document['github_exclusion']['drains'] for document in self.journal.writes]
        previous = {}
        for proposed in ledgers:
            validate_drain_transition(previous, proposed); previous = proposed
        final = ledgers[-1]
        changes = [lambda new: new.clear(),
                   lambda new: new['9'].update(observed_disabled=False),
                   lambda new: new['9']['runs'].clear(),
                   lambda new: new['9']['runs']['42:1'].update(cancel=None),
                   lambda new: new['9']['runs']['42:1'].update(status='in_progress', conclusion=None),
                   lambda new: new['9'].update(proof=None),
                   lambda new: new['9']['proof'].update(readback_sha256='b'*64),
                   lambda new: new['9']['runs']['42:1']['identity'].update(run_attempt=2)]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(StateInvalid):
                proposed = copy.deepcopy(final); change(proposed)
                validate_drain_transition(final, proposed)

    def test_disable_reconciliation_is_bounded_after_repeated_uncertain_no_effect(self):
        original = self.github.request
        def drop_before_effect(method, path, body=None):
            if method == 'PUT':
                self.github.calls.append((method, path))
                raise GitHubError(None, 'lost before effect', uncertain=True)
            return original(method, path, body)
        self.github.request = drop_before_effect
        for _ in range(8): self.assertEqual(self.step()['status'], 'pending')
        self.assertEqual(len(self.mutations('/disable')), 2)

    def test_incomplete_or_contradictory_five_status_inventory_is_rejected(self):
        self.github.workflows[0]['state'] = 'disabled_manually'
        original = self.github.request
        for broken in ({'total_count': 1, 'workflow_runs': []},
                       {'total_count': 1001, 'workflow_runs': []},
                       {'total_count': 1, 'workflow_runs': [{'id':42, 'run_attempt':1,
                           'workflow_id':9, 'path':PATH, 'status':'in_progress'}]}):
            with self.subTest(broken=broken), self.assertRaises(StateInvalid):
                def wrong(method, path, body=None):
                    return broken if 'status=queued&' in path else original(method, path, body)
                self.github.request = wrong
                self.step()
            self.github.request = original
