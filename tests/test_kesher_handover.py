"""Offline authority transfer: durable evidence, failure injection and no providers."""
import copy
import unittest

from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.github import LoadedState, GitHubError
from scripts.kesher_runtime.state import StateConflict, StateInvalid
from tests.test_kesher_runtime_migration import inputs


class Backend:
    """Disposable service; only the state/main CAS is atomic, like Git refs."""
    repo = 'owner/repo'
    store_key = 'handover-test'

    def __init__(self, document, main):
        from tests.test_kesher_external_exclusion import protection_fixture
        self.fence, _ = protection_fixture()
        self.fence.establish()
        self.document = copy.deepcopy(document)
        self.sha = '1' * 40
        self.main = main
        self.serial = 1
        self.writes = []
        self.disables = []
        self.drop = False
        self.before_write = None
        self.observation = {
            'main_sha': main, 'policy_sha256': 'a' * 64, 'code_sha256': 'b' * 64,
            'approved_revision': {'repo':self.repo,'policy_sha256':'a'*64,'code_sha256':'b'*64},
            'definitions_valid': True, 'inventory_complete': True,
            'workflows': [
                {'id': 1, 'path': 'controller.yml', 'role': 'controller', 'state': 'active'},
                {'id': 2, 'path': 'worker.yml', 'role': 'worker', 'state': 'active'},
                {'id': 3, 'path': 'legacy.yml', 'role': 'retired', 'state': 'active'},
                {'id': 4, 'path': 'diagnostic.yml', 'role': 'diagnostic', 'state': 'active'}],
            'runs_complete': True, 'active_runs': [],
            'external': self.fence.authority_observation(),
            'key_binding': {'name': 'NOTEBOOKLM_STATE_KEY', 'available': True,
                            'updated_at': '2026-08-10T13:35:14Z'},
        }

    def load(self):
        return LoadedState(self.document, self.sha, self.store_key)

    def observe(self):
        result = copy.deepcopy(self.observation)
        result['main_sha'] = self.main
        return result

    def save(self, loaded, proposed, *, main_sha):
        if self.before_write:
            callback, self.before_write = self.before_write, None
            callback()
        if loaded.blob_sha != self.sha or self.main != main_sha:
            raise StateConflict('State/main changed at atomic CAS')
        old_schema = self.document['schema_version']
        self.document = copy.deepcopy(proposed)
        self.serial += 1
        self.sha = f'{self.serial:040x}'
        self.writes.append((old_schema, proposed['schema_version']))
        if self.drop:
            self.drop = False
            raise GitHubError(None, 'Lost response', uncertain=True)
        return self.load()

    def disable(self, workflow_id):
        self.disables.append(workflow_id)
        next(w for w in self.observation['workflows'] if w['id'] == workflow_id)['state'] = 'disabled_manually'


class HandoverTests(unittest.TestCase):
    def setUp(self):
        self.args, self.params = inputs()
        self.backend = Backend(self.params['controller'], self.params['main_sha'])
        self.params['controller_sha'] = self.backend.sha
        from scripts.kesher_runtime.migration import prepare_migration
        self.params['retained_evidence'] = prepare_migration(**self.params)
        self.closure = {'adjudication': 'c' * 64, 'replay': 'd' * 64,
                        'retained_evidence':digest(self.params['retained_evidence'])}
        self.backend.observation['approved_revision']['closed_evidence_sha256'] = self.closure['retained_evidence']

    def coordinator(self, **kwargs):
        from scripts.kesher_runtime.handover import Coordinator
        return Coordinator(self.backend, self.params, closure=self.closure,
                           key=lambda: 'synthetic-runtime-key-at-least-24-chars', **kwargs)

    def finish(self, coordinator=None):
        coordinator = coordinator or self.coordinator()
        for _ in range(50):
            result = coordinator.tick()
            if result == 'VERIFIED':
                return self.backend.document
        self.fail('Handover did not finish')

    def advance_to(self, phase, coordinator=None):
        coordinator = coordinator or self.coordinator()
        for _ in range(50):
            if coordinator.tick() == phase:
                self.assertEqual(self.backend.document['handover']['phase'], phase)
                return
        self.fail('Did not reach durable phase ' + phase)

    def test_phase_transition_changes_the_durable_document(self):
        c = self.coordinator()
        self.assertEqual(c.tick(), 'PREPARED')
        self.assertEqual(c.tick(), 'LEGACY_QUIESCING')
        self.assertEqual(self.backend.document['handover']['phase'], 'LEGACY_QUIESCING')

    def test_omitted_or_replaced_closed_floor_cannot_be_self_approved(self):
        for change in ('missing', 'replacement'):
            with self.subTest(change=change):
                self.setUp()
                if change == 'missing':
                    self.params.pop('retained_evidence')
                else:
                    self.params['retained_evidence']['quarantine'].append({'failure_class':'unreviewed'})
                    self.closure['retained_evidence'] = digest(self.params['retained_evidence'])
                with self.assertRaises(StateInvalid):
                    self.coordinator().tick()
                self.assertFalse(self.backend.writes)

    def test_missing_retained_capability_cannot_complete_sealing_by_omission(self):
        from scripts.kesher_runtime.migration import prepare_migration
        params = copy.deepcopy(self.params); params.pop('retained_evidence')
        params['artifacts'][0]['items'][0]['upload_session_uri'] = 'synthetic-only-capability'
        self.params['retained_evidence'] = prepare_migration(**params)
        self.params['artifacts'] = []
        self.closure['retained_evidence'] = digest(self.params['retained_evidence'])
        self.backend.observation['approved_revision']['closed_evidence_sha256'] = self.closure['retained_evidence']
        self.advance_to('IMPORT_READY')
        with self.assertRaises(StateInvalid): self.coordinator().tick()
        self.assertEqual(self.backend.document['schema_version'], 5)

    def test_explicit_phases_single_import_and_repeated_success(self):
        from scripts.kesher_runtime.handover import PHASES
        state = self.finish()
        self.assertEqual([p['phase'] for p in state['handover']['journal']], list(PHASES))
        self.assertEqual(self.backend.writes.count((5, 6)), 1)
        self.assertEqual(self.backend.disables, [3])
        self.assertEqual(state['migration']['runtime_owner'], 'kesher-canonical-controller')
        count = len(self.backend.writes)
        self.finish()
        self.assertEqual(len(self.backend.writes), count)

    def test_restart_after_every_durable_phase(self):
        from scripts.kesher_runtime.handover import PHASES
        for phase in PHASES:
            with self.subTest(phase=phase):
                self.setUp()
                for _ in range(50):
                    if self.coordinator().tick() == phase:
                        break
                self.finish(self.coordinator())
                self.assertEqual(self.backend.writes.count((5, 6)), 1)

    def test_lost_import_response_is_adopted_without_second_import(self):
        c = self.coordinator()
        self.advance_to('CAPABILITY_SEALED', c)
        self.backend.drop = True
        with self.assertRaises(GitHubError): c.tick()
        self.finish(self.coordinator())
        self.assertEqual(self.backend.writes.count((5, 6)), 1)

    def test_lost_phase_response_resumes_proven_phase(self):
        self.backend.drop = True
        with self.assertRaises(GitHubError): self.coordinator().tick()
        self.finish()
        self.assertEqual(self.backend.writes.count((5, 6)), 1)

    def test_two_coordinators_race_initial_cas(self):
        first, second = self.coordinator(), self.coordinator()
        self.backend.before_write = lambda: second.tick()
        with self.assertRaises(StateConflict): first.tick()
        self.finish()
        self.assertEqual(self.backend.writes.count((5, 6)), 1)

    def test_main_race_at_import_is_atomic_conflict(self):
        c = self.coordinator()
        self.advance_to('CAPABILITY_SEALED', c)
        self.backend.before_write = lambda: setattr(self.backend, 'main', 'e'*40)
        with self.assertRaises(StateConflict): c.tick()
        self.assertEqual(self.backend.document['schema_version'], 5)

    def test_changed_main_input_closure_key_or_topology_fails_closed(self):
        for change in ['main', 'input', 'closure', 'key', 'topology', 'code', 'body']:
            with self.subTest(change=change):
                self.setUp(); c = self.coordinator(); c.tick()
                if change == 'main': self.backend.main = 'e'*40
                elif change == 'input': self.params['artifacts'][0]['run_id'] = 'changed'
                elif change == 'closure': self.closure['replay'] = 'e'*64
                elif change == 'key': self.backend.observation['key_binding']['updated_at'] = 'changed'
                elif change == 'topology': self.backend.observation['workflows'][0]['id'] = 99
                elif change == 'code': self.backend.observation['code_sha256'] = 'e'*64
                else: self.backend.document['unexpected_legacy_writer'] = True
                with self.assertRaises(StateInvalid): self.coordinator().tick()
                self.assertEqual(self.backend.document['schema_version'], 5)

    def test_active_queued_old_code_and_external_writers_block_import(self):
        for status in ['queued','in_progress','waiting','pending','requested','external']:
            with self.subTest(status=status):
                self.setUp(); c = self.coordinator()
                c.tick()
                if status == 'external':
                    self.backend.observation['external']['writers'] = [{'id':'session','state':'IN_PROGRESS'}]
                else:
                    self.backend.observation['active_runs'] = [{'id':7,'workflow_id':1,'head_sha':'e'*40,'status':status}]
                for _ in range(8):
                    try: c.tick()
                    except StateInvalid: break
                self.assertEqual(self.backend.document['schema_version'], 5)

    def test_missing_exclusive_fence_or_incomplete_inventory_refuses(self):
        for field in ['inventory_complete','runs_complete','definitions_valid','external']:
            with self.subTest(field=field):
                self.setUp()
                if field == 'external': self.backend.observation['external']['fenced'] = False
                else: self.backend.observation[field] = False
                with self.assertRaises(StateInvalid): self.coordinator().tick()
                self.assertFalse(self.backend.writes)

    def test_unexpected_mutating_path_is_not_blessed_by_known_name(self):
        self.backend.observation['workflows'].append({'id':99,'path':'unexpected.yml','role':'unknown','state':'active'})
        with self.assertRaises(StateInvalid): self.coordinator().tick()

    def test_lost_disable_response_and_midway_retirement(self):
        original = self.backend.disable
        def lost(workflow):
            original(workflow)
            self.backend.disable = original
            raise GitHubError(None, 'Lost disable response', uncertain=True)
        self.backend.disable = lost
        c = self.coordinator()
        with self.assertRaises(GitHubError):
            for _ in range(20): c.tick()
        self.finish(self.coordinator())
        self.assertEqual(self.backend.disables,[3])

    def test_disabled_writer_is_never_reactivated(self):
        self.finish()
        self.backend.observation['workflows'][2]['state'] = 'active'
        with self.assertRaises(StateInvalid): self.coordinator().tick()
        self.assertEqual(self.backend.disables,[3])

    def test_sealing_preserves_quarantine_and_does_not_grant_upload(self):
        from scripts.kesher_runtime.sealed import unseal
        from scripts.kesher_runtime.identity import identity_from_dict
        uri = 'synthetic-capability-never-contacted'
        self.params['artifacts'][0]['items'][0]['upload_session_uri'] = uri
        state = self.finish()
        self.assertNotIn(uri,str(state))
        self.assertTrue(any(q['failure_class']=='LEGACY_UPLOAD_CAPABILITY_REQUIRES_SEALING' for q in state['quarantine']))
        sealed = state['handover']['sealed_capabilities'][0]
        self.assertEqual(unseal(sealed['envelope'],'synthetic-runtime-key-at-least-24-chars',
            identity_from_dict(sealed['target']),repo='owner/repo',purpose='youtube_upload'),uri)
        self.assertFalse(state['commands'])
        self.assertFalse(state['audit'][-1]['public_completion_inferred'])

    def test_corrupted_import_cannot_be_blessed_by_later_phases(self):
        for corruption in ('quarantine','receipts','commands'):
            with self.subTest(corruption=corruption):
                self.setUp()
                if corruption == 'quarantine':
                    self.params['artifacts'][0]['items'][0]['upload_session_uri'] = 'synthetic-only'
                self.advance_to('STATE_IMPORTED')
                if corruption == 'quarantine': self.backend.document['quarantine'] = []
                elif corruption == 'receipts':
                    for item in self.backend.document['items'].values(): item['receipts'] = {}
                else: self.backend.document['audit'].append({'unapproved':'external-authority'})
                with self.assertRaises(StateInvalid): self.coordinator().tick()
                self.assertEqual(self.backend.document['handover']['phase'],'STATE_IMPORTED')

    def test_wrong_runtime_key_on_resume_refuses_import(self):
        self.params['artifacts'][0]['items'][0]['upload_session_uri'] = 'synthetic-only'
        self.advance_to('CAPABILITY_SEALED')
        c = self.coordinator(); c.key = lambda:'different-runtime-key-with-at-least-24-chars'
        with self.assertRaises(StateInvalid): c.tick()
        self.assertEqual(self.backend.document['schema_version'],5)

    def test_new_writer_in_last_prewrite_observation_refuses_import(self):
        for writer in ('legacy_run','external'):
            with self.subTest(writer=writer):
                self.setUp(); self.advance_to('CAPABILITY_SEALED')
                original = self.backend.observe; calls = 0
                def observe():
                    nonlocal calls
                    calls += 1
                    result = original()
                    if calls >= 2:
                        if writer == 'legacy_run':
                            result['active_runs'] = [{'id':7,'workflow_id':3,'head_sha':'e'*40,'status':'queued'}]
                        else:
                            result['external']['writers'] = [{'id':'old-provider'}]
                            result['external']['inventory_sha256'] = digest(result['external']['writers'])
                    return result
                self.backend.observe = observe
                with self.assertRaises(StateInvalid): self.coordinator().tick()
                self.assertEqual(self.backend.document['schema_version'],5)

    def test_no_canonical_admission_before_verified(self):
        from scripts.kesher_runtime.handover import require_authority
        c = self.coordinator()
        for _ in range(50):
            phase = c.tick()
            if phase == 'VERIFIED': break
            with self.assertRaises(StateInvalid): require_authority(self.backend.document,self.backend.observe())
        else: self.fail('Did not reach VERIFIED')
        require_authority(self.backend.document,self.backend.observe())

    def test_verified_authority_allows_exact_current_canonical_runs(self):
        from scripts.kesher_runtime.handover import require_authority
        state = self.finish()
        self.backend.observation['active_runs'] = [{'id':8,'workflow_id':1,
            'head_sha':self.params['main_sha'],'status':'in_progress'}]
        require_authority(state,self.backend.observe())

    def test_altered_sealing_evidence_cannot_keep_verified_phase(self):
        from scripts.kesher_runtime.handover import require_authority
        state = self.finish()
        state['handover']['sealed_capabilities'].append({'unexpected':'entry'})
        with self.assertRaises(StateInvalid): require_authority(state,self.backend.observe())


if __name__ == '__main__': unittest.main()


def install_verified_authority(store, document):
    """Use the actual nine-phase coordinator to establish admission fixtures."""
    case = HandoverTests(); case.setUp()
    verified = case.finish()
    document['handover'] = verified['handover']
    document['migration'] = verified['migration']
    store.authority_observer = case.backend.observe
    return case.backend
