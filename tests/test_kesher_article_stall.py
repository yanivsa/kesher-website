"""Oct 4 incident: absence, stale legacy labels and exact rerun ownership."""
import copy
import unittest
from datetime import datetime, timedelta

from scripts.kesher_runtime.controller import Observation, reconcile, run_tick
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.observe import RepositoryObserver
from scripts.kesher_runtime.outbox import workflow_for
from scripts.kesher_runtime.state import StateInvalid, new_state
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, ContentsServer


SLOT = '2026-10-04'
NOW = '2026-10-04T05:00:00+00:00'


def absent(now=NOW, runs=()):
    return Observation({'observed_at': now, 'main_sha': CODE, 'current_slot': SLOT,
                        'publications': [], 'article_prs': [], 'runs': list(runs)})


def claimed():
    first = reconcile(new_state(), absent(), now=NOW)
    server = ContentsServer(first.state)
    store = GitHubStateStore(server, 'owner/repo')
    worker = WorkerContext(store, first.command_id, '37175772325/1', SlotIdentity(SLOT),
                           code_sha=CODE, now=lambda: NOW)
    worker.claim()
    return server, store, first.command_id


class ArticleStallTests(unittest.TestCase):
    def test_legacy_article_generating_is_refused_before_any_write_or_dispatch(self):
        legacy = {'schema_version': 5, 'cycle': SLOT, 'status': 'article_generating',
                  'article': {'status': 'running', 'run_id': 37175772325}}
        server = ContentsServer(legacy)
        dispatched = []
        with self.assertRaises(StateInvalid):
            run_tick(GitHubStateStore(server, 'owner/repo'), absent(), now=NOW,
                     dispatch=dispatched.append)
        self.assertEqual(server.document, legacy)
        self.assertEqual(server.writes, [])
        self.assertEqual(dispatched, [])

    def test_no_article_pr_or_child_persists_exact_intent_before_dispatch(self):
        server = ContentsServer()
        dispatched = []
        def dispatch(command_id):
            self.assertEqual(len(server.writes), 1)
            command = server.document['commands'][command_id]
            self.assertEqual(command['target'], SlotIdentity(SLOT).to_dict())
            self.assertEqual(command['operation'], 'create_article')
            self.assertEqual(command['outcome'], 'pending')
            self.assertFalse(server.document['slots'][SLOT].get('complete', False))
            dispatched.append(command_id)
        result = run_tick(GitHubStateStore(server, 'owner/repo'), absent(), now=NOW,
                          dispatch=dispatch)
        self.assertEqual(dispatched, [result.command_id])
        self.assertNotIn('status', result.state)
        repeated = reconcile(server.document, absent(), now=NOW)
        self.assertEqual(repeated.command_id, result.command_id)
        self.assertEqual(len(repeated.state['commands']), 1)

    def test_missing_claimed_child_reaches_repair_incident_without_second_command(self):
        server, _, command_id = claimed()
        later = (datetime.fromisoformat(NOW) + timedelta(seconds=7201)).isoformat()
        result = reconcile(server.document, absent(later), now=later)
        self.assertIsNone(result.command_id)
        self.assertEqual(list(result.state['commands']), [command_id])
        self.assertEqual(result.state['commands'][command_id]['owner']['run_id'], '37175772325/1')
        incident = next(iter(result.state['incidents'].values()))
        self.assertEqual(incident['failure_class'], 'WORKER_STALLED')
        self.assertEqual(incident['status'], 'repair_required')
        self.assertFalse(result.state['slots'][SLOT].get('complete', False))

    def test_newer_attempt_cannot_settle_the_claimed_attempt_or_free_duplicate_work(self):
        server, _, command_id = claimed()
        other_attempt = {'command_id': command_id, 'run_id': '37175772325/2',
                         'code_sha': CODE, 'status': 'completed', 'conclusion': 'failure'}
        result = reconcile(server.document, absent(runs=[other_attempt]), now=NOW)
        self.assertIsNone(result.command_id)
        self.assertEqual(result.state['commands'][command_id]['outcome'], 'pending')
        self.assertEqual(len(result.state['commands']), 1)
        self.assertFalse(result.state['slots'][SLOT].get('complete', False))

    def test_observer_requests_claimed_attempt_and_rejects_other_attempt_response(self):
        server, _, command_id = claimed()
        command = server.document['commands'][command_id]
        class Reads:
            def __init__(self): self.calls = []
            def request(self, method, path):
                self.calls.append((method, path))
                return {'id': 37175772325, 'run_attempt': 2, 'head_sha': CODE,
                        'head_branch': 'main', 'event': 'workflow_dispatch',
                        'display_title': 'kesher-command:' + command_id,
                        'path': '.github/workflows/' + workflow_for(command),
                        'status': 'completed', 'conclusion': 'failure'}
        github = Reads()
        before = copy.deepcopy(server.document)
        observer = RepositoryObserver(github, 'owner/repo', inventory_reader=None, auditor=None)
        with self.assertRaises(StateInvalid):
            observer.runs(server.document)
        self.assertEqual(github.calls, [('GET', '/repos/owner/repo/actions/runs/37175772325/attempts/1')])
        self.assertEqual(server.document, before)


if __name__ == '__main__':
    unittest.main()
