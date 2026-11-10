"""Lost provider responses are matched by exact intent, never nearest/newest task."""
import asyncio
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.media_state import CanonicalMediaState
from scripts.kesher_runtime.provider import bind_generation_prompt, probe_generation, probe_source, reconcile_provider
from scripts.kesher_runtime.state import StateInvalid
from tests import test_kesher_media_state as media_fixtures


class ProviderRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = media_fixtures.MediaProjectionTests()
        self.fixture.setUp()
        self.state = self.fixture.project()
        self.worker = self.fixture.worker

    def test_prompt_correlates_exact_provider_source_and_kind_without_time_based_adoption(self):
        self.state.item['source_id'] = 'provider-source'
        a = bind_generation_prompt(self.state, self.state.item, 'הנחיות', 'explainer')
        self.assertEqual(a, bind_generation_prompt(self.state, self.state.item, 'הנחיות', 'explainer'))
        self.state.item['source_id'] = 'other-provider-source'
        self.assertNotEqual(a, bind_generation_prompt(self.state, self.state.item, 'הנחיות', 'explainer'))

    def test_source_probe_requires_exact_title_and_indexed_content(self):
        import hashlib
        request = {'notebook_id': 'notebook', 'title': 'exact-marker',
                   'body_normalized_sha256': hashlib.sha256('מקור מלא'.encode()).hexdigest()}
        client = SimpleNamespace(sources=SimpleNamespace(
            list=AsyncMock(return_value=[SimpleNamespace(id='wrong', title='nearby'), SimpleNamespace(id='right', title='exact-marker')]),
            get_fulltext=AsyncMock(return_value=SimpleNamespace(source_id='right', title='exact-marker', content='מקור\n מלא'))))
        self.assertEqual(asyncio.run(probe_source(client, request)), {'source_id': 'right'})
        client.sources.get_fulltext.return_value.content = 'תוכן אחר'
        with self.assertRaises(StateInvalid):
            asyncio.run(probe_source(client, request))
        client.sources.list.return_value.append(SimpleNamespace(id='duplicate', title='exact-marker'))
        with self.assertRaises(StateInvalid):
            asyncio.run(probe_source(client, request))

    def test_artifact_probe_matches_full_prompt_and_rejects_duplicate_matches(self):
        import hashlib
        prompt = 'בקשה מדויקת עם מזהה'
        request = {'notebook_id': 'notebook', 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
        artifacts = [SimpleNamespace(id='newest-but-wrong', kind='video', generation_prompt='אחר'),
                     SimpleNamespace(id='exact-task', kind='video', generation_prompt=prompt)]
        client = SimpleNamespace(artifacts=SimpleNamespace(list=AsyncMock(return_value=artifacts)))
        self.assertEqual(asyncio.run(probe_generation(client, request)), {'task_id': 'exact-task', 'artifact_id': 'exact-task'})
        artifacts.append(SimpleNamespace(id='duplicate', kind='video', generation_prompt=prompt))
        with self.assertRaises(StateInvalid):
            asyncio.run(probe_generation(client, request))

    def test_uncertain_effect_is_recovered_without_new_creation(self):
        request = {'notebook_id': 'notebook', 'title': 'marker', 'body_sha256': 'a' * 64}
        self.worker.begin_effect('provider_source', request)
        calls = []
        def observe(name, observed_request):
            calls.append((name, observed_request))
            return {'source_id': 'already-created'}
        self.assertTrue(reconcile_provider(self.state, observe))
        self.assertEqual(calls, [('provider_source', request)])
        self.assertEqual(self.state.item['source_id'], 'already-created')
        self.assertEqual(self.state.item['status'], 'source_added')
        self.assertFalse(self.worker.begin_effect('provider_source', request).execute)

    def test_absent_or_pending_provider_result_does_not_authorize_new_creation(self):
        self.worker.begin_effect('provider_source', {'notebook_id': 'notebook', 'title': 'marker'})
        self.assertFalse(reconcile_provider(self.state, lambda *_: None))
        self.assertIsNone(self.state.item.get('source_id'))
        effect = self.fixture.server.document['commands'][self.fixture.command_id]['effects']['provider_source']
        self.assertIsNone(effect['receipt'])

    def test_known_receipt_rehydrates_item_without_another_remote_probe(self):
        self.worker.begin_effect('provider_source', {'notebook_id': 'notebook', 'title': 'marker'})
        self.worker.complete_effect('provider_source', {'source_id': 'durable-source'})
        def no_probe(*_):
            raise AssertionError('known receipt needs no remote lookup')
        self.assertTrue(reconcile_provider(self.state, no_probe))
        self.assertEqual(self.state.item['source_id'], 'durable-source')


if __name__ == '__main__':
    unittest.main()
