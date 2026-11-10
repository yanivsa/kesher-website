"""Exact single-item worker projection; durable checkpoints replace newest artifact state."""
import copy
import json
import unittest

from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.media_state import CanonicalMediaState
from scripts.kesher_runtime.sealed import seal, unseal
from scripts.kesher_runtime.state import StateInvalid, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, NOW, OVERVIEW, SHORT, ContentsServer, requested

KEY = 'test-only-key-never-a-real-provider-secret'
URI = 'https://www.googleapis.com/upload/youtube/v3/videos?upload_id=test-only-capability'


class MediaProjectionTests(unittest.TestCase):
    def setUp(self):
        state, self.command_id = requested()
        self.server = ContentsServer(state)
        self.store = GitHubStateStore(self.server, 'owner/repo')
        self.worker = WorkerContext(self.store, self.command_id, '123/1', OVERVIEW, code_sha=CODE, now=lambda: NOW)
        self.worker.claim()
        self.item = {'id': 'exact-overview', 'type': 'video_overview', 'status': 'source_selected',
                     'source': {'date': OVERVIEW.slot, 'slug': OVERVIEW.source.slug,
                                'content_sha256': OVERVIEW.source.content_sha256},
                     'source_id': None, 'task_id': None, 'artifact_id': None}

    def project(self, *, worker=None, item=None):
        return CanonicalMediaState(worker or self.worker, self.item if item is None else item, encryption_key=KEY)

    def test_recovery_loads_only_exact_kind_identity_and_keeps_all_provenance(self):
        state = self.project()
        state.item.update(source_id='source-1', task_id='task-1', artifact_id='task-1', status='generating',
                          signature_provenance={'final_sha256': 'f' * 64},
                          overview_provider_identity={'task_id': 'independent-overview'})
        state.persist()
        restored = self.project()
        self.assertEqual(restored.item['task_id'], 'task-1')
        self.assertEqual(restored.item['signature_provenance'], {'final_sha256': 'f' * 64})
        self.assertEqual(restored.item['overview_provider_identity'], {'task_id': 'independent-overview'})
        self.assertEqual(len(restored['items']), 1)
        self.assertEqual(self.server.document['items'][SHORT.key]['receipts'], {})

    def test_heartbeat_and_repeat_snapshot_never_manufacture_meaningful_progress(self):
        state = self.project()
        state.persist()
        before = copy.deepcopy(self.server.document)
        state.item['updated_at'] = 'tomorrow'
        state.item['last_polled_at'] = 'later'
        state.persist()
        self.assertEqual(self.server.document, before)

    def test_item_replacement_wrong_kind_source_and_duplicate_items_fail_before_write(self):
        for mutation in [lambda state: state.item.update(type='article_short'),
                         lambda state: state.item['source'].update(content_sha256='b' * 64),
                         lambda state: state['items'].append(copy.deepcopy(state.item)),
                         lambda state: state.item.update(id='foreign-item')]:
            with self.subTest(mutation=mutation):
                state = self.project()
                before = len(self.server.writes)
                mutation(state)
                with self.assertRaises(StateInvalid):
                    state.persist()
                self.assertEqual(len(self.server.writes), before)

    def test_completed_receipts_survive_new_recovery_command_without_new_provider_ids(self):
        state = self.project()
        state.item.update(task_id='task-1', artifact_id='task-1', status='generating')
        state.persist()
        self.worker.finish(failure={'class': 'DOWNLOAD_TRANSIENT'})
        loaded = self.store.load()
        proposed, new_id = plan_command(loaded.state, OVERVIEW, 'reconcile', 1, inputs={}, code_sha=CODE, now=NOW)
        self.store.save(loaded, proposed)
        worker = WorkerContext(self.store, new_id, '124/1', OVERVIEW, code_sha=CODE, now=lambda: NOW)
        worker.claim()
        restored = self.project(worker=worker)
        self.assertEqual(restored.item['task_id'], 'task-1')
        restored.item['task_id'] = 'unrelated-global-task'
        with self.assertRaises(StateInvalid):
            restored.persist()

    def test_upload_capability_is_durable_encrypted_and_bound_to_exact_media(self):
        state = self.project()
        state.item.update(status='uploading', upload_session_uri=URI)
        state.persist()
        encoded = json.dumps(self.server.document)
        self.assertNotIn(URI, encoded)
        self.assertNotIn('upload_session_uri', encoded)
        self.assertNotIn(KEY, encoded)
        restored = self.project()
        self.assertEqual(restored.item['upload_session_uri'], URI)
        before = copy.deepcopy(self.server.document)
        restored.persist()
        self.assertEqual(self.server.document, before)
        envelope = seal(URI, KEY, OVERVIEW, repo='owner/repo', purpose='youtube_upload')
        self.assertEqual(unseal(envelope, KEY, OVERVIEW, repo='owner/repo', purpose='youtube_upload'), URI)
        for target, key, purpose in [(SHORT, KEY, 'youtube_upload'), (OVERVIEW, KEY + 'bad', 'youtube_upload'),
                                    (OVERVIEW, KEY, 'notebook_auth')]:
            with self.assertRaises(StateInvalid):
                unseal(envelope, key, target, repo='owner/repo', purpose=purpose)

    def test_existing_upload_and_provider_ids_cannot_be_silently_erased(self):
        state = self.project()
        state.item.update(youtube_id='existing-video', source_id='source-1', status='uploaded')
        state.persist()
        for field in ('youtube_id', 'source_id'):
            restored = self.project()
            restored.item.pop(field)
            with self.assertRaises(StateInvalid):
                restored.persist()

    def test_completed_upload_retires_live_capability_only_after_video_id_is_durable(self):
        state = self.project()
        state.item.update(status='uploading', upload_session_uri=URI)
        state.persist()
        state.item['youtube_id'] = 'existing-video'
        state.persist()
        state.item.pop('upload_session_uri')
        state.persist()
        restored = self.project()
        self.assertEqual(restored.item['youtube_id'], 'existing-video')
        self.assertNotIn('upload_session_uri', restored.item)

    def test_pending_upload_cannot_resume_with_different_render_bytes(self):
        state = self.project()
        state.item.update(final_sha256='f' * 64, status='uploading', upload_session_uri=URI)
        state.persist()
        state.item['final_sha256'] = 'e' * 64
        with self.assertRaises(StateInvalid):
            state.persist()

    def test_core_save_state_uses_canonical_adapter_without_writing_artifact_state(self):
        from unittest.mock import patch
        from scripts import kesher_daily_pipeline as core
        state = self.project()
        with patch.object(core, 'atomic_json_write') as old_write:
            core.save_state(state)
        old_write.assert_not_called()
        self.assertTrue(self.server.document['commands'][self.command_id]['receipts'])

    def test_provider_receipt_precedes_local_snapshot_and_survives_crash(self):
        from unittest.mock import patch
        from scripts import kesher_daily_pipeline as core
        self.item['source']['title'] = 'כותרת בדיקה'
        state = self.project()
        with patch.object(core, 'article_body_for_item', return_value='מקור בדיקה'), \
                patch.object(core, 'run_notebooklm', return_value={'source_id': 'created-source'}) as provider:
            with patch.object(core, 'save_state', side_effect=RuntimeError('crash before local snapshot')):
                with self.assertRaises(RuntimeError):
                    core.add_source(state, state.item)
            restored = self.project()
            core.add_source(restored, restored.item)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(restored.item['source_id'], 'created-source')
        effect = self.server.document['commands'][self.command_id]['effects']['provider_source']
        self.assertEqual(effect['receipt'], {'source_id': 'created-source'})

    def test_uncertain_provider_response_never_repeats_creation(self):
        from unittest.mock import patch
        from scripts import kesher_daily_pipeline as core
        self.item['source']['title'] = 'כותרת בדיקה'
        with patch.object(core, 'article_body_for_item', return_value='מקור בדיקה'), \
                patch.object(core, 'run_notebooklm', side_effect=TimeoutError('response lost')) as provider:
            state = self.project()
            with self.assertRaises(TimeoutError):
                core.add_source(state, state.item)
            restored = self.project()
            with self.assertRaises(StateInvalid):
                core.add_source(restored, restored.item)
        self.assertEqual(provider.call_count, 1)

    def test_concurrent_same_owner_snapshots_cannot_fork_the_recovery_sequence(self):
        from scripts.kesher_runtime.identity import digest
        state = self.project()
        state.persist()
        evidence = copy.deepcopy(state._latest)
        evidence['item']['status'] = 'generating'
        with self.assertRaises(StateInvalid):
            self.worker.checkpoint('media_state_' + digest(evidence)[:40], evidence, phase='STARTED')

    def test_missing_encryption_secret_fails_before_upload_creation_or_intent(self):
        state = CanonicalMediaState(self.worker, self.item)
        from unittest.mock import Mock
        create = Mock(return_value=URI)
        with self.assertRaises(StateInvalid):
            state.external_capability('youtube_session', {'final_sha256': 'f' * 64}, create)
        create.assert_not_called()
        self.assertEqual(self.server.document['commands'][self.command_id]['effects'], {})

    def test_resumable_creation_receipt_is_encrypted_before_local_snapshot(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import Mock, patch
        from scripts import kesher_daily_pipeline as core
        self.item['youtube_metadata'] = {'title': 'כותרת', 'description': 'תיאור', 'tags': ['בדיקה']}
        self.item['final_sha256'] = 'f' * 64
        response = Mock(status_code=200, headers={'Location': URI})
        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / 'video.mp4'
            video.write_bytes(b'media-test-bytes')
            state = self.project()
            with patch.object(core.requests, 'post', return_value=response) as post:
                with patch.object(core, 'save_state', side_effect=RuntimeError('crash after receipt')):
                    with self.assertRaises(RuntimeError):
                        core.start_resumable_upload(state, state.item, 'test-access', video)
                restored = self.project()
                self.assertEqual(core.start_resumable_upload(restored, restored.item, 'test-access', video), URI)
            self.assertEqual(post.call_count, 1)
        self.assertNotIn(URI, json.dumps(self.server.document))
        self.assertNotIn('test-access', json.dumps(self.server.document))


if __name__ == '__main__':
    unittest.main()
