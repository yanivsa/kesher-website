"""Service bootstrap must fail before effects; IDs/config are not live proof."""
import copy
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.kesher_runtime.state import StateInvalid
from scripts.kesher_runtime.cutover_service import CutoverApplication, InvocationJournal
from scripts.kesher_runtime.cutover_auth import ActionsIdentity
from tests import test_kesher_production_cutover as fixtures


class CutoverInstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def application(self):
        from scripts.kesher_runtime.cutover_installation import REPOSITORY, REPOSITORY_ID, REPOSITORY_NODE_ID, SUPERVISOR_TASK_ID
        runtime, _, services = fixtures.ProductionCutoverTests().runtime()
        fence = runtime.fence
        fence.repo = REPOSITORY
        fence.bindings['github'] = REPOSITORY_NODE_ID
        cp = fence.control_planes
        cp.repo = REPOSITORY; cp.bindings = copy.deepcopy(fence.bindings); cp.supervisor_id = SUPERVISOR_TASK_ID
        path = self.root/'ledger.sqlite'; InvocationJournal.initialize(path)
        install = dict(repo=REPOSITORY, repository_id=REPOSITORY_ID, repository_node_id=REPOSITORY_NODE_ID,
            supervisor_task_id=SUPERVISOR_TASK_ID, epoch=fence.epoch, owner=fence.owner,
            reviewed_revision='b'*40, https_origin='https://cutover.example',
            ledger_path=str(path), resource_bindings=copy.deepcopy(fence.bindings))
        identity = ActionsIdentity(SimpleNamespace(), repo=REPOSITORY, repository_id=REPOSITORY_ID,
                                   main_sha='b'*40, audience=install['https_origin'])
        app = CutoverApplication(runtime=runtime, identity=identity, journal=InvocationJournal(path),
            epoch=fence.epoch, reviewed_revision='b'*40, review_check=lambda: None, installation=install)
        return app, services

    def test_valid_installation_is_read_only_and_does_not_claim_live_readiness(self):
        from scripts.kesher_runtime.cutover_installation import validate_installation
        app, services = self.application(); before = Path(app.journal.path).read_bytes()
        validate_installation(app)
        self.assertEqual(Path(app.journal.path).read_bytes(), before)
        self.assertTrue(all(s.requests == 0 for s in services.values()))

    def test_exact_supervisor_resource_epoch_and_oidc_identity_are_bound(self):
        from scripts.kesher_runtime.cutover_installation import validate_installation
        app, _ = self.application()
        for field, value in [('supervisor_task_id','other-task'), ('repo','other/repo'),
                             ('repository_id',1), ('epoch','other'), ('owner','other'),
                             ('reviewed_revision','c'*40), ('repository_node_id','other')]:
            original=copy.deepcopy(app.installation)
            with self.subTest(field=field), self.assertRaises(StateInvalid):
                app.installation[field]=value; validate_installation(app)
            app.installation=original
        app.identity.audience='https://wrong.example'
        with self.assertRaises(StateInvalid):validate_installation(app)

    def test_https_only_no_static_key_no_missing_or_placeholder_resource(self):
        from scripts.kesher_runtime.cutover_installation import validate_installation
        app, _ = self.application(); original=copy.deepcopy(app.installation)
        for url in ('http://cutover.example','https://u:p@cutover.example','https://cutover.example/path',
                    'https://cutover.example?key=secret','https://cutover.example#fragment'):
            with self.subTest(url=url), self.assertRaises(StateInvalid):
                app.installation['https_origin']=url; validate_installation(app)
        app.installation=copy.deepcopy(original); app.installation['api_key']='not-allowed'
        with self.assertRaises(StateInvalid):validate_installation(app)
        for value in (None, '', 'UNRESOLVED'):
            app.installation=copy.deepcopy(original); app.installation['resource_bindings']['jules']=value
            with self.assertRaises(StateInvalid):validate_installation(app)
        app.installation=copy.deepcopy(original); del app.installation['resource_bindings']['youtube']
        with self.assertRaises(StateInvalid):validate_installation(app)

    def test_missing_corrupt_or_wrong_schema_ledger_is_never_created_or_repaired(self):
        for kind in ('missing','corrupt','wrong-schema'):
            path=self.root/(kind+'.sqlite')
            if kind=='corrupt':path.write_bytes(b'broken')
            if kind=='wrong-schema':
                with sqlite3.connect(path) as db:db.execute('CREATE TABLE invocations(epoch TEXT,run TEXT)')
            before=path.read_bytes() if path.exists() else None
            with self.subTest(kind=kind), self.assertRaises(StateInvalid):InvocationJournal(path).check()
            self.assertEqual(path.read_bytes() if path.exists() else None,before)

    def test_ledger_readcheck_preserves_restart_replay_denial(self):
        path=self.root/'durable.sqlite'; InvocationJournal.initialize(path)
        InvocationJournal(path).claim('epoch','42/1')
        journal=InvocationJournal(path); journal.check()
        with self.assertRaises(StateInvalid):journal.claim('epoch','42/1')
        journal.claim('epoch','42/2')

    def test_factory_hash_and_external_location_checked_before_module_execution(self):
        from scripts.kesher_runtime.cutover_installation import load_factory
        path=self.root/'trusted_factory.py'; path.write_text('def build():\n    return "fixture"\n')
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(load_factory('trusted_factory:build',self.root,sha)(),'fixture')
        with self.assertRaises(StateInvalid):load_factory('trusted_factory:build',self.root,'0'*64)
        with self.assertRaises(StateInvalid):load_factory('scripts.kesher_runtime:build',self.root,sha)
        repo=Path(__file__).resolve().parents[1]
        with self.assertRaises(StateInvalid):load_factory('trusted_factory:build',repo,sha)
        path.unlink();path.symlink_to(__file__)
        with self.assertRaises(StateInvalid):load_factory('trusted_factory:build',self.root,sha)

    def test_readiness_checks_native_observers_without_retiring_any_resource(self):
        runtime,case,services=fixtures.ProductionCutoverTests().runtime()
        rows=runtime.preflight()
        self.assertEqual(set(rows),set(services))
        self.assertTrue(all(s.requests == 0 for s in services.values()));self.assertEqual(case.backend.writes,[])
        from scripts.kesher_runtime.production_ports import PrerequisitePort
        runtime.fence.ports['youtube']=PrerequisitePort('youtube','unavailable')
        with self.assertRaises(StateInvalid):runtime.preflight()
        self.assertTrue(all(s.requests == 0 for s in services.values()))

    def test_expected_task_id_cannot_make_unresolved_readback_valid(self):
        from scripts.kesher_runtime.cutover_installation import SUPERVISOR_TASK_ID
        runtime,case,services=fixtures.ProductionCutoverTests().runtime()
        runtime.fence.control_planes.supervisor_id=SUPERVISOR_TASK_ID
        with self.assertRaises(StateInvalid):runtime.preflight()
        self.assertTrue(all(s.requests == 0 for s in services.values()));self.assertEqual(case.backend.writes,[])

    def test_check_only_never_calls_step_or_starts_http_server(self):
        from scripts.kesher_runtime.cutover_service import main
        app,_=self.application()
        with patch.object(app,'preflight') as preflight, patch.object(app.runtime,'step') as step, \
             patch('scripts.kesher_runtime.cutover_installation.load_factory',return_value=lambda:app), \
             patch('scripts.kesher_runtime.cutover_service.HTTPServer') as server:
            main(['--factory','trusted_factory:build','--factory-root',str(self.root),
                  '--factory-sha256','a'*64,'--check-only'])
        preflight.assert_called_once();step.assert_not_called();server.assert_not_called()
