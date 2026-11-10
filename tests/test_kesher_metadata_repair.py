"""Metadata repair mutates an existing exact video; never invokes upload/generation."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts import kesher_daily_pipeline as core
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import MediaIdentity, SourceIdentity
from scripts.kesher_runtime.media_state import CanonicalMediaState
from scripts.kesher_runtime.state import StateInvalid, bind_source, new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from scripts.kesher_runtime.youtube import repair_metadata
from tests.test_kesher_canonical_state import CODE, NOW, ContentsServer
from tests import test_kesher_public_delivery as public_fixtures


class MetadataRepairTests(unittest.TestCase):
    def setUp(self):
        fixture = public_fixtures.PublicMetadataTests()
        fixture.setUp()
        self.expected = copy.deepcopy(fixture.row)
        self.remote = copy.deepcopy(self.expected)
        self.remote['snippet']['description'] = 'תיאור ישן וקישור מקוצר'
        self.remote['snippet']['categoryId'] = '27'
        self.item = copy.deepcopy(fixture.item)
        self.item.update(id='existing-item', status='uploaded', uploaded=True)
        self.source = SourceIdentity(fixture.source['date'], fixture.source['slug'], fixture.source['content_sha256'])
        target = MediaIdentity(self.source, 'overview')
        state = bind_source(new_state(), self.source, now=NOW)
        state, self.command_id = plan_command(state, target, 'repair_metadata', 1, inputs={}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state)
        store = GitHubStateStore(self.server, 'owner/repo')
        worker = WorkerContext(store, self.command_id, '123/1', target, code_sha=CODE, now=lambda: NOW)
        worker.claim()
        self.state = CanonicalMediaState(worker, self.item)
        self.state.persist()

    def get(self, *args, **kwargs):
        return {'items': [copy.deepcopy(self.remote)]}

    def put(self, url, **kwargs):
        self.assertEqual(url, 'https://www.googleapis.com/youtube/v3/videos')
        self.assertEqual(kwargs['params'], {'part': 'snippet'})
        self.assertEqual(kwargs['json']['id'], 'exact-video')
        self.assertEqual(kwargs['json']['snippet']['categoryId'], '27')
        self.remote['snippet'].update(kwargs['json']['snippet'])
        return SimpleNamespace(status_code=200, json=lambda: copy.deepcopy(self.remote))

    def test_repair_fetches_remote_metadata_and_preserves_video_id_category_and_visibility(self):
        with patch.object(core, 'youtube_get', side_effect=self.get), \
                patch.object(core.requests, 'put', side_effect=self.put) as put, \
                patch.object(core.requests, 'post', side_effect=AssertionError('must not insert')):
            receipt = repair_metadata(self.state, core, 'test-token')
        self.assertEqual(put.call_count, 1)
        self.assertEqual(self.remote['status'], {'privacyStatus': 'public'})
        self.assertEqual(receipt['remote_description'], self.expected['snippet']['description'])
        self.assertEqual(self.state.item['youtube_id'], 'exact-video')
        self.assertNotEqual(self.server.document['items'][self.state.context.target.key]['phase'], 'PUBLICLY_VERIFIED')

    def test_lost_update_response_is_adopted_from_remote_read_without_second_write(self):
        def lost(url, **kwargs):
            self.put(url, **kwargs)
            raise TimeoutError('accepted update, response lost')
        with patch.object(core, 'youtube_get', side_effect=self.get), \
                patch.object(core.requests, 'put', side_effect=lost) as put:
            with self.assertRaises(TimeoutError):
                repair_metadata(self.state, core, 'test-token')
            receipt = repair_metadata(self.state, core, 'test-token')
        self.assertEqual(put.call_count, 1)
        self.assertEqual(receipt['video_id'], 'exact-video')
        self.assertIsNotNone(self.server.document['commands'][self.command_id]['effects']['youtube_metadata']['receipt'])

    def test_wrong_channel_cannot_be_corrected_by_overwriting_metadata(self):
        self.remote['snippet']['channelId'] = 'foreign-channel'
        with patch.object(core, 'youtube_get', side_effect=self.get), \
                patch.object(core.requests, 'put') as put:
            with self.assertRaises(StateInvalid):
                repair_metadata(self.state, core, 'test-token')
        put.assert_not_called()

    def test_unchanged_remote_metadata_does_not_consume_another_mutation(self):
        self.remote['snippet'].update(self.expected['snippet'])
        with patch.object(core, 'youtube_get', side_effect=self.get), \
                patch.object(core.requests, 'put') as put:
            repair_metadata(self.state, core, 'test-token')
            repair_metadata(self.state, core, 'test-token')
        put.assert_not_called()


if __name__ == '__main__':
    unittest.main()
