"""Review, resume and upload must keep the initiating canonical media item."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import jules_video_reviewer as reviewer
from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_exact_video_target as seed
from scripts import kesher_video_reconcile as reconcile
from scripts import prepare_jules_video_evidence as evidence


class ExactItemBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = {'date': '2026-10-05', 'slug': '20-second-hug-relationship-stress',
                       'content_sha256': 'a' * 64}
        self.new = {'id': 'video-new', 'type': 'video_overview', 'source': dict(self.source),
                    'status': 'pending_review', 'technical_verified': True,
                    'fresh_generation_attempt': 2, 'review_notes': {}, 'final_sha256': 'b' * 64}
        self.old = {**copy.deepcopy(self.new), 'id': 'video-old', 'israel_date': '2099-01-01'}
        self.state = {'version': 1, 'items': [self.old, self.new]}
        self.env = {'TARGET_ITEM_ID': 'video-new', 'TARGET_SLUG': self.source['slug'],
                    'TARGET_CONTENT_SHA256': 'a' * 64, 'KESHER_MEDIA_MODE': 'video_overview'}
        self.environment = patch.dict(os.environ, self.env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.save()

    def save(self):
        (self.root / 'state.json').write_text(json.dumps(self.state), encoding='utf-8')

    def test_review_chooses_requested_item_over_old_pending_rejected_or_stale(self):
        for status in ('pending_review', 'rejected', 'superseded'):
            with self.subTest(status=status):
                self.old['status'] = status
                self.save()
                try:
                    _, item = reviewer.load_pending(self.root)
                except reviewer.ReviewError as exc:
                    self.fail(f'Exact requested new item was not selected: {exc}')
                self.assertEqual(item['id'], 'video-new')

    def test_review_missing_explicit_item_never_falls_back(self):
        self.state['items'] = [self.old]
        self.save()
        with self.assertRaises(reviewer.ReviewError):
            reviewer.load_pending(self.root)

    def test_review_without_item_id_refuses_even_one_pending(self):
        self.state['items'] = [self.new]
        self.save()
        os.environ.pop('TARGET_ITEM_ID')
        with self.assertRaises(reviewer.ReviewError):
            reviewer.load_pending(self.root)

    def test_review_identity_mismatches_fail_closed(self):
        self.state['items'] = [self.new]
        for key, wrong in (('TARGET_SLUG', 'other'), ('TARGET_CONTENT_SHA256', 'c' * 64)):
            with self.subTest(key=key), patch.dict(os.environ, {key: wrong}):
                self.save()
                with self.assertRaises(reviewer.ReviewError):
                    reviewer.load_pending(self.root)
        self.new['type'] = 'article_short'
        self.save()
        with self.assertRaises(reviewer.ReviewError):
            reviewer.load_pending(self.root)

    def test_review_restart_preserves_id_despite_list_order(self):
        for rows in ([self.old, self.new], [self.new, self.old]):
            self.state['items'] = rows
            self.save()
            try:
                _, item = reviewer.load_pending(self.root)
            except reviewer.ReviewError as exc:
                self.fail(str(exc))
            self.assertEqual(item['id'], 'video-new')

    def test_active_missing_explicit_item_refuses_instead_of_fresh_generation(self):
        with self.assertRaises(pipeline.PipelineError):
            pipeline.active_item(self.state, item_id='missing')

    def test_active_source_only_multiple_items_refuse(self):
        os.environ.pop('TARGET_ITEM_ID')
        with self.assertRaises(pipeline.PipelineError):
            pipeline.active_item(self.state, slug=self.source['slug'])

    def test_active_exact_item_validates_source_hash_and_kind(self):
        for field, wrong in (('slug', 'other'), ('content_sha256', 'c' * 64)):
            with self.subTest(field=field):
                self.new['source'][field] = wrong
                with self.assertRaises(pipeline.PipelineError):
                    pipeline.active_item(self.state, item_id='video-new')
                self.new['source'] = dict(self.source)
        self.new['type'] = 'article_short'
        with self.assertRaises(pipeline.PipelineError):
            pipeline.active_item(self.state, item_id='video-new')

    def test_missing_item_generation_refuses_without_creating_provider_work(self):
        with patch.object(pipeline, 'auth_preflight'), patch.object(pipeline, 'load_state', return_value=self.state), \
                patch.object(pipeline, 'new_item', side_effect=AssertionError('duplicate item')), \
                patch.object(pipeline, 'article_by_slug', return_value=self.source):
            with self.assertRaises(pipeline.PipelineError):
                pipeline.run_generation(1, None, item_id='missing')
        self.assertEqual(len(self.state['items']), 2)

    def test_exact_seed_multiple_same_source_items_refuse_latest(self):
        with patch.object(seed, 'exact_source', return_value=self.source), \
                patch.object(pipeline, 'load_state', return_value=self.state):
            with self.assertRaises(pipeline.PipelineError):
                seed.seed_exact_target(self.source['slug'], 'a' * 64)

    def test_upload_missing_explicit_item_refuses(self):
        with self.assertRaises(pipeline.PipelineError):
            pipeline.upload_only(item_id='missing', state=self.state)

    def test_upload_missing_id_refuses_timestamp_selection(self):
        os.environ.pop('TARGET_ITEM_ID')
        for item in self.state['items']:
            item.update(status='approved', youtube_id='already-inserted')
        with patch.object(pipeline, 'youtube_access_token', return_value='fake'), \
                patch.object(pipeline, 'verify_authenticated_channel'), \
                patch.object(pipeline, '_verify_and_record_upload'):
            with self.assertRaises(pipeline.PipelineError):
                pipeline.upload_only(slug=self.source['slug'], state=self.state)

    def test_upload_wrong_source_or_kind_refuses_before_external_access(self):
        self.new['status'] = 'approved'
        for field, wrong in (('slug', 'other'), ('content_sha256', 'c' * 64)):
            with self.subTest(field=field):
                self.new['source'][field] = wrong
                with self.assertRaises(pipeline.PipelineError):
                    pipeline.upload_only(item_id='video-new', state=self.state)
                self.new['source'] = dict(self.source)
        self.new['type'] = 'article_short'
        with self.assertRaises(pipeline.PipelineError):
            pipeline.upload_only(item_id='video-new', state=self.state)

    def test_upload_restart_verifies_same_receipt_without_second_insert(self):
        self.new.update(status='uploading', youtube_id='existing-new')
        self.old.update(status='approved', youtube_id='existing-old')
        seen = []
        def record(state, item, token):
            seen.append(item['id'])
        with patch.object(pipeline, 'youtube_access_token', return_value='fake'), \
                patch.object(pipeline, 'verify_authenticated_channel'), \
                patch.object(pipeline, '_verify_and_record_upload', side_effect=record), \
                patch.object(pipeline, 'start_resumable_upload', side_effect=AssertionError('duplicate upload')):
            pipeline.upload_only(item_id='video-new', state=self.state)
            self.state['items'].reverse()
            pipeline.upload_only(item_id='video-new', state=self.state)
        self.assertEqual(seen, ['video-new', 'video-new'])

    def test_recovery_without_item_id_refuses_first_rejected_item(self):
        os.environ.pop('TARGET_ITEM_ID')
        self.old.update(status='rejected', technical_verified=False)
        with patch.object(pipeline, 'load_state', return_value=self.state), \
                patch.object(reconcile, 'published_slugs', return_value={self.source['slug']}):
            with self.assertRaises(pipeline.PipelineError):
                reconcile.prepare_upload(target_slug=self.source['slug'])

    def test_evidence_exports_only_exact_item_with_multiple_pending(self):
        for item in self.state['items']:
            item['frame_paths'] = []
            item['frame_sha256'] = {}
            for path_key, hash_key in (('manifest_path', 'manifest_sha256'), ('transcript_path', 'transcript_sha256'),
                                       ('source_path', 'source_file_sha256'), ('visual_review_path', 'visual_review_sha256')):
                name = f"{item['id']}-{path_key}.txt"
                (self.root / name).write_bytes(name.encode())
                item[path_key] = name
                item[hash_key] = hashlib.sha256(name.encode()).hexdigest()
            for n in range(pipeline.REVIEW_FRAME_COUNT):
                name = f"{item['id']}-frame-{n}.png"
                (self.root / name).write_bytes(name.encode())
                item['frame_paths'].append(name)
                item['frame_sha256'][name] = hashlib.sha256(name.encode()).hexdigest()
        self.save()
        output = self.root / 'evidence'
        try:
            prepared = evidence.prepare(self.root, output)
        except evidence.EvidenceError as exc:
            self.fail(f'Exact evidence could not be exported: {exc}')
        self.assertEqual(prepared['id'], 'video-new')
        self.assertEqual([i['id'] for i in json.loads((output / 'state.json').read_text())['items']], ['video-new'])
        self.assertFalse(any(output.glob('video-old*')))

    def test_short_explicit_identity_still_resumes(self):
        self.new.update(type='article_short', status='generating')
        with patch.dict(os.environ, {'KESHER_MEDIA_MODE': 'article_short'}):
            self.assertEqual(pipeline.active_item(self.state, item_id='video-new')['id'], 'video-new')


if __name__ == '__main__':
    unittest.main()
