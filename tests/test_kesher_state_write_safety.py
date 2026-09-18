"""Historical controller boundary regressions: no stale overwrite or blind POST retry."""
import base64
import copy
import json
import unittest
import urllib.error
from unittest.mock import patch

from scripts import kesher_content_controller as controller


class StateServer(controller.GitHubClient):
    """Contents API model with real compare-and-swap behavior, no network."""

    def __init__(self):
        super().__init__('owner/repo', 'test-only-token')
        self.document = {'schema_version': 5, 'cycle': '2026-09-17', 'status': 'article_live'}
        self.sha = 'observed-1'
        self.writes = []
        self.conflict = False

    def request(self, method, url, body=None, **kwargs):
        if '/git/ref/' in url:
            return {'object': {'sha': 'ref-1'}}
        if method == 'GET':
            return {'sha': self.sha, 'encoding': 'base64',
                    'content': base64.b64encode(json.dumps(self.document).encode()).decode()}
        self.writes.append(copy.deepcopy(body))
        if self.conflict or body.get('sha') != self.sha:
            raise controller.ControllerError('GITHUB_HTTP_409: stale state revision')
        self.document = json.loads(base64.b64decode(body['content']))
        self.sha = f'written-{len(self.writes)}'
        return {'content': {'sha': self.sha}}


class StateWriteSafetyTests(unittest.TestCase):
    def test_stale_controller_cannot_overwrite_newer_observation(self):
        client = StateServer()
        stale = client.load_controller_state()
        client.document['status'] = 'publicly_verified'
        client.sha = 'concurrent-writer-2'
        stale['status'] = 'generating'
        with self.assertRaisesRegex(controller.ControllerError, '409'):
            client.save_controller_state(stale)
        self.assertEqual(client.document['status'], 'publicly_verified')
        self.assertEqual(len(client.writes), 1)
        self.assertEqual(client.writes[0]['sha'], 'observed-1')

    def test_cas_conflict_does_not_rebind_same_stale_payload_to_new_sha(self):
        client = StateServer()
        state = client.load_controller_state()
        client.conflict = True
        with patch.object(controller.time, 'sleep'), self.assertRaises(controller.ControllerError):
            client.save_controller_state(state)
        self.assertEqual(len(client.writes), 1)

    def test_successful_second_write_uses_first_write_receipt(self):
        client = StateServer()
        state = client.load_controller_state()
        state['status'] = 'provider_pending'
        client.save_controller_state(state)
        state['status'] = 'output_created'
        client.save_controller_state(state)
        self.assertEqual([write['sha'] for write in client.writes], ['observed-1', 'written-1'])
        self.assertEqual(client.document['status'], 'output_created')

    def test_save_without_an_observed_revision_fails_closed(self):
        client = StateServer()
        with self.assertRaisesRegex(controller.ControllerError, 'STATE_NOT_LOADED'):
            client.save_controller_state({'cycle': '2026-09-17', 'status': 'complete'})
        self.assertEqual(client.writes, [])

    def test_lost_dispatch_response_is_not_blindly_retried(self):
        client = controller.GitHubClient('owner/repo', 'test-only-token')
        with patch.object(controller.urllib.request, 'urlopen', side_effect=urllib.error.URLError('response lost')) as request:
            with patch.object(controller.time, 'sleep'), self.assertRaises(controller.ControllerError):
                client.dispatch('kesher-daily-video.yml', {'operation': 'full'})
        self.assertEqual(request.call_count, 1, 'An accepted POST with a lost response may not create a second workflow')

    def test_transient_get_remains_bounded_and_retryable(self):
        client = controller.GitHubClient('owner/repo', 'test-only-token')
        with patch.object(controller.urllib.request, 'urlopen', side_effect=urllib.error.URLError('temporary network')) as request:
            with patch.object(controller.time, 'sleep'), self.assertRaises(controller.ControllerError):
                client.main_sha()
        self.assertEqual(request.call_count, 4)


if __name__ == '__main__':
    unittest.main()
