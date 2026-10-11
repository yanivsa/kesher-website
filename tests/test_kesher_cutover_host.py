"""Operator bootstrap and read-only production admission, on disposable services."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

import yaml

from scripts.kesher_runtime.authority_topology import executable_digest, inventory, policy
from scripts.kesher_runtime.cutover_service import InvocationJournal
from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.state import StateInvalid
from tests.test_kesher_external_exclusion import protection_fixture
from tests import test_kesher_handover as handover_fixtures
from tests.test_kesher_handover_github import GitService

ROOT = Path(__file__).resolve().parents[1]


class ControllerActivationContractTests(unittest.TestCase):
    def test_manual_main_can_run_but_other_events_repositories_and_refs_cannot(self):
        data = yaml.safe_load((ROOT/'.github/workflows/kesher-content-controller.yml').read_text())
        self.assertEqual(set(data.get('on', data.get(True))), {'workflow_dispatch'})
        expression = data['jobs']['reconcile']['if'].removeprefix('${{').removesuffix('}}').strip()
        expression = expression.replace('&&', 'and')
        for repo, ref, event, expected in (
            ('yanivsa/kesher-website', 'refs/heads/main', 'workflow_dispatch', True),
            ('other/repo', 'refs/heads/main', 'workflow_dispatch', False),
            ('yanivsa/kesher-website', 'refs/heads/other', 'workflow_dispatch', False),
            ('yanivsa/kesher-website', 'refs/heads/main', 'schedule', False),
        ):
            with self.subTest(repo=repo, ref=ref, event=event):
                self.assertEqual(eval(expression, {'__builtins__': {}},
                    {'github': SimpleNamespace(repository=repo, ref=ref, event_name=event)}), expected)


class CutoverHostTests(unittest.TestCase):
    def setUp(self):
        if importlib.util.find_spec('scripts.kesher_runtime.cutover_host') is None:
            self.fail('The executable read-only cutover installation/preflight path is missing')
        from scripts.kesher_runtime import cutover_host as host
        self.host = host
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'code'; self.root.mkdir()
        rules = policy(ROOT)
        rules['workflows'] = {p:copy.deepcopy(e) for p,e in rules['workflows'].items()
            if e['role'] in {'controller','worker','handover'} or p.endswith('/kesher-goal-dispatch.yml')}
        rules['registrations'] = {}
        for path, entry in rules['workflows'].items():
            entry['review']['call_chain'] = {}
            if entry['role'] == 'retired':
                entry['review']['dispatches'] = []
                entry['review'].pop('dispatch_bindings', None)
            file = self.root/path; file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes((ROOT/path).read_bytes())
        file = self.root/'scripts/kesher_runtime/authority_policy.json'
        file.parent.mkdir(parents=True); file.write_text(json.dumps(rules))
        from scripts.kesher_runtime.sync_authority_policy import synchronize
        synchronize(self.root, update=True)
        rules = policy(self.root)
        for args in (['init','-q'], ['add','.'], ['-c','user.name=Test','-c','user.email=test@example.invalid',
                                              'commit','-qm','Reviewed fixture']):
            subprocess.run(['git',*args],cwd=self.root,check=True,capture_output=True)
        main = subprocess.check_output(['git','rev-parse','HEAD'],cwd=self.root,text=True).strip()
        case = handover_fixtures.HandoverTests(); case.setUp()
        self.material = {k:v for k,v in case.params.items() if k not in {'controller','controller_sha','main_sha'}}
        from scripts.kesher_runtime.identity import SourceIdentity
        self.material['source_git_paths'] = {SourceIdentity(s['date'],s['slug'],s['content_sha256']).key:
            'src/data/posts.json' for s in self.material['sources']}
        self.material['post_freeze_boundary'] = {'frozen_cycle':case.params['controller']['cycle'],
            'cutover_slot':case.params['now'][:10],
            'adopted_source_keys':[next(iter(case.params['retained_evidence']['sources']))], 'excluded_source_keys':[]}
        self.raw = GitService(case.params['controller'], main)
        self.posts = [{'id':'exact','date':'2026-09-22','title':'כותרת מקורית',
            'category':'משפחה','excerpt':'תיאור בעברית','content':'<p>תוכן מלא בעברית</p>'}]
        self.recent = []
        self.rows = [{'id':e.get('registration_id', i), 'path':p,
                      'state':'disabled_manually' if e['role']=='retired' else 'active'}
                     for i,(p,e) in enumerate(rules['workflows'].items(),1)]
        self.runs = []
        native_request = self.raw.request
        def request(method,path,body=None,**kwargs):
            if method == 'GET' and '/contents/src/data/posts.json?' in path:
                import base64
                return {'encoding':'base64','content':base64.b64encode(json.dumps(self.posts).encode()).decode()}
            if method == 'GET' and '/contents/src/data/postsRecent.json?' in path:
                import base64
                return {'encoding':'base64','content':base64.b64encode(json.dumps(self.recent).encode()).decode()}
            if method == 'GET' and '/actions/workflows?' in path:
                self.raw.calls.append((method,path,body))
                return {'total_count':len(self.rows),'workflows':copy.deepcopy(self.rows)}
            if method == 'GET' and '/actions/runs?' in path:
                self.raw.calls.append((method,path,body))
                status = path.split('status=')[1].split('&')[0]
                batch = [r for r in self.runs if r['status']==status]
                return {'total_count':len(batch),'workflow_runs':copy.deepcopy(batch)}
            if method == 'GET' and path == '/repos/owner/repo':
                return {'id':123,'node_id':'repository-id'}
            return native_request(method,path,body)
        self.raw.request = request
        self.fence, self.ports = protection_fixture()
        self.metadata = {'name':'NOTEBOOKLM_STATE_KEY','available':True,'updated_at':'2026-10-10T00:00:00Z'}
        self.ledger = Path(self.temp.name)/'invocations.sqlite'; InvocationJournal.initialize(self.ledger)
        snapshot = host.read_snapshot(self.raw, 'owner/repo')
        review = {'repo':'owner/repo','main_sha':main,'code_sha256':executable_digest(self.root),
                  'policy_sha256':digest({'policy':rules,'definitions':inventory(self.root,rules)}),
                  'migration_material_sha256':digest(self.material),
                  'closed_evidence_sha256':case.closure['retained_evidence'],
                  'closure_sha256':digest(case.closure),
                  'registrations_sha256':digest({r['path']:r['id'] for r in self.rows}),
                  'key_binding_sha256':digest(self.metadata),
                  'legacy_commit_sha':snapshot.commit_sha,'legacy_blob_sha':snapshot.blob_sha,
                  'legacy_body_sha256':digest(snapshot.state)}
        native = host.NativePorts(github=self.raw, boundary=self.ports['github'],
            external_ports={k:v for k,v in self.ports.items() if k!='github'},
            separation_observer=lambda:{'proofs':{}}, key=lambda:'synthetic-runtime-key-at-least-24-chars',
            key_binding=lambda:copy.deepcopy(self.metadata), review_check=lambda:None,
            authority_observer=case.backend.observe)
        self.install = host.Installation(root=self.root,repo='owner/repo',repository_id='123',
            epoch=self.fence.epoch,owner=self.fence.owner,gateway_url='https://cutover.example',
            ledger=self.ledger,review=review,material=self.material,closure=case.closure,
            bindings=self.fence.bindings,registrations={r['path']:r['id'] for r in self.rows},native=native)
        self.probe = lambda url:host.health(self.install)

    def preflight(self, *, clock=None):
        before = self.ledger.read_bytes() if self.ledger.exists() else None
        try: return self.host.preflight(self.install, probe=self.probe,
                                       clock=clock or (lambda:self.material['now']))
        finally:
            self.assertTrue(all(method=='GET' for method,_,_ in self.raw.calls))
            self.assertTrue(all(port.requests==0 and not port.effects for port in self.ports.values()))
            if before is not None: self.assertEqual(self.ledger.read_bytes(), before)

    def test_complete_observed_prerequisites_pass_without_any_effect(self):
        report = self.preflight()
        self.assertEqual(report['status'],'READY_FOR_CUTOVER_REVIEW')
        self.assertEqual(report['schema_version'],5)
        self.assertFalse(report['production_activated'])
        self.assertFalse(report['public_completion_inferred'])

    def test_initial_preflight_requires_reviewed_current_israel_day(self):
        from datetime import datetime,timedelta
        later=(datetime.fromisoformat(self.material['now'])+timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(StateInvalid,'REVIEWED_CUTOVER_DATE_REQUIRED'):
            self.preflight(clock=lambda:later)

    def test_exact_recent_catalog_provenance_is_required_and_independently_observed(self):
        self.recent,self.posts=self.posts,[]
        self.material['source_git_paths']={key:'src/data/postsRecent.json' for key in self.material['source_git_paths']}
        self.install.review['migration_material_sha256']=digest(self.material)
        self.assertEqual(self.preflight()['schema_version'],5)
        for corruption in (None,{}, {key:'src/data/posts.json' for key in self.material['source_git_paths']}):
            with self.subTest(paths=corruption):
                self.material['source_git_paths']=corruption
                self.install.review['migration_material_sha256']=digest(self.material)
                with self.assertRaisesRegex(StateInvalid,'EXACT_MAIN_SOURCE_GIT_PATHS_REQUIRED'):self.preflight()

    def test_missing_or_wrong_gateway_blocks(self):
        for probe in (lambda url:None, lambda url:{'service':'other'},
                      lambda url:self.host.health(self.install)|{'reviewed_revision':'f'*40}):
            self.probe = probe
            with self.subTest(probe=probe), self.assertRaises(StateInvalid): self.preflight()

    def test_missing_or_corrupt_ledger_blocks_without_recreation(self):
        self.ledger.unlink()
        with self.assertRaises(StateInvalid): self.preflight()
        self.assertFalse(self.ledger.exists())
        self.ledger.write_bytes(b'not sqlite')
        with self.assertRaises(StateInvalid): self.preflight()

    def test_metadata_or_actual_sealing_key_missing_blocks(self):
        self.metadata['available'] = False
        with self.assertRaises(StateInvalid): self.preflight()
        self.metadata['available'] = True
        self.install.native.key = lambda:''
        with self.assertRaises(StateInvalid): self.preflight()

    def test_competing_writer_and_unclassified_run_block(self):
        row = self.rows[0]
        self.runs = [{'id':42,'run_attempt':1,'workflow_id':row['id'],'path':row['path'],
                      'head_sha':self.install.review['main_sha'],'status':'in_progress','conclusion':None}]
        with self.assertRaises(StateInvalid): self.preflight()

    def test_retired_workflow_active_blocks(self):
        next(r for r in self.rows if r['path'].endswith('/kesher-goal-dispatch.yml'))['state']='active'
        with self.assertRaises(StateInvalid): self.preflight()

    def test_changed_main_or_exact_legacy_ref_blocks(self):
        main = self.raw.refs['main']; self.raw.refs['main']='f'*40
        with self.assertRaises(StateInvalid): self.preflight()
        self.raw.refs['main']=main; self.install.review['legacy_commit_sha']='f'*40
        with self.assertRaises(StateInvalid): self.preflight()

    def test_step_lineage_accepts_owned_anchor_recovery_but_not_another_initial_snapshot(self):
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch
        from tests.test_kesher_git_exclusion import EpochGit
        raw=EpochGit(json.loads(next(iter(self.raw.blobs.values()))))
        self.install.native.github=raw
        epoch=GitExclusionEpoch(raw,'owner/repo',epoch='one',owner='coordinator',
            resource_id='repository-id',main_sha='b'*40,policy_sha256='d'*64)
        self.host.verify_cutover_lineage(self.install,epoch)
        epoch.acquire('a'*40)
        raw.calls.clear()
        self.host.verify_cutover_lineage(self.install,epoch)
        self.assertTrue(all(method=='GET' for method,_,_ in raw.calls))
        self.install.review['legacy_commit_sha']='f'*40
        with self.assertRaisesRegex(StateInvalid,'UNREVIEWED_LEGACY_LINEAGE'):
            self.host.verify_cutover_lineage(self.install,epoch)
        self.assertTrue(all(method=='GET' for method,_,_ in raw.calls))

    def test_missing_native_provider_and_surviving_external_actor_block(self):
        from scripts.kesher_runtime.production_ports import PrerequisitePort
        old = self.install.native.external_ports['notebooklm']
        self.install.native.external_ports['notebooklm']=PrerequisitePort('notebooklm','resource-id:notebooklm')
        with self.assertRaises(StateInvalid): self.preflight()
        self.install.native.external_ports['notebooklm']=old
        old.actors=[{'id':'stale-session','state':'IN_PROGRESS'}]
        with self.assertRaises(StateInvalid): self.preflight()

    def test_unknown_registration_or_unavailable_worker_blocks(self):
        self.rows.append({'id':999999,'path':'.github/workflows/unknown.yml','state':'active'})
        with self.assertRaises(StateInvalid): self.preflight()
        self.rows.pop(); self.rows[0]['state']='disabled_manually'
        with self.assertRaises(StateInvalid): self.preflight()

    def test_changed_material_or_closed_quarantine_floor_blocks(self):
        self.install.material['artifacts']=[]
        with self.assertRaises(StateInvalid): self.preflight()

    def test_post_freeze_source_cannot_be_omitted_from_approved_material(self):
        from scripts.kesher_daily_pipeline import source_metadata
        from scripts.kesher_runtime.identity import SourceIdentity
        self.posts = [next(p for p in json.loads((ROOT/'src/data/posts.json').read_text())
                           if p['slug']=='how-to-repair-after-couple-fight')]
        source = source_metadata(self.posts[0])
        self.material.update(now='2026-10-10T10:00:00+03:00',post_freeze_boundary={
            'frozen_cycle':'2026-10-04','cutover_slot':'2026-10-10',
            'adopted_source_keys':[SourceIdentity(source['date'],source['slug'],source['content_sha256']).key],
            'excluded_source_keys':[]})
        # Keep the immutable snapshot's actual freeze in this independent main
        # completeness test. A false approved boundary cannot hide the source.
        self.material['post_freeze_boundary']['frozen_cycle'] = json.loads(next(iter(self.raw.blobs.values())))['cycle']
        self.install.review['migration_material_sha256'] = digest(self.material)
        with self.assertRaisesRegex(StateInvalid,'EXACT_POST_FREEZE_MAIN_SOURCES_REQUIRED'): self.preflight()

    def test_prefreeze_material_source_must_also_match_independent_main_bytes(self):
        older=copy.deepcopy(self.material['sources'][0])
        older.update(date='2025-01-01',slug='unproven-old-source')
        self.material['sources'].append(older)
        self.install.review['migration_material_sha256']=digest(self.material)
        with self.assertRaisesRegex(StateInvalid,'EXACT_MAIN_SOURCE_MATERIAL_REQUIRED'): self.preflight()

    def test_gateway_cannot_return_live_authority_for_schema5_or_forged_migration_flags(self):
        # No configured review/availability flag can substitute for VERIFIED.
        obs = self.install.native.authority_observer()
        obs.update(code_sha256=self.install.review['code_sha256'],policy_sha256=self.install.review['policy_sha256'])
        self.install.native.authority_observer = lambda:obs
        for migration in ({}, {'status':'complete','runtime_owner':'kesher-canonical-controller'}):
            legacy = json.loads(next(iter(self.raw.blobs.values())))
            legacy['migration'] = migration
            self.install.native.github = GitService(legacy,self.install.review['main_sha'])
            # The snapshot remains Schema-5; even valid independently observed
            # resource proof cannot manufacture the handover journal.
            with self.subTest(migration=migration), self.assertRaises(StateInvalid):
                self.host.authority_observation(self.install,'unsigned-client-claim')
        self.assertTrue(all(method=='GET' for method,_,_ in self.raw.calls))

    def test_invalid_bearer_never_reaches_credentialed_installation_or_native_observers(self):
        from unittest.mock import patch
        before=copy.deepcopy(self.raw.calls)
        with patch.object(self.host,'reviewed_installation') as reviewed:
            for token in ('unsigned-client-claim','a.b.c','x'*32769):
                with self.subTest(token=token[:20]),self.assertRaises(StateInvalid):
                    self.host.authority_observation(self.install,token,jwks=lambda:self.fail('No JWKS required'))
            reviewed.assert_not_called()
        self.assertEqual(self.raw.calls,before)

    def test_signed_canonical_reader_requires_actual_nine_phase_handover_and_has_no_effect(self):
        import base64
        import time
        from cryptography.hazmat.primitives.asymmetric import rsa,padding
        from cryptography.hazmat.primitives import hashes
        case=handover_fixtures.HandoverTests(); case.setUp()
        case.params['main_sha']=case.backend.main=self.install.review['main_sha']
        case.backend.observation.update(code_sha256=self.install.review['code_sha256'],
            policy_sha256=self.install.review['policy_sha256'],key_binding=self.metadata,
            approved_revision={k:self.install.review[k] for k in
                               ('repo','code_sha256','policy_sha256','closed_evidence_sha256')})
        rules=policy(self.root)
        case.backend.observation['workflows']=[r|{'role':rules['workflows'][r['path']]['role']} for r in self.rows]
        verified=case.finish()
        from scripts.kesher_runtime.handover import PHASES
        self.assertEqual([r['phase'] for r in verified['handover']['journal']],list(PHASES))
        controller=next(r for r in case.backend.observation['workflows'] if r['role']=='controller')
        run={'id':42,'run_attempt':1,'workflow_id':controller['id'],'path':controller['path'],
             'head_sha':case.backend.main,'head_branch':'main','event':'workflow_dispatch','status':'in_progress'}
        case.backend.observation['active_runs']=[run]
        class Readback(GitService):
            def request(self,method,path,body=None):
                if method=='GET' and path.endswith('/actions/runs/42'):
                    self.calls.append((method,path,body)); return run
                return super().request(method,path,body)
        raw=Readback(verified,case.backend.main)
        self.install.native.github=raw; self.install.native.authority_observer=case.backend.observe
        encode=lambda b:base64.urlsafe_b64encode(b).decode().rstrip('=')
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        public=key.public_key().public_numbers()
        integer=lambda v:encode(v.to_bytes((v.bit_length()+7)//8,'big'))
        now=int(time.time())
        claims={'iss':'https://token.actions.githubusercontent.com','aud':self.install.gateway_url,
            'repository':self.install.repo,'repository_id':'123','ref':'refs/heads/main',
            'sha':case.backend.main,'workflow_sha':case.backend.main,'run_id':'42','run_attempt':'1',
            'workflow_ref':self.install.repo+'/'+controller['path']+'@refs/heads/main',
            'event_name':'workflow_dispatch','exp':now+300,'nbf':now-1,'iat':now}
        def token(values):
            message=(encode(b'{"alg":"RS256","kid":"one"}')+'.'+encode(json.dumps(values).encode())).encode()
            return message.decode()+'.'+encode(key.sign(message,padding.PKCS1v15(),hashes.SHA256()))
        jwks=lambda:{'keys':[{'kty':'RSA','kid':'one','n':integer(public.n),'e':integer(public.e)}]}
        ledger=self.ledger.read_bytes(); state=copy.deepcopy(raw.blobs)
        self.assertEqual(self.host.authority_observation(self.install,token(claims),jwks=jwks),case.backend.observe())
        for change in ({'sha':'f'*40},{'environment':'kesher-cutover'}, {'run_attempt':'2'},
                       {'workflow_ref':self.install.repo+'/.github/workflows/kesher-production-cutover.yml@refs/heads/main'}):
            with self.subTest(change=change),self.assertRaises(StateInvalid):
                self.host.authority_observation(self.install,token(claims|change),jwks=jwks)
        self.assertTrue(all(method=='GET' for method,_,_ in raw.calls))
        self.assertEqual(raw.blobs,state); self.assertEqual(self.ledger.read_bytes(),ledger)
        from unittest.mock import patch
        with patch.object(self.host,'reviewed_installation') as reviewed:
            for change in ({'environment':'kesher-cutover'},{'sha':'f'*40}):
                with self.subTest(early_rejection=change),self.assertRaises(StateInvalid):
                    self.host.authority_observation(self.install,token(claims|change),jwks=jwks)
            reviewed.assert_not_called()
        # A correctly signed, live canonical invocation still cannot consume
        # Schema-5 or self-declared migration flags in lieu of VERIFIED handover.
        for migration in ({},{'status':'complete','runtime_owner':'kesher-canonical-controller'}):
            legacy={'schema_version':5,'migration':migration}
            self.install.native.github=Readback(legacy,case.backend.main)
            with self.subTest(signed_legacy=migration),self.assertRaises(StateInvalid):
                self.host.authority_observation(self.install,token(claims),jwks=jwks)

    def test_read_only_transport_refuses_mutation_even_if_called_by_a_future_check(self):
        transport = self.host.ReadOnlyGitHub(self.raw)
        with self.assertRaises(StateInvalid): transport.request('POST','/graphql',{})
        self.assertTrue(all(method=='GET' for method,_,_ in self.raw.calls))

    def test_operator_command_missing_configuration_is_nonzero_and_redacts_details(self):
        result = subprocess.run(['python3','-B','-m','scripts.kesher_runtime.cutover_host',
            '--config',str(Path(self.temp.name)/'missing-private-config'),'preflight'],
            cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertNotIn('missing-private-config',result.stderr)

    def test_operator_reports_only_whitelisted_stable_prerequisite_codes(self):
        import contextlib
        import io
        from unittest.mock import patch
        for error,expected in ((StateInvalid('CUTOVER_RUNTIME_KEY_BINDING_REQUIRED'),
                                'CUTOVER_RUNTIME_KEY_BINDING_REQUIRED'),
                               (StateInvalid('PRIVATE_SECRET_NEVER_LOG_THIS'),'CUTOVER_HOST_BLOCKED')):
            output=io.StringIO()
            with patch.object(self.host,'load_installation',side_effect=error),contextlib.redirect_stderr(output):
                self.assertEqual(self.host.main(['--config','/administrator/path','preflight']),1)
            self.assertIn(expected,output.getvalue())
            self.assertNotIn('PRIVATE_SECRET',output.getvalue())


class AuthorityClientTests(unittest.TestCase):
    def test_invalid_step_identity_never_reaches_custody_review_or_ledger_or_effect(self):
        from unittest.mock import Mock
        from scripts.kesher_runtime.cutover_service import CutoverApplication
        reviewed=Mock(); journal=Mock(); runtime=Mock()
        identity=Mock(); identity.verify.side_effect=StateInvalid('CUTOVER_ACTIONS_IDENTITY_DENIED')
        app=CutoverApplication(runtime=runtime,identity=identity,journal=journal,epoch='one',
            reviewed_revision='b'*40,review_check=reviewed)
        with self.assertRaises(StateInvalid):
            app.step('invalid',{'epoch':'one','reviewed_revision':'b'*40})
        reviewed.assert_not_called(); journal.claim.assert_not_called(); runtime.step.assert_not_called()

    def test_actions_observation_uses_oidc_get_without_client_state_or_evidence(self):
        if importlib.util.find_spec('scripts.kesher_runtime.authority_client') is None:
            self.fail('Canonical Actions entrypoints have no independently authenticated live observer')
        from scripts.kesher_runtime.authority_client import ActionsAuthorityObserver
        import io
        env = {'GITHUB_REPOSITORY':'yanivsa/kesher-website','GITHUB_REF':'refs/heads/main',
               'GITHUB_EVENT_NAME':'workflow_dispatch',
               'GITHUB_WORKFLOW_REF':'yanivsa/kesher-website/.github/workflows/kesher-content-controller.yml@refs/heads/main',
               'KESHER_CUTOVER_GATEWAY_URL':'https://cutover.example',
               'ACTIONS_ID_TOKEN_REQUEST_URL':'https://example.actions.githubusercontent.com/token',
               'ACTIONS_ID_TOKEN_REQUEST_TOKEN':'private-oidc-request-token'}
        requests = []
        def open_url(request,timeout):
            requests.append(request)
            if len(requests)==1:return io.BytesIO(b'{"value":"signed-token"}')
            return io.BytesIO(b'{"main_sha":"observed"}')
        observation = ActionsAuthorityObserver(env, opener=open_url)()
        self.assertEqual(observation, {'main_sha':'observed'})
        self.assertEqual(len(requests),2)
        self.assertEqual(requests[1].full_url,'https://cutover.example/v1/authority')
        self.assertEqual(requests[1].get_method(),'GET')
        self.assertIsNone(requests[1].data)
        self.assertEqual(requests[1].headers['Authorization'],'Bearer signed-token')
        for change in ({'GITHUB_REF':'refs/heads/repair'}, {'GITHUB_EVENT_NAME':'push'},
                       {'GITHUB_WORKFLOW_REF':'yanivsa/kesher-website/.github/workflows/legacy.yml@refs/heads/main'},
                       {'KESHER_CUTOVER_GATEWAY_URL':'http://cutover.example'},
                       {'ACTIONS_ID_TOKEN_REQUEST_URL':'https://evil.example/token'}):
            requests.clear()
            with self.subTest(change=change), self.assertRaises(StateInvalid):
                ActionsAuthorityObserver(env|change,opener=open_url)()
            self.assertEqual(requests,[])

    def test_http_surface_has_only_one_mutation_route_and_redacts_failed_admission(self):
        from http.server import HTTPServer
        import threading
        import urllib.request
        import urllib.error
        from scripts.kesher_runtime.cutover_service import handler
        effects=[]; reads=[]
        def authority(token):
            reads.append(token)
            raise StateInvalid('private-provider-credential-must-never-be-revealed')
        app=SimpleNamespace(health=lambda:{'service':'kesher-cutover'},authority=authority,
            step=lambda token,request:effects.append(request))
        server=HTTPServer(('127.0.0.1',0),handler(app))
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            url='http://127.0.0.1:'+str(server.server_port)
            with urllib.request.urlopen(url+'/healthz') as response:
                self.assertEqual(json.load(response),{'service':'kesher-cutover'})
            for request in (urllib.request.Request(url+'/v1/authority'),
                            urllib.request.Request(url+'/v1/authority',headers={'Authorization':'Bearer signed-token'}),
                            urllib.request.Request(url+'/v1/authority',data=b'{}',method='POST')):
                with self.assertRaises(urllib.error.HTTPError) as caught: urllib.request.urlopen(request)
                self.assertNotIn(b'private-provider',caught.exception.read())
                caught.exception.close()
            self.assertEqual(reads,['signed-token']); self.assertEqual(effects,[])
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__': unittest.main()
