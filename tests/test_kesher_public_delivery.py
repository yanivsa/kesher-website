"""Public YouTube verification counterexamples from #857/#863/#864 and M-GAP-01."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_short_pipeline_v4 as short


class PublicMetadataTests(unittest.TestCase):
    def setUp(self):
        self.source = pipeline.source_metadata({
            'id': 'exact', 'slug': 'exact', 'date': '2026-09-17', 'category': 'זוגיות',
            'title': 'כותרת בעברית', 'excerpt': 'תיאור מבוסס על המאמר', 'content': '<p>תוכן המאמר בעברית</p>',
        })
        description = f"{self.source['excerpt']}\n\nלקריאת המאמר המלא:\n{self.source['canonical_url']}\n\nלאתר קשר:\n{pipeline.SITE_URL}"
        self.item = {'type': 'video_overview', 'source': self.source, 'youtube_id': 'exact-video',
                     'youtube_metadata': {'title': self.source['title'], 'description': description, 'tags': ['זוגיות']}}
        self.row = {'id': 'exact-video', 'snippet': {
            'channelId': pipeline.YOUTUBE_CHANNEL_ID, 'title': self.source['title'], 'description': description,
            'tags': ['זוגיות'], 'defaultLanguage': 'he', 'defaultAudioLanguage': 'he'},
            'status': {'privacyStatus': 'public'}, 'processingDetails': {'processingStatus': 'succeeded'}}

    def verify(self, row=None, item=None):
        with patch.object(pipeline, 'youtube_get', return_value={'items': [row or self.row]}):
            return pipeline.verify_public_upload(item or self.item, 'test-only-token', timeout_seconds=0)

    def test_wrong_article_link_cannot_pass_by_containing_site_domain(self):
        row = copy.deepcopy(self.row)
        row['snippet']['description'] = 'תיאור בעברית\nhttps://kesher.saharoni.com/blog/wrong'
        with self.assertRaises(pipeline.PipelineError):
            self.verify(row)

    def test_remote_complete_description_must_match_approved_metadata(self):
        for description in [self.row['snippet']['description'].replace('תיאור מבוסס', 'טענה חדשה'),
                            self.source['canonical_url'], self.row['snippet']['description'].replace('/blog/exact', '/blog/exac')]:
            row = copy.deepcopy(self.row)
            row['snippet']['description'] = description
            with self.subTest(description=description), self.assertRaises(pipeline.PipelineError):
                self.verify(row)

    def test_remote_resource_id_must_match_the_requested_upload(self):
        row = copy.deepcopy(self.row)
        row['id'] = 'different-video'
        with self.assertRaises(pipeline.PipelineError):
            self.verify(row)

    def test_bad_local_metadata_cannot_authorize_equally_bad_remote_metadata(self):
        for description in [f"תיאור\n{pipeline.SITE_URL}/blog/wrong\n{pipeline.SITE_URL}",
                            f"תיאור\n{self.source['canonical_url']}",
                            f"תיאור\n{self.source['canonical_url']}\n{pipeline.SITE_URL}/blog/another"]:
            item, row = copy.deepcopy(self.item), copy.deepcopy(self.row)
            item['youtube_metadata']['description'] = row['snippet']['description'] = description
            with self.subTest(description=description), self.assertRaises(pipeline.PipelineError):
                self.verify(row, item)

    def test_public_receipt_contains_remote_metadata_and_exact_identity(self):
        receipt = self.verify()
        self.assertEqual(receipt['remote_title'], self.row['snippet']['title'])
        self.assertEqual(receipt['remote_description'], self.row['snippet']['description'])
        self.assertEqual(receipt['content_sha256'], self.source['content_sha256'])
        self.assertEqual(receipt['kind'], 'overview')
        self.assertEqual(receipt['verifier_version'], 1)
        self.assertTrue(receipt['verified_at'])

    def test_private_pending_wrong_channel_or_language_are_not_public_completion(self):
        cases = [('status', 'privacyStatus', 'unlisted'), ('processingDetails', 'processingStatus', 'processing'),
                 ('snippet', 'channelId', 'different-channel'), ('snippet', 'defaultAudioLanguage', 'en')]
        for group, key, value in cases:
            row = copy.deepcopy(self.row)
            row[group][key] = value
            with self.subTest(key=key), self.assertRaises(pipeline.PipelineError):
                self.verify(row)

    def test_overview_and_short_have_distinct_source_derived_titles_and_complete_links(self):
        overview = pipeline.new_item(self.source)
        native_short = short.new_item(self.source)
        self.assertNotEqual(overview['youtube_metadata']['title'], native_short['youtube_metadata']['title'])
        self.assertIn(self.source['title'], native_short['youtube_metadata']['title'])
        for item in [overview, native_short]:
            lines = item['youtube_metadata']['description'].splitlines()
            self.assertIn(self.source['canonical_url'], lines)
            self.assertIn(pipeline.SITE_URL, lines)

    def test_long_hebrew_excerpt_does_not_truncate_links_or_exceed_youtube_bytes(self):
        post = {'id': 'ארוך', 'date': '2026-09-17', 'category': 'זוגיות', 'title': 'כותרת',
                'excerpt': 'מילה ' * 4000, 'content': '<p>תוכן בעברית</p>'}
        source = pipeline.source_metadata(post)
        for item in [pipeline.new_item(source), short.new_item(source)]:
            description = item['youtube_metadata']['description']
            self.assertLessEqual(len(description.encode('utf-8')), 5000)
            self.assertIn(source['canonical_url'], description.splitlines())
            self.assertIn(pipeline.SITE_URL, description.splitlines())

    def upload_fixture(self, directory, *, video_id=None, session=None, keep_files=True):
        item = copy.deepcopy(self.item)
        item.update(id='exact-item', status='uploading', technical_verified=True, uploaded=False,
                    final_mp4='final.mp4', manifest_path='manifest.json')
        if video_id is None:
            item.pop('youtube_id', None)
        else:
            item['youtube_id'] = video_id
        if session:
            item['upload_session_uri'] = session
        if keep_files:
            (directory / 'final.mp4').write_bytes(b'technically-validated-fixture')
            (directory / 'manifest.json').write_text('{}')
        pipeline.save_state({'version': 1, 'items': [item]})

    def test_existing_upload_id_is_reverified_without_files_or_another_insert(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(pipeline, 'STATE_DIR', root), patch.object(pipeline, 'STATE_FILE', root / 'state.json'), \
                    patch.object(pipeline, 'youtube_access_token', return_value='test-only-token'), \
                    patch.object(pipeline, 'verify_authenticated_channel'), \
                    patch.object(pipeline, 'youtube_get', return_value={'items': [self.row]}), \
                    patch.object(pipeline, 'start_resumable_upload', side_effect=AssertionError('duplicate insert')), \
                    patch.object(pipeline, 'upload_bytes', side_effect=AssertionError('duplicate bytes')):
                self.upload_fixture(root, video_id='exact-video', keep_files=False)
                pipeline.upload_only(slug='exact', item_id='exact-item')
                self.assertTrue(pipeline.load_state()['items'][0]['uploaded'])

    def test_completed_resumable_session_recovers_its_video_id_without_reupload(self):
        response = SimpleNamespace(status_code=200, headers={}, json=lambda: {'id': 'exact-video'})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(pipeline, 'STATE_DIR', root), patch.object(pipeline, 'STATE_FILE', root / 'state.json'), \
                    patch.object(pipeline, 'youtube_access_token', return_value='test-only-token'), \
                    patch.object(pipeline, 'verify_authenticated_channel'), \
                    patch.object(pipeline, 'youtube_get', return_value={'items': [self.row]}), \
                    patch.object(pipeline.requests, 'put', return_value=response) as resume, \
                    patch.object(pipeline, 'start_resumable_upload', side_effect=AssertionError('duplicate insert')), \
                    patch.object(pipeline, 'upload_bytes', side_effect=AssertionError('duplicate bytes')):
                self.upload_fixture(root, session='https://upload.invalid/session')
                pipeline.upload_only(slug='exact', item_id='exact-item')
                item = pipeline.load_state()['items'][0]
                self.assertEqual(item['youtube_id'], 'exact-video')
                self.assertTrue(item['uploaded'])
                self.assertEqual(resume.call_count, 1)


if __name__ == '__main__':
    unittest.main()
