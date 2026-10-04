"""Canonical worker executes exact production primitives without global/FIFO selection."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import kesher_daily_pipeline as core
from scripts import kesher_short_pipeline_v4 as short
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import MediaIdentity, SourceIdentity
from scripts.kesher_runtime.media_state import CanonicalMediaState
from scripts.kesher_runtime.media_worker import run_media
from scripts.kesher_runtime.state import StateInvalid, bind_source, new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, NOW, ContentsServer


class MediaWorkerTests(unittest.TestCase):
    def setUp(self):
        self.source = core.source_metadata({'id': 'exact', 'date': '2026-09-17', 'title': 'כותרת',
                                           'category': 'משפחה', 'excerpt': 'תיאור', 'content': '<p>תוכן בעברית</p>'})
        source = SourceIdentity(self.source['date'], self.source['slug'], self.source['content_sha256'])
        target = MediaIdentity(source, 'overview')
        state = bind_source(new_state(), source, now=NOW)
        state, self.command_id = plan_command(state, target, 'publish', 1, inputs={'generation_attempt': '1'}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state)
        self.worker = WorkerContext(GitHubStateStore(self.server, 'owner/repo'), self.command_id, '123/1',
                                    target, code_sha=CODE, now=lambda: NOW)
        self.worker.claim()

    def test_source_change_stops_before_auth_or_generation(self):
        with patch.object(core, 'article_by_slug', return_value={**self.source, 'content_sha256': 'f' * 64}), \
                patch.object(core, 'auth_preflight') as auth:
            with self.assertRaises(StateInvalid):
                run_media(self.worker, encryption_key='test-only-encryption-key-for-fixtures')
        auth.assert_not_called()

    def test_provider_pending_returns_a_bounded_wait_without_upload_or_newest_selection(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(core, 'STATE_DIR', Path(folder)), \
                patch.object(core, 'article_by_slug', return_value=self.source), \
                patch.object(core, 'article_body_for_item', return_value=self.source['body']), \
                patch.object(core, 'auth_preflight'), \
                patch.object(core, 'youtube_access_token', return_value='test-token'), \
                patch.object(core, 'verify_authenticated_channel'), \
                patch.object(core, 'run_notebooklm', side_effect=[{'source_id': 'exact-source'}, {'task_id': 'exact-task'}, {'status': 'processing'}]) as provider, \
                patch.object(core, 'select_newest_unused_article', side_effect=AssertionError('lost identity')), \
                patch.object(core, 'upload_only', side_effect=AssertionError('not ready')):
            result = run_media(self.worker, encryption_key='test-only-encryption-key-for-fixtures')
        self.assertEqual(result.status, 'waiting')
        self.assertEqual(provider.call_count, 3)
        self.assertIn('exact-source', provider.call_args_list[1].args[0])
        self.assertIn('exact-task', provider.call_args_list[2].args[0])
        effects = self.server.document['commands'][self.command_id]['effects']
        self.assertEqual(effects['provider_source']['receipt']['source_id'], 'exact-source')
        self.assertEqual(effects['provider_generation']['receipt']['task_id'], 'exact-task')
        persisted = CanonicalMediaState(self.worker, core.new_item(self.source)).item
        self.assertEqual(persisted['source'], self.source)

    def test_existing_upload_uses_metadata_reconciliation_without_media_files_or_provider_auth(self):
        initial = core.new_item(self.source)
        initial.update(youtube_id='existing-video', status='uploaded', uploaded=True)
        state = CanonicalMediaState(self.worker, initial)
        state.persist()
        with patch.object(core, 'article_by_slug', return_value=self.source), \
                patch.object(core, 'auth_preflight', side_effect=AssertionError('no generation')), \
                patch.object(core, 'youtube_access_token', return_value='test-token'), \
                patch.object(core, 'verify_authenticated_channel'), \
                patch('scripts.kesher_runtime.media_worker.repair_metadata', return_value={'video_id': 'existing-video'}) as repair, \
                patch.object(core, 'upload_only', side_effect=AssertionError('duplicate upload')):
            result = run_media(self.worker, encryption_key='test-only-encryption-key-for-fixtures')
        self.assertEqual(result.status, 'observed_public')
        self.assertEqual(repair.call_args.args[0].item['youtube_id'], 'existing-video')
        self.assertIsNone(self.server.document['items'][self.worker.target.key]['phase'])

    def test_render_must_be_durably_archived_before_upload_can_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def download(state, item):
                raw = root / 'raw.mp4'; raw.write_bytes(b'raw')
                item.update(raw_mp4='raw.mp4', raw_sha256=core.sha256_file(raw), status='downloaded')
                core.save_state(state)
                return raw
            def validate(state, item, raw):
                self.assertEqual(item['task_id'], 'exact-task')
                (root / 'final.mp4').write_bytes(b'final')
                (root / 'manifest.json').write_text('{}')
                item.update(final_mp4='final.mp4', final_sha256=core.sha256_file(root / 'final.mp4'),
                            manifest_path='manifest.json', technical_verified=True, status='pending_review')
                core.save_state(state)
            def upload(*, slug, item_id, state):
                self.assertIsInstance(state, CanonicalMediaState)
                self.assertEqual(slug, self.source['slug'])
                self.assertEqual(item_id, state.item['id'])
                self.assertEqual(state.item['status'], 'approved')
                state.item.update(youtube_id='new-video', uploaded=True, status='uploaded')
                core.save_state(state)
                return 0
            with patch.object(core, 'STATE_DIR', root), patch.object(core, 'article_by_slug', return_value=self.source), \
                    patch.object(core, 'article_body_for_item', return_value=self.source['body']), \
                    patch.object(core, 'auth_preflight'), \
                patch.object(core, 'youtube_access_token', return_value='test-token'), \
                patch.object(core, 'verify_authenticated_channel'), \
                    patch.object(core, 'run_notebooklm', side_effect=[{'source_id': 'exact-source'}, {'task_id': 'exact-task'}, {'status': 'completed'}]), \
                    patch.object(core, 'download_artifact', side_effect=download), \
                    patch.object(core, 'validate_and_manifest', side_effect=validate), \
                    patch.object(core, 'upload_only', side_effect=upload) as uploaded:
                result = run_media(self.worker, encryption_key='test-only-encryption-key-for-fixtures')
        self.assertEqual(uploaded.call_count, 0)
        self.assertEqual(result.status, 'output_ready')
        self.assertIsNone(self.server.document['items'][self.worker.target.key]['phase'])

    def test_voice_rejection_is_durable_and_exact_but_resolution_rejection_is_not_fresh_generation(self):
        for female_ok in (False, True):
            with self.subTest(female_ok=female_ok):
                self.setUp()
                with tempfile.TemporaryDirectory() as folder:
                    root = Path(folder)
                    def download(state, item):
                        raw = root / 'raw.mp4'; raw.write_bytes(b'exact completed provider output')
                        item.update(raw_mp4=raw.name, raw_sha256=core.sha256_file(raw), status='downloaded')
                        state.persist()
                        return raw
                    def reject(state, item, raw):
                        final = root / 'final.mp4'; final.write_bytes(b'rejected render')
                        item.update(final_mp4=final.name, status='rejected', technical_verified=False)
                        state.persist()
                    with patch.object(core, 'STATE_DIR', root), patch.object(core, 'article_by_slug', return_value=self.source), \
                            patch.object(core, 'article_body_for_item', return_value=self.source['body']), \
                            patch.object(core, 'auth_preflight'), patch.object(core, 'youtube_access_token', return_value='test-token'), \
                            patch.object(core, 'verify_authenticated_channel'), \
                            patch.object(core, 'run_notebooklm', side_effect=[{'source_id': 'exact-source'}, {'task_id': 'exact-task'}, {'status': 'completed'}]), \
                            patch.object(core, 'download_artifact', side_effect=download), \
                            patch.object(core, 'validate_and_manifest', side_effect=reject), \
                            patch.object(core, 'validate_female_voice', return_value=(female_ok, 120., 'fixture')), \
                            patch.object(core, 'upload_only', side_effect=AssertionError('rejected output cannot upload')):
                        with self.assertRaises(StateInvalid):
                            run_media(self.worker, encryption_key='test-only-encryption-key-for-fixtures')
                    persisted = CanonicalMediaState(self.worker, core.new_item(self.source)).item
                    self.assertEqual(persisted['status'], 'rejected')
                    if not female_ok:
                        self.assertEqual(persisted['generation_rejection'], {'reason': 'voice', 'attempt': 1,
                            'raw_sha256': core.sha256_file(root / 'raw.mp4'), 'artifact_id': 'exact-task'})
                    else:
                        self.assertNotIn('generation_rejection', persisted)

    def test_non_native_short_is_rejected_before_render_without_changing_provider_identity(self):
        overview = CanonicalMediaState(self.worker, core.new_item(self.source))
        overview.item.update(source_id='overview-source', task_id='overview-task', artifact_id='overview-task', raw_sha256='a'*64)
        overview.persist(); self.worker.finish()
        target = MediaIdentity(self.worker.target.source, 'short')
        store = self.worker.store
        loaded = store.load()
        state, command_id = plan_command(loaded.state, target, 'publish', 1,
            {'generation_attempt': '1'}, code_sha=CODE, now=NOW)
        store.save(loaded, state)
        worker = WorkerContext(store, command_id, '124/1', target, code_sha=CODE, now=lambda: NOW)
        worker.claim()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            def download(state, item):
                raw = root / 'native-short.mp4'; raw.write_bytes(b'landscape provider output')
                item.update(raw_mp4=raw.name, raw_sha256=core.sha256_file(raw), status='downloaded')
                state.persist()
                return raw
            with patch.object(core, 'STATE_DIR', root), patch.object(core, 'article_by_slug', return_value=self.source), \
                    patch.object(core, 'article_body_for_item', return_value=self.source['body']), \
                    patch.object(core, 'auth_preflight'), patch.object(core, 'youtube_access_token', return_value='test-token'), \
                    patch.object(core, 'verify_authenticated_channel'), \
                    patch.object(core, 'run_notebooklm', side_effect=[{'source_id': 'short-source'}, {'task_id': 'short-task'}, {'status': 'completed'}]), \
                    patch.object(core, 'download_artifact', side_effect=download), \
                    patch.object(core, 'ffprobe', return_value={'width': 1280, 'height': 720, 'duration': 20}), \
                    patch.object(short, 'validate_and_manifest', side_effect=AssertionError('must reject before render')), \
                    patch.object(core, 'upload_only', side_effect=AssertionError('must not upload')):
                with self.assertRaisesRegex(StateInvalid, 'PROVIDER_MEDIA_REJECTED'):
                    run_media(worker, encryption_key='test-only-encryption-key-for-fixtures')
            persisted = CanonicalMediaState(worker, short.new_item(self.source)).item
            self.assertEqual(persisted['generation_rejection'], {'reason': 'native_short', 'attempt': 1,
                'raw_sha256': core.sha256_file(root / 'native-short.mp4'), 'artifact_id': 'short-task'})
            self.assertEqual((persisted['source_id'], persisted['task_id']), ('short-source', 'short-task'))


if __name__ == '__main__':
    unittest.main()
