"""Crash recovery restores exact declared output without creating another upload."""
import copy
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import kesher_daily_pipeline as core
from scripts.kesher_runtime.identity import canonical_json
from scripts.kesher_runtime.media_state import CanonicalMediaState
from scripts.kesher_runtime.output_artifacts import (artifact_name, complete_bundle, prepare_bundle,
    recover_bundle, require_bundle, restore_bundle, sha256_file, download_actions_artifact)
from scripts.kesher_runtime.state import StateInvalid, plan_command
from scripts.kesher_runtime.media_worker import run_media
from scripts.kesher_runtime.worker import WorkerContext
from tests import test_kesher_media_worker as worker_fixture


class OutputArtifactTests(unittest.TestCase):
    def setUp(self):
        worker_fixture.MediaWorkerTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'output'
        self.root.mkdir()
        self.item = core.new_item(self.source)
        self.item.update(technical_verified=True, source_id='source-1', task_id='task-1', artifact_id='task-1')
        for path_key, hash_key, name, data in [('raw_mp4', 'raw_sha256', 'raw.mp4', b'provider-output'),
                                              ('final_mp4', 'final_sha256', 'final.mp4', b'rendered-output'),
                                              ('manifest_path', 'manifest_sha256', 'manifest.json', b'{"proof":"fixture"}')]:
            (self.root / name).write_bytes(data)
            self.item[path_key], self.item[hash_key] = name, sha256_file(self.root / name)
        self.state = CanonicalMediaState(self.worker, self.item)
        self.state.persist()
        self.bundle = Path(self.temp.name) / 'bundle'
        self.archive = Path(self.temp.name) / 'archive.zip'
        self.metadata = {}
        self.run = {'id': 123, 'event': 'workflow_dispatch', 'display_title': 'kesher-command:' + self.command_id,
                    'head_sha': self.worker.code_sha, 'head_branch': 'main'}
        original = self.server.request
        def api(method, path, body=None, **kwargs):
            if method == 'GET' and path.endswith('/artifacts/71'):
                return copy.deepcopy(self.metadata)
            if method == 'GET' and path.endswith('/runs/123'):
                return copy.deepcopy(self.run)
            if method == 'GET' and '/runs/123/artifacts?' in path:
                return {'artifacts': [copy.deepcopy(self.metadata)]}
            return original(method, path, body, **kwargs)
        self.server.request = api

    def upload(self):
        result = prepare_bundle(self.worker, self.item, self.root, self.bundle)
        self.assertEqual(result['status'], 'upload')
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for path in sorted(self.bundle.rglob('*')):
                if path.is_file():
                    archive.write(path, str(path.relative_to(self.bundle)))
        self.metadata = {'id': 71, 'name': result['name'], 'expired': False,
                         'size_in_bytes': self.archive.stat().st_size,
                         'digest': 'sha256:' + sha256_file(self.archive),
                         'workflow_run': {'id': 123, 'head_sha': self.worker.code_sha, 'head_branch': 'main',
                                          'repository_id': 1, 'head_repository_id': 1}}
        return result

    def download(self, artifact_id, destination):
        self.assertEqual(artifact_id, 71)
        shutil.copyfile(self.archive, destination)

    def test_no_upload_permission_until_remote_archive_readback_then_crash_restore(self):
        with self.assertRaisesRegex(StateInvalid, 'OUTPUT_NOT_DURABLE'):
            require_bundle(self.worker, self.item, self.root)
        self.upload()
        with self.assertRaisesRegex(StateInvalid, 'OUTPUT_NOT_DURABLE'):
            require_bundle(self.worker, self.item, self.root)
        receipt = complete_bundle(self.worker, 71, download=self.download)
        self.assertEqual(require_bundle(self.worker, self.item, self.root), receipt)
        shutil.rmtree(self.root)
        self.assertTrue(restore_bundle(self.worker, self.item, self.root, download=self.download))
        self.assertEqual(require_bundle(self.worker, self.item, self.root), receipt)
        self.assertEqual((self.root / 'final.mp4').read_bytes(), b'rendered-output')
        self.assertFalse((self.root / 'state.json').exists())
        self.assertEqual(prepare_bundle(self.worker, self.item, self.root, self.bundle)['status'], 'archived')

    def test_publish_after_archive_never_reenters_generation_and_uses_exact_restored_item(self):
        self.upload()
        complete_bundle(self.worker, 71, download=self.download)
        shutil.rmtree(self.root)
        restore_bundle(self.worker, self.item, self.root, download=self.download)
        def upload(*, slug, item_id, state):
            self.assertEqual(slug, self.source['slug'])
            self.assertEqual(item_id, self.item['id'])
            self.assertEqual((self.root / state.item['final_mp4']).read_bytes(), b'rendered-output')
            state.item.update(youtube_id='restored-video', status='uploaded', uploaded=True)
            state.persist()
        with patch.object(core, 'STATE_DIR', self.root), patch.object(core, 'article_by_slug', return_value=self.source), \
                patch.object(core, 'auth_preflight', side_effect=AssertionError('publish cannot enter provider')), \
                patch.object(core, 'ffprobe', return_value={'duration': 100}), \
                patch('scripts.kesher_e2e_delivery_guard._signature_verified', return_value=True), \
                patch.object(core, 'upload_only', side_effect=upload) as uploader:
            result = run_media(self.worker, phase='publish', encryption_key='test-only-encryption-key-for-fixtures')
        self.assertEqual(result.status, 'uploaded')
        self.assertEqual(uploader.call_count, 1)

    def test_publish_without_archive_refuses_before_auth_or_any_external_call(self):
        with patch.object(core, 'STATE_DIR', self.root), patch.object(core, 'article_by_slug', return_value=self.source), \
                patch.object(core, 'youtube_access_token', side_effect=AssertionError('no auth before archive')), \
                patch.object(core, 'upload_only', side_effect=AssertionError('no upload before archive')):
            with self.assertRaisesRegex(StateInvalid, 'OUTPUT_NOT_DURABLE'):
                run_media(self.worker, phase='publish', encryption_key='test-only-encryption-key-for-fixtures')

    def test_lost_service_response_adopts_only_exact_producer_run_and_name(self):
        self.upload()
        retry = prepare_bundle(self.worker, self.item, self.root, self.bundle)
        self.assertEqual(retry['status'], 'uncertain')
        saved_name = self.metadata['name']
        self.metadata['name'] = 'kesher-output-nearest-other-run'
        self.assertIsNone(recover_bundle(self.worker, download=self.download))
        self.metadata['name'] = saved_name
        receipt = recover_bundle(self.worker, download=self.download)
        self.assertEqual(receipt['artifact_id'], 71)
        self.assertEqual(len(self.server.document['commands'][self.command_id]['effects']), 1)

    def test_next_recovery_command_restores_prior_producer_without_a_new_archive(self):
        self.upload()
        complete_bundle(self.worker, 71, download=self.download)
        self.worker.finish(failure={'class': 'WORKER_FAILED'})
        loaded = self.worker.store.load()
        proposed, command_id = plan_command(loaded.state, self.worker.target, 'reconcile', 1,
            {'generation_attempt': '1'}, code_sha=self.worker.code_sha, now=self.worker.now())
        self.worker.store.save(loaded, proposed)
        recovery = WorkerContext(self.worker.store, command_id, '456/1', self.worker.target,
                                 code_sha=self.worker.code_sha, now=self.worker.now)
        recovery.claim()
        shutil.rmtree(self.root)
        restore_bundle(recovery, self.item, self.root, download=self.download)
        result = prepare_bundle(recovery, self.item, self.root, Path(self.temp.name) / 'never-created')
        self.assertEqual(result['status'], 'archived')
        self.assertEqual(result['receipt']['artifact_id'], 71)
        self.assertFalse((Path(self.temp.name) / 'never-created').exists())

    def test_authenticated_download_never_forwards_token_to_archive_host(self):
        calls = []
        class Response:
            def __init__(self, status, headers=None):
                self.status_code, self.headers = status, headers or {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def iter_content(self, **kwargs):
                yield b'archive-fixture'
        def get(url, **kwargs):
            calls.append((url, kwargs))
            return Response(302, {'Location': 'https://archive.example.test/exact'}) if len(calls) == 1 else Response(200)
        with patch('requests.get', side_effect=get):
            download_actions_artifact('owner/repo', 'test-only-token', 71, Path(self.temp.name) / 'downloaded')
        self.assertIn('Authorization', calls[0][1]['headers'])
        self.assertNotIn('headers', calls[1][1])
        self.assertFalse(calls[0][1]['allow_redirects'])

    def test_wrong_producer_code_or_fork_cannot_certify_archive(self):
        self.upload()
        original = copy.deepcopy(self.metadata)
        for overrides in [{'head_sha': 'f' * 40}, {'id': 124}, {'head_repository_id': 2}]:
            self.metadata = copy.deepcopy(original)
            self.metadata['workflow_run'].update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(StateInvalid):
                complete_bundle(self.worker, 71, download=self.download)
        self.assertIsNone(self.server.document['commands'][self.command_id]['effects']['output_artifact']['receipt'])

    def test_changed_download_and_wrong_kind_never_restore_or_replace_files(self):
        self.upload()
        complete_bundle(self.worker, 71, download=self.download)
        self.archive.write_bytes(self.archive.read_bytes() + b'changed')
        target = Path(self.temp.name) / 'restored'
        with self.assertRaises(StateInvalid):
            restore_bundle(self.worker, self.item, target, download=self.download)
        self.assertFalse(target.exists())
        with self.assertRaises(StateInvalid):
            require_bundle(self.worker, {**self.item, 'type': 'article_short'}, self.root)

    def test_archive_extra_path_or_duplicate_is_rejected_even_with_correct_service_digest(self):
        self.upload()
        original = self.archive.read_bytes()
        for name in ['../outside', 'files/final.mp4', 'state.json']:
            self.archive.write_bytes(original)
            with zipfile.ZipFile(self.archive, 'a') as archive:
                archive.writestr(name, b'undesired')
            self.metadata.update(size_in_bytes=self.archive.stat().st_size, digest='sha256:' + sha256_file(self.archive))
            with self.subTest(name=name), self.assertRaises(StateInvalid):
                complete_bundle(self.worker, 71, download=self.download)

    def test_symlink_and_changed_output_never_acquire_upload_permission(self):
        self.upload()
        complete_bundle(self.worker, 71, download=self.download)
        (self.root / 'final.mp4').write_bytes(b'new-render')
        with self.assertRaises(StateInvalid):
            require_bundle(self.worker, self.item, self.root)
        original = self.root / 'final.mp4'
        original.unlink()
        original.symlink_to(self.root / 'raw.mp4')
        with self.assertRaises(StateInvalid):
            require_bundle(self.worker, self.item, self.root)

    def test_prepare_declares_only_output_files_never_auth_or_canonical_state(self):
        (self.root / 'state.json').write_text('{"token":"not-an-actual-secret"}')
        (self.root / 'cookies.json').write_text('[]')
        self.upload()
        with zipfile.ZipFile(self.archive) as zipped:
            self.assertEqual(set(zipped.namelist()), {'bundle.json', 'files/raw.mp4', 'files/final.mp4', 'files/manifest.json'})

    def test_expired_archive_and_conflicting_local_file_preserve_existing_output(self):
        self.upload()
        complete_bundle(self.worker, 71, download=self.download)
        self.metadata['expired'] = True
        with self.assertRaises(StateInvalid):
            restore_bundle(self.worker, self.item, self.root, download=self.download)
        self.metadata['expired'] = False
        (self.root / 'final.mp4').write_bytes(b'unrelated')
        with self.assertRaises(StateInvalid):
            restore_bundle(self.worker, self.item, self.root, download=self.download)
        self.assertEqual((self.root / 'final.mp4').read_bytes(), b'unrelated')


if __name__ == '__main__':
    unittest.main()
