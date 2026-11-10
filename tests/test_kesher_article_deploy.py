"""One Pages creation request; uncertain responses recover the exact deployment."""
import copy
import unittest

from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.state import StateInvalid
from tests import test_kesher_deployment_artifact as artifact_tests
from tests.test_kesher_canonical_state import CODE


class PagesFixture:
    account_id = '1'*32
    project_name = 'kesher-website'
    project_id = '41773648-4870-407a-b868-5f05f2a2da57'

    def __init__(self, context):
        self.context = context
        self.rows = []
        self.calls = []
        self.canonical = None
        self.lose_response = False
        self.skip_create = False
        self.config = {'date': '2026-05-15', 'flags': []}

    def project(self):
        return {'id': self.project_id, 'name': self.project_name, 'production_branch': 'main',
                'compatibility': self.config, 'canonical_deployment': copy.deepcopy(self.canonical)}

    def inventory(self):
        return copy.deepcopy(self.rows)

    def deployment(self, key):
        return copy.deepcopy(next(row for row in self.rows if row['id'] == key))

    def upload_assets(self, root):
        self.calls.append('assets')
        return {'/index.html': 'a'*32}

    def create(self, request, root, manifest):
        from scripts.kesher_runtime.cloudflare_pages import PagesError
        effects = self.context.store.load().state['commands'][self.context.command_id]['effects']
        assert any(effect['request'] == request for effect in effects.values()), 'POST preceded durable intent'
        self.calls.append('create')
        if not self.skip_create:
            row = {'id': f'{len(self.rows)+1:08x}-1234-4234-8234-123456789abc', 'environment': 'production',
                   'project_name': self.project_name, 'url': 'https://12345678.kesher-website.pages.dev',
                   'branch': 'main', 'commit_sha': request['code_sha'], 'marker': request['marker'],
                   'stage': 'deploy', 'status': 'success', 'is_skipped': False,
                   'created_on': '2026-09-17T20:00:01Z'}
            self.rows.append(row)
            self.canonical = row
        if self.lose_response:
            raise PagesError('DEPLOY_CREATE_UNCERTAIN')
        return None  # A malformed accepted response is deliberately not authority.


class DeployTests(unittest.TestCase):
    upload = artifact_tests.DeploymentArtifactTests.upload
    download = artifact_tests.DeploymentArtifactTests.download

    def setUp(self):
        artifact_tests.DeploymentArtifactTests.setUp(self)
        from scripts.kesher_runtime.deployment_artifact import complete
        self.upload()
        complete(self.context, 71, download=self.download)
        self.pages = PagesFixture(self.context)
        self.current = CODE
        self.main = lambda: self.current

    def publish(self):
        from scripts.kesher_runtime.article_deploy import publish
        return publish(self.context, self.pages, self.build, read_main=self.main)

    def test_route_uses_admitted_canonical_deployment_workflow(self):
        from scripts.kesher_runtime.outbox import workflow_for
        self.assertEqual(workflow_for(self.context.store.load().state['commands'][self.key]), 'kesher-article-deploy.yml')

    def test_lost_accepted_or_malformed_response_is_adopted_by_exact_remote_identity(self):
        self.pages.lose_response = True
        result = self.publish()
        self.assertEqual(result['status'], 'deployed')
        self.assertEqual(result['deployment_id'], self.pages.rows[0]['id'])
        self.assertEqual(result['build_sha256'], self.context.store.load().state['commands'][self.key]
                         ['effects']['deployment_artifact_' + CODE[:24]]['request']['build_sha256'])
        self.publish()
        self.assertEqual(self.pages.calls.count('create'), 1)
        self.assertNotIn('PUBLICLY_VERIFIED', str(result))

    def test_uncertain_absence_never_creates_again(self):
        self.pages.skip_create = self.pages.lose_response = True
        first = self.publish()
        self.assertEqual(first['status'], 'waiting')
        self.assertEqual(first['failure_class'], 'DEPLOY_CREATE_UNCERTAIN')
        self.publish()
        self.assertEqual(self.pages.calls.count('create'), 1)

    def test_stale_main_cannot_start_asset_upload_or_deploy(self):
        self.current = 'b'*40
        with self.assertRaisesRegex(StateInvalid, 'CODE_CHANGED'):
            self.publish()
        self.assertEqual(self.pages.calls, [])

    def test_main_changes_during_asset_upload_prevents_creation(self):
        original = self.pages.upload_assets
        def assets(root):
            self.current = 'b'*40
            return original(root)
        self.pages.upload_assets = assets
        with self.assertRaisesRegex(StateInvalid, 'CODE_CHANGED'):
            self.publish()
        self.assertEqual(self.pages.calls, ['assets'])

    def test_changed_compatibility_or_project_refuses_publication(self):
        self.pages.config['date'] = '2026-09-01'
        with self.assertRaisesRegex(StateInvalid, 'DEPLOY_CONFIG_CHANGED'):
            self.publish()
        self.assertEqual(self.pages.calls, [])

    def test_known_deployment_is_observed_without_artifact_bytes_or_new_main_write(self):
        self.publish()
        import shutil
        shutil.rmtree(self.build)
        self.current = 'f'*40
        result = self.publish()
        self.assertEqual(result['status'], 'deployed')
        self.assertEqual(self.pages.calls, ['assets', 'create'])

    def test_same_sha_wrong_marker_is_never_adopted(self):
        self.pages.skip_create = self.pages.lose_response = True
        self.publish()
        self.pages.rows.append({'id': 'wrong', 'commit_sha': CODE, 'marker': 'unrelated',
                                'environment': 'production', 'branch': 'main'})
        self.assertEqual(self.publish()['status'], 'waiting')
        self.assertEqual(self.pages.calls.count('create'), 1)

    def test_duplicate_marker_conflict_cannot_be_selected_by_latest_timestamp(self):
        self.publish()
        duplicate = {**self.pages.rows[0], 'id': '87654321-1234-4234-8234-123456789abc'}
        self.pages.rows.append(duplicate)
        with self.assertRaisesRegex(StateInvalid, 'DEPLOY_DUPLICATE'):
            self.publish()

    def test_finished_but_noncanonical_deployment_is_not_reported_as_current(self):
        self.publish()
        self.pages.canonical = {**self.pages.rows[0], 'id': 'different'}
        result = self.publish()
        self.assertEqual(result['status'], 'superseded')
        self.assertEqual(self.pages.calls.count('create'), 1)

    def test_confirmed_failed_creation_can_retry_same_bytes(self):
        self.publish()
        self.pages.rows[0]['status'] = 'failure'
        self.pages.canonical = None
        result = self.publish()
        self.assertEqual(result['status'], 'deployed')
        self.assertEqual(self.pages.calls.count('create'), 2)

    def test_new_runner_restores_original_archive_before_permitted_retry(self):
        from scripts.kesher_runtime.article_deploy import initialize
        import shutil
        self.publish()
        self.pages.rows[0]['status'] = 'failure'
        self.pages.canonical = None
        self.context = artifact_tests.DeploymentArtifactTests.replacement(self)
        self.pages.context = self.context
        shutil.rmtree(self.build)
        result = initialize(self.context, self.pages, self.build, download=self.download)
        self.assertEqual(result['status'], 'archived')
        self.assertTrue((self.build/'functions/_worker.bundle').is_file())
        self.assertEqual(self.publish()['status'], 'deployed')
        self.assertEqual(self.pages.calls.count('create'), 2)
        self.pages.rows[1]['status'] = 'failure'
        self.pages.canonical = None
        result = self.publish()
        self.assertEqual(result['failure_class'], 'DEPLOY_ATTEMPTS_EXHAUSTED')
        self.assertEqual(self.pages.calls.count('create'), 2)

    def test_auth_rejection_is_classified_as_definite_failure(self):
        from scripts.kesher_runtime.cloudflare_pages import PagesError
        def reject(request, root, manifest):
            self.pages.calls.append('create')
            raise PagesError('DEPLOY_AUTH_REJECTED')
        self.pages.create = reject
        result = self.publish()
        self.assertEqual(result['failure_class'], 'DEPLOY_AUTH_REJECTED')
        self.assertEqual(result['status'], 'failed')


class PagesTransportTests(unittest.TestCase):
    def test_every_server_error_is_uncertain_without_a_second_post(self):
        from scripts.kesher_runtime.cloudflare_pages import PagesClient, PagesError
        from types import SimpleNamespace
        for status in (500, 501, 502, 503, 504, 507, 520, 599):
            with self.subTest(status=status):
                calls = []
                def send(*args, **kwargs):
                    calls.append(kwargs)
                    return SimpleNamespace(status_code=status)
                client = PagesClient('1'*32, 'key', send=send)
                with self.assertRaises(PagesError) as caught:
                    client.request('POST', '/deployments', data={})
                self.assertEqual(caught.exception.failure_class, 'DEPLOY_CREATE_UNCERTAIN')
                self.assertEqual(len(calls), 1)

    def test_redirect_is_ambiguous_and_never_permission_to_repeat_creation(self):
        from scripts.kesher_runtime.cloudflare_pages import PagesClient, PagesError
        from types import SimpleNamespace
        calls = []
        def send(*args, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status_code=303)
        client = PagesClient('1'*32, 'key', send=send)
        with self.assertRaises(PagesError) as caught:
            client.request('POST', '/deployments', data={})
        self.assertEqual(caught.exception.failure_class, 'DEPLOY_CREATE_UNCERTAIN')
        self.assertEqual(len(calls), 1)

    def test_transport_does_not_retry_or_redirect_creation_and_never_logs_response_secrets(self):
        from scripts.kesher_runtime.cloudflare_pages import PagesClient, PagesError
        class Response:
            status_code = 503
            def json(self):
                return {'success': False, 'errors': [{'message': 'secret-canary'}]}
        calls = []
        def send(method, url, **kwargs):
            calls.append((method, url, kwargs))
            return Response()
        client = PagesClient('1'*32, 'private-api-key', send=send, sleeper=lambda n: None)
        with self.assertRaises(PagesError) as caught:
            client.request('POST', '/deployments', data={'branch': 'main'})
        self.assertEqual(len(calls), 1)
        self.assertFalse(calls[0][2]['allow_redirects'])
        self.assertNotIn('secret-canary', str(caught.exception))
        self.assertNotIn('private-api-key', str(caught.exception))

    def test_incomplete_or_duplicate_paginated_inventory_never_means_absent(self):
        from scripts.kesher_runtime.cloudflare_pages import PagesClient, PagesError
        client = PagesClient('1'*32, 'key')
        row = {'id': '12345678-1234-4234-8234-123456789abc', 'project_name': 'kesher-website',
               'environment': 'production', 'is_skipped': False,
               'created_on': '2026-09-17T20:00:01Z', 'url': 'https://12345678.kesher-website.pages.dev',
               'deployment_trigger': {'metadata': {'branch': 'main', 'commit_hash': CODE, 'commit_message': 'message'}},
               'latest_stage': {'name': 'deploy', 'status': 'success'}, 'env_vars': {'SECRET': {'value': 'canary'}}}
        response = {'success': True, 'result': [row], 'result_info': {'page': 1, 'per_page': 25,
                      'count': 1, 'total_count': 2, 'total_pages': 1}}
        client.request = lambda *a, **k: copy.deepcopy(response)
        with self.assertRaises(PagesError):
            client.inventory()
        response['result_info']['total_count'] = 1
        safe = client.inventory()
        self.assertNotIn('canary', str(safe))
        self.assertNotIn('env_vars', str(safe))
