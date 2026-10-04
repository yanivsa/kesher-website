"""Exact Jules request recovery without creating real sessions."""
import copy
import io
import json
import unittest
import urllib.error

from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.state import new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, DAY, NOW, ContentsServer
from scripts.kesher_runtime.jules import Jules, JulesError, acquire_session


REQUEST = {'title': 'Kesher article ' + DAY, 'prompt': 'Exact approved text for ' + DAY,
           'sourceContext': {'source': 'sources/github/yanivsa/kesher-website',
                             'githubRepoContext': {'startingBranch': 'main'}},
           'requirePlanApproval': False, 'automationMode': 'AUTO_CREATE_PR'}


def session(name='sessions/one', **updates):
    # These two fields are input-only in the official Session API.
    row = {key: copy.deepcopy(value) for key, value in REQUEST.items()
           if key not in {'requirePlanApproval', 'automationMode'}}
    return dict(row, name=name, state='QUEUED', **updates)


class JulesServer:
    def __init__(self):
        self.rows = []
        self.creates = 0
        self.lost = False
        self.reject = None
        self.before_create = lambda: None

    def sessions(self):
        return copy.deepcopy(self.rows)

    def get(self, name):
        return copy.deepcopy(next(row for row in self.rows if row['name'] == name))

    def create(self, body):
        self.before_create()
        self.creates += 1
        if self.reject:
            raise self.reject
        row = {key: copy.deepcopy(value) for key, value in body.items()
               if key not in {'requirePlanApproval', 'automationMode'}}
        self.rows.append(dict(row, name='sessions/created', state='QUEUED'))
        if self.lost:
            raise JulesError('TRANSIENT_API', uncertain=True)
        return copy.deepcopy(self.rows[-1])


class JulesSessionsTests(unittest.TestCase):
    def setUp(self):
        self.target = SlotIdentity(DAY)
        state, command = plan_command(new_state(), self.target, 'create_article', 1, {}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state)
        self.store = GitHubStateStore(self.server, 'yanivsa/kesher-website')
        self.worker = WorkerContext(self.store, command, '1/1', self.target, code_sha=CODE, now=lambda: NOW)
        self.worker.claim()
        self.api = JulesServer()

    def test_intent_precedes_create_and_receipt_survives_lost_response(self):
        self.api.lost = True
        self.api.before_create = lambda: self.assertTrue(
            self.server.document['commands'][self.worker.command_id]['effects'])
        result = acquire_session(self.worker, self.api, REQUEST)
        self.assertEqual(result['name'], 'sessions/created')
        self.assertEqual(self.api.creates, 1)
        self.assertEqual(acquire_session(self.worker, self.api, REQUEST)['name'], result['name'])
        self.assertEqual(self.api.creates, 1)

    def test_create_intent_without_server_evidence_never_reposts(self):
        self.worker.begin_effect('jules_create_1', REQUEST)
        for _ in range(2):
            with self.assertRaisesRegex(JulesError, 'JULES_CREATE_UNCERTAIN'):
                acquire_session(self.worker, self.api, REQUEST)
        self.assertEqual(self.api.creates, 0)

    def test_completed_existing_session_is_adopted_instead_of_recreated(self):
        row = session(); row['state'] = 'COMPLETED'; self.api.rows = [row]
        self.assertEqual(acquire_session(self.worker, self.api, REQUEST)['name'], 'sessions/one')
        self.assertEqual(self.api.creates, 0)

    def test_same_title_with_changed_prompt_or_source_blocks_creation(self):
        for field, value in [('prompt', 'Different request'), ('sourceContext', {'source': 'foreign'})]:
            with self.subTest(field=field):
                row = session(); row[field] = value; self.api.rows = [row]
                with self.assertRaisesRegex(JulesError, 'JULES_IDENTITY_MISMATCH'):
                    acquire_session(self.worker, self.api, REQUEST)
        self.assertEqual(self.api.creates, 0)

    def test_two_matching_sessions_never_choose_latest(self):
        self.api.rows = [session(), session('sessions/two')]
        with self.assertRaisesRegex(JulesError, 'JULES_DUPLICATE_SESSIONS'):
            acquire_session(self.worker, self.api, REQUEST)
        self.assertEqual(self.api.creates, 0)

    def test_recovery_under_new_policy_uses_original_durable_request(self):
        acquire_session(self.worker, self.api, REQUEST)
        self.worker.finish(failure={'class': 'TRANSIENT_API'})
        loaded = self.store.load()
        state, command = plan_command(loaded.state, self.target, 'create_article', 2, {}, code_sha='d'*40, now=NOW)
        self.store.save(loaded, state)
        worker = WorkerContext(self.store, command, '2/1', self.target, code_sha='d'*40, now=lambda: NOW)
        worker.claim()
        changed = dict(REQUEST, prompt='Updated policy after code repair')
        self.assertEqual(acquire_session(worker, self.api, changed)['name'], 'sessions/created')
        self.assertEqual(self.api.creates, 1)
        effect = next(iter(self.server.document['commands'][command]['effects'].values()))
        self.assertEqual(effect['request'], REQUEST)

    def test_definite_rejection_can_retry_but_only_within_fixed_budget(self):
        self.api.reject = JulesError('TRANSIENT_API', status=429, uncertain=False)
        for _ in range(3):
            with self.assertRaisesRegex(JulesError, 'TRANSIENT_API'):
                acquire_session(self.worker, self.api, REQUEST)
        with self.assertRaisesRegex(JulesError, 'JULES_CREATE_EXHAUSTED'):
            acquire_session(self.worker, self.api, REQUEST)
        self.assertEqual(self.api.creates, 3)

    def test_bound_session_get_is_rechecked_and_cannot_switch_source(self):
        acquire_session(self.worker, self.api, REQUEST)
        self.api.rows[0]['sourceContext'] = {'source': 'wrong'}
        with self.assertRaisesRegex(JulesError, 'JULES_IDENTITY_MISMATCH'):
            acquire_session(self.worker, self.api, REQUEST)
        self.assertEqual(self.api.creates, 1)


class JulesTransportTests(unittest.TestCase):
    def test_lost_post_is_not_retried_and_exception_contains_no_api_body(self):
        calls = []
        def opener(request, **kwargs):
            calls.append(request)
            raise urllib.error.URLError('sensitive provider response must stay private')
        client = Jules('not-real-key', opener=opener, sleeper=lambda _: None)
        with self.assertRaises(JulesError) as caught:
            client.create(REQUEST)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('sensitive', str(caught.exception))

    def test_all_pages_are_read_and_repeating_token_is_never_absence(self):
        responses = [{'sessions': [session()], 'nextPageToken': 'page two'},
                     {'sessions': [session('sessions/two')]}]
        calls = []
        def opener(request, **kwargs):
            calls.append(request.full_url)
            return io.BytesIO(json.dumps(responses.pop(0)).encode())
        client = Jules('not-real-key', opener=opener)
        self.assertEqual(len(client.sessions()), 2)
        self.assertIn('pageToken=page+two', calls[1])
        responses.extend([{'nextPageToken': 'same'}, {'nextPageToken': 'same'}])
        with self.assertRaisesRegex(JulesError, 'JULES_INVENTORY_INVALID'):
            client.sessions()

    def test_read_retries_are_bounded_and_auth_failure_does_not_retry(self):
        calls, waits = [], []
        def transient(request, **kwargs):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url, 503, 'private', {}, io.BytesIO(b'private'))
        client = Jules('not-real-key', opener=transient, sleeper=waits.append)
        with self.assertRaises(JulesError): client.get('sessions/one')
        self.assertEqual(len(calls), 4)
        self.assertEqual(waits, [1, 2, 4])
        def denied(request, **kwargs):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url, 403, 'private', {}, io.BytesIO(b'private'))
        client._open = denied
        with self.assertRaisesRegex(JulesError, 'AUTH_SCOPE_INVALID'): client.get('sessions/one')
        self.assertEqual(len(calls), 5)


if __name__ == '__main__':
    unittest.main()
