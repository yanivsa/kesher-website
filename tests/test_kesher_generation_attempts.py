"""A definite provider rejection can advance once; uncertainty cannot create work."""
import copy
import unittest

from scripts import kesher_daily_pipeline as core
from scripts.kesher_runtime.controller import _eligible
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import MediaIdentity, SourceIdentity, digest
from scripts.kesher_runtime.media_state import CanonicalMediaState, snapshots
from scripts.kesher_runtime.media_observer import observe_media
from scripts.kesher_runtime.provider import reconcile_provider
from scripts.kesher_runtime.state import StateInvalid, bind_source, new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, NOW, ContentsServer
from tests.test_kesher_autonomous_controller import later
from tests.test_kesher_media_publication import fixture


class GenerationAttemptTests(unittest.TestCase):
    def setUp(self):
        self.source = core.source_metadata({'id': 'bounded', 'date': '2026-09-17',
            'title': 'כותרת', 'category': 'משפחה', 'excerpt': 'תיאור', 'content': '<p>מקור מדויק</p>'})
        self.target = MediaIdentity(SourceIdentity(self.source['date'], self.source['slug'],
                                                   self.source['content_sha256']), 'overview')
        state = bind_source(new_state(), self.target.source, now=NOW)
        state, self.first_id = plan_command(state, self.target, 'publish', 1,
            {'generation_attempt': '1'}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state)
        self.store = GitHubStateStore(self.server, 'owner/repo')
        self.first = WorkerContext(self.store, self.first_id, '1/1', self.target, code_sha=CODE, now=lambda: NOW)
        self.first.claim()
        media = CanonicalMediaState(self.first, self.initial(1))
        media.external('provider_source', {'notebook_id': 'notebook', 'title': f'kesher:{self.target.key}:1',
            'body_sha256': self.source['content_sha256']}, lambda: {'source_id': 'source-1'})
        media.external('provider_generation', {'notebook_id': 'notebook', 'source_id': 'source-1',
            'prompt': 'הנחיות', 'prompt_sha256': core.sha256_text('הנחיות'), 'format': 'explainer'},
            lambda: {'task_id': 'task-1', 'artifact_id': 'task-1'})
        media.item.update(source_id='source-1', task_id='task-1', artifact_id='task-1',
            status='rejected', technical_verified=False, last_provider_status='completed', raw_sha256='b'*64,
            generation_rejection={'reason': 'voice', 'attempt': 1, 'raw_sha256': 'b'*64, 'artifact_id': 'task-1'})
        media.persist()
        self.first.finish(failure={'class': 'PROVIDER_MEDIA_REJECTED'})

    def initial(self, attempt):
        item = core.new_item(self.source)
        item['source'] = copy.deepcopy(self.source)
        item['id'] = f'media-attempt-{attempt}'
        item['fresh_generation_attempt'] = attempt
        item['notebook_id'] = 'notebook'
        return item

    def next_worker(self, attempt=2, *, predecessor=None):
        loaded = self.store.load()
        latest = snapshots(loaded.state, self.target)[-1]
        proposed, key = plan_command(loaded.state, self.target, 'publish', attempt,
            {'generation_attempt': str(attempt), 'rejected_snapshot_sha256': predecessor or digest(latest)},
            code_sha=CODE, now=later(4000))
        self.store.save(loaded, proposed)
        worker = WorkerContext(self.store, key, f'{attempt}/1', self.target, code_sha=CODE, now=lambda: later(4000))
        worker.claim()
        return worker

    def test_definite_rejection_advances_without_erasing_old_provider_receipts(self):
        old = copy.deepcopy(self.server.document['commands'][self.first_id])
        worker = self.next_worker()
        media = CanonicalMediaState(worker, self.initial(2))
        self.assertEqual(media.item['fresh_generation_attempt'], 2)
        self.assertIsNone(media.item['task_id'])
        media.persist()
        self.assertEqual(self.server.document['commands'][self.first_id], old)
        self.assertEqual([row['item']['fresh_generation_attempt'] for row in snapshots(self.server.document, self.target)], [1, 2])

    def test_controller_authorizes_exact_second_attempt_after_bounded_delay(self):
        result = _eligible(self.server.document, self.target,
            {'status': 'failed', 'failure_class': 'PROVIDER_MEDIA_REJECTED'}, {},
            now=later(4000), default_operation='publish')
        self.assertIsNotNone(result)
        self.assertEqual(result[1], 'publish')
        self.assertEqual(result[2]['generation_attempt'], '2')
        self.assertEqual(result[2]['rejected_snapshot_sha256'], digest(snapshots(self.server.document, self.target)[-1]))

    def test_independent_observer_requires_complete_inventory_before_retry(self):
        inventory = {**fixture()['inventory'], 'observed_at': NOW, 'videos': []}
        observed = observe_media(self.server.document, self.target, self.source,
            inventory=inventory, now=NOW, audit=lambda *args: self.fail('rejected output cannot be published'))
        self.assertEqual(observed['failure_class'], 'PROVIDER_MEDIA_REJECTED')
        unknown = observe_media(self.server.document, self.target, self.source,
            inventory=None, now=NOW, audit=lambda *args: self.fail('no inventory'))
        self.assertEqual(unknown['status'], 'unknown')
        self.assertIsNone(_eligible(self.server.document, self.target, unknown, {},
            now=later(4000), default_operation='publish'))

    def test_failure_receipt_cannot_bypass_exact_transition_inputs(self):
        result = _eligible(self.server.document, self.target, {'status': 'failed'}, {},
            now=later(4000), default_operation='publish')
        self.assertEqual(result[2]['generation_attempt'], '2')
        self.assertEqual(result[2]['rejected_snapshot_sha256'], digest(snapshots(self.server.document, self.target)[-1]))

    def test_uncertain_source_or_generation_never_authorizes_replacement(self):
        for name in ('provider_source', 'provider_generation'):
            with self.subTest(name=name):
                self.setUp()
                self.server.document['commands'][self.first_id]['effects'][name]['receipt'] = None
                worker = self.next_worker()
                with self.assertRaises(StateInvalid):
                    CanonicalMediaState(worker, self.initial(2))

    def test_lost_response_reconciled_by_exact_receipt_allows_definite_rejection_retry(self):
        original = self.server.document['commands'][self.first_id]['effects']['provider_generation']
        known = copy.deepcopy(original['receipt'])
        original['receipt'] = None
        loaded = self.store.load()
        proposed, key = plan_command(loaded.state, self.target, 'reconcile', 1,
            {'generation_attempt': '1'}, code_sha=CODE, now=later(2000))
        self.store.save(loaded, proposed)
        worker = WorkerContext(self.store, key, 'reconcile/1', self.target, code_sha=CODE, now=lambda: later(2000))
        worker.claim()
        media = CanonicalMediaState(worker, self.initial(1))
        queries = []
        def observe(name, request):
            queries.append((name, request))
            return known
        self.assertTrue(reconcile_provider(media, observe))
        worker.finish(failure={'class': 'PROVIDER_MEDIA_REJECTED'})
        self.assertEqual(queries, [('provider_generation', original['request'])])
        next_media = CanonicalMediaState(self.next_worker(), self.initial(2))
        self.assertEqual(next_media.item['fresh_generation_attempt'], 2)
        self.assertIsNone(self.server.document['commands'][self.first_id]['effects']['provider_generation']['receipt'])
        self.assertEqual(self.server.document['commands'][key]['effects']['provider_generation']['receipt'], known)
        # Two inconsistent definite receipts cannot settle the original intent.
        self.server.document['commands'][self.first_id]['effects']['provider_generation']['receipt'] = {
            **known, 'task_id': 'conflicting-task'}
        from scripts.kesher_runtime.media_state import next_generation_attempt
        self.assertIsNone(next_generation_attempt(self.server.document, self.target,
            current_command_id=next_media.context.command_id))

    def test_any_upload_or_archive_intent_blocks_a_new_provider_attempt(self):
        for name in ('youtube_session', 'output_artifact'):
            with self.subTest(name=name):
                self.setUp()
                self.server.document['commands'][self.first_id]['outcome'] = 'pending'
                self.first.begin_effect(name, {'identity': 'uncertain-prior-effect'})
                self.first.finish(failure={'class': 'PROVIDER_MEDIA_REJECTED'})
                worker = self.next_worker()
                with self.assertRaises(StateInvalid):
                    CanonicalMediaState(worker, self.initial(2))

    def test_a_stale_rejection_digest_cannot_reset_provider_identity(self):
        worker = self.next_worker(predecessor='0'*64)
        with self.assertRaises(StateInvalid):
            CanonicalMediaState(worker, self.initial(2))

    def test_skipped_or_fourth_attempt_is_refused(self):
        for attempt in (3, 4):
            with self.subTest(attempt=attempt):
                self.setUp()
                worker = self.next_worker(attempt)
                with self.assertRaises(StateInvalid):
                    CanonicalMediaState(worker, self.initial(attempt))

    def test_new_attempt_does_not_adopt_the_rejected_task(self):
        media = CanonicalMediaState(self.next_worker(), self.initial(2))
        calls = []
        self.assertTrue(reconcile_provider(media, lambda *args: calls.append(args)))
        self.assertEqual(calls, [])
        self.assertIsNone(media.item['source_id'])
        self.assertIsNone(media.item['task_id'])
        creations = []
        request = {'notebook_id': 'notebook', 'title': 'attempt-2', 'body_sha256': self.source['content_sha256']}
        def create():
            creations.append('source-2')
            return {'source_id': 'source-2'}
        self.assertEqual(media.external('provider_source', request, create), {'source_id': 'source-2'})
        self.assertEqual(media.external('provider_source', request, create), {'source_id': 'source-2'})
        self.assertEqual(creations, ['source-2'])

    def test_second_rejection_can_reach_three_but_never_four(self):
        worker = self.next_worker()
        media = CanonicalMediaState(worker, self.initial(2))
        media.external('provider_source', {'notebook_id': 'notebook', 'title': f'kesher:{self.target.key}:2',
            'body_sha256': self.source['content_sha256']}, lambda: {'source_id': 'source-2'})
        media.external('provider_generation', {'notebook_id': 'notebook', 'source_id': 'source-2',
            'prompt': 'הנחיות ניסיון שני', 'prompt_sha256': core.sha256_text('הנחיות ניסיון שני'), 'format': 'explainer'},
            lambda: {'task_id': 'task-2', 'artifact_id': 'task-2'})
        media.item.update(source_id='source-2', task_id='task-2', artifact_id='task-2',
            status='rejected', technical_verified=False, last_provider_status='completed', raw_sha256='c'*64,
            generation_rejection={'reason': 'voice', 'attempt': 2, 'raw_sha256': 'c'*64, 'artifact_id': 'task-2'})
        media.persist()
        worker.finish(failure={'class': 'PROVIDER_MEDIA_REJECTED'})
        result = _eligible(self.server.document, self.target,
            {'status': 'failed', 'failure_class': 'PROVIDER_MEDIA_REJECTED'}, {},
            now=later(8000), default_operation='publish')
        self.assertEqual(result[2]['generation_attempt'], '3')
        third_worker = self.next_worker(3)
        third = CanonicalMediaState(third_worker, self.initial(3))
        third.external('provider_source', {'notebook_id': 'notebook', 'title': f'kesher:{self.target.key}:3',
            'body_sha256': self.source['content_sha256']}, lambda: {'source_id': 'source-3'})
        third.external('provider_generation', {'notebook_id': 'notebook', 'source_id': 'source-3',
            'prompt': 'הנחיות שלישיות', 'prompt_sha256': core.sha256_text('הנחיות שלישיות'), 'format': 'explainer'},
            lambda: {'task_id': 'task-3', 'artifact_id': 'task-3'})
        third.item.update(source_id='source-3', task_id='task-3', artifact_id='task-3',
            status='rejected', technical_verified=False, last_provider_status='completed', raw_sha256='d'*64,
            generation_rejection={'reason': 'voice', 'attempt': 3, 'raw_sha256': 'd'*64, 'artifact_id': 'task-3'})
        third.persist()
        third_worker.finish(failure={'class': 'PROVIDER_MEDIA_REJECTED'})
        self.assertEqual([row['item']['task_id'] for row in snapshots(self.server.document, self.target)][:2],
                         ['task-1', 'task-2'])
        from scripts.kesher_runtime.media_state import next_generation_attempt
        self.assertIsNone(next_generation_attempt(self.server.document, self.target))
        self.assertIsNone(_eligible(self.server.document, self.target,
            {'status': 'failed', 'failure_class': 'PROVIDER_MEDIA_REJECTED'}, {},
            now=later(12000), default_operation='publish'))

    def test_unseeded_second_attempt_is_refused(self):
        state = bind_source(new_state(), self.target.source, now=NOW)
        state, key = plan_command(state, self.target, 'publish', 1, {'generation_attempt': '2'}, code_sha=CODE, now=NOW)
        store = GitHubStateStore(ContentsServer(state), 'owner/repo')
        worker = WorkerContext(store, key, '1/1', self.target, code_sha=CODE, now=lambda: NOW)
        worker.claim()
        with self.assertRaises(StateInvalid):
            CanonicalMediaState(worker, self.initial(2))

    def test_mutating_a_live_projection_cannot_create_a_new_provider_attempt(self):
        worker = self.next_worker()
        media = CanonicalMediaState(worker, self.initial(2))
        media.item['fresh_generation_attempt'] = 3
        creations = []
        with self.assertRaises(StateInvalid):
            media.external('provider_source', {'title': 'forbidden'}, lambda: creations.append('created'))
        self.assertEqual(creations, [])
        with self.assertRaises(StateInvalid):
            media.persist()


if __name__ == '__main__':
    unittest.main()
