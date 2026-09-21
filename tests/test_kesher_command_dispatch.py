"""Command outbox: no dispatch before CAS, no timestamp-only run adoption."""
import copy
import unittest

from scripts.kesher_runtime.github import GitHubError, GitHubStateStore
from scripts.kesher_runtime.outbox import ObservedRuns, deliver_command, workflow_for
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.state import new_state, plan_command
from scripts.kesher_runtime.state import StateConflict, StateInvalid, claim_command
from tests.test_kesher_canonical_state import CODE, NOW, OVERVIEW, ContentsServer, requested


class CommandDispatchTests(unittest.TestCase):
    def test_deployment_requires_a_merged_source_not_an_unresolved_slot(self):
        state, command_id = plan_command(new_state(), SlotIdentity('2026-09-17'), 'deploy_article', 1,
                                         {'deploy_sha': CODE}, code_sha=CODE, now=NOW)
        with self.assertRaises(StateInvalid):
            workflow_for(state['commands'][command_id])

    def test_premerge_article_stages_bind_the_slot_and_exact_pr_head(self):
        for operation, workflow in [('normalize_article', 'normalize-article-pr.yml'),
                                    ('attach_image', 'kesher-article-image.yml'),
                                    ('merge_article', 'kesher-article-generation.yml')]:
            with self.subTest(operation=operation):
                state, command_id = plan_command(new_state(), SlotIdentity('2026-09-17'), operation, 1,
                                                 {'pr_number': '854', 'pr_head_sha': CODE}, code_sha=CODE, now=NOW)
                self.assertEqual(workflow_for(state['commands'][command_id]), workflow)

    def setUp(self):
        state, self.command_id = requested()
        self.server = ContentsServer(state)
        self.store = GitHubStateStore(self.server, 'owner/repo')
        self.calls = []

    def send(self, workflow, inputs):
        persisted = self.server.document['commands'][self.command_id]
        self.assertEqual(len(persisted['dispatch']['attempts']), len(self.calls) + 1)
        self.assertEqual(persisted['dispatch']['attempts'][-1]['receipt'], None)
        self.calls.append((workflow, copy.deepcopy(inputs)))

    def run_row(self, *, name=None, status='in_progress', conclusion=None):
        return {'id': 123, 'display_title': name or f'kesher-command:{self.command_id}',
                'path': '.github/workflows/kesher-daily-video.yml', 'head_branch': 'main',
                'event': 'workflow_dispatch', 'status': status, 'conclusion': conclusion}

    def deliver(self, rows=None, *, now=NOW, send=None, main_sha=CODE):
        observed = ObservedRuns('kesher-daily-video.yml', tuple(rows or []), now)
        return deliver_command(self.store, self.command_id, observed, send or self.send, now=now, trusted_main_sha=main_sha)

    def test_dispatch_happens_after_durable_intent_and_second_scheduler_does_not_repeat(self):
        first = self.deliver()
        self.assertEqual(first.status, 'dispatched')
        self.assertEqual(self.calls, [('kesher-daily-video.yml', {'command_id': self.command_id})])
        self.assertEqual(self.deliver().status, 'waiting')
        self.assertEqual(len(self.calls), 1)

    def test_cas_conflict_prevents_every_external_dispatch(self):
        original = self.server.request

        def race(method, path, body=None, **kwargs):
            if method == 'PUT':
                self.server.sha = 'f' * 40
            return original(method, path, body, **kwargs)

        self.server.request = race
        with self.assertRaises(StateConflict):
            self.deliver()
        self.assertEqual(self.calls, [])

    def test_lost_dispatch_response_waits_for_exact_run_then_claim(self):
        def lost(workflow, inputs):
            self.send(workflow, inputs)
            raise GitHubError(None, 'response lost', uncertain=True)

        self.assertEqual(self.deliver(send=lost).status, 'uncertain')
        self.assertEqual(self.deliver([self.run_row()]).status, 'waiting')
        state, _ = claim_command(self.server.document, self.command_id, '123/1', OVERVIEW, code_sha=CODE, now=NOW)
        self.server.document = state
        self.assertEqual(self.deliver().status, 'claimed')
        self.assertEqual(len(self.calls), 1)

    def test_nearby_run_of_same_workflow_is_not_adopted(self):
        unrelated = self.run_row(name='kesher-command:command:' + 'b' * 64)
        self.assertEqual(self.deliver([unrelated]).status, 'dispatched')
        self.assertEqual(len(self.calls), 1)

    def test_successful_workflow_without_command_receipt_requires_repair(self):
        result = self.deliver([self.run_row(status='completed', conclusion='success')])
        self.assertEqual(result.status, 'repair_required')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.server.document['commands'][self.command_id]['phase'], 'REQUESTED')

    def test_crash_before_post_can_redeliver_same_command_with_finite_budget(self):
        def never_returns(workflow, inputs):
            self.send(workflow, inputs)
            raise RuntimeError('process killed before POST')

        with self.assertRaises(RuntimeError):
            self.deliver(send=never_returns)
        self.assertEqual(self.deliver().status, 'waiting')
        self.assertEqual(self.deliver(now='2026-09-17T20:15:00+00:00').status, 'dispatched')
        self.assertEqual(self.deliver(now='2026-09-17T20:30:00+00:00').status, 'dispatched')
        self.assertEqual(self.deliver(now='2026-09-17T20:45:00+00:00').status, 'repair_required')
        self.assertEqual({inputs['command_id'] for _, inputs in self.calls}, {self.command_id})
        self.assertEqual(len(self.calls), 3)

    def test_worker_claim_during_dispatch_receipt_write_is_preserved(self):
        def claimed(workflow, inputs):
            self.send(workflow, inputs)
            snapshot = self.store.load()
            state, _ = claim_command(snapshot.state, self.command_id, '123/1', OVERVIEW, code_sha=CODE, now=NOW)
            self.store.save(snapshot, state)

        self.assertEqual(self.deliver(send=claimed).status, 'dispatched')
        self.assertEqual(self.server.document['commands'][self.command_id]['owner']['run_id'], '123/1')
        self.assertEqual(self.deliver().status, 'claimed')

    def test_old_code_and_foreign_workflow_cannot_dispatch(self):
        self.assertEqual(self.deliver(main_sha='d' * 40).status, 'code_changed')
        foreign = self.run_row()
        foreign['path'] = '.github/workflows/kesher-short-v4.yml'
        self.assertEqual(self.deliver([foreign]).status, 'dispatched')

    def test_unclaimed_running_workflow_has_a_bounded_acceptance_deadline(self):
        result = self.deliver([self.run_row()], now='2026-09-18T08:00:00+00:00')
        self.assertEqual(result.status, 'repair_required')
        self.assertIn('ACCEPTANCE_STALLED', result.reason)
        self.assertEqual(self.calls, [])

    def test_dispatch_intent_and_receipt_cannot_be_erased_or_rewritten(self):
        self.deliver()
        loaded = self.store.load()
        original = loaded.state
        for field, value in [('attempts', []), ('receipt', {'status': 'rejected', 'http_status': 401})]:
            self.server.document = copy.deepcopy(original)
            loaded = self.store.load()
            mutated = loaded.state
            if field == 'attempts':
                mutated['commands'][self.command_id]['dispatch']['attempts'] = value
            else:
                mutated['commands'][self.command_id]['dispatch']['attempts'][0]['receipt'] = value
            with self.subTest(field=field), self.assertRaises(StateInvalid):
                self.store.save(loaded, mutated)


if __name__ == '__main__':
    unittest.main()
