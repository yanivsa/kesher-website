"""Worker crash/replay contract: durable claims and external-effect intents."""
import copy
import unittest

from scripts.kesher_runtime.github import GitHubError, GitHubStateStore
from scripts.kesher_runtime.identity import SourceIdentity
from scripts.kesher_runtime.state import ClaimRejected, StateInvalid, bind_source, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, DAY, NOW, OVERVIEW, SHORT, SOURCE, ContentsServer, requested


class WorkerCommandTests(unittest.TestCase):
    def setUp(self):
        state, self.command_id = requested()
        self.server = ContentsServer(state)
        self.store = GitHubStateStore(self.server, 'owner/repo')

    def worker(self, run='run-1/attempt-1', target=OVERVIEW):
        return WorkerContext(self.store, self.command_id, run, target, code_sha=CODE, now=lambda: NOW)

    def test_only_worker_with_durably_accepted_claim_can_start_external_work(self):
        worker = self.worker()
        with self.assertRaises(ClaimRejected):
            worker.begin_effect('generate', {'source_id': 'source-1'})
        self.assertTrue(worker.claim().execute)
        self.assertFalse(self.worker('run-2/attempt-1').claim().execute)
        self.assertFalse(self.worker('run-1/attempt-2').claim().execute)
        decision = worker.begin_effect('generate', {'source_id': 'source-1'})
        self.assertTrue(decision.execute)
        intent = self.server.document['commands'][self.command_id]['effects']['generate']
        self.assertEqual(intent['request'], {'source_id': 'source-1'})
        self.assertIsNone(intent['receipt'])

    def test_crash_after_effect_intent_does_not_authorize_repeated_creation(self):
        worker = self.worker()
        worker.claim()
        worker.begin_effect('generate', {'source_id': 'source-1'})
        restarted = self.worker()
        restarted.attach()
        decision = restarted.begin_effect('generate', {'source_id': 'source-1'})
        self.assertFalse(decision.execute)
        self.assertIsNone(decision.receipt)
        restarted.complete_effect('generate', {'provider_job_id': 'existing-task'})
        decision = restarted.begin_effect('generate', {'source_id': 'source-1'})
        self.assertFalse(decision.execute)
        self.assertEqual(decision.receipt, {'provider_job_id': 'existing-task'})

    def test_lost_claim_receipt_never_starts_an_external_effect(self):
        worker = self.worker()
        self.server.lose_response = True
        with self.assertRaises(GitHubError):
            worker.claim()
        with self.assertRaises(ClaimRejected):
            worker.begin_effect('generate', {'source_id': 'source-1'})
        self.assertEqual(self.server.document['commands'][self.command_id]['effects'], {})

    def test_lost_checkpoint_response_is_adopted_by_exact_receipt(self):
        worker = self.worker()
        worker.claim()
        self.server.lose_response = True
        worker.checkpoint('provider', {'provider_job_id': 'task-1'}, phase='STARTED')
        self.assertEqual(self.server.document['commands'][self.command_id]['receipts']['provider']['evidence'],
                         {'provider_job_id': 'task-1'})
        self.assertEqual(len(self.server.writes), 2)

    def test_checkpoint_reconciles_cas_without_overwriting_other_kind(self):
        worker = self.worker()
        worker.claim()
        original = self.server.request
        raced = False

        def conflict_once(method, path, body=None, **kwargs):
            nonlocal raced
            if method == 'PUT' and not raced:
                raced = True
                self.server.document['items'][SHORT.key]['receipts']['other-worker'] = {'artifact_sha256': 'b' * 64}
                self.server.document['revision'] += 1
                self.server.sha = 'f' * 40
            return original(method, path, body, **kwargs)

        self.server.request = conflict_once
        worker.checkpoint('provider', {'provider_job_id': 'task-1'}, phase='STARTED')
        self.assertEqual(self.server.document['items'][SHORT.key]['receipts']['other-worker'], {'artifact_sha256': 'b' * 64})
        self.assertEqual(self.server.document['commands'][self.command_id]['receipts']['provider']['target'], OVERVIEW.to_dict())

    def test_wrong_kind_wrong_run_and_changed_payload_fail_closed(self):
        worker = self.worker()
        worker.claim()
        for impostor in [self.worker(target=SHORT), self.worker('run-2/attempt-1')]:
            with self.assertRaises(ClaimRejected):
                impostor.attach()
        worker.begin_effect('generate', {'source_id': 'source-1'})
        with self.assertRaises(StateInvalid):
            worker.begin_effect('generate', {'source_id': 'source-2'})
        worker.complete_effect('generate', {'provider_job_id': 'task-1'})
        with self.assertRaises(StateInvalid):
            worker.complete_effect('generate', {'provider_job_id': 'task-2'})

    def test_source_edit_preserves_old_receipt_but_prevents_further_side_effects(self):
        worker = self.worker()
        worker.claim()
        worker.begin_effect('generate', {'source_id': 'source-1'})
        snapshot = self.store.load()
        updated = bind_source(snapshot.state, SourceIdentity(DAY, 'article', 'b' * 64), previous_source_key=SOURCE.key, now=NOW)
        self.store.save(snapshot, updated)
        worker.complete_effect('generate', {'provider_job_id': 'task-1'})
        worker.checkpoint('provider', {'provider_job_id': 'task-1'}, phase='STARTED')
        with self.assertRaises(ClaimRejected):
            worker.begin_effect('upload', {'file_sha256': 'c' * 64})
        self.assertEqual(self.server.document['commands'][self.command_id]['effects']['generate']['receipt'], {'provider_job_id': 'task-1'})

    def test_worker_success_is_not_public_product_success(self):
        worker = self.worker()
        worker.claim()
        with self.assertRaises(StateInvalid):
            worker.checkpoint('public', {'verified': True}, phase='PUBLICLY_VERIFIED')
        worker.checkpoint('render', {'file_sha256': 'e' * 64}, phase='OUTPUT_CREATED')
        worker.finish()
        command = self.server.document['commands'][self.command_id]
        self.assertEqual(command['outcome'], 'succeeded')
        self.assertEqual(command['phase'], 'OUTPUT_CREATED')
        self.assertIsNone(self.server.document['items'][OVERVIEW.key]['phase'])

    def test_semantic_progress_ignores_repeated_receipt_and_timestamps(self):
        worker = self.worker()
        worker.claim()
        worker.checkpoint('provider', {'provider_job_id': 'task-1'}, phase='STARTED')
        before = copy.deepcopy(self.server.document)
        worker.now = lambda: '2026-09-18T02:00:00+00:00'
        worker.checkpoint('provider', {'provider_job_id': 'task-1'}, phase='STARTED')
        self.assertEqual(self.server.document, before)
        with self.assertRaises(StateInvalid):
            worker.checkpoint('provider', {'provider_job_id': 'task-2'}, phase='STARTED')

    def test_auth_and_upload_capability_material_never_enters_canonical_receipts(self):
        worker = self.worker()
        worker.claim()
        for payload in [{'refresh_token': 'not-real'}, {'upload': {'session_uri': 'https://example.invalid/capability'}},
                        {'upload_session_uri': 'https://example.invalid/capability'},
                        {'nested': [{'Authorization': 'not-real'}]}]:
            with self.subTest(payload=payload), self.assertRaises(StateInvalid):
                worker.checkpoint('unsafe', payload, phase='STARTED')

    def test_cas_store_refuses_erasing_a_persisted_external_intent(self):
        worker = self.worker()
        worker.claim()
        worker.begin_effect('generate', {'source_id': 'source-1'})
        loaded = self.store.load()
        forged = loaded.state
        forged['commands'][self.command_id]['effects'] = {}
        with self.assertRaises(StateInvalid):
            self.store.save(loaded, forged)

    def recovery_worker(self, worker):
        worker.finish(failure={'class': 'PROVIDER_TIMEOUT'})
        loaded = self.store.load()
        state, new_id = plan_command(loaded.state, OVERVIEW, 'publish', 2, {}, code_sha=CODE, now=NOW)
        self.store.save(loaded, state)
        recovered = WorkerContext(self.store, new_id, 'run-2/attempt-1', OVERVIEW, code_sha=CODE, now=lambda: NOW)
        recovered.claim()
        return recovered

    def test_recovery_command_adopts_prior_effect_instead_of_creating_again(self):
        worker = self.worker()
        worker.claim()
        worker.begin_effect('generate', {'source_id': 'source-1'})
        worker.complete_effect('generate', {'provider_job_id': 'task-1'})
        recovered = self.recovery_worker(worker)
        decision = recovered.begin_effect('generate', {'source_id': 'source-1'})
        self.assertFalse(decision.execute)
        self.assertEqual(decision.receipt, {'provider_job_id': 'task-1'})

    def test_uncertain_prior_creation_survives_command_failure_and_blocks_changed_request(self):
        worker = self.worker()
        worker.claim()
        worker.begin_effect('generate', {'source_id': 'source-1'})
        recovered = self.recovery_worker(worker)
        with self.assertRaises(StateInvalid):
            recovered.begin_effect('generate', {'source_id': 'source-2'})
        self.assertFalse(recovered.begin_effect('generate', {'source_id': 'source-1'}).execute)
        recovered.complete_effect('generate', {'provider_job_id': 'reconciled-task-1'})
        self.assertEqual(recovered.begin_effect('generate', {'source_id': 'source-1'}).receipt,
                         {'provider_job_id': 'reconciled-task-1'})


if __name__ == '__main__':
    unittest.main()
