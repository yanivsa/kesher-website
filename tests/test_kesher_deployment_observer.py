import copy
import unittest

from tests import test_kesher_article_deploy as deploy_tests
from tests.test_kesher_canonical_state import CODE
from scripts.kesher_runtime.state import StateInvalid


class DeploymentObservationTests(unittest.TestCase):
    setUp = deploy_tests.DeployTests.setUp
    upload = deploy_tests.DeployTests.upload
    download = deploy_tests.DeployTests.download
    publish = deploy_tests.DeployTests.publish

    def observe(self):
        from scripts.kesher_runtime.deployment_observer import read_deployment
        return read_deployment(self.context.store.load().state, self.pages, self.server, 'owner/repo', CODE)

    def test_remote_canonical_id_and_immutable_archive_are_both_required(self):
        self.publish()
        result = self.observe()
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['evidence']['provider'], 'cloudflare_pages')
        self.assertEqual(result['evidence']['deployment_id'], self.pages.rows[0]['id'])
        self.metadata['digest'] = 'sha256:'+'e'*64
        self.assertNotEqual(self.observe()['status'], 'verified')

    def test_contradictory_canonical_skip_or_url_cannot_verify_deployment(self):
        self.publish()
        for change in ({'is_skipped': True}, {'url': 'https://other.kesher-website.pages.dev'}):
            self.pages.canonical = {**self.pages.rows[0], **change}
            with self.subTest(change=change):
                self.assertNotEqual(self.observe()['status'], 'verified')

    def test_pending_observation_commands_do_not_consume_second_creation(self):
        from scripts.kesher_runtime.controller import reconcile
        from scripts.kesher_runtime.worker import WorkerContext
        from tests.test_kesher_autonomous_controller import observed, publication, later
        create = self.pages.create
        def active(*args):
            create(*args)
            self.pages.rows[-1]['status'] = 'active'
        self.pages.create = active
        self.assertEqual(self.publish()['failure_class'], 'DEPLOY_PENDING')
        for index in (1, 2):
            self.context.checkpoint('execution_result', {'status': 'waiting', 'failure_class': 'DEPLOY_PENDING'}, phase='STARTED')
            self.context.finish()
            when = later(index*4000)
            if index == 2:
                self.pages.rows[0]['status'] = 'failure'
            entry = publication(overview='verified', short='verified')
            entry['article'] = self.observe()
            loaded = self.context.store.load()
            result = reconcile(loaded.state, observed(entry, now=when), now=when)
            self.assertIsNotNone(result.command_id, 'Pending observation is not a Pages creation attempt')
            self.context.store.save(loaded, result.state)
            self.context = WorkerContext(self.context.store, result.command_id, f'{123+index}/1', self.context.target,
                                         code_sha=CODE, now=lambda when=when: when)
            self.context.claim()
            self.pages.context = self.context
            self.publish()
        self.assertEqual(self.pages.calls.count('create'), 2)

    def test_worker_failure_after_accepted_create_does_not_hide_actual_deployment(self):
        self.publish()
        state = self.server.document
        command = state['commands'][self.key]
        for key, effect in command['effects'].items():
            if key.startswith('pages_create_'):
                effect['receipt'] = None
        command['outcome'] = 'failed'
        command['failure'] = {'class': 'WORKER_FAILED'}
        self.assertEqual(self.observe()['status'], 'verified')

    def test_no_intent_or_noncanonical_same_sha_never_becomes_deployment_proof(self):
        self.assertEqual(self.observe()['status'], 'pending')
        self.publish()
        self.pages.canonical = {**self.pages.rows[0], 'id': 'another'}
        self.assertNotEqual(self.observe()['status'], 'verified')

    def test_uncertain_prior_revision_is_not_reported_as_permission_for_new_deployment(self):
        from scripts.kesher_runtime.deployment_observer import read_deployment
        self.pages.skip_create = self.pages.lose_response = True
        self.publish()
        result = read_deployment(self.context.store.load().state, self.pages, self.server, 'owner/repo', 'e'*40)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(result['failure_class'], 'DEPLOY_PREDECESSOR_UNCERTAIN')

    def test_wrong_artifact_receipt_request_is_rejected(self):
        self.publish()
        state = self.server.document
        request = next(effect['request'] for name, effect in state['commands'][self.key]['effects'].items()
                       if name.startswith('pages_create_'))
        request['artifact']['request_sha256'] = 'b'*64
        # Direct function input still must reject tampering even without the store schema check.
        from scripts.kesher_runtime.deployment_observer import read_deployment
        with self.assertRaises(StateInvalid):
            read_deployment(copy.deepcopy(state), self.pages, self.server, 'owner/repo', CODE)
