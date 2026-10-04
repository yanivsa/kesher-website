"""A site archive binds hidden publication proof, Functions and every served byte."""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import canonical_json
from scripts.kesher_runtime.state import StateInvalid, bind_source, new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, SOURCE, NOW, ContentsServer


class DeploymentArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.build.mkdir()
        files = {'dist/index.html': b'<html>site</html>', 'dist/blog/article/index.html': b'<html>article</html>',
                 'dist/.well-known/kesher-publication.json': json.dumps({'schema_version': 1, 'deploy_sha': CODE,
                     'articles': {SOURCE.slug: {'identity': SOURCE.to_dict()}}}).encode(),
                 'dist/_headers': b'/*\n  X-Content-Type-Options: nosniff',
                 'dist/_routes.json': b'{"version":1,"include":["/*"],"exclude":[]}',
                 'functions/_worker.bundle': b'compiled multipart worker',
                 'functions/routing.json': b'{"routes":[]}', 'dist/empty.txt': b''}
        for name, data in files.items():
            path = self.build / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        state = bind_source(new_state(), SOURCE, now=NOW)
        state, self.key = plan_command(state, SOURCE, 'deploy_article', 1, {'deploy_sha': CODE}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state)
        self.context = WorkerContext(GitHubStateStore(self.server, 'owner/repo'), self.key, '123/1',
                                     SOURCE, code_sha=CODE, now=lambda: NOW)
        self.context.claim()
        self.metadata = {}
        self.run = {'id': 123, 'run_attempt': 1, 'event': 'workflow_dispatch', 'head_branch': 'main',
                    'head_sha': CODE, 'display_title': 'kesher-command:' + self.key,
                    'path': '.github/workflows/kesher-article-deploy.yml'}
        original = self.server.request
        def api(method, path, body=None, **kwargs):
            if method == 'GET' and path.endswith('/artifacts/71'):
                return copy.deepcopy(self.metadata)
            if method == 'GET' and path.endswith('/runs/123/attempts/1'):
                return copy.deepcopy(self.run)
            if method == 'GET' and '/runs/123/artifacts?' in path:
                return {'total_count': 1, 'artifacts': [copy.deepcopy(self.metadata)]}
            return original(method, path, body, **kwargs)
        self.server.request = api

    def upload(self):
        from scripts.kesher_runtime.deployment_artifact import prepare, sha256_file
        result = prepare(self.context, self.build)
        self.archive = self.root / 'artifact.zip'
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for path in sorted(self.build.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(self.build).as_posix())
        self.metadata = {'id': 71, 'name': result['name'], 'expired': False,
                         'size_in_bytes': self.archive.stat().st_size, 'digest': 'sha256:' + sha256_file(self.archive),
                         'workflow_run': {'id': 123, 'head_sha': CODE, 'head_branch': 'main',
                                          'repository_id': 1, 'head_repository_id': 1}}
        return result

    def download(self, artifact_id, destination):
        self.assertEqual(artifact_id, 71)
        shutil.copyfile(self.archive, destination)

    def test_only_readback_archive_allows_publication_and_restores_hidden_and_function_bytes(self):
        from scripts.kesher_runtime.deployment_artifact import complete, require_archive, restore
        self.upload()
        with self.assertRaises(StateInvalid):
            require_archive(self.context, self.build)
        receipt = complete(self.context, 71, download=self.download)
        self.assertEqual(require_archive(self.context, self.build), receipt)
        destination = self.root / 'restored'
        restore(self.context, destination, download=self.download)
        self.assertEqual(require_archive(self.context, destination), receipt)
        self.assertEqual((destination/'functions/_worker.bundle').read_bytes(), b'compiled multipart worker')
        self.assertTrue((destination/'dist/.well-known/kesher-publication.json').is_file())

    def test_lost_upload_receipt_adopts_existing_id_without_new_archive_request(self):
        from scripts.kesher_runtime.deployment_artifact import recover
        self.upload()
        receipt = recover(self.context, download=self.download)
        self.assertEqual(receipt['artifact_id'], 71)
        self.assertEqual(len(self.server.document['commands'][self.key]['effects']), 1)

    def replacement(self):
        self.context.finish(failure={'class': 'WORKER_FAILED'})
        loaded = self.context.store.load()
        state, key = plan_command(loaded.state, SOURCE, 'deploy_article', 2, {'deploy_sha': CODE}, code_sha=CODE, now=NOW)
        self.context.store.save(loaded, state)
        context = WorkerContext(self.context.store, key, '124/1', SOURCE, code_sha=CODE, now=lambda: NOW)
        context.claim()
        return context

    def test_replacement_adopts_lost_receipt_original_producer_before_rebuilding(self):
        from scripts.kesher_runtime.deployment_artifact import recover, restore
        self.upload()
        context = self.replacement()
        receipt = recover(context, download=self.download)
        self.assertEqual(receipt['artifact_id'], 71)
        self.assertEqual(context.store.load().state['commands'][context.command_id]['effects']
                         ['deployment_artifact_' + CODE[:24]]['request']['run_id'], '123/1')
        restore(context, self.root/'replacement', download=self.download)

    def test_unpublished_archive_intent_from_old_code_cannot_poison_new_main_build(self):
        from scripts.kesher_runtime.deployment_artifact import prepare
        self.upload()
        self.context.finish(failure={'class': 'CODE_CHANGED'})
        loaded = self.context.store.load()
        code = 'd'*40
        state, key = plan_command(loaded.state, SOURCE, 'deploy_article', 2, {'deploy_sha': code}, code_sha=code, now=NOW)
        self.context.store.save(loaded, state)
        context = WorkerContext(self.context.store, key, '125/1', SOURCE, code_sha=code, now=lambda: NOW)
        context.claim()
        path = self.build/'dist/.well-known/kesher-publication.json'
        proof = json.loads(path.read_bytes())
        proof['deploy_sha'] = code
        path.write_text(json.dumps(proof))
        self.assertEqual(prepare(context, self.build)['status'], 'upload')

    def test_confirmed_stopped_producer_without_archive_releases_only_build_not_publication(self):
        from scripts.kesher_runtime.deployment_artifact import prepare, recover
        prepare(self.context, self.build)
        context = self.replacement()
        self.run.update(status='completed', conclusion='failure')
        original = self.server.request
        def absent(method, path, *args, **kwargs):
            if '/runs/123/artifacts?' in path:
                return {'total_count': 0, 'artifacts': []}
            return original(method, path, *args, **kwargs)
        self.server.request = absent
        self.assertIsNone(recover(context, download=self.download))
        effect = context.store.load().state['commands'][context.command_id]['effects']['deployment_artifact_'+CODE[:24]]
        self.assertEqual(effect['receipt']['status'], 'unavailable')
        self.assertEqual(effect['receipt']['producer_run'], '123/1')
        context.finish(failure={'class': 'DEPLOY_ARCHIVE_REBUILD'})
        loaded = context.store.load()
        state, key = plan_command(loaded.state, SOURCE, 'deploy_article', 3, {'deploy_sha': CODE}, code_sha=CODE, now=NOW)
        context.store.save(loaded, state)
        next_context = WorkerContext(context.store, key, '126/1', SOURCE, code_sha=CODE, now=lambda: NOW)
        next_context.claim()
        self.assertEqual(prepare(next_context, self.build)['status'], 'upload')

    def test_crash_before_restore_commit_leaves_no_partial_destination_and_retry_succeeds(self):
        from scripts.kesher_runtime.deployment_artifact import complete, restore
        self.upload()
        complete(self.context, 71, download=self.download)
        destination = self.root/'restore-crash'
        with patch('scripts.kesher_runtime.deployment_artifact.os.replace', side_effect=OSError('killed')):
            with self.assertRaises(OSError):
                restore(self.context, destination, download=self.download)
        self.assertFalse(destination.exists())
        self.assertTrue(restore(self.context, destination, download=self.download))
        self.assertTrue(restore(self.context, destination, download=self.download))

    def test_changed_worker_static_bytes_and_added_file_are_rejected_after_archiving(self):
        from scripts.kesher_runtime.deployment_artifact import complete, require_archive
        self.upload()
        complete(self.context, 71, download=self.download)
        for name in ['functions/_worker.bundle', 'dist/index.html', 'dist/new.html']:
            with self.subTest(name=name):
                path = self.build/name
                original = path.read_bytes() if path.exists() else None
                path.write_bytes(b'changed')
                with self.assertRaises(StateInvalid):
                    require_archive(self.context, self.build)
                path.unlink() if original is None else path.write_bytes(original)

    def test_wrong_source_or_commit_cannot_be_prepared(self):
        from scripts.kesher_runtime.deployment_artifact import prepare
        path = self.build/'dist/.well-known/kesher-publication.json'
        original = json.loads(path.read_bytes())
        for proof in [{**original, 'deploy_sha': 'd'*40}, {**original, 'articles': {}},
                      {**original, 'articles': {SOURCE.slug: {'identity': {**SOURCE.to_dict(), 'content_sha256': 'b'*64}}}}]:
            path.write_text(json.dumps(proof))
            with self.assertRaises(StateInvalid):
                prepare(self.context, self.build)
        self.assertEqual(self.server.document['commands'][self.key]['effects'], {})

    def test_symlink_credentials_and_unexpected_function_file_fail_before_intent(self):
        from scripts.kesher_runtime.deployment_artifact import prepare
        for name in ['dist/.env', 'functions/storage-state.json', 'dist/../credential.txt']:
            path = self.build/name
            path.write_bytes(b'private')
            with self.assertRaises(StateInvalid):
                prepare(self.context, self.build)
            path.unlink()
        (self.build/'dist/link').symlink_to(self.build/'dist/index.html')
        with self.assertRaises(StateInvalid):
            prepare(self.context, self.build)
        self.assertEqual(self.server.document['commands'][self.key]['effects'], {})

    def test_missing_function_bundle_and_hidden_manifest_fail_before_intent(self):
        from scripts.kesher_runtime.deployment_artifact import prepare
        for name in ['functions/_worker.bundle', 'dist/.well-known/kesher-publication.json']:
            path = self.build/name
            original = path.read_bytes()
            path.unlink()
            with self.assertRaises(StateInvalid):
                prepare(self.context, self.build)
            path.write_bytes(original)

    def test_wrong_run_attempt_workflow_service_digest_and_expired_artifact_are_rejected(self):
        from scripts.kesher_runtime.deployment_artifact import complete
        self.upload()
        for target, field, value in [(self.run, 'run_attempt', 2), (self.run, 'path', '.github/workflows/deploy.yml'),
                                     (self.metadata, 'expired', True), (self.metadata, 'digest', 'sha256:'+'0'*64)]:
            old = target[field]
            target[field] = value
            with self.assertRaises(StateInvalid):
                complete(self.context, 71, download=self.download)
            target[field] = old

    def test_extra_duplicate_or_path_escape_archive_entry_cannot_be_restored(self):
        from scripts.kesher_runtime.deployment_artifact import complete, sha256_file
        self.upload()
        original = self.archive.read_bytes()
        for name in ['dist/extra.html', '../escape', 'dist/index.html']:
            self.archive.write_bytes(original)
            with zipfile.ZipFile(self.archive, 'a') as archive:
                archive.writestr(name, b'bad')
            self.metadata.update(size_in_bytes=self.archive.stat().st_size, digest='sha256:'+sha256_file(self.archive))
            with self.assertRaises(StateInvalid):
                complete(self.context, 71, download=self.download)

    def test_manifest_changes_cannot_be_blessed_by_recomputing_service_archive_hash(self):
        from scripts.kesher_runtime.deployment_artifact import complete, sha256_file
        self.upload()
        descriptor = json.loads((self.build/'deployment.json').read_bytes())
        descriptor['files']['dist/index.html']['sha256'] = hashlib.sha256(b'evil').hexdigest()
        (self.build/'deployment.json').write_text(canonical_json(descriptor))
        (self.build/'dist/index.html').write_bytes(b'evil')
        with zipfile.ZipFile(self.archive, 'w') as archive:
            for path in self.build.rglob('*'):
                if path.is_file():
                    archive.write(path, path.relative_to(self.build).as_posix())
        self.metadata.update(size_in_bytes=self.archive.stat().st_size, digest='sha256:'+sha256_file(self.archive))
        with self.assertRaises(StateInvalid):
            complete(self.context, 71, download=self.download)
