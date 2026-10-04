import copy
import unittest
from unittest.mock import Mock

from scripts.kesher_runtime.media_observer import YouTubeInventory, observe_media, upload_assignments
from scripts.kesher_runtime.media_publication import MediaVerificationError
from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.state import bind_source, new_state
from scripts.kesher_runtime.verification import YOUTUBE_CHANNEL_ID
from tests.test_kesher_media_publication import NOW, fixture


class YouTubeInventoryTests(unittest.TestCase):
    def test_complete_inventory_paginates_channel_uploads_and_binds_exact_channel(self):
        calls = []
        def get(resource, params):
            calls.append((resource, params))
            if resource == 'channels':
                return {'items': [{'id': YOUTUBE_CHANNEL_ID, 'contentDetails': {'relatedPlaylists': {'uploads': 'uploads'}}}]}
            if resource == 'playlistItems':
                ids = ['second'] if 'pageToken' in params else ['first']
                return {'items': [{'contentDetails': {'videoId': key}} for key in ids],
                        **({} if 'pageToken' in params else {'nextPageToken': 'next'})}
            return {'items': [{'id': key, 'snippet': {'channelId': YOUTUBE_CHANNEL_ID}} for key in params['id'].split(',')]}
        result = YouTubeInventory(get).read(now=NOW)
        self.assertTrue(result['complete'])
        self.assertEqual([row['id'] for row in result['videos']], ['first', 'second'])
        self.assertEqual([resource for resource, _ in calls], ['channels', 'playlistItems', 'playlistItems', 'videos'])
        self.assertIn('fileDetails', calls[-1][1]['part'])

    def test_missing_resource_duplicate_page_and_wrong_channel_fail_closed(self):
        for broken in ('missing', 'cycle', 'wrong_channel'):
            def get(resource, params):
                if resource == 'channels':
                    return {'items': [{'id': 'wrong' if broken == 'wrong_channel' else YOUTUBE_CHANNEL_ID,
                        'contentDetails': {'relatedPlaylists': {'uploads': 'uploads'}}}]}
                if resource == 'playlistItems':
                    return {'items': [{'contentDetails': {'videoId': 'one'}}], **({'nextPageToken': 'cycle'} if broken == 'cycle' else {})}
                return {'items': []}
            with self.subTest(broken=broken), self.assertRaises(MediaVerificationError):
                YouTubeInventory(get).read(now=NOW)


def canonical_state(args):
    state = bind_source(new_state(), args['identity'].source, now=NOW)
    for kind, item in [('short', args['item']), ('overview', args['overview'])]:
        identity = {**args['identity'].to_dict(), 'kind': kind}
        evidence = {'sequence': 1, 'item': copy.deepcopy(item), 'capabilities': {}}
        state['commands'][kind] = {'target': identity, 'receipts': {
            'media_state_' + digest(evidence)[:40]: {'evidence': evidence}}, 'effects': {}}
    return state


class MediaObserverTests(unittest.TestCase):
    def test_archive_wait_and_retirement_are_observed_separately_from_provider_generation(self):
        from scripts.kesher_runtime.output_artifacts import descriptor
        args = fixture()
        args['item'].pop('youtube_id')
        state = canonical_state(args)
        request = {'run_id': '123/1', 'output': descriptor(args['identity'], args['item'])}
        effect = {'request': request, 'request_sha256': digest(request), 'receipt': None}
        state['commands']['short']['effects']['output_artifact'] = effect
        inventory = {**args['inventory'], 'videos': []}
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result['failure_class'], 'OUTPUT_ARCHIVE_PENDING')
        effect['receipt'] = {'status': 'unavailable', 'producer_run': '123/1', 'request_sha256': digest(request)}
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result['failure_class'], 'OUTPUT_ARCHIVE_REBUILD')

    def test_changed_render_cannot_hide_exhausted_archive_attempts(self):
        from scripts.kesher_runtime.output_artifacts import descriptor
        args = fixture()
        args['item'].pop('youtube_id')
        state = canonical_state(args)
        for index in range(3):
            output = descriptor(args['identity'], args['item'])
            output['files']['final.mp4'] = str(index)*64
            request = {'run_id': f'{123+index}/1', 'output': output}
            state['commands'][f'archive{index}'] = {'target': args['identity'].to_dict(), 'receipts': {},
                'effects': {'output_artifact': {'request': request, 'request_sha256': digest(request),
                    'receipt': {'status': 'unavailable', 'producer_run': request['run_id'], 'request_sha256': digest(request)}}}}
        result = observe_media(state, args['identity'], args['source'], inventory={**args['inventory'], 'videos': []}, now=NOW, audit=Mock())
        self.assertEqual(result['failure_class'], 'OUTPUT_ARCHIVE_ATTEMPTS_EXHAUSTED')

    def test_unresolved_legacy_upload_or_pending_capability_cannot_become_absence(self):
        args = fixture(); state = bind_source(new_state(), args['identity'].source, now=NOW)
        inventory = {**args['inventory'], 'videos': []}
        state['migration']['observed_youtube_ids'] = {'known-history': [{'target': args['identity'].to_dict()}]}
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result['failure_class'], 'LEGACY_EVIDENCE_UNRESOLVED')
        state['migration'] = {}
        state['quarantine'] = [{'target': args['identity'].to_dict(), 'failure_class': 'LEGACY_UPLOAD_CAPABILITY_REQUIRES_SEALING'}]
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result['failure_class'], 'LEGACY_EVIDENCE_UNRESOLVED')

    def test_unresolved_targeted_source_claim_blocks_its_source_without_guessing_a_date(self):
        args = fixture(); state = bind_source(new_state(), args['identity'].source, now=NOW)
        inventory = {**args['inventory'], 'videos': []}
        state['quarantine'] = [{'failure_class': 'LEGACY_TARGETED_SOURCE_UNRESOLVED',
            'source_claim': {'slug': args['source']['slug'], 'content_sha256': args['source']['content_sha256']}}]
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result.get('failure_class'), 'LEGACY_EVIDENCE_UNRESOLVED')
        state['quarantine'][0]['source_claim']['content_sha256'] = 'f' * 64
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result['status'], 'absent')

    def test_unbound_legacy_stage_claim_blocks_only_its_known_slot_and_slug(self):
        args = fixture(); state = bind_source(new_state(), args['identity'].source, now=NOW)
        inventory = {**args['inventory'], 'videos': []}
        state['quarantine'] = [{'failure_class': 'LEGACY_SOURCE_UNRESOLVED',
            'slot': args['source']['date'], 'slug': None, 'stages': {'short': {'artifact_id': 'existing'}}}]
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result.get('failure_class'), 'LEGACY_EVIDENCE_UNRESOLVED')
        state['quarantine'][0]['slot'] = '2026-01-01'
        result = observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=Mock())
        self.assertEqual(result['status'], 'absent')

    def test_absence_requires_fresh_complete_inventory_before_authorizing_creation(self):
        args = fixture(); state = bind_source(new_state(), args['identity'].source, now=NOW)
        audit = Mock(side_effect=AssertionError('No output exists'))
        observe = lambda inventory: observe_media(state, args['identity'], args['source'], inventory=inventory, now=NOW, audit=audit)
        self.assertEqual(observe({**args['inventory'], 'videos': []})['status'], 'absent')
        self.assertEqual(observe({})['status'], 'unknown')
        conflict = observe(args['inventory'])
        self.assertEqual(conflict['failure_class'], 'DUPLICATE_UPLOAD')
        audit.assert_not_called()

    def test_existing_video_is_observed_without_calling_worker_or_provider(self):
        args = fixture(); state = canonical_state(args)
        audit = Mock(return_value=args['technical'])
        result = observe_media(state, args['identity'], args['source'], inventory=args['inventory'], now=NOW, audit=audit)
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['technical_evidence'], args['technical'])
        audit.assert_called_once()

    def test_lost_api_read_cannot_turn_existing_upload_into_absence(self):
        args = fixture(); state = canonical_state(args)
        result = observe_media(state, args['identity'], args['source'], inventory=None, now=NOW, audit=Mock())
        self.assertEqual(result['status'], 'unknown')

    def test_published_invalid_output_requires_repair_without_regeneration(self):
        args = fixture(); state = canonical_state(args)
        audit = Mock(side_effect=MediaVerificationError('MEDIA_EVIDENCE_INVALID'))
        result = observe_media(state, args['identity'], args['source'], inventory=args['inventory'], now=NOW, audit=audit)
        self.assertEqual(result['failure_class'], 'PUBLISHED_MEDIA_INVALID')

    def test_one_youtube_id_cannot_be_assigned_to_both_kinds(self):
        args = fixture(); state = canonical_state(args)
        state['commands']['overview']['receipts'][next(iter(state['commands']['overview']['receipts']))]['evidence']['item']['youtube_id'] = args['item']['youtube_id']
        with self.assertRaises(MediaVerificationError):
            upload_assignments(state)


if __name__ == '__main__':
    unittest.main()
