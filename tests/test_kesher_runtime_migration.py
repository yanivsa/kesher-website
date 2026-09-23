"""Legacy evidence is imported explicitly; timestamps never choose a winner."""
import copy
import unittest

from scripts.kesher_runtime.identity import MediaIdentity, digest
from scripts.kesher_runtime.media_state import snapshots
from scripts.kesher_runtime.migration import prepare_migration
from scripts.kesher_runtime.state import StateInvalid, validate_state
from tests.test_kesher_media_publication import NOW, fixture


def inputs():
    args = fixture(); item = copy.deepcopy(args['item']); source = args['source']
    item['source'].pop('body')
    controller = {'schema_version': 5, 'cycle': source['date'], 'status': 'complete',
        'article': {'slug': source['slug'], 'published_date': source['date'], 'quality_content_sha256': source['content_sha256']},
        'long_video': {}, 'short': {'item_id': item['id'], 'youtube_id': item['youtube_id'], 'attempt_count': 55}, 'backlog': []}
    return args, dict(controller=controller, controller_sha='a'*40, main_sha='b'*40,
        sources=[source], artifacts=[{'artifact_id': 7, 'archive_sha256': 'c'*64, 'run_id': '123/1', 'items': [item]}], now=NOW)


class RuntimeMigrationTests(unittest.TestCase):
    def test_exact_historical_git_source_preserves_old_upload_without_replacing_current_binding(self):
        from scripts.kesher_runtime.provider import text_hash
        from scripts.kesher_runtime.identity import SourceIdentity
        args, params = inputs()
        current = copy.deepcopy(args['source']); current['body'] += '\nתוכן חדש'
        current['content_sha256'] = text_hash(current['body'])
        params['sources'] = [current]
        historical = {'source': args['source'], 'commit_sha': 'd'*40, 'blob_sha': 'e'*40}
        state = prepare_migration(**params, historical_sources=[historical])
        active = SourceIdentity(current['date'], current['slug'], current['content_sha256'])
        self.assertEqual(state['slots'][active.slot]['source_key'], active.key)
        self.assertEqual(snapshots(state, MediaIdentity(active, 'short')), [])
        old = snapshots(state, args['identity'])
        self.assertEqual(old[0]['item']['youtube_id'], args['item']['youtube_id'])
        self.assertEqual(old[0]['legacy_import']['source_git_origin'],
                         {'commit_sha': 'd'*40, 'blob_sha': 'e'*40, 'path': 'src/data/posts.json'})

    def test_live_upload_capability_is_sealed_for_exact_identity_and_duplicate_copies_reuse_it(self):
        from scripts.kesher_runtime.sealed import seal, unseal
        args, params = inputs()
        uri = 'https://upload.example.test/resume/private-test-capability'
        params['artifacts'][0]['items'][0]['upload_session_uri'] = uri
        params['artifacts'].append(copy.deepcopy(params['artifacts'][0]))
        calls = []
        def sealer(value, target):
            calls.append(target)
            return seal(value, 'local-test-key-with-enough-length', target, repo='owner/repo', purpose='youtube_upload')
        state = prepare_migration(**params, capability_sealer=sealer)
        history = snapshots(state, args['identity'])
        self.assertEqual(len(history), 1)
        self.assertNotIn(uri, str(state))
        envelope = history[0]['capabilities'][history[0]['item']['upload_capability_sha256']]
        self.assertEqual(unseal(envelope, 'local-test-key-with-enough-length', args['identity'], repo='owner/repo', purpose='youtube_upload'), uri)
        self.assertEqual(calls, [args['identity']])

    def test_missing_sealer_quarantines_exact_pending_target_without_leaking_capability(self):
        args, params = inputs()
        item = params['artifacts'][0]['items'][0]
        item['upload_session_uri'] = 'https://upload.example.test/private-test-capability'
        state = prepare_migration(**params)
        self.assertEqual(snapshots(state, args['identity']), [])
        self.assertNotIn('private-test-capability', str(state))
        self.assertTrue(any(row.get('target') == args['identity'].to_dict() and
                            row['failure_class'] == 'LEGACY_UPLOAD_CAPABILITY_REQUIRES_SEALING' for row in state['quarantine']))

    def test_next_worker_checkpoint_extends_imported_history_without_replacing_it(self):
        from scripts.kesher_runtime.github import GitHubStateStore
        from scripts.kesher_runtime.media_state import CanonicalMediaState
        from scripts.kesher_runtime.state import plan_command
        from scripts.kesher_runtime.worker import WorkerContext
        from tests.test_kesher_canonical_state import ContentsServer
        args, params = inputs(); state = prepare_migration(**params)
        baseline = copy.deepcopy(snapshots(state, args['identity'])[0])
        state, command_id = plan_command(state, args['identity'], 'repair_metadata', 1, {}, code_sha='b'*40, now=NOW)
        server = ContentsServer(state)
        context = WorkerContext(GitHubStateStore(server, 'owner/repo'), command_id, '456/1', args['identity'],
                                code_sha='b'*40, now=lambda: NOW)
        context.claim()
        projection = CanonicalMediaState(context, {})
        projection.item['status'] = 'uploaded'; projection.persist()
        history = snapshots(server.document, args['identity'])
        self.assertEqual([row['sequence'] for row in history], [1, 2])
        self.assertEqual(history[0], baseline)
        self.assertEqual(history[1]['item']['youtube_id'], baseline['item']['youtube_id'])
        validate_state(server.document)

    def test_corrupted_imported_baseline_is_rejected_by_canonical_state_validation(self):
        args, params = inputs(); state = prepare_migration(**params)
        row = state['items'][args['identity'].key]
        next(iter(row['receipts'].values()))['item']['youtube_id'] = 'tampered'
        with self.assertRaises(StateInvalid): validate_state(state)

    def test_complete_flag_does_not_certify_publication_but_exact_upload_is_preserved(self):
        args, params = inputs(); state = prepare_migration(**params)
        validate_state(state)
        self.assertEqual(state['migration']['status'], 'prepared')
        self.assertFalse(state['slots'][args['identity'].source.slot]['complete'])
        self.assertIsNone(state['items'][args['identity'].key]['phase'])
        item = snapshots(state, args['identity'])[-1]['item']
        self.assertEqual(item['youtube_id'], args['item']['youtube_id'])
        self.assertEqual(item['source']['body'], args['source']['body'])
        self.assertEqual(state['commands'], {})

    def test_repeated_identical_artifact_copies_do_not_duplicate_the_baseline(self):
        args, params = inputs(); other = copy.deepcopy(params['artifacts'][0]); other['artifact_id'] = 8
        params['artifacts'].append(other)
        state = prepare_migration(**params)
        self.assertEqual(len(snapshots(state, args['identity'])), 1)

    def test_two_upload_ids_are_quarantined_without_picking_the_latest_timestamp(self):
        args, params = inputs(); other = copy.deepcopy(params['artifacts'][0]['items'][0])
        other.update(id='other', youtube_id='lmnopqrstuv', updated_at='2099-01-01T00:00:00+00:00')
        params['artifacts'][0]['items'].append(other)
        state = prepare_migration(**params)
        self.assertEqual(snapshots(state, args['identity']), [])
        self.assertTrue(any(row['failure_class'] == 'DUPLICATE_UPLOAD' for row in state['quarantine']))
        ids = state['migration']['observed_youtube_ids']
        self.assertEqual(set(ids), {'abcdefghijk', 'lmnopqrstuv'})

    def test_stale_content_and_wrong_kind_never_fill_the_current_short(self):
        for field, value in [('type', 'video_overview'), ('source', {**fixture()['source'], 'content_sha256': '0'*64})]:
            args, params = inputs(); params['artifacts'][0]['items'][0][field] = value
            state = prepare_migration(**params)
            self.assertEqual(snapshots(state, args['identity']), [])
            self.assertTrue(state['quarantine'])

    def test_global_strike_count_is_retained_without_becoming_generation_attempts(self):
        args, params = inputs(); state = prepare_migration(**params)
        self.assertEqual(snapshots(state, args['identity'])[-1]['item']['fresh_generation_attempt'], 1)
        self.assertEqual(state['migration']['controller_sha256'], digest(params['controller']))
        self.assertEqual(state['migration']['legacy_stage_budgets'][args['identity'].key]['attempt_count'], 55)


if __name__ == '__main__': unittest.main()
