"""Independent remote evidence, never uploaded=True or a green worker run."""
import copy
import unittest

from scripts import kesher_daily_pipeline as core
from scripts.kesher_runtime.identity import MediaIdentity, SourceIdentity, digest
from scripts.kesher_runtime.media_publication import MediaVerificationError, verify_media_publication
from scripts.kesher_runtime.output_artifacts import descriptor
from scripts.kesher_runtime.verification import YOUTUBE_CHANNEL_ID, publication_metadata
from tests.test_media_provenance_contract import bound_short

NOW = '2026-09-22T16:00:00+00:00'


def fixture():
    source = core.source_metadata({'id': 'exact', 'date': '2026-09-22', 'title': 'כותרת מקורית',
        'category': 'משפחה', 'excerpt': 'תיאור בעברית', 'content': '<p>תוכן מלא בעברית</p>'})
    target = MediaIdentity(SourceIdentity(source['date'], source['slug'], source['content_sha256']), 'short')
    item = bound_short(132.0)
    item.update(source=source, youtube_id='abcdefghijk', youtube_metadata=publication_metadata(source, 'short'),
                technical_verified=True, raw_mp4='raw.mp4', final_mp4='final.mp4', manifest_path='manifest.json',
                manifest_sha256='1'*64, render_input_sha256='2'*64)
    overview = {'id': 'overview-1', 'source': source, 'type': 'video_overview', **item['overview_provider_identity']}
    technical = {'schema_version': 1, 'identity': target.to_dict(), 'output_sha256': digest(descriptor(target, item)),
                 'verifier_sha256': '3'*64, 'media': item['media'], 'final_size_bytes': 12345,
                 'raw_sha256': item['raw_sha256'], 'final_sha256': item['final_sha256'],
                 'audio_sha256': item['audio_provenance']['raw_audio_sha256']}
    remote = {'id': item['youtube_id'], 'snippet': {**item['youtube_metadata'], 'channelId': YOUTUBE_CHANNEL_ID,
        'defaultLanguage': 'he', 'defaultAudioLanguage': 'he'},
        'status': {'privacyStatus': 'public', 'uploadStatus': 'processed'},
        'processingDetails': {'processingStatus': 'succeeded'},
        'contentDetails': {'duration': 'PT2M12S'},
        'fileDetails': {'fileSize': '12345', 'durationMs': '132000', 'videoStreams': [
            {'widthPixels': 1080, 'heightPixels': 1920, 'rotation': 'none'}], 'audioStreams': [{'channelCount': 1}]}}
    inventory = {'observed_at': NOW, 'channel_id': YOUTUBE_CHANNEL_ID, 'complete': True, 'videos': [remote]}
    return dict(identity=target, source=source, item=item, overview=overview, technical=technical,
                remote=remote, inventory=inventory, assignments={item['youtube_id']: target.to_dict()}, verified_at=NOW)


class IndependentMediaPublicationTests(unittest.TestCase):
    def test_exact_remote_publication_yields_full_source_kind_receipt(self):
        args = fixture()
        proof = verify_media_publication(**args)
        self.assertEqual(proof['identity'], args['identity'].to_dict())
        self.assertEqual(proof['public_url'], 'https://youtu.be/abcdefghijk')
        self.assertEqual(proof['verified_at'], NOW)
        self.assertEqual(proof['upload_count'], 1)

    def rejects(self, args, code):
        with self.assertRaises(MediaVerificationError) as raised:
            verify_media_publication(**args)
        self.assertEqual(raised.exception.code, code)

    def test_worker_flags_and_metadata_cannot_replace_independent_bytes(self):
        args = fixture(); args['technical'] = {}
        args['item'].update(uploaded=True, status='uploaded', youtube_verification={'verified': True})
        self.rejects(args, 'MEDIA_EVIDENCE_INVALID')

    def test_byte_audit_is_bound_to_every_output_and_exact_kind(self):
        for field, value in [('final_sha256', '0'*64), ('manifest_sha256', '0'*64), ('render_input_sha256', '0'*64)]:
            args = fixture(); args['item'][field] = value
            self.rejects(args, 'MEDIA_EVIDENCE_INVALID')
        args = fixture(); args['technical']['identity']['kind'] = 'overview'
        self.rejects(args, 'MEDIA_EVIDENCE_INVALID')

    def test_same_slug_changed_authoritative_title_is_not_certified_from_item(self):
        args = fixture(); args['source'] = {**args['source'], 'title': 'כותרת אחרת'}
        self.rejects(args, 'SOURCE_IDENTITY_MISMATCH')

    def test_short_must_compare_to_authoritative_overview_not_its_own_claim(self):
        args = fixture(); args['overview']['task_id'] = args['item']['task_id']
        self.rejects(args, 'PROVIDER_IDENTITY_MISMATCH')

    def test_wrong_channel_and_stale_remote_metadata_reject(self):
        for field, value in [('channelId', 'wrong'), ('title', 'wrong'), ('description', 'truncated'),
                             ('defaultLanguage', 'en')]:
            args = fixture(); args['remote']['snippet'][field] = value
            self.rejects(args, 'PUBLIC_METADATA_INVALID')

    def test_processing_visibility_and_missing_video_are_distinct(self):
        for state, code in [('processing', 'PUBLIC_PROCESSING_PENDING'), ('failed', 'YOUTUBE_PROCESSING_FAILED'),
                            ('terminated', 'YOUTUBE_PROCESSING_FAILED')]:
            args = fixture(); args['remote']['processingDetails']['processingStatus'] = state
            self.rejects(args, code)
        args = fixture(); args['remote']['status']['privacyStatus'] = 'unlisted'
        self.rejects(args, 'YOUTUBE_NOT_PUBLIC')
        args = fixture(); args['remote'] = None
        self.rejects(args, 'YOUTUBE_UPLOAD_MISSING')

    def test_remote_uploaded_file_must_match_archived_size_timeline_orientation(self):
        for field, value in [('fileSize', '999'), ('durationMs', '55000'), ('videoStreams', [
            {'widthPixels': 1920, 'heightPixels': 1080}]), ('audioStreams', [])]:
            args = fixture(); args['remote']['fileDetails'][field] = value
            self.rejects(args, 'REMOTE_MEDIA_MISMATCH')
        args = fixture(); args['remote'].pop('fileDetails')
        self.rejects(args, 'REMOTE_MEDIA_UNAVAILABLE')

    def test_youtube_editor_trim_cannot_hide_behind_original_uploaded_file_details(self):
        args = fixture(); args['remote']['contentDetails']['duration'] = 'PT55S'
        self.rejects(args, 'REMOTE_MEDIA_MISMATCH')

    def test_duplicate_even_with_different_title_blocks_public_completion(self):
        args = fixture(); duplicate = copy.deepcopy(args['remote'])
        duplicate['id'] = 'lmnopqrstuv'; duplicate['snippet']['title'] = 'כותרת ישנה'
        args['inventory']['videos'].append(duplicate)
        self.rejects(args, 'DUPLICATE_UPLOAD')

    def test_independently_bound_other_kind_is_not_a_duplicate(self):
        args = fixture(); overview = copy.deepcopy(args['remote']); overview['id'] = 'lmnopqrstuv'
        args['inventory']['videos'].append(overview)
        args['assignments'][overview['id']] = MediaIdentity(args['identity'].source, 'overview').to_dict()
        self.assertEqual(verify_media_publication(**args)['upload_count'], 1)

    def test_incomplete_stale_or_foreign_inventory_cannot_claim_exactly_once(self):
        for field, value in [('complete', False), ('observed_at', '2026-09-22T15:00:00+00:00'), ('channel_id', 'wrong')]:
            args = fixture(); args['inventory'][field] = value
            self.rejects(args, 'YOUTUBE_INVENTORY_UNAVAILABLE')

    def test_missing_bound_id_in_complete_inventory_never_infers_public_success(self):
        args = fixture(); args['inventory']['videos'] = []
        self.rejects(args, 'YOUTUBE_INVENTORY_UNAVAILABLE')

    def test_match_youtube_metadata_preserves_item_metadata_and_full_tags(self):
        from scripts.kesher_runtime.verification import match_youtube_metadata
        args = fixture()
        item = args['item']
        # Simulate item where source had youtube_metadata stripped but item['youtube_metadata'] has tags
        item['type'] = 'video_overview'
        meta = publication_metadata(args['source'], 'overview')
        meta['tags'] = ['משפחה', 'זוגיות', 'תקשורת ומריבות']
        item['source'] = {k: v for k, v in args['source'].items() if k not in {'body', 'youtube_metadata'}}
        item['youtube_metadata'] = meta
        item['youtube_id'] = 'exact-vid-id'
        row = {
            'id': 'exact-vid-id',
            'snippet': {
                'channelId': YOUTUBE_CHANNEL_ID,
                'title': meta['title'],
                'description': meta['description'],
                'tags': meta['tags'],
                'defaultLanguage': 'he',
                'defaultAudioLanguage': 'he',
            }
        }
        evidence = match_youtube_metadata(item, row)
        self.assertEqual(evidence['remote_tags'], item['youtube_metadata']['tags'])


if __name__ == '__main__':
    unittest.main()
