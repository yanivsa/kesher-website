"""Production boundary regressions; provider effects use disposable services."""
import copy
import json
import unittest
from pathlib import Path

from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.state import StateInvalid
from tests.test_kesher_external_exclusion import protection_fixture
from tests import test_kesher_handover as handover_fixtures

ROOT = Path(__file__).resolve().parents[1]


class ProductionCutoverTests(unittest.TestCase):
    def runtime(self):
        from scripts.kesher_runtime.production_cutover import CutoverRuntime
        case = handover_fixtures.HandoverTests(); case.setUp()
        fence, services = protection_fixture()
        fence.review = case.backend.observation['approved_revision']
        fence.key_binding = case.backend.observation['key_binding']
        runtime = CutoverRuntime(fence=fence, backend=case.backend, inputs=case.params,
            closure=case.closure, key=lambda: 'synthetic-runtime-key-at-least-24-chars',
            infrastructure_check=lambda: None)
        return runtime, case, services

    def test_missing_provider_cannot_be_replaced_by_evidence_json(self):
        from scripts.kesher_runtime.production_ports import PrerequisitePort
        port = PrerequisitePort('notebooklm', 'exact-notebook')
        for operation in (lambda: port.inspect('owner/repo'),
                          lambda: port.exclude('owner/repo', 1, {'fenced': True})):
            with self.assertRaisesRegex(StateInvalid, 'CUTOVER_PREREQUISITE_NOTEBOOKLM'):
                operation()

    def test_trusted_live_input_supplier_is_not_copied_or_detached_from_transport(self):
        from scripts.kesher_runtime.production_cutover import CutoverRuntime
        runtime,case,_=self.runtime()
        class Supplier:
            def __deepcopy__(self,memo):raise TypeError('native transport cannot be copied')
            def __call__(self,loaded):return case.params
        supplier=Supplier()
        composed=CutoverRuntime(fence=runtime.fence,backend=case.backend,inputs=supplier,
            closure=case.closure,key=runtime.key,infrastructure_check=runtime.infrastructure_check)
        self.assertIs(composed.inputs,supplier)

    def test_all_six_preflight_before_first_effect_and_resource_specific_failure(self):
        from scripts.kesher_runtime.production_ports import PrerequisitePort
        runtime, case, services = self.runtime()
        runtime.fence.ports['image_provider'] = PrerequisitePort('image_provider', 'resource-id:image_provider')
        with self.assertRaisesRegex(StateInvalid, 'CUTOVER_PREREQUISITE_IMAGE_PROVIDER'):
            runtime.step()
        self.assertTrue(all(s.requests == 0 for s in services.values()))
        self.assertEqual(case.backend.writes, [])

    def test_infrastructure_failure_never_disables_or_changes_any_resource(self):
        runtime, case, services = self.runtime()
        def missing(): raise StateInvalid('CUTOVER_INFRASTRUCTURE_BOUNDARY_MISSING')
        runtime.infrastructure_check = missing
        with self.assertRaisesRegex(StateInvalid, 'INFRASTRUCTURE_BOUNDARY_MISSING'): runtime.step()
        self.assertTrue(all(s.requests == 0 for s in services.values()))
        self.assertEqual(case.backend.disables, [])

    def test_one_resource_effect_per_invocation_and_no_partial_admission(self):
        runtime, case, services = self.runtime()
        for count in range(1, 7):
            runtime.step()
            self.assertEqual(sum(s.requests for s in services.values()), count)
            self.assertEqual(case.backend.writes, [])
            if count < 6:
                with self.assertRaises(StateInvalid): runtime.fence.assert_exclusive('owner/repo')

    def test_lost_resource_response_adopts_on_restart_without_replay(self):
        from scripts.kesher_runtime.github import GitHubError
        runtime, case, services = self.runtime()
        services['github'].drop = True
        with self.assertRaises(GitHubError): runtime.step()
        runtime.step()
        self.assertEqual(services['github'].requests, 1)
        self.assertEqual(services['jules'].requests, 1)
        self.assertEqual(case.backend.writes, [])

    def test_competing_epoch_stops_before_any_more_effect(self):
        runtime, _, services = self.runtime(); runtime.step()
        runtime.fence.epoch = 'competitor'
        with self.assertRaises(StateInvalid): runtime.step()
        self.assertEqual(sum(s.requests for s in services.values()), 1)

    def test_live_external_session_surviving_actions_drain_blocks_prepared(self):
        runtime, case, services = self.runtime()
        for _ in range(6): runtime.step()
        services['jules'].actors = [{'id':'surviving-session', 'state':'IN_PROGRESS'}]
        case.backend.observation['external'] = runtime.fence.authority_observation()
        self.assertEqual(runtime.step()['phase'], 'WAITING_FOR_LEGACY_DRAIN')
        self.assertEqual(case.backend.writes, [])

    def test_restart_every_phase_uses_original_coordinator_and_never_dispatches(self):
        from scripts.kesher_runtime.production_cutover import CutoverRuntime
        from scripts.kesher_runtime.handover import PHASES, require_authority
        runtime, case, _ = self.runtime()
        for _ in range(6): runtime.step()
        seen = []
        for _ in range(50):
            case.backend.observation['external'] = runtime.fence.authority_observation()
            result = runtime.step(); phase = result['phase']
            if phase in PHASES and phase not in seen: seen.append(phase)
            if phase == 'VERIFIED': break
            with self.assertRaises(StateInvalid): require_authority(case.backend.document, case.backend.observe())
            runtime = CutoverRuntime(fence=runtime.fence, backend=case.backend, inputs=case.params,
                closure=case.closure, key=runtime.key, infrastructure_check=runtime.infrastructure_check)
        self.assertEqual(seen, list(PHASES))
        self.assertFalse(result['production_activated'])
        self.assertFalse(result['public_completion_inferred'])

    def test_bridge_guard_refuses_epoch_and_every_handover_phase(self):
        from scripts.kesher_runtime.bridge_admission import require_bridge
        from scripts.kesher_runtime.handover import PHASES
        require_bridge({'schema_version': 5})
        for phase in PHASES:
            with self.subTest(phase=phase), self.assertRaises(StateInvalid):
                require_bridge({'schema_version': 5, 'handover': {'phase': phase}})
        for state in ({'schema_version':6}, {'schema_version':5, 'github_exclusion':{'epoch':'one'}}):
            with self.assertRaises(StateInvalid): require_bridge(state)

    def test_dispatcher_admission_mode_cannot_widen_manual_bridge_admission(self):
        from scripts.kesher_runtime.bridge_admission import require_invocation
        from scripts.kesher_runtime.worker_entry import REPOSITORY
        path='.github/workflows/kesher-targeted-media-recovery-dispatch.yml'
        env={'GITHUB_REPOSITORY':REPOSITORY,'GITHUB_REF':'refs/heads/main','GITHUB_EVENT_NAME':'push',
             'GITHUB_WORKFLOW_REF':REPOSITORY+'/'+path+'@refs/heads/main'}
        require_invocation(env,dispatcher=True)
        with self.assertRaises(StateInvalid):require_invocation(env)
        for change in ({'GITHUB_EVENT_NAME':'workflow_dispatch'},{'GITHUB_REF':'refs/heads/other'},
                       {'GITHUB_WORKFLOW_REF':REPOSITORY+'/.github/workflows/kesher-short-v4.yml@refs/heads/main'}):
            with self.subTest(change=change),self.assertRaises(StateInvalid):require_invocation(env|change,dispatcher=True)

    def test_current_111_registration_inventory_is_complete_and_exact(self):
        from scripts.kesher_runtime.production_cutover import reconcile_registrations
        from scripts.kesher_runtime.authority_topology import policy
        evidence = json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/production-cutover-registration-baseline-20261004.json').read_text())
        rules = policy(ROOT)
        # The new cutover workflow is registered only after merge. Its independent
        # registration binding is a prerequisite, never a guessed service ID.
        del rules['workflows']['.github/workflows/kesher-production-cutover.yml']
        del rules['workflows']['.github/workflows/kesher-targeted-media-recovery-dispatch.yml']
        rows = reconcile_registrations(evidence['workflows'], rules)
        self.assertEqual(len(rows), 111)
        self.assertEqual(len(rules['registrations']), 37)
        for changed in (rows[:-1], rows + [{'id':999999999,'path':'.github/workflows/unknown.yml','state':'active'}]):
            with self.assertRaises(StateInvalid): reconcile_registrations(changed, rules)
        changed = copy.deepcopy(rows); changed[0]['id'] = 999999999
        with self.assertRaises(StateInvalid): reconcile_registrations(changed, rules)

    def test_non_github_control_roles_cannot_bless_a_bridge_or_cutover_schedule(self):
        from scripts.kesher_runtime.authority_topology import policy, check_definitions
        rules = policy(ROOT)
        definitions = {str(p.relative_to(ROOT)):p.read_text() for p in (ROOT/'.github/workflows').glob('*.yml')}
        for path in ('.github/workflows/kesher-production-cutover.yml', '.github/workflows/kesher-daily-video.yml', '.github/workflows/kesher-short-v4.yml'):
            changed = dict(definitions)
            changed[path] = changed[path].replace('  workflow_dispatch:', '  schedule:\n    - cron: "0 * * * *"\n  workflow_dispatch:', 1)
            changed_rules = copy.deepcopy(rules)
            import hashlib
            changed_rules['workflows'][path]['definition_sha256'] = hashlib.sha256(changed[path].encode()).hexdigest()
            with self.subTest(path=path), self.assertRaises(StateInvalid): check_definitions(changed, changed_rules)

    def test_late_main_dispatcher_is_pinned_guarded_retired_and_registration_complete(self):
        from scripts.kesher_runtime.production_cutover import reconcile_registrations
        from scripts.kesher_runtime.authority_topology import policy,check_definitions,classify_registered
        import hashlib
        rules=policy(ROOT);del rules['workflows']['.github/workflows/kesher-production-cutover.yml']
        rows=json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/production-cutover-registration-final-20261004.json').read_text())['workflows']
        self.assertEqual(len(reconcile_registrations(rows,rules)),112)
        path='.github/workflows/kesher-targeted-media-recovery-dispatch.yml'
        row=next(r for r in rows if r['path']==path)
        self.assertEqual(row['id'],374765037)
        self.assertEqual(classify_registered([row],rules)[0]['role'],'retired')
        text=(ROOT/path).read_text()
        self.assertLess(text.index('bridge_admission --dispatcher'),text.index('Resolve exact enabled recovery target'))
        definitions={p:(ROOT/p).read_text() for p in rules['workflows']}
        for changed in [text.replace('  push:','  workflow_dispatch:',1),text.replace("branches: [main]","branches: ['other']",1),
                        text.replace('bridge_admission --dispatcher','bridge_admission')]:
            changed_rules=copy.deepcopy(rules)
            changed_rules['workflows'][path]['definition_sha256']=hashlib.sha256(changed.encode()).hexdigest()
            with self.assertRaises(StateInvalid):check_definitions(definitions|{path:changed},changed_rules)


class CredentialGatewayTests(unittest.TestCase):
    def test_two_exact_dependabot_registrations_journal_cancel_and_terminal_readback(self):
        from scripts.kesher_runtime.github_drain import GithubDrain
        from scripts.kesher_runtime.authority_topology import run_identity
        from tests.test_kesher_github_drain import Journal
        from urllib.parse import urlsplit,parse_qs
        for wid,path in [(294204178,'dynamic/dependabot/dependabot-updates'),
                         (320961763,'dynamic/dependabot/update-graph')]:
            with self.subTest(path=path):
                journal=Journal()
                class Native:
                    def __init__(self):
                        self.workflow={'id':wid,'path':path,'state':'active'}
                        self.run={'id':42,'run_attempt':1,'workflow_id':wid,'path':path,
                                  'head_sha':'a'*40,'status':'queued','conclusion':None}
                        self.effects=[]
                    def request(self,method,url):
                        parsed=urlsplit(url);q=parse_qs(parsed.query);tail=parsed.path
                        if method=='GET':
                            if tail.endswith('/actions/workflows'):return {'total_count':1,'workflows':[copy.deepcopy(self.workflow)]}
                            if tail.endswith('/actions/runs'):
                                rows=[copy.deepcopy(self.run)] if self.run['status']==q['status'][0] else []
                                return {'total_count':len(rows),'workflow_runs':rows}
                            if '/actions/runs/42' in tail:return copy.deepcopy(self.run)
                            if tail.endswith('/actions/workflows/'+str(wid)):return copy.deepcopy(self.workflow)
                        entry=journal.document['github_exclusion']['drains'][str(wid)]
                        if method=='PUT' and tail.endswith('/disable'):
                            assert entry['disable']['attempts'][-1]=={'outcome':'intent'}
                            self.effects.append('disable');self.workflow['state']='disabled_manually';return {}
                        if method=='POST' and tail.endswith('/cancel'):
                            assert entry['runs']['42:1']['cancel']=={'outcome':'intent'}
                            self.effects.append('cancel');self.run.update(status='completed',conclusion='cancelled');return {}
                        raise AssertionError((method,url))
                native=Native();drain=GithubDrain(native,'owner/repo',journal=journal,
                    authority=lambda:'epoch-one',registered=lambda:[native.workflow])
                for _ in range(20):
                    result=drain.step(wid,path)
                    if result['status']=='drained':break
                self.assertEqual(result['status'],'drained')
                self.assertEqual(native.effects,['disable','cancel'])
                self.assertEqual(drain.observe(wid,path)['runs'][0]['run_attempt'],1)
                self.assertEqual(drain.observe(wid,path)['runs'][0]['conclusion'],'cancelled')
        with self.assertRaises(StateInvalid):run_identity(dict(native.run,path='dynamic/unreviewed/writer'))

    def test_separation_cannot_choose_its_own_repository_or_protected_resources(self):
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_git_exclusion import EpochGit
        from tests.test_kesher_authority_topology import AuthorityCapabilityTests
        fixture=AuthorityCapabilityTests()
        rules,row,binding,protected,proof=fixture.separation()
        fence,_=protection_fixture();raw=EpochGit()
        adapter=GitHubResourceExclusion(raw,'owner/repo',main_sha='b'*40,policy=fence._policy('github'),
            rules=rules,registered=lambda:[row],guard=fence.ports['github'],
            separation=lambda:{'binding':binding,'protected_resources':protected,'proofs':proof})
        with self.assertRaisesRegex(StateInvalid,'INFRASTRUCTURE_BOUNDARY_MISSING'): adapter.targets()
        self.assertFalse(any(m!='GET' for m,_,_ in raw.calls))

    def test_infrastructure_fresh_proof_must_match_independent_six_domain_binding(self):
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_git_exclusion import EpochGit
        from tests.test_kesher_authority_topology import AuthorityCapabilityTests
        fixture=AuthorityCapabilityTests();rules,row,binding,_,proof=fixture.separation()
        fence,_=protection_fixture();protected=copy.deepcopy(fence.bindings)
        binding.update(code_sha256='e'*64)
        fixture.rebind_separation(rules,row,binding,protected,proof)
        expected=copy.deepcopy(binding);resources=copy.deepcopy(protected)
        context={'binding':binding,'protected_resources':protected,'proofs':proof}
        adapter=GitHubResourceExclusion(EpochGit(),'owner/repo',main_sha='b'*40,
            policy=fence._policy('github'),rules=rules,registered=lambda:[row],guard=fence.ports['github'],
            separation=lambda:context,separation_binding=expected,protected_resources=resources)
        self.assertEqual(adapter.targets(),[])
        for field,value in [('repo','other/repo'),('policy_sha256','9'*64),('code_sha256','8'*64)]:
            context['binding']=dict(binding,**{field:value})
            with self.subTest(field=field),self.assertRaises(StateInvalid):adapter.targets()
        context['binding']=binding
        for field in protected:
            context['protected_resources']=dict(protected,**{field:'different-service-resource'})
            with self.subTest(resource=field),self.assertRaises(StateInvalid):adapter.targets()
        context['protected_resources']={k:v for k,v in protected.items() if k!='youtube'}
        with self.assertRaises(StateInvalid):adapter.targets()

    def test_batch_recertification_78_targets_bounds_reads_and_rejects_bridge_race(self):
        from scripts.kesher_runtime.github_drain import GithubDrain
        from scripts.kesher_runtime.authority_topology import policy
        from tests.test_kesher_github_drain import Journal
        from urllib.parse import urlsplit,parse_qs
        rules=policy(ROOT)
        rows=json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/production-cutover-registration-baseline-20261004.json').read_text())['workflows']
        targets=[r for r in rows if r['path'] in rules['registrations'] or
                 rules['workflows'][r['path']]['role'] in {'retired','emergency_bridge'}]
        self.assertEqual(len(targets),78)
        for r in targets:r['state']='disabled_manually'
        journal=Journal();drains=journal.document['github_exclusion']['drains']
        for r in targets:
            proof={'status':'drained','epoch':'epoch-one','workflow_id':r['id'],'workflow_path':r['path'],
                   'state':'disabled_manually','runs':[],'readback_sha256':'f'*64}
            drains[str(r['id'])]={'workflow_id':r['id'],'workflow_path':r['path'],'epoch':'epoch-one',
                'observed_disabled':True,'disable':{'attempts':[]},'runs':{},'proof':proof}
        class Native:
            def __init__(self):self.calls=[];self.race=False
            def request(self,method,path):
                self.calls.append((method,path));url=urlsplit(path);q=parse_qs(url.query)
                if url.path.endswith('/actions/workflows'):
                    page=int(q['page'][0]);return {'total_count':len(rows),'workflows':copy.deepcopy(rows[(page-1)*100:page*100])}
                if url.path.endswith('/actions/runs'):
                    active=[]
                    if self.race and q['status'][0]=='queued':
                        bridge=next(r for r in targets if r['path'].endswith('kesher-short-v4.yml'))
                        active=[{'id':99,'run_attempt':1,'workflow_id':bridge['id'],'path':bridge['path'],
                                 'head_sha':'a'*40,'status':'queued','conclusion':None}]
                    return {'total_count':len(active),'workflow_runs':active}
                raise AssertionError(path)
        native=Native();drain=GithubDrain(native,'owner/repo',journal=journal,authority=lambda:'epoch-one',registered=lambda:rows)
        pairs=[(r['id'],r['path']) for r in targets]
        self.assertEqual(len(drain.observe_many(pairs)),78)
        self.assertEqual(len(native.calls),18)
        native.race=True
        with self.assertRaisesRegex(StateInvalid,'RUN_AFTER_PROOF'):drain.observe_many(pairs)
        native.race=False;targets[-1]['state']='active'
        with self.assertRaisesRegex(StateInvalid,'REENABLED'):drain.observe_many(pairs)

    def test_gateway_rejects_drain_intent_for_every_nonretirement_role(self):
        from scripts.kesher_runtime.cutover_gateway import GuardedGitHub
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch, GitDrainJournal
        from tests.test_kesher_git_exclusion import EpochGit
        from scripts.kesher_runtime.authority_topology import policy
        rules=policy(ROOT)
        for path,entry in rules['workflows'].items():
            if entry['role'] not in {'worker','controller','diagnostic','separate_infrastructure'}:continue
            with self.subTest(path=path):
                fence,_=protection_fixture();fence.establish();raw=EpochGit()
                approval={'repo':'owner/repo','main_sha':'b'*40,'code_sha256':'e'*64,
                          'policy_sha256':'a'*64,'closed_evidence_sha256':'c'*64}
                gateway=GuardedGitHub(raw,repo='owner/repo',policy=fence._policy('github'),
                    approval=approval,boundary=fence.ports['github'])
                epoch=GitExclusionEpoch(gateway,'owner/repo',epoch=fence.epoch,owner=fence.owner,
                    resource_id='repository-id',main_sha='b'*40,policy_sha256=digest(fence._policy('github')))
                epoch.acquire('a'*40);journal=GitDrainJournal(epoch);journal.initialize()
                loaded=journal.load();proposed=copy.deepcopy(loaded.state)
                proposed['github_exclusion']['drains']['1']={'workflow_id':1,'workflow_path':path,
                    'epoch':fence.epoch,'observed_disabled':False,'disable':{'attempts':[]},'runs':{},'proof':None}
                with self.assertRaisesRegex(StateInvalid,'RETIREMENT_TARGET'):journal.save(loaded,proposed)
                self.assertFalse(any('/disable' in p or '/cancel' in p for _,p,_ in raw.calls))

    def test_real_gateway_restart_all_nine_phases_and_uncertain_cas(self):
        import base64
        from scripts.kesher_runtime.cutover_gateway import GuardedGitHub
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch, GitDrainJournal
        from scripts.kesher_runtime.handover_github import GitHubHandover
        from scripts.kesher_runtime.live_cutover import OriginalMigrationInputs
        from scripts.kesher_runtime.handover import Coordinator, PHASES, require_authority
        from scripts.kesher_runtime.github import GitHubError
        from tests.test_kesher_git_exclusion import EpochGit
        case=handover_fixtures.HandoverTests();case.setUp();fence=case.backend.fence
        class Native(EpochGit):
            def request(self,method,path,body=None):
                if method=='GET' and '/git/blobs/' in path:
                    sha=path.split('/')[-1]
                    return {'sha':sha,'encoding':'base64','content':base64.b64encode(self.blobs[sha]).decode()}
                return super().request(method,path,body)
        raw=Native(case.params['controller'])
        approval=dict(case.backend.observation['approved_revision'],main_sha=case.params['main_sha'])
        material={k:v for k,v in case.params.items() if k not in {'controller','controller_sha','main_sha'}}
        def fresh():
            gate=GuardedGitHub(raw,repo='owner/repo',policy=fence._policy('github'),approval=approval,
                              boundary=fence.ports['github'])
            backend=GitHubHandover(gate,'owner/repo',observer=case.backend.observe,fence=fence)
            supplier=OriginalMigrationInputs(gate,'owner/repo',main_sha=case.params['main_sha'],
                                            material=material,approved_digest=digest(material))
            return gate,backend,supplier
        gate,backend,supplier=fresh()
        epoch=GitExclusionEpoch(gate,'owner/repo',epoch=fence.epoch,owner=fence.owner,
            resource_id='repository-id',main_sha=case.params['main_sha'],policy_sha256=digest(fence._policy('github')))
        epoch.acquire('a'*40);GitDrainJournal(epoch).initialize()
        original=backend.read_snapshot()
        case.backend.observation['workflows'][2]['state']='disabled_manually'
        raw.drop=True
        with self.assertRaises(GitHubError):
            Coordinator(backend,supplier(backend.read_snapshot()),closure=case.closure,
                key=lambda:'synthetic-runtime-key-at-least-24-chars').tick()
        cas_count=sum(p=='/graphql' for _,p,_ in raw.calls)
        gate,backend,supplier=fresh()
        self.assertEqual(backend.read_snapshot().state['handover']['phase'],'PREPARED')
        self.assertEqual(sum(p=='/graphql' for _,p,_ in raw.calls),cas_count)
        seen=['PREPARED']
        for _ in range(30):
            gate,backend,supplier=fresh();loaded=backend.read_snapshot()
            phase=Coordinator(backend,supplier(loaded),closure=case.closure,
                key=lambda:'synthetic-runtime-key-at-least-24-chars').tick()
            if phase in PHASES and phase not in seen:seen.append(phase)
            if phase=='VERIFIED':break
            with self.assertRaises(StateInvalid):require_authority(backend.read_snapshot().state,case.backend.observe())
        self.assertEqual(seen,list(PHASES))
        self.assertEqual(raw.refs['main'],case.params['main_sha'])
        self.assertEqual(supplier(backend.read_snapshot())['controller'],original.state)
        self.assertEqual(supplier(backend.read_snapshot())['controller_sha'],original.blob_sha)
        self.assertFalse(any('/dispatches' in p or '/deployments' in p for _,p,_ in raw.calls))

    def test_migration_inputs_recover_original_exact_blob_after_schema_import(self):
        from scripts.kesher_runtime.live_cutover import OriginalMigrationInputs
        from scripts.kesher_runtime.handover_github import GitHubHandover
        from tests.test_kesher_handover_github import GitService
        from types import SimpleNamespace
        case=handover_fixtures.HandoverTests();case.setUp()
        raw=GitService(case.params['controller'],'b'*40)
        original=GitHubHandover(raw,'owner/repo',observer=None,fence=None).read_snapshot()
        material={k:v for k,v in case.params.items() if k not in {'controller','controller_sha','main_sha'}}
        supplier=OriginalMigrationInputs(raw,'owner/repo',main_sha='b'*40,material=material,
                                       approved_digest=digest(material))
        self.assertEqual(supplier(original)['controller'],case.params['controller'])
        imported=SimpleNamespace(state={'schema_version':6,'handover':{'basis':{'legacy_blob_sha':original.blob_sha}}})
        old_request=raw.request
        def blobs(method,path,body=None):
            if '/git/blobs/' in path:
                import base64
                sha=path.split('/')[-1]
                return {'sha':sha,'encoding':'base64','content':base64.b64encode(raw.blobs[sha]).decode()}
            return old_request(method,path,body)
        raw.request=blobs
        recovered=supplier(imported)
        self.assertEqual(recovered['controller'],case.params['controller'])
        self.assertEqual(recovered['controller_sha'],original.blob_sha)
        self.assertEqual(recovered['main_sha'],'b'*40)
        with self.assertRaises(StateInvalid):OriginalMigrationInputs(raw,'owner/repo',main_sha='b'*40,
            material=material,approved_digest='f'*64)

    def test_actual_gateway_refuses_general_publication_and_arbitrary_git_objects(self):
        from scripts.kesher_runtime.cutover_gateway import GuardedGitHub
        from tests.test_kesher_git_exclusion import EpochGit
        fence, _ = protection_fixture(); fence.establish()
        raw = EpochGit()
        approval = {'repo':'owner/repo', 'main_sha':'b'*40, 'code_sha256':'e'*64,
                    'policy_sha256':'a'*64, 'closed_evidence_sha256':'c'*64}
        gateway = GuardedGitHub(raw, repo='owner/repo', policy=fence._policy('github'),
            approval=approval, boundary=fence.ports['github'])
        for method, path, body in (
                ('POST','/repos/owner/repo/deployments', {}),
                ('POST','/repos/owner/repo/actions/workflows/x/dispatches', {'ref':'main'}),
                ('POST','/repos/owner/repo/git/trees', {'base_tree':'c'*40,'tree':[]}),
                ('PUT','/repos/owner/repo/contents/anything', {'branch':'main'}),
                ('POST','/graphql', {'query':'arbitrary mutation'})):
            with self.subTest(path=path), self.assertRaises(StateInvalid): gateway.request(method,path,body)
        self.assertFalse(any(method != 'GET' for method, _, _ in raw.calls))

    def test_gateway_stages_only_the_original_automation_state_tree_epoch(self):
        from scripts.kesher_runtime.cutover_gateway import GuardedGitHub
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch
        from tests.test_kesher_git_exclusion import EpochGit
        fence, _ = protection_fixture(); fence.establish()
        raw = EpochGit()
        approval = {'repo':'owner/repo','main_sha':'b'*40,'code_sha256':'e'*64,
                    'policy_sha256':'a'*64,'closed_evidence_sha256':'c'*64}
        gateway = GuardedGitHub(raw,repo='owner/repo',policy=fence._policy('github'),
            approval=approval,boundary=fence.ports['github'])
        epoch = GitExclusionEpoch(gateway,'owner/repo',epoch=fence.epoch,owner=fence.owner,
            resource_id='repository-id',main_sha='b'*40,policy_sha256=digest(fence._policy('github')))
        anchor = epoch.acquire('a'*40)
        self.assertEqual(raw.commits[anchor['commit_sha']], raw.commits['a'*40])
        self.assertEqual(raw.refs['main'], 'b'*40)

    def test_absent_or_alive_predecessor_boundary_refuses_before_git_epoch(self):
        from scripts.kesher_runtime.cutover_gateway import GuardedGitHub
        from scripts.kesher_runtime.production_ports import PrerequisitePort
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch
        from tests.test_kesher_git_exclusion import EpochGit
        fence, _ = protection_fixture(); raw=EpochGit()
        approval={'repo':'owner/repo','main_sha':'b'*40,'code_sha256':'e'*64,
                  'policy_sha256':'a'*64,'closed_evidence_sha256':'c'*64}
        gateway=GuardedGitHub(raw,repo='owner/repo',policy=fence._policy('github'),approval=approval,
                             boundary=PrerequisitePort('github','repository-id'))
        epoch=GitExclusionEpoch(gateway,'owner/repo',epoch=fence.epoch,owner=fence.owner,
            resource_id='repository-id',main_sha='b'*40,policy_sha256=digest(fence._policy('github')))
        with self.assertRaises(StateInvalid): epoch.acquire('a'*40)
        self.assertFalse(any(method!='GET' for method,_,_ in raw.calls))

    def test_oidc_verifies_signature_and_exact_main_attempt_and_never_accepts_self_claims(self):
        import base64, time
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        from scripts.kesher_runtime.cutover_auth import ActionsIdentity
        encode=lambda raw:base64.urlsafe_b64encode(raw).decode().rstrip('=')
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        public=key.public_key().public_numbers()
        integer=lambda x:encode(x.to_bytes((x.bit_length()+7)//8,'big'))
        now=int(time.time())
        claims={'iss':'https://token.actions.githubusercontent.com','aud':'https://cutover.example',
                'exp':now+300,'nbf':now-1,'iat':now,'repository':'owner/repo','repository_id':'123',
                'ref':'refs/heads/main','workflow_ref':'owner/repo/.github/workflows/kesher-production-cutover.yml@refs/heads/main',
                'workflow_sha':'b'*40,'sha':'b'*40,'run_id':'42','run_attempt':'2', 'event_name':'workflow_dispatch',
                'environment':'kesher-cutover'}
        def token(values):
            message=(encode(json.dumps({'alg':'RS256','kid':'one'}).encode())+'.'+encode(json.dumps(values).encode())).encode()
            return message.decode()+'.'+encode(key.sign(message,padding.PKCS1v15(),hashes.SHA256()))
        class NativeReadback:
            def request(self,method,path):
                if path.endswith('/git/ref/heads/main'): return {'object':{'sha':'b'*40}}
                if path.endswith('/actions/runs/42'):return {'id':42,'run_attempt':2,'status':'in_progress',
                    'head_sha':'b'*40,'head_branch':'main','event':'workflow_dispatch',
                    'path':'.github/workflows/kesher-production-cutover.yml'}
                raise AssertionError(path)
        auth=ActionsIdentity(NativeReadback(),repo='owner/repo',repository_id='123',main_sha='b'*40,
            audience='https://cutover.example',jwks=lambda:{'keys':[{'kty':'RSA','kid':'one','n':integer(public.n),'e':integer(public.e)}]})
        self.assertEqual(auth.verify(token(claims)), '42/2')
        for change in ({'repository':'other/repo'}, {'workflow_sha':'c'*40}, {'run_attempt':'1'},
                       {'aud':'https://evil.example'}, {'exp':now-1}, {'ref':'refs/heads/topic'},
                       {'environment':'other'}, {'job_workflow_ref':'unreviewed/reusable@main'}):
            with self.subTest(change=change), self.assertRaises(StateInvalid): auth.verify(token(claims|change))
        bad=token(claims).split('.'); bad[-1]=encode(b'not-a-signature')
        with self.assertRaises(StateInvalid): auth.verify('.'.join(bad))

    def test_durable_invocation_intent_precedes_effect_and_replay_is_denied_after_restart(self):
        from tempfile import TemporaryDirectory
        from scripts.kesher_runtime.cutover_service import InvocationJournal, CutoverApplication
        from scripts.kesher_runtime.production_cutover import CutoverRuntime
        effects=[]
        class Runtime:
            def step(self): effects.append('transition'); return CutoverRuntime._report('PREPARED')
        class Identity:
            def verify(self,token): return '42/1'
        with TemporaryDirectory() as directory:
            path=Path(directory)/'invocations.sqlite'; InvocationJournal.initialize(path)
            app=CutoverApplication(runtime=Runtime(),identity=Identity(),journal=InvocationJournal(path),
                epoch='one',reviewed_revision='b'*40,review_check=lambda:None)
            request={'epoch':'one','reviewed_revision':'b'*40}
            self.assertEqual(app.step('signed-identity',request)['phase'],'PREPARED')
            app.journal=InvocationJournal(path)
            with self.assertRaises(StateInvalid):app.step('signed-identity',request)
            with self.assertRaises(StateInvalid):app.step('signed-identity',request|{'epoch':'other'})
            path.unlink()
            with self.assertRaises(StateInvalid):app.step('signed-identity',request)
            self.assertEqual(effects,['transition'])

    def test_client_binds_main_and_never_retries_an_uncertain_gateway_post(self):
        import io
        from scripts.kesher_runtime.cutover_entry import invoke
        from scripts.kesher_runtime.worker_entry import REPOSITORY
        from scripts.kesher_runtime.cutover_auth import WORKFLOW
        main='b'*40
        env={'GITHUB_REPOSITORY':REPOSITORY,'GITHUB_REF':'refs/heads/main',
            'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_WORKFLOW_REF':REPOSITORY+'/'+WORKFLOW+'@refs/heads/main',
            'GITHUB_SHA':main,'ACTIONS_ID_TOKEN_REQUEST_URL':'https://pipelines.actions.githubusercontent.com/token',
            'ACTIONS_ID_TOKEN_REQUEST_TOKEN':'fixture-request-credential'}
        class Native:
            def request(self,method,path):return {'object':{'sha':main}}
        calls=[]
        def transport(request,timeout):
            calls.append(request)
            if request.get_method()=='GET':return io.BytesIO(b'{"value":"signed-fixture"}')
            raise OSError('lost response')
        with self.assertRaises(OSError):invoke(epoch='one',reviewed_revision=main,gateway_url='https://cutover.example',
            environ=env,github=Native(),checkout=main,opener=transport)
        self.assertEqual([r.get_method() for r in calls],['GET','POST'])
        self.assertEqual(json.loads(calls[-1].data),{'epoch':'one','reviewed_revision':main})
        calls.clear()
        with self.assertRaises(StateInvalid):invoke(epoch='one',reviewed_revision=main,gateway_url='https://cutover.example',
            environ=env|{'GITHUB_REF':'refs/heads/other'},github=Native(),checkout=main,opener=transport)
        self.assertEqual(calls,[])

    def test_unseparated_current_infrastructure_is_never_blindly_disabled(self):
        from scripts.kesher_runtime.authority_topology import policy
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_git_exclusion import EpochGit
        from tests.test_kesher_external_exclusion import ProtectedService
        rules=policy(ROOT)
        del rules['workflows']['.github/workflows/kesher-production-cutover.yml']
        del rules['workflows']['.github/workflows/kesher-targeted-media-recovery-dispatch.yml']
        evidence=json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/production-cutover-registration-baseline-20261004.json').read_text())
        fence,_=protection_fixture(); raw=EpochGit(); guard=ProtectedService('github')
        adapter=GitHubResourceExclusion(raw,'owner/repo',main_sha='b'*40,policy=fence._policy('github'),
            rules=rules,registered=lambda:evidence['workflows'],guard=guard)
        with self.assertRaisesRegex(StateInvalid,'INFRASTRUCTURE_BOUNDARY_MISSING'):adapter.targets()
        self.assertFalse(any(m!='GET' for m,_,_ in raw.calls))
        self.assertEqual(guard.requests,0)


if __name__ == '__main__': unittest.main()
