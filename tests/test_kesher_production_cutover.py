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
        # These read-only Master Owner workflows were added on October 31 and
        # have no registration in the immutable October 4 inventory.
        del rules['workflows']['.github/workflows/kesher-master-intent-shadow.yml']
        del rules['workflows']['.github/workflows/kesher-master-owner-foundation-ci.yml']
        # Project only this immutable October 4 fixture; October 6 metadata
        # authority remains classified in the current policy and refusal test.
        del rules['workflows']['.github/workflows/kesher-exact-short-metadata-recovery-20261006.yml']
        # The new cutover workflow is registered only after merge. Its independent
        # registration binding is a prerequisite, never a guessed service ID.
        del rules['workflows']['.github/workflows/kesher-production-cutover.yml']
        del rules['workflows']['.github/workflows/kesher-targeted-media-recovery-dispatch.yml']
        del rules['workflows']['.github/workflows/kesher-controller-liveness.yml']
        # This immutable October 4 inventory predates the October 25 advisory reviewer.
        # Never invent its GitHub registration ID in historical evidence; project the
        # policy to the exact definition set that existed when the fixture was captured.
        del rules['workflows']['.github/workflows/kesher-video-advisory-review.yml']
        rows = reconcile_registrations(evidence['workflows'], rules)
        self.assertEqual(len(rows), 111)
        self.assertEqual(len(rules['registrations']), 57)
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
        # These read-only Master Owner workflows were added on October 31 and
        # have no registration in the immutable October 4 inventory.
        del rules['workflows']['.github/workflows/kesher-master-intent-shadow.yml']
        del rules['workflows']['.github/workflows/kesher-master-owner-foundation-ci.yml']
        # This immutable October 4 snapshot predates the metadata workflow.
        del rules['workflows']['.github/workflows/kesher-exact-short-metadata-recovery-20261006.yml']
        del rules['workflows']['.github/workflows/kesher-controller-liveness.yml']
        # The October 4 final snapshot also predates the October 25 advisory reviewer;
        # its real registration must be observed after merge, never guessed here.
        del rules['workflows']['.github/workflows/kesher-video-advisory-review.yml']
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

    def test_batch_recertification_92_targets_bounds_reads_and_rejects_bridge_race(self):
        from scripts.kesher_runtime.github_drain import GithubDrain
        from scripts.kesher_runtime.authority_topology import policy
        from tests.test_kesher_github_drain import Journal
        from urllib.parse import urlsplit,parse_qs
        rules=policy(ROOT)
        rows=json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/production-cutover-registration-baseline-20261004.json').read_text())['workflows']
        targets=[r for r in rows if r['path'] in rules['registrations'] or
                 rules['workflows'][r['path']]['role'] in {'retired','emergency_bridge'}]
        self.assertEqual(len(targets),92)
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
        self.assertEqual(len(drain.observe_many(pairs)),92)
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
        # These read-only Master Owner workflows were added on October 31 and
        # have no registration in the immutable October 4 inventory.
        del rules['workflows']['.github/workflows/kesher-master-intent-shadow.yml']
        del rules['workflows']['.github/workflows/kesher-master-owner-foundation-ci.yml']
        del rules['workflows']['.github/workflows/kesher-production-cutover.yml']
        del rules['workflows']['.github/workflows/kesher-targeted-media-recovery-dispatch.yml']
        del rules['workflows']['.github/workflows/kesher-controller-liveness.yml']
        # This refusal fixture starts from the immutable October 4 registration snapshot.
        # The October 25 advisory workflow has no historical registration in that evidence;
        # project it out rather than fabricating an ID, while retaining the explicit Oct6 overlay below.
        del rules['workflows']['.github/workflows/kesher-video-advisory-review.yml']
        evidence=json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/production-cutover-registration-baseline-20261004.json').read_text())
        # Retain the current metadata writer in this unseparated-authority
        # refusal test rather than treating the dated fixture as current.
        evidence['workflows'].append({'id':376735017,
            'path':'.github/workflows/kesher-exact-short-metadata-recovery-20261006.yml',
            'state':'active'})
        fence,_=protection_fixture(); raw=EpochGit(); guard=ProtectedService('github')
        adapter=GitHubResourceExclusion(raw,'owner/repo',main_sha='b'*40,policy=fence._policy('github'),
            rules=rules,registered=lambda:evidence['workflows'],guard=guard)
        with self.assertRaisesRegex(StateInvalid,'INFRASTRUCTURE_BOUNDARY_MISSING'):adapter.targets()
        self.assertFalse(any(m!='GET' for m,_,_ in raw.calls))
        self.assertEqual(guard.requests,0)



class CutoverApprovalReadinessTests(unittest.TestCase):
    """Owner approval remains unreachable until an actual matched gateway responds."""

    def _code(self):
        source = (ROOT / '.github/workflows/kesher-production-cutover.yml').read_text()
        self.assertIn('  transition:\n    needs: readiness\n', source)
        self.assertIn('    environment: kesher-cutover\n', source)
        ready = source.split('  readiness:\n', 1)[1].split('\n  transition:\n', 1)[0]
        self.assertNotIn('environment: kesher-cutover', ready)
        body = ready.split('        run: |\n', 1)[1]
        return '\n'.join(row[10:] if row.startswith('          ') else row for row in body.splitlines())

    def _run(self, **values):
        import os
        import subprocess
        import sys
        env = dict(os.environ, GATEWAY_URL='', REVIEWED_REVISION='a'*40,
                   ACTUAL_REVISION='a'*40, CUTOVER_EPOCH='epoch1')
        env.update(values)
        return subprocess.run([sys.executable, '-c', self._code()], env=env,
                              text=True, capture_output=True, timeout=20)

    def test_missing_gateway_never_requests_approval(self):
        result = self._run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('KESHER_CUTOVER_GATEWAY_URL_UNCONFIGURED', result.stderr)

    def test_unreviewed_main_never_requests_approval(self):
        result = self._run(REVIEWED_REVISION='b'*40)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REVIEWED_MAIN_SHA_MISMATCH', result.stderr)

    def test_untrusted_scheme_rejected_without_http_call(self):
        result = self._run(GATEWAY_URL='http://example.com')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PINNED_HTTPS_GATEWAY_REQUIRED', result.stderr)

    def test_health_check_is_not_production_activation(self):
        code = self._code()
        self.assertIn('/healthz', code)
        self.assertIn('GATEWAY_HEALTH_REVISION_OR_EPOCH_MISMATCH', code)
        self.assertIn('does not attest native resource fences', code)


class GithubOwnerReadinessTests(unittest.TestCase):
    """Approval of the alternative cannot launch a provider or revive Jules."""

    def _github(self, *, old_status='disabled_manually', old_runs=None, provider_runs=None, schema=5, main='a'*40, orphan_jobs=0, orphan_updated='2026-11-08T20:55:18Z'):
        import base64
        import json
        from unittest.mock import Mock
        gh=Mock()
        state=json.dumps({'schema_version': schema, 'cycle': '2026-11-08'}).encode()
        def request(method, path):
            self.assertEqual(method, 'GET')
            if path.endswith('/git/ref/heads/main'):
                return {'object': {'sha': main}}
            if path.endswith('/actions/workflows/337960554'):
                return {'id':337960554, 'state':old_status}
            if path.endswith('/actions/runs/42522546178'):
                return {'id':42522546178,'workflow_id':337960554,'run_attempt':1,
                        'status':'queued','conclusion':None,'event':'workflow_dispatch',
                        'created_at':'2026-11-08T20:55:18Z','updated_at':orphan_updated}
            if path.endswith('/actions/runs/42522546178/jobs?per_page=100'):
                return {'jobs':[{'id':1}]*orphan_jobs,'total_count':orphan_jobs}
            if '/actions/workflows/' in path and '/runs?status=' in path:
                is_legacy = '/actions/workflows/337960554/runs?' in path
                status = path.split('status=', 1)[1].split('&', 1)[0]
                candidate = (old_runs if is_legacy else provider_runs) or []
                rows = [row for row in candidate if row['status'] == status]
                return {'workflow_runs':rows,'total_count':len(rows)}
            if path.endswith('/contents/.kesher-controller/state.json?ref=automation-state'):
                return {'sha':'b'*40,'encoding':'base64','content':base64.b64encode(state).decode()}
            raise AssertionError(path)
        gh.request.side_effect=request
        return gh

    def _run(self, gh):
        from scripts.kesher_runtime.github_owner_readiness import inventory
        return inventory(gh,expected_main='a'*40,
            workflow_ref='yanivsa/kesher-website/.github/workflows/kesher-controller-liveness.yml@refs/heads/main',
            event_name='workflow_dispatch',repo='yanivsa/kesher-website')

    def test_exact_zero_job_old_orphan_is_quarantined_read_only(self):
        result=self._run(self._github(old_runs=[{'id':42522546178,'status':'queued'}]))
        self.assertEqual(result['status'],'READY_FOR_REVIEWED_MIGRATION_ONLY')
        self.assertFalse(result['production_activated'])
        self.assertFalse(result['provider_dispatch'])
        self.assertEqual(result['quarantined_old_orphans'][0]['run'],42522546178)

    def test_unknown_or_changed_legacy_queue_still_blocks(self):
        for run, kwargs in (
            ({'id':111,'status':'queued'}, {}),
            ({'id':42522546178,'status':'queued'}, {'orphan_jobs':1}),
            ({'id':42522546178,'status':'queued'}, {'orphan_updated':'2026-11-17T12:00:00Z'}),
        ):
            with self.subTest(run=run,kwargs=kwargs):
                result=self._run(self._github(old_runs=[run],**kwargs))
                self.assertEqual(result['status'],'BLOCKED_EXISTING_OWNER_OR_TASK')
                self.assertEqual(result['quarantined_old_orphans'],[])

    def test_unresolved_provider_job_refuses_activation(self):
        result=self._run(self._github(provider_runs=[{'id':42,'status':'in_progress'}]))
        self.assertEqual(result['status'],'BLOCKED_EXISTING_OWNER_OR_TASK')
        self.assertFalse(result['provider_dispatch'])

    def test_quiescent_inventory_only_allows_reviewed_migration(self):
        result=self._run(self._github())
        self.assertEqual(result['status'],'READY_FOR_REVIEWED_MIGRATION_ONLY')
        self.assertFalse(result['production_activated'])
        self.assertEqual(result['legacy_cycle'],'2026-11-08')

    def test_active_legacy_controller_cannot_approve(self):
        result=self._run(self._github(old_status='active'))
        self.assertEqual(result['status'],'BLOCKED_EXISTING_OWNER_OR_TASK')

    def test_legacy_schema_or_main_drift_fails_closed(self):
        from scripts.kesher_runtime.state import StateInvalid
        with self.assertRaises(StateInvalid):
            self._run(self._github(schema=6))
        with self.assertRaises(StateInvalid):
            self._run(self._github(main='c'*40))

    def test_workflow_has_no_production_side_effect_for_probe(self):
        text=(ROOT/'.github/workflows/kesher-controller-liveness.yml').read_text()
        probe=text.split('  github_owner_probe:\n',1)[1].split('\n  github_owner_prepare:',1)[0]
        self.assertNotIn('environment: kesher-cutover',probe)
        self.assertNotIn('id-token: write',probe)
        self.assertNotIn('secrets.',probe)
        self.assertIn('contents: read',probe)
        self.assertIn('github_owner_readiness',probe)
        self.assertIn("inputs.route != 'github_only_probe'", text)


class GithubOnlyAtomicLedgerTests(unittest.TestCase):
    """Disposable GraphQL CAS test; never accesses live GitHub/providers."""

    def setUp(self):
        import base64
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        self.expected_main = 'a' * 40
        self.command = 'f' * 64
        self.ledger = {
            'schema_version': 1, 'epoch': 'safe-epoch-1',
            'owner': 'github-only', 'reviewed_main_sha': self.expected_main,
            'activation': 'PROTECTED_VERIFIED', 'inventory_complete': True,
            'commands': {},
        }
        self.bytes = (canonical_json(self.ledger) + '\n').encode()
        self.blob = _blob_sha(self.bytes)
        self.initial_ref = 'b' * 40
        self.initial_tree = 'c' * 40

        class FakeGithub:
            def __init__(this):
                this.ref = self.initial_ref
                this.main = self.expected_main
                this.tree = self.initial_tree
                this.raw = self.bytes
                this.blob = self.blob
                this.calls = []
                this.conflict = False
                this.unknown_ack = False
                this.missing = False

            def request(this, method, path, body=None, **kwargs):
                this.calls.append((method, path, body))
                if method == 'GET':
                    if path.endswith('/git/ref/heads/main'):
                        return {'object': {'sha': this.main}}
                    if path.endswith('/git/ref/heads/automation-state'):
                        return {'object': {'sha': this.ref}}
                    if '/git/commits/' in path:
                        ref = path.rsplit('/', 1)[1]
                        return {'sha': ref, 'tree': {'sha': this.tree}}
                    if '/contents/.kesher-controller/github-only-owner.json?ref=' in path:
                        if this.missing:
                            return None
                        return {'sha': this.blob, 'encoding': 'base64',
                                'content': base64.b64encode(this.raw).decode()}
                    if path == '/repos/yanivsa/kesher-website':
                        return {'node_id': 'repo-node-123'}
                if method == 'POST':
                    if path.endswith('/git/blobs'):
                        this.next_raw = base64.b64decode(body['content'], validate=True)
                        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
                        return {'sha': _blob_sha(this.next_raw)}
                    if path.endswith('/git/trees'):
                        self_outer = this
                        self_outer.expected_old_tree = body['base_tree']
                        return {'sha': 'd' * 40}
                    if path.endswith('/git/commits'):
                        this.expected_parent = body['parents'][0]
                        return {'sha': 'e' * 40}
                    if path == '/graphql':
                        updates = body['variables']['input']['refUpdates']
                        assert len(updates) == 2
                        assert updates[0] == {'name':'refs/heads/main',
                            'beforeOid':this.main,'afterOid':this.main,'force':False}
                        assert updates[1]['beforeOid'] == this.ref
                        assert updates[1]['afterOid'] == 'e'*40
                        if this.conflict:
                            return {'errors': [{'message': 'Stale ref'}]}
                        this.ref = 'e'*40
                        this.tree = 'd'*40
                        this.raw = this.next_raw
                        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
                        this.blob = _blob_sha(this.raw)
                        if this.unknown_ack:
                            return {'data': {'updateRefs': {'clientMutationId': None}}}
                        return {'data': {'updateRefs': {
                            'clientMutationId': body['variables']['input']['clientMutationId']}}}
                raise AssertionError((method, path))

        self.gh = FakeGithub()
        from scripts.kesher_runtime.github_only_owner_store import GitHubOnlyLedgerStore
        self.store = GitHubOnlyLedgerStore(self.gh)

    def _claim(self, snapshot, *, provider_tasks=None, pending=None):
        return self.store.claim(
            snapshot, epoch='safe-epoch-1', command_id=self.command,
            workflow_run='123:1',
            observed_provider_tasks={} if provider_tasks is None else provider_tasks,
            pending_github_runs=[] if pending is None else pending,
        )

    def test_exact_ref_cas_claim_readback_and_duplicate_noop(self):
        initial = self.store.load(reviewed_main_sha=self.expected_main)
        status, written = self._claim(initial)
        self.assertEqual(status, 'CLAIMED')
        self.assertEqual(written.ref_sha, 'e'*40)
        self.assertEqual(written.document['commands'][self.command]['run_id'], '123:1')
        self.assertEqual(self.gh.expected_old_tree, 'c'*40)
        self.assertEqual(self.gh.expected_parent, 'b'*40)
        before = sum(path == '/graphql' for _, path, _ in self.gh.calls)
        status, _ = self._claim(written)
        self.assertEqual(status, 'NOOP')
        self.assertEqual(before, sum(path == '/graphql' for _, path, _ in self.gh.calls))

    def test_competing_ref_is_conflict_not_retry(self):
        from scripts.kesher_runtime.state import StateConflict
        initial = self.store.load(reviewed_main_sha=self.expected_main)
        self.gh.conflict = True
        with self.assertRaisesRegex(StateConflict, 'CAS_REJECTED'):
            self._claim(initial)
        self.assertEqual(sum(path == '/graphql' for _, path, _ in self.gh.calls), 1)
        self.assertEqual(self.gh.ref, self.initial_ref)

    def test_uncertain_ack_is_never_replayed(self):
        from scripts.kesher_runtime.github import GitHubError
        initial = self.store.load(reviewed_main_sha=self.expected_main)
        self.gh.unknown_ack = True
        with self.assertRaises(GitHubError) as caught:
            self._claim(initial)
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(sum(path == '/graphql' for _, path, _ in self.gh.calls), 1)

    def test_no_automatic_bootstrap_or_missing_activation(self):
        from scripts.kesher_runtime.state import StateInvalid
        self.gh.missing = True
        with self.assertRaisesRegex(StateInvalid, 'NOT_BOOTSTRAPPED'):
            self.store.load(reviewed_main_sha=self.expected_main)
        self.gh.missing = False
        initial = self.store.load(reviewed_main_sha=self.expected_main)
        self.ledger['activation'] = 'READY_FOR_REVIEWED_MIGRATION_ONLY'
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        self.gh.raw = (canonical_json(self.ledger) + '\n').encode()
        self.gh.blob = _blob_sha(self.gh.raw)
        blocked = self.store.load(reviewed_main_sha=self.expected_main)
        from scripts.kesher_runtime.github_only_owner_policy import OwnerLedgerBlocked
        with self.assertRaisesRegex(OwnerLedgerBlocked, 'PROTECTED_ACTIVATION_REQUIRED'):
            self._claim(blocked)
        self.assertFalse(any(method == 'POST' for method, _, _ in self.gh.calls))

    def test_stale_main_unknown_provider_and_parallel_wake_block(self):
        from scripts.kesher_runtime.state import StateConflict
        from scripts.kesher_runtime.github_only_owner_policy import OwnerLedgerBlocked
        initial = self.store.load(reviewed_main_sha=self.expected_main)
        self.gh.main = 'c'*40
        with self.assertRaisesRegex(StateConflict, 'MAIN'):
            self._claim(initial)
        self.gh.main = self.expected_main
        with self.assertRaisesRegex(OwnerLedgerBlocked, 'UNRECONCILED_PROVIDER_TASK'):
            self._claim(initial, provider_tasks={'provider-task':'GENERATING'})
        with self.assertRaisesRegex(OwnerLedgerBlocked, 'COMPETING_GITHUB_RUN'):
            self._claim(initial, pending=[{'run_id':987}])
        self.assertFalse(any(method == 'POST' for method, _, _ in self.gh.calls))

    def test_forged_activation_snapshot_is_not_an_owner_proof(self):
        from dataclasses import replace
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.state import StateConflict
        snapshot = self.store.load(reviewed_main_sha=self.expected_main)
        forged = snapshot.document
        forged['epoch'] = 'safe-epoch-1'
        forged['activation'] = 'PROTECTED_VERIFIED'
        forged['commands']['other'] = {'phase': 'CLAIMED'}
        counterfeit = replace(snapshot, encoded=canonical_json(forged))
        with self.assertRaisesRegex(StateConflict, 'SNAPSHOT_NOT_CURRENT'):
            self._claim(counterfeit)
        self.assertFalse(any(method == 'POST' for method, _, _ in self.gh.calls))

    def test_corrupted_git_blob_is_rejected(self):
        from scripts.kesher_runtime.state import StateInvalid
        self.gh.blob = '0'*40
        with self.assertRaisesRegex(StateInvalid, 'BLOB_INTEGRITY'):
            self.store.load(reviewed_main_sha=self.expected_main)

    def test_module_is_not_a_dispatcher(self):
        from pathlib import Path
        code = (ROOT / 'scripts/kesher_runtime/github_only_owner_store.py').read_text()
        self.assertNotIn('workflow_dispatch', code)
        self.assertNotIn('/youtube/v3/', code)
        self.assertNotIn('notebooklm.generate', code)


class GithubOnlyProtectedPrepareTests(unittest.TestCase):
    """Tests owner-reviewed PREPARED only, without inheriting claim test cases."""

    def setUp(self):
        base = GithubOnlyAtomicLedgerTests()
        base.setUp()
        self.gh, self.store = base.gh, base.store
        self.expected_main = base.expected_main
        self._claim = base._claim
        self.gh.missing = True
        self.legacy_blob = '9' * 40
        original = self.gh.request

        def request(method, path, body=None, **kwargs):
            if method == 'GET' and path.endswith(
                    '/contents/.kesher-controller/state.json?ref=' + self.gh.ref):
                return {'sha': self.legacy_blob}
            if method == 'GET' and path == '/repos/yanivsa/kesher-website':
                return {'node_id':'repo-node-123','full_name':'yanivsa/kesher-website'}
            answer = original(method, path, body, **kwargs)
            if method == 'POST' and path == '/graphql' and not self.gh.conflict:
                self.gh.missing = False
            return answer

        self.gh.request = request
        self.proof = dict(status='READY_FOR_REVIEWED_MIGRATION_ONLY', pending=[],
                          production_activated=False,provider_dispatch=False,
                          quarantined_old_orphans=[{
                              'workflow':337960554,'run':42522546178,
                              'reason':'ORPHAN_ZERO_JOBS_DISABLED_PREDECESSOR'}],
                          legacy_blob_sha=self.legacy_blob,legacy_cycle='2026-11-08')

    def _prepare(self, **kwargs):
        from unittest.mock import patch
        from scripts.kesher_runtime.github_only_owner_prepare import prepare_owner
        opts=dict(expected_main=self.expected_main,epoch='owner-epoch-1',
            reviewer_run='123:1',
            workflow_ref='yanivsa/kesher-website/.github/workflows/kesher-controller-liveness.yml@refs/heads/main',
            event_name='workflow_dispatch',repository='yanivsa/kesher-website')
        opts.update(kwargs)
        with patch('scripts.kesher_runtime.github_only_owner_prepare.inventory',
                   return_value=self.proof):
            return prepare_owner(self.gh, **opts)

    def test_protected_review_only_prepares_no_live_controller(self):
        result = self._prepare()
        self.assertEqual(result['status'],'PREPARED_NOT_LIVE')
        self.assertFalse(result['production_activated'])
        from scripts.kesher_runtime.github_only_owner_store import GitHubOnlyLedgerStore
        ledger = GitHubOnlyLedgerStore(self.gh).load(
            reviewed_main_sha=self.expected_main).document
        self.assertEqual(ledger['activation'],'PREPARED_NOT_LIVE')
        self.assertFalse(ledger['inventory_complete'])
        self.assertEqual(ledger['commands'],{})
        self.assertEqual(ledger['migration_basis']['legacy_blob_sha'],
                         self.legacy_blob)
        from scripts.kesher_runtime.github_only_owner_policy import OwnerLedgerBlocked
        with self.assertRaises(OwnerLedgerBlocked):
            self._claim(self.store.load(reviewed_main_sha=self.expected_main))
        self.assertEqual(sum(p=='/graphql' for _,p,_ in self.gh.calls),1)

    def test_repeat_same_epoch_is_noop(self):
        self._prepare()
        before=sum(p=='/graphql' for _,p,_ in self.gh.calls)
        result=self._prepare(reviewer_run='124:1')
        self.assertEqual(result['status'],'ALREADY_PREPARED_NOOP')
        self.assertEqual(before,sum(p=='/graphql' for _,p,_ in self.gh.calls))

    def test_wrong_or_dirty_approval_is_fail_closed(self):
        from scripts.kesher_runtime.state import StateInvalid
        with self.assertRaises(StateInvalid):
            self._prepare(epoch='')
        with self.assertRaises(StateInvalid):
            self._prepare(workflow_ref='unauthorized/workflow@refs/heads/main')
        self.proof['pending']=[{'workflow':'kesher-daily-video.yml','run':100}]
        with self.assertRaisesRegex(StateInvalid,'INVENTORY_NOT_CLEAN'):
            self._prepare()
        self.assertFalse(any(method == 'POST' for method,_,_ in self.gh.calls))

    def test_prepare_cas_conflict_never_retries(self):
        from scripts.kesher_runtime.state import StateConflict
        self.gh.conflict = True
        with self.assertRaisesRegex(StateConflict,'REF_CAS_REJECTED'):
            self._prepare()
        self.assertEqual(sum(p=='/graphql' for _,p,_ in self.gh.calls),1)

    def test_existing_native_cutover_unchanged_and_review_is_real(self):
        code=(ROOT/'.github/workflows/kesher-controller-liveness.yml').read_text()
        prep=code.split('  github_owner_prepare:\n',1)[1].split('\n  watchdog:',1)[0]
        self.assertIn('environment: kesher-cutover',prep)
        self.assertIn('needs: github_owner_probe',prep)
        self.assertIn('github_only_owner_prepare',prep)
        self.assertIn('contents: write',prep)
        self.assertNotIn('secrets.',prep)
        self.assertNotIn('id-token: write',prep)
        self.assertIn("inputs.route != 'github_only_prepare'",code)
        self.assertIn('7,22,37,52 * * * *',code)
        self.assertNotIn('KESHER_CUTOVER_GATEWAY_URL',prep)


class GithubOnlyDurableEffectsTests(unittest.TestCase):
    """Hermetic crash/duplicate tests. No provider credentials or API calls."""

    def setUp(self):
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_policy import command_identity
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        from scripts.kesher_runtime.github_only_effects import GitHubOnlyEffectJournal

        fixture = GithubOnlyAtomicLedgerTests()
        fixture.setUp()
        self.gh, self.store = fixture.gh, fixture.store
        self.main = fixture.expected_main
        self.slot = "2026-11-18"
        self.slug = "couple-conversation-stuck-pursue-withdraw-cycle"
        self.source_sha = "e" * 64
        self.epoch = "safe-epoch-1"
        self.run = "123:1"
        self.operation = "notebooklm_long"
        self.command = command_identity(
            slot=self.slot, source_sha256=self.source_sha,
            operation=self.operation,
        )
        self.ledger = fixture.ledger
        self.ledger["commands"][self.command] = {
            "phase": "CLAIMED", "run_id": self.run,
            "epoch": self.epoch, "reviewed_main_sha": self.main,
        }
        self.gh.raw = (canonical_json(self.ledger) + "\\n").encode()
        self.gh.blob = _blob_sha(self.gh.raw)
        self.journal = GitHubOnlyEffectJournal(self.store)
        self.args = dict(
            epoch=self.epoch, command_id=self.command,
            run_id=self.run, slot=self.slot, slug=self.slug,
            source_sha256=self.source_sha, operation=self.operation,
        )
        self.request = "1" * 64

    def _load(self):
        return self.store.load(reviewed_main_sha=self.main)

    def _begin(self, loaded=None, **kwargs):
        args = dict(self.args)
        args.update(dict(effect_kind="notebooklm_long",
                         request_sha256=self.request))
        args.update(kwargs)
        return self.journal.begin(self._load() if loaded is None else loaded,
                                  **args)

    def _posts(self):
        return sum(method == "POST" for method, _, _ in self.gh.calls)

    def test_one_intent_recorded_by_dual_ref_cas_and_duplicate_is_noop(self):
        status, saved = self._begin()
        self.assertEqual(status, "INTENT_RECORDED")
        entry = saved.document["commands"][self.command]["effects"]["notebooklm_long"]
        self.assertEqual(entry["request_sha256"], self.request)
        self.assertEqual(entry["phase"], "INTENT_RECORDED")
        self.assertIsNone(entry["provider_id"])
        self.assertEqual(self.gh.expected_parent, "b" * 40)
        self.assertEqual(self.gh.expected_old_tree, "c" * 40)
        self.assertEqual(self._posts(), 4)
        status, again = self._begin(saved)
        self.assertEqual(status, "ALREADY_RECORDED_NO_RETRY")
        self.assertEqual(again, saved)
        self.assertEqual(self._posts(), 4)

    def test_uncertain_provider_creation_cannot_start_another_effect(self):
        _, saved = self._begin()
        with self.assertRaisesRegex(ValueError, "UNCERTAIN_REMOTE_CALL"):
            self._begin(saved, effect_kind="youtube_long")
        self.assertEqual(self._posts(), 4)

    def test_owning_run_and_source_identity_cannot_be_forged(self):
        for changed in (
            dict(run_id="124:1"),
            dict(source_sha256="d" * 64),
            dict(slot="2026-11-17"),
            dict(slug="../other"),
            dict(epoch="other-epoch"),
        ):
            with self.assertRaises(ValueError):
                self._begin(**changed)
        self.assertEqual(self._posts(), 0)

    def test_protected_activation_is_a_hard_precondition(self):
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        for field, value in (("activation", "PREPARED_NOT_LIVE"),
                             ("inventory_complete", False)):
            old = self.ledger[field]
            self.ledger[field] = value
            self.gh.raw = (canonical_json(self.ledger) + "\\n").encode()
            self.gh.blob = _blob_sha(self.gh.raw)
            with self.assertRaisesRegex(ValueError, "PROTECTED_LIVE_REQUIRED"):
                self._begin()
            self.ledger[field] = old
        self.assertEqual(self._posts(), 0)

    def test_conflicting_intent_rejected_without_side_effect(self):
        _, saved = self._begin()
        with self.assertRaisesRegex(ValueError, "CONFLICTING_RETRY"):
            self._begin(saved, request_sha256="2" * 64)
        self.assertEqual(self._posts(), 4)

    def test_remote_id_receipt_must_bind_exact_original_intent(self):
        _, saved = self._begin()
        status, observed = self.journal.observe(
            saved, **self.args, effect_kind="notebooklm_long",
            request_sha256=self.request,
            provider_id="63b37426-9fd2-49e3-a2ce-a412fc347484",
            receipt_sha256="3" * 64,
        )
        self.assertEqual(status, "REMOTE_ID_OBSERVED")
        self.assertEqual(
            observed.document["commands"][self.command]["effects"]
                ["notebooklm_long"]["provider_id"],
            "63b37426-9fd2-49e3-a2ce-a412fc347484",
        )
        before = self._posts()
        status, _ = self.journal.observe(
            observed, **self.args, effect_kind="notebooklm_long",
            request_sha256=self.request,
            provider_id="63b37426-9fd2-49e3-a2ce-a412fc347484",
            receipt_sha256="3" * 64,
        )
        self.assertEqual(status, "ALREADY_OBSERVED_NO_RETRY")
        self.assertEqual(self._posts(), before)
        with self.assertRaisesRegex(ValueError, "CONFLICTING_REMOTE_RECEIPT"):
            self.journal.observe(
                observed, **self.args, effect_kind="notebooklm_long",
                request_sha256=self.request,
                provider_id="12c218a9-9912-4f65-869b-3517cacb57a6",
                receipt_sha256="3" * 64,
            )

    def test_cas_conflict_and_unknown_ack_never_auto_retry(self):
        from scripts.kesher_runtime.state import StateConflict
        from scripts.kesher_runtime.github import GitHubError
        self.gh.conflict = True
        with self.assertRaisesRegex(StateConflict, "CAS_REJECTED"):
            self._begin()
        self.assertEqual(self._posts(), 4)
        self.gh.conflict = False
        self.gh.unknown_ack = True
        with self.assertRaises(GitHubError) as caught:
            self._begin()
        self.assertTrue(caught.exception.uncertain)
        self.assertEqual(self._posts(), 8)

    def test_stale_main_and_stale_ref_are_refused(self):
        from scripts.kesher_runtime.state import StateConflict
        snap = self._load()
        self.gh.main = "0" * 40
        with self.assertRaises(StateConflict):
            self._begin(snap)
        self.gh.main = self.main
        self.gh.ref = "0" * 40
        with self.assertRaises(StateConflict):
            self._begin(snap)
        self.assertEqual(self._posts(), 0)

    def test_invalid_provider_identifier_is_rejected_before_write(self):
        _, saved = self._begin()
        with self.assertRaisesRegex(ValueError, "PROVIDER_ID_INVALID"):
            self.journal.observe(
                saved, **self.args, effect_kind="notebooklm_long",
                request_sha256=self.request, provider_id="unknown",
                receipt_sha256="3" * 64,
            )
        self.assertEqual(self._posts(), 4)

if __name__ == '__main__': unittest.main()
