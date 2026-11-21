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
        del rules['workflows']['.github/workflows/kesher-publish-request.yml']
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
        del rules['workflows']['.github/workflows/kesher-publish-request.yml']
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
        controller = '.github/workflows/kesher-content-controller.yml'
        worker = '.github/workflows/kesher-media-worker.yml'

        class ScheduledReadback(NativeReadback):
            def request(self, method, path):
                row = super().request(method, path)
                if path.endswith('/actions/runs/42'):
                    return row | {'path': controller, 'event': 'schedule'}
                return row

        scheduled = ActionsIdentity(ScheduledReadback(), repo='owner/repo', repository_id='123',
            main_sha='b'*40, audience='https://cutover.example', jwks=auth.jwks,
            workflows=(controller, worker), environment=None, allow_controller_schedule=True)
        scheduled_claims = claims | {'event_name': 'schedule', 'environment': None,
                                     'workflow_ref': 'owner/repo/' + controller + '@refs/heads/main'}
        self.assertEqual(scheduled.verify(token(scheduled_claims)), '42/2')
        with self.assertRaises(StateInvalid):
            scheduled.authenticate(token(scheduled_claims | {
                'workflow_ref': 'owner/repo/' + worker + '@refs/heads/main'}))
        with self.assertRaises(StateInvalid):
            scheduled.verify(token(scheduled_claims | {'event_name': 'workflow_dispatch'}))
        for change in ({'repository':'other/repo'}, {'workflow_sha':'c'*40}, {'run_attempt':'1'},
                       {'event_name':'schedule'},
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
        del rules['workflows']['.github/workflows/kesher-publish-request.yml']
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

    def _step(self):
        import yaml

        source = ROOT / '.github/workflows/kesher-production-cutover.yml'
        jobs = yaml.safe_load(source.read_text())['jobs']
        self.assertEqual(jobs['transition']['needs'], 'readiness')
        self.assertEqual(jobs['transition']['environment'], 'kesher-cutover')
        self.assertNotIn('environment', jobs['readiness'])
        return next(step for step in jobs['readiness']['steps'] if 'run' in step)

    def _run(self, **values):
        import os
        import subprocess
        import sys
        env = dict(os.environ, GATEWAY_URL='', REVIEWED_REVISION='a'*40,
                   ACTUAL_REVISION='a'*40, CUTOVER_EPOCH='epoch1')
        env.update(values)
        step = self._step()
        interpreters = {'python': [sys.executable], 'bash': ['bash', '-e']}
        command = [*interpreters[step.get('shell', 'bash')], '-c', step['run']]
        return subprocess.run(command, env=env, text=True, capture_output=True, timeout=20)

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
        code = self._step()['run']
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
            # A NotebookLM Long now MUST follow independently verified
            # exact-source fulltext. Preserve that safety gate in all
            # legacy durability tests without relaxing production policy.
            "effects": {
                "notebooklm_source": {
                    "phase": "VERIFIED_OUTPUT",
                    "source_slug": self.slug,
                    "source_sha256": self.source_sha,
                    "request_sha256": "0" * 64,
                    "provider_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "receipt_sha256": "1" * 64,
                    "qa_sha256": self.source_sha,
                    "evidence_kind": "source_fulltext",
                }
            },
        }
        self.gh.raw = (canonical_json(self.ledger) + "\n").encode()
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
            self.gh.raw = (canonical_json(self.ledger) + "\n").encode()
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


class GithubOnlyProtectedLiveActivationTests(unittest.TestCase):
    """Disposable, authenticated-review and double-CAS tests with no network."""

    def setUp(self):
        import base64
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        self.main = "a" * 40
        self.legacy = "d" * 40
        self.doc = {
            "schema_version": 1, "owner": "github-only",
            "epoch": "kesher-ghonly-20261117-prepare1",
            "activation": "PREPARED_NOT_LIVE", "inventory_complete": False,
            "reviewed_main_sha": "f" * 40, "commands": {},
            "migration_basis": {
                "legacy_blob_sha": self.legacy,
                "legacy_cycle": "2026-11-08",
                "approved_review_run": "44142546286:1",
            },
        }
        self.report = {
            "notebooklm_authenticated": True, "youtube_authenticated": True,
            "no_active_notebooklm_tasks": True,
            "youtube_scan_complete": True, "known_historical_task_count": 8,
            "provider_mutations": False,
        }
        self.audit = {
            "status": "READY_FOR_REVIEWED_MIGRATION_ONLY",
            "pending": [], "production_activated": False,
            "provider_dispatch": False,
            "legacy_blob_sha": self.legacy,
            "legacy_cycle": "2026-11-08",
        }

        class FakeGitHub:
            def __init__(this):
                this.main = self.main
                this.ref = "b" * 40
                this.tree = "c" * 40
                this.doc = self.doc
                this.raw = (canonical_json(this.doc) + "\n").encode()
                this.blob = _blob_sha(this.raw)
                this.pending_raw = None
                this.calls = []
                this.approved = True
                this.conflict = False
                this.missing_ack = False

            def request(this, method, path, body=None, **kwargs):
                this.calls.append((method, path, body))
                if method == "GET":
                    if path.endswith("/git/ref/heads/main"):
                        return {"object": {"sha": this.main}}
                    if path.endswith("/git/ref/heads/automation-state"):
                        return {"object": {"sha": this.ref}}
                    if "/git/commits/" in path:
                        return {"sha": path.rsplit("/", 1)[1], "tree": {"sha": this.tree}}
                    if "/contents/.kesher-controller/github-only-owner.json?ref=" in path:
                        return {"sha": this.blob, "encoding": "base64",
                                "content": base64.b64encode(this.raw).decode()}
                    if path.endswith("/actions/runs/123"):
                        return {"id": 123, "event": "workflow_dispatch",
                                "head_branch": "main", "head_sha": this.main, "run_attempt": 1}
                    if path.endswith("/actions/runs/123/approvals"):
                        return ([{"state": "approved", "user": {"login": "yanivsa"},
                                 "environments": [{"name": "kesher-cutover"}]}]
                                if this.approved else [])
                    if path == "/repos/yanivsa/kesher-website":
                        return {"full_name": "yanivsa/kesher-website",
                                "node_id": "repo-123"}
                if method == "POST":
                    if path.endswith("/git/blobs"):
                        this.pending_raw = base64.b64decode(body["content"])
                        return {"sha": _blob_sha(this.pending_raw)}
                    if path.endswith("/git/trees"):
                        if body["base_tree"] != this.tree:
                            raise AssertionError("Stale tree")
                        return {"sha": "1" * 40}
                    if path.endswith("/git/commits"):
                        if body["parents"] != [this.ref]:
                            raise AssertionError("Stale ref")
                        return {"sha": "2" * 40}
                    if path == "/graphql":
                        if this.conflict:
                            return {"errors": [{"message": "REF_CHANGED"}]}
                        this.ref = "2" * 40
                        this.tree = "1" * 40
                        this.raw = this.pending_raw
                        this.blob = _blob_sha(this.raw)
                        return {"data": {"updateRefs": {
                            "clientMutationId": (
                                "invalid" if this.missing_ack
                                else body["variables"]["input"]["clientMutationId"]
                            )
                        }}}
                raise AssertionError((method, path))

        self.gh = FakeGitHub()

    def _act(self, report=None):
        from scripts.kesher_runtime.github_only_live_activation import activate
        from scripts.kesher_runtime.identity import digest
        from unittest.mock import patch
        with patch("scripts.kesher_runtime.github_only_live_activation.inventory",
                   return_value=self.audit):
            return activate(
                self.gh, expected_main=self.main,
                epoch=self.doc["epoch"], reviewer_run="123:1",
                reviewed_inventory_sha256=digest(self.report),
                report=self.report if report is None else report,
            )

    def _preflight(self):
        from scripts.kesher_runtime.github_only_live_activation import preflight
        from unittest.mock import patch
        with patch("scripts.kesher_runtime.github_only_live_activation.inventory",
                   return_value=self.audit):
            return preflight(self.gh, expected_main=self.main,
                             epoch=self.doc["epoch"], report=self.report)

    def test_read_only_preflight_does_not_ask_for_approval_or_mutate(self):
        result = self._preflight()
        self.assertEqual(result["status"], "READY_FOR_PROTECTED_LIVE_REVIEW")
        self.assertEqual(result["inventory_sha256"], __import__(
            "scripts.kesher_runtime.identity", fromlist=["digest"]).digest(self.report))
        self.assertFalse(any(m != "GET" for m, _, _ in self.gh.calls))

    def test_real_owner_review_and_double_cas_activate_without_media(self):
        result = self._act()
        self.assertEqual(result["status"], "PROTECTED_VERIFIED")
        self.assertFalse(result["provider_dispatch"])
        self.assertTrue(result["media_qa_required"])
        self.assertTrue(self.gh.doc["activation"] == "PREPARED_NOT_LIVE")
        self.assertEqual(__import__("json").loads(self.gh.raw)["commands"], {})
        self.assertEqual(__import__("json").loads(self.gh.raw)["protected_live"][
            "approved_review_run"], "123:1")
        self.assertTrue(any(p == "/graphql" and b["variables"]["input"][
            "refUpdates"][0]["beforeOid"] == self.main
            for m, p, b in self.gh.calls if m == "POST"))

    def test_missing_human_environment_approval_blocks_before_any_mutation(self):
        self.gh.approved = False
        with self.assertRaisesRegex(ValueError, "HUMAN_ENV_REVIEW_NOT_PROVEN"):
            self._act()
        self.assertFalse(any(m == "POST" for m, _, _ in self.gh.calls))

    def test_changed_provider_scan_blocks_before_any_mutation(self):
        bad = dict(self.report, videos_count=999)
        with self.assertRaisesRegex(Exception, "INVENTORY_CHANGED_SINCE_REVIEW"):
            self._act(bad)
        self.assertFalse(any(m == "POST" for m, _, _ in self.gh.calls))

    def test_unsettled_github_tasks_and_untrusted_legacy_block(self):
        for change in (
            ("status", "BLOCKED_EXISTING_OWNER_OR_TASK"),
            ("legacy_blob_sha", "0" * 40),
        ):
            field, next_value = change
            old = self.audit[field]
            self.audit[field] = next_value
            with self.assertRaises(ValueError):
                self._preflight()
            self.audit[field] = old
        self.assertFalse(any(m == "POST" for m, _, _ in self.gh.calls))

    def test_no_commands_allowed_in_prepared_ledger(self):
        self.doc["commands"]["old"] = {"phase": "WAITING_PROVIDER"}
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        self.gh.raw = (canonical_json(self.doc) + "\n").encode()
        self.gh.blob = _blob_sha(self.gh.raw)
        with self.assertRaisesRegex(ValueError, "PREPARED_BASIS_NOT_SAFE"):
            self._preflight()
        self.assertFalse(any(m == "POST" for m, _, _ in self.gh.calls))

    def test_cas_conflict_and_unknown_ack_do_not_retry(self):
        from scripts.kesher_runtime.state import StateConflict
        from scripts.kesher_runtime.github import GitHubError
        self.gh.conflict = True
        with self.assertRaisesRegex(StateConflict, "REF_CAS_REJECTED"):
            self._act()
        self.assertEqual(sum(m == "POST" for m, _, _ in self.gh.calls), 4)
        self.gh.conflict = False
        self.gh.missing_ack = True
        with self.assertRaises(GitHubError) as ctx:
            self._act()
        self.assertTrue(ctx.exception.uncertain)
        self.assertEqual(sum(m == "POST" for m, _, _ in self.gh.calls), 8)

    def test_stale_main_refused_before_approval(self):
        from scripts.kesher_runtime.state import StateConflict
        self.gh.main = "0" * 40
        with self.assertRaises(StateConflict):
            self._preflight()
        self.assertFalse(any(m == "POST" for m, _, _ in self.gh.calls))


class GithubOnlyAuthenticatedProviderInventoryTests(unittest.TestCase):
    """No provider creation, uploads, token access or GH mutations in tests."""

    def setUp(self):
        from scripts.kesher_runtime.github_only_live_inventory import HISTORICAL_TASKS
        self.tasks = HISTORICAL_TASKS
        self.video_rows = [{"id": k, "status": "completed"} for k in self.tasks]
        self.sources = [{"id": "source-1"}]

    def command(self, args):
        if args[0] == "auth":
            return {"status": "ok", "checks": {"token_fetch": True}}
        if args[0] == "artifact":
            return {"artifacts": self.video_rows}
        if args[0] == "source":
            return {"sources": self.sources}
        raise AssertionError("Untrusted provider invocation")

    def test_all_eight_exact_tasks_are_reconciled_without_dispatch(self):
        from scripts.kesher_runtime.github_only_live_inventory import inspect_provider_catalog
        result = inspect_provider_catalog(command=self.command)
        self.assertEqual(result["known_historical_task_count"], 8)
        self.assertTrue(result["no_active_notebooklm_tasks"])

    def test_active_task_rejected_and_no_new_task_spawned(self):
        from scripts.kesher_runtime.github_only_live_inventory import inspect_provider_catalog
        self.video_rows.append({"id": "not-owned", "status": "generating"})
        with self.assertRaisesRegex(ValueError, "ACTIVE_EXTERNAL_TASK"):
            inspect_provider_catalog(command=self.command)

    def test_historic_task_missing_fails_closed(self):
        from scripts.kesher_runtime.github_only_live_inventory import inspect_provider_catalog
        self.video_rows.pop()
        with self.assertRaisesRegex(ValueError, "CATALOG_INCOMPLETE|HISTORICAL_TASK_NOT_FOUND"):
            inspect_provider_catalog(command=self.command)

    def test_unknown_provider_status_fails_closed(self):
        from scripts.kesher_runtime.github_only_live_inventory import inspect_provider_catalog
        self.video_rows[0]["status"] = "something-new"
        with self.assertRaisesRegex(ValueError, "UNKNOWN_EXTERNAL_TASK_STATUS"):
            inspect_provider_catalog(command=self.command)

    def test_youtube_scan_has_to_be_complete_and_bound_to_all_targets(self):
        from scripts.kesher_runtime.github_only_live_inventory import inspect_live_inventory
        from unittest.mock import patch
        rows = [{"date": "2026-11-%02d" % day, "slug": "example-%d" % day,
                 "exact_match_count": 0, "legacy_candidate_count": 0,
                 "youtube_scan_complete": True,
                 "new_provider_generation_authorized": False,
                 "upload_authorized": False} for day in range(1, 8)]
        record = {
            "channel_verified": True, "youtube_scan_complete": True,
            "unresolved_video_fingerprints": [],
            "uploaded_playlist_count": 229, "resolved_video_count": 219,
            "confirmed_deleted_tombstones": 10, "items": rows,
        }
        with patch("scripts.kesher_runtime.ghonly_youtube_gap_audit.audit_channel",
                   return_value=record):
            safe = inspect_live_inventory(command=self.command, channel=lambda: object())
        self.assertFalse(safe["provider_mutations"])
        record["youtube_scan_complete"] = False
        with patch("scripts.kesher_runtime.ghonly_youtube_gap_audit.audit_channel",
                   return_value=record):
            with self.assertRaisesRegex(ValueError, "YOUTUBE_INVENTORY_UNTRUSTED"):
                inspect_live_inventory(command=self.command, channel=lambda: object())


class GithubOnlyActionsWorkflowContextRegressionTests(unittest.TestCase):
    def test_ghonly_protected_job_env_has_no_unavailable_runner_context(self):
        from pathlib import Path
        workflow = (Path(__file__).resolve().parents[1]
                    / ".github/workflows/kesher-controller-liveness.yml").read_text()
        self.assertEqual(
            workflow.count("NOTEBOOKLM_HOME: /tmp/kesher-ghonly-notebooklm"), 5,
        )
        self.assertNotIn("NOTEBOOKLM_HOME: ${{ runner.temp }}", workflow)
        self.assertIn("environment: kesher-cutover", workflow)
        self.assertIn("needs: github_owner_live_inventory", workflow)


class GithubOnlyLiveRevisionRebindTests(unittest.TestCase):
    """Only a real environment review and complete same-inventory CAS can rebind."""

    def setUp(self):
        import base64
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        self.old = "b" * 40
        self.main = "a" * 40
        self.legacy = "e" * 40
        self.report = {
            "notebooklm_authenticated": True, "youtube_authenticated": True,
            "no_active_notebooklm_tasks": True, "youtube_scan_complete": True,
            "known_historical_task_count": 8, "provider_mutations": False,
        }
        self.audit = {
            "status": "READY_FOR_REVIEWED_MIGRATION_ONLY",
            "pending": [], "production_activated": False,
            "provider_dispatch": False,
            "legacy_blob_sha": self.legacy, "legacy_cycle": "2026-11-08",
        }
        self.doc = {
            "schema_version": 1, "owner": "github-only",
            "epoch": "kesher-ghonly-20261117-prepare1",
            "activation": "PROTECTED_VERIFIED", "inventory_complete": True,
            "reviewed_main_sha": self.old,
            "commands": {},
            "migration_basis": {"legacy_blob_sha": self.legacy,
                                "legacy_cycle": "2026-11-08"},
            "protected_live": {
                "approved_review_run": "99:1",
                "inventory_sha256": "f" * 64,
                "legacy_blob_sha": self.legacy,
                "source_publication_authorized": False,
                "media_qa_required": True, "single_writer": "github-only",
            },
        }

        class FakeGitHub:
            def __init__(this):
                this.main = self.main
                this.ref = "c" * 40
                this.tree = "d" * 40
                this.doc = self.doc
                this.raw = (canonical_json(this.doc) + "\n").encode()
                this.blob = _blob_sha(this.raw)
                this.calls = []
                this.approved = True
                this.descendant = True
                this.pending_raw = None
                this.cas_conflict = False
                this.ack_unknown = False
                this.run_heads = {99: self.old, 100: self.main}

            def request(this, method, path, body=None, **kwargs):
                this.calls.append((method, path, body))
                if method == "GET":
                    if path.endswith("/git/ref/heads/main"):
                        return {"object": {"sha": this.main}}
                    if path.endswith("/git/ref/heads/automation-state"):
                        return {"object": {"sha": this.ref}}
                    if "/git/commits/" in path:
                        return {"sha": path.rsplit("/", 1)[1],
                                "tree": {"sha": this.tree}}
                    if "/contents/.kesher-controller/github-only-owner.json?ref=" in path:
                        return {"sha": this.blob, "encoding": "base64",
                                "content": base64.b64encode(this.raw).decode()}
                    if path.startswith("/repos/yanivsa/kesher-website/actions/runs/"):
                        parts = path.split("/")
                        rid = int(parts[6])
                        if rid not in this.run_heads:
                            raise AssertionError("Unexpected protected run")
                        if path.endswith("/approvals"):
                            return ([{"state": "approved",
                                      "user": {"login": "yanivsa"},
                                      "environments": [{"name": "kesher-cutover"}]}]
                                    if this.approved else [])
                        return {"id": rid, "event": "workflow_dispatch",
                                "head_sha": this.run_heads[rid], "head_branch": "main",
                                "run_attempt": 1}
                    if "/compare/" in path:
                        return {"status": "ahead" if this.descendant else "diverged",
                                "ahead_by": 1, "behind_by": 0 if this.descendant else 1,
                                "base_commit": {"sha": self.old},
                                "merge_base_commit": {"sha": self.old}}
                    if path == "/repos/yanivsa/kesher-website":
                        return {"full_name": "yanivsa/kesher-website",
                                "node_id": "repository-id"}
                if method == "POST":
                    if path.endswith("/git/blobs"):
                        this.pending_raw = base64.b64decode(body["content"])
                        return {"sha": _blob_sha(this.pending_raw)}
                    if path.endswith("/git/trees"):
                        return {"sha": "1" * 40}
                    if path.endswith("/git/commits"):
                        self.next_sha = "2" * 40
                        return {"sha": self.next_sha}
                    if path == "/graphql":
                        if this.cas_conflict:
                            return {"errors": [{"message": "ref changed"}]}
                        this.ref = self.next_sha
                        this.tree = "1" * 40
                        this.raw = this.pending_raw
                        this.blob = _blob_sha(this.raw)
                        return {"data": {"updateRefs": {"clientMutationId":
                            ("wrong" if this.ack_unknown else body["variables"]["input"]["clientMutationId"])}}}
                raise AssertionError((method, path))

        self.gh = FakeGitHub()
        self.reviewer_run = "100:1"

    def _call(self, stage="preflight", report=None):
        from scripts.kesher_runtime.github_only_revision_rebind import preflight, rebind
        from scripts.kesher_runtime.identity import digest
        from unittest.mock import patch
        with patch("scripts.kesher_runtime.github_only_revision_rebind.inventory",
                   return_value=self.audit):
            if stage == "preflight":
                return preflight(self.gh, expected_main=self.main,
                                 epoch=self.doc["epoch"], report=self.report)
            return rebind(self.gh, expected_main=self.main,
                          epoch=self.doc["epoch"], reviewer_run=self.reviewer_run,
                          reviewed_inventory_sha256=digest(self.report),
                          report=report if report is not None else self.report)

    def test_rebind_preflight_is_read_only_and_revision_bound(self):
        result = self._call()
        self.assertEqual(result["status"], "READY_FOR_REVIEWED_REVISION_REBIND")
        self.assertEqual(result["prior_main"], self.old)
        self.assertFalse(any(m != "GET" for m, _, _ in self.gh.calls))

    def test_genuine_review_single_dual_ref_cas_rebinds_live_owner_not_media(self):
        result = self._call("rebind")
        self.assertEqual(result["status"], "PROTECTED_REVIEWED_REVISION_REBOUND")
        self.assertFalse(result["provider_dispatch"])
        next_doc = __import__("json").loads(self.gh.raw)
        self.assertEqual(next_doc["reviewed_main_sha"], self.main)
        self.assertEqual(next_doc["activation"], "PROTECTED_VERIFIED")
        self.assertEqual(next_doc["commands"], {})
        self.assertEqual(next_doc["protected_live"]["code_revision_reviews"][-1][
            "approved_review_run"], "100:1")
        self.assertEqual(len([p for m,p,b in self.gh.calls if p == "/graphql"]), 1)

    def _prepare_second_review(self):
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        # The original LIVE approval 99:1 remains tied to b*40.
        # The first authentic revision review 100:1 is tied to a*40.
        # The second pending protected review 101:1 is tied to c*40.
        self.old = "a" * 40
        self.main = "c" * 40
        self.reviewer_run = "101:1"
        self.gh.main = self.main
        self.gh.run_heads = {99: "b" * 40, 100: "a" * 40, 101: "c" * 40}
        self.doc["reviewed_main_sha"] = self.old
        self.doc["protected_live"]["code_revision_reviews"] = [{
            "previous_main": "b" * 40,
            "reviewed_main": "a" * 40,
            "approved_review_run": "100:1",
            "prior_ledger_ref": "c" * 40,
            "inventory_sha256": "f" * 64,
        }]
        self.gh.raw = (canonical_json(self.doc) + "\n").encode()
        self.gh.blob = _blob_sha(self.gh.raw)

    def test_second_rebind_validates_entire_real_review_chain_not_original_against_new_sha(self):
        self._prepare_second_review()
        result = self._call()
        self.assertEqual(result["prior_main"], "a" * 40)
        self.assertEqual(result["new_main"], "c" * 40)
        self.assertFalse(any(m != "GET" for m, _, _ in self.gh.calls))
        checked = [p for m, p, _ in self.gh.calls
                   if p in {"/repos/yanivsa/kesher-website/actions/runs/99",
                            "/repos/yanivsa/kesher-website/actions/runs/100"}]
        self.assertEqual(checked[-2:],
                         ["/repos/yanivsa/kesher-website/actions/runs/99",
                          "/repos/yanivsa/kesher-website/actions/runs/100"])
        activated = self._call("rebind")
        self.assertEqual(activated["status"], "PROTECTED_REVIEWED_REVISION_REBOUND")
        self.assertEqual(len(__import__("json").loads(
            self.gh.raw)["protected_live"]["code_revision_reviews"]), 2)

    def test_second_rebind_tampered_or_skipped_review_never_writes(self):
        from scripts.kesher_runtime.identity import canonical_json
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        self._prepare_second_review()
        changes = (
            ("previous_main", "d" * 40, "NOT_TRUSTED"),
            ("reviewed_main", "d" * 40, "NOT_TRUSTED"),
            ("approved_review_run", "101:1", "NOT_TRUSTED"),
        )
        for key, tampered, blocker in changes:
            row = self.doc["protected_live"]["code_revision_reviews"][0]
            original = row[key]
            row[key] = tampered
            self.gh.raw = (canonical_json(self.doc) + "\n").encode()
            self.gh.blob = _blob_sha(self.gh.raw)
            with self.assertRaisesRegex(ValueError, blocker):
                self._call()
            row[key] = original
        self.assertEqual(len([1 for m, p, _ in self.gh.calls if m == "POST"]), 0)

    def test_missing_review_stale_provider_and_nonancestor_all_block_before_write(self):
        from scripts.kesher_runtime.identity import digest
        self.gh.approved = False
        with self.assertRaisesRegex(ValueError, "HUMAN_ENV_REVIEW_NOT_PROVEN"):
            self._call("rebind")
        self.gh.approved = True
        self.gh.descendant = False
        with self.assertRaisesRegex(ValueError, "NOT_DESCENDANT"):
            self._call()
        self.gh.descendant = True
        self.audit["pending"] = [{"workflow": "kesher-media-worker.yml", "run": 555}]
        with self.assertRaisesRegex(ValueError, "COMPETING_OWNER_OR_RUN"):
            self._call()
        self.audit["pending"] = []
        with self.assertRaisesRegex(Exception, "INVENTORY_CHANGED_AFTER_REVIEW"):
            self._call("rebind", report={**self.report, "videos_count": 999})
        self.assertFalse(any(m == "POST" for m, _, _ in self.gh.calls))

    def test_existing_command_and_publication_permission_are_hard_blockers(self):
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        from scripts.kesher_runtime.identity import canonical_json
        for key, value, blocker in (
            ("commands", {"unsettled": {"phase": "WAITING_PROVIDER"}},
             "GHONLY_QA_HOLD_UNRELATED_COMMAND_BLOCKED"),
            ("protected_live", {**self.doc["protected_live"],
                                "source_publication_authorized": True},
             "LIVE_OWNER_NOT_ELIGIBLE"),
        ):
            old = self.doc[key]
            self.doc[key] = value
            self.gh.raw = (canonical_json(self.doc) + "\n").encode()
            self.gh.blob = _blob_sha(self.gh.raw)
            with self.assertRaisesRegex(ValueError, blocker):
                self._call()
            self.doc[key] = old
        self.assertFalse(any(m == "POST" for m, _, _ in self.gh.calls))

    def test_conflict_or_unknown_ack_never_retries_cas(self):
        from scripts.kesher_runtime.state import StateConflict
        from scripts.kesher_runtime.github import GitHubError
        self.gh.cas_conflict = True
        with self.assertRaisesRegex(StateConflict, "CAS_CONFLICT"):
            self._call("rebind")
        self.assertEqual(len([1 for m,p,b in self.gh.calls if p == "/graphql"]), 1)
        self.gh.cas_conflict = False
        self.gh.ack_unknown = True
        with self.assertRaises(GitHubError) as c:
            self._call("rebind")
        self.assertTrue(c.exception.uncertain)
        self.assertEqual(len([1 for m,p,b in self.gh.calls if p == "/graphql"]), 2)



class GithubOnlySealedQualityHoldTests(unittest.TestCase):
    """No new provider POST, no lost provenance, no QA-as-publication."""

    def setUp(self):
        from scripts.kesher_runtime.github_only_qa_hold import (
            COMMAND_ID, ORIGINAL_RUN, ORIGINAL_TASK_ID, ORIGINAL_SOURCE_ID,
            ORIGINAL_REVIEWED_MAIN, SOURCE_SHA, SOURCE_SLUG, SOURCE_REQUEST,
            SOURCE_RECEIPT, LONG_REQUEST, LONG_RECEIPT,
        )
        self.id = COMMAND_ID
        self.task = ORIGINAL_TASK_ID
        self.document = {
            "epoch": "kesher-ghonly-20261117-prepare1",
            "commands": {self.id: {
                "phase": "CLAIMED",
                "epoch": "kesher-ghonly-20261117-prepare1",
                "run_id": ORIGINAL_RUN,
                "reviewed_main_sha": ORIGINAL_REVIEWED_MAIN,
                "effects": {
                    "notebooklm_source": {
                        "phase": "VERIFIED_OUTPUT",
                        "provider_id": ORIGINAL_SOURCE_ID,
                        "request_sha256": SOURCE_REQUEST,
                        "receipt_sha256": SOURCE_RECEIPT,
                        "qa_sha256": SOURCE_SHA,
                        "evidence_kind": "source_fulltext",
                        "source_sha256": SOURCE_SHA,
                        "source_slug": SOURCE_SLUG,
                    },
                    "notebooklm_long": {
                        "phase": "REMOTE_ID_OBSERVED",
                        "provider_id": ORIGINAL_TASK_ID,
                        "request_sha256": LONG_REQUEST,
                        "receipt_sha256": LONG_RECEIPT,
                        "source_sha256": SOURCE_SHA,
                        "source_slug": SOURCE_SLUG,
                    },
                },
            }},
        }

        class FakeGithub:
            def __init__(this):
                this.artifact = True
                this.approved = True
                this.run_ok = True
            def request(this, method, path, *args):
                from scripts.kesher_runtime.github_only_qa_hold import (
                    ORIGINAL_RUN, ORIGINAL_REVIEWED_MAIN,
                    ORIGINAL_ARTIFACT_ID, ORIGINAL_ARTIFACT_NAME, ORIGINAL_ARCHIVE_DIGEST,
                )
                self.assertEqual(method, "GET")
                run_id = int(ORIGINAL_RUN.split(":")[0])
                if path.endswith("/actions/runs/" + str(run_id)):
                    return {
                        "id": run_id, "head_sha": ORIGINAL_REVIEWED_MAIN,
                        "path": ".github/workflows/kesher-media-worker.yml",
                        "event": "workflow_dispatch", "head_branch": "main",
                        "run_attempt": 1,
                        "status": "completed" if this.run_ok else "in_progress",
                        "conclusion": "success" if this.run_ok else None,
                    }
                if path.endswith("/actions/runs/" + str(run_id) + "/approvals"):
                    return ([{"state": "approved", "user": {"login": "yanivsa"},
                             "environments": [{"name": "kesher-cutover"}]}]
                            if this.approved else [])
                if path.endswith("/actions/runs/" + str(run_id) + "/artifacts"):
                    return {"artifacts": [{
                        "id": ORIGINAL_ARTIFACT_ID,
                        "name": ORIGINAL_ARTIFACT_NAME,
                        "digest": (ORIGINAL_ARCHIVE_DIGEST if this.artifact else "sha256:" + "0" * 64),
                        "expired": False,
                        "workflow_run": {"id": run_id,
                                         "head_sha": ORIGINAL_REVIEWED_MAIN},
                    }]}
                raise AssertionError(path)
        self.gh = FakeGithub()

    def _verify(self, rows=None):
        from scripts.kesher_runtime.github_only_qa_hold import verified_qa_hold
        if rows is None:
            rows = [{"id": self.task, "status": "completed"}]
        return verified_qa_hold(
            self.gh, self.document, command=lambda args: {"artifacts": rows},
        )

    def test_empty_journal_has_no_hold_or_provider_request(self):
        from scripts.kesher_runtime.github_only_qa_hold import hold_basis
        self.assertIsNone(hold_basis({"commands": {}}))

    def test_completed_original_and_authenticated_artifact_can_be_sealed(self):
        from scripts.kesher_runtime.github_only_qa_hold import SEALED_EVIDENCE
        evidence = self._verify()
        self.assertEqual(evidence, SEALED_EVIDENCE)
        self.assertEqual(evidence["status"], "QA_HOLD")
        self.assertFalse(evidence["youtube_upload_authorized"])
        self.assertFalse(evidence["short_generation_authorized"])
        self.assertEqual(self.document["commands"][self.id]["phase"], "CLAIMED")

    def test_false_or_missing_github_review_never_seals(self):
        self.gh.approved = False
        with self.assertRaisesRegex(ValueError, "HUMAN_ENV_REVIEW_NOT_PROVEN"):
            self._verify()
        self.gh.approved = True
        self.gh.run_ok = False
        with self.assertRaisesRegex(ValueError, "ORIGINAL_PRODUCTION_RUN_UNTRUSTED"):
            self._verify()

    def test_tampered_qa_zip_and_incomplete_provider_are_blockers(self):
        self.gh.artifact = False
        with self.assertRaisesRegex(ValueError, "ARTIFACT_HASH_MISMATCH"):
            self._verify()
        self.gh.artifact = True
        for rows in (
            [],
            [{"id": self.task, "status": "generating"}],
            [{"id": self.task, "status": "completed"},
             {"id": self.task, "status": "completed"}],
        ):
            with self.assertRaisesRegex(ValueError, "PROVIDER_TASK_NOT_COMPLETED"):
                self._verify(rows)

    def test_extra_upload_or_changed_receipt_is_hard_blocker(self):
        from scripts.kesher_runtime.github_only_qa_hold import hold_basis
        import copy
        for key, value in (
            ("phase", "WAITING_PROVIDER"),
            ("run_id", "111:1"),
        ):
            doc = copy.deepcopy(self.document)
            doc["commands"][self.id][key] = value
            with self.assertRaises(ValueError):
                hold_basis(doc)
        doc = copy.deepcopy(self.document)
        doc["commands"][self.id]["effects"]["youtube_long"] = {
            "phase": "VERIFIED_OUTPUT"}
        with self.assertRaisesRegex(ValueError, "UNVERIFIED_EXTRA_EFFECT"):
            hold_basis(doc)
        doc = copy.deepcopy(self.document)
        doc["commands"][self.id]["effects"]["notebooklm_long"]["receipt_sha256"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "UNTRUSTED_LONG_RECEIPT"):
            hold_basis(doc)

    def test_sealed_hold_remains_valid_after_archive_expiry_without_new_post(self):
        from scripts.kesher_runtime.github_only_qa_hold import (
            SEALED_EVIDENCE, hold_basis,
        )
        self.document["commands"][self.id].update({
            "phase": "QA_HOLD", "quality_checkpoint": dict(SEALED_EVIDENCE),
        })
        self.gh.artifact = False
        self.assertEqual(self._verify(), SEALED_EVIDENCE)
        self.document["commands"][self.id]["quality_checkpoint"]["youtube_upload_authorized"] = True
        with self.assertRaisesRegex(ValueError, "EVIDENCE_TAMPERED"):
            hold_basis(self.document)

    def test_owner_rebind_preserves_original_run_and_seals_quality_hold_atomically(self):
        # Main-SHA change is approved by the EXISTING protected rebind action;
        # it must never mutate the immutable original command/run/receipt.
        from unittest.mock import patch
        from scripts.kesher_runtime import github_only_revision_rebind as rev
        from scripts.kesher_runtime.github_only_qa_hold import SEALED_EVIDENCE
        from scripts.kesher_runtime.identity import digest
        from scripts.kesher_runtime.github_only_owner_store import _blob_sha
        from scripts.kesher_runtime.identity import canonical_json
        case = GithubOnlyLiveRevisionRebindTests("test_rebind_preflight_is_read_only_and_revision_bound")
        case.setUp()
        case.doc["commands"] = __import__("copy").deepcopy(self.document["commands"])
        case.gh.raw = (canonical_json(case.doc) + "\n").encode()
        case.gh.blob = _blob_sha(case.gh.raw)
        with patch("scripts.kesher_runtime.github_only_revision_rebind.inventory",
                   return_value=case.audit), patch(
             "scripts.kesher_runtime.github_only_revision_rebind.verified_qa_hold",
             return_value=SEALED_EVIDENCE):
            verified = rev.rebind(
                case.gh, expected_main=case.main, epoch=case.doc["epoch"],
                reviewer_run=case.reviewer_run, report=case.report,
                reviewed_inventory_sha256=digest(case.report),
            )
        self.assertTrue(verified["qa_hold_sealed"])
        after = __import__("json").loads(case.gh.raw)
        self.assertEqual(after["commands"][self.id]["phase"], "QA_HOLD")
        self.assertEqual(after["commands"][self.id]["quality_checkpoint"], SEALED_EVIDENCE)
        self.assertEqual(after["commands"][self.id]["run_id"], "44462713412:1")
        self.assertEqual(after["commands"][self.id]["reviewed_main_sha"],
                         "1eccad173d19e2842f3f7b1e6379c7f55f2cad89")
        self.assertEqual(after["reviewed_main_sha"], case.main)
        self.assertFalse(after["protected_live"]["source_publication_authorized"])


class GithubOnlyMediaRecoveryCanaryTests(unittest.TestCase):
    def test_historical_exact_task_identity_is_unique_and_completed(self):
        from scripts.kesher_runtime.github_only_media_canary import (
            exact_provider_task, NOTEBOOK_TASK_ID,
        )
        from scripts.kesher_runtime.github_only_live_inventory import HISTORICAL_TASKS
        video = [{"id": task, "status": "completed"} for task in HISTORICAL_TASKS]
        def command(args):
            self.assertEqual(args[:2], ["artifact", "list"])
            return {"artifacts": video}
        self.assertEqual(exact_provider_task(command=command)["id"], NOTEBOOK_TASK_ID)
        video[2]["status"] = "generating"
        with self.assertRaisesRegex(ValueError, "NOT_COMPLETED"):
            exact_provider_task(command=command)
        video[2]["status"] = "completed"
        video.append({"id": NOTEBOOK_TASK_ID, "status": "completed"})
        with self.assertRaisesRegex(ValueError, "NOT_UNIQUE"):
            exact_provider_task(command=command)

    def test_qa_uses_existing_frame_and_hebrew_transcript_without_approval(self):
        from scripts.kesher_runtime.github_only_media_canary import original_media_qa
        import tempfile
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "original.mp4"
            path.write_bytes(b"a" * 2000)
            sheet = Path(d) / "sheet.png"; sheet.write_bytes(b"sheet")
            transcript = Path(d) / "transcript.txt"
            transcript.write_text("שלום עולם " * 35, encoding="utf-8")
            core = Mock()
            core.ffprobe.return_value = {
                "width": 1280, "height": 720, "duration": 130.0,
                "audio_codec": "aac", "codec": "h264",
            }
            core.estimate_voice_pitch.return_value = 240.0
            core.FEMALE_PITCH_MIN_HZ = 155.0
            core.sha256_file.return_value = "a" * 64
            core.create_contact_sheet.return_value = sheet
            core.transcribe_hebrew.return_value = transcript
            qa = original_media_qa(path, core=core)
            self.assertEqual(qa["qa_status"], "TECHNICAL_ACCEPTED_EDITORIAL_HOLD")
            self.assertEqual(qa["visual_review_frames"], 8)
            self.assertFalse(qa["youtube_upload_authorized"])
            self.assertFalse(qa["owner_visual_review_approved"])
            core.create_contact_sheet.assert_called_once()
            core.transcribe_hebrew.assert_called_once()

    def test_existing_media_worker_remains_exact_command_only_and_canary_is_read_only(self):
        from pathlib import Path
        import yaml
        root = Path(__file__).resolve().parents[1] / ".github/workflows"
        worker = yaml.safe_load((root / "kesher-media-worker.yml").read_text())
        self.assertEqual(set(worker["jobs"]), {"media", "github_only_production"})
        ghonly = worker["jobs"]["github_only_production"]
        self.assertEqual(ghonly["environment"], "kesher-cutover")
        self.assertEqual(ghonly["permissions"]["actions"], "read")
        self.assertEqual(ghonly["permissions"]["contents"], "write")
        self.assertIn("149ed4c8a86a3da1a8ceca9195d782039e3458cf8553cd1647add649a473fbf9",
                      ghonly["if"])
        self.assertIn("inputs.command_id !=", worker["jobs"]["media"]["if"])
        self.assertIn("github_only_media_production",
                      str(ghonly["steps"]))
        self.assertEqual(set(worker[True]["workflow_dispatch"]["inputs"]), {"command_id"})
        watchdog = yaml.safe_load((root / "kesher-controller-liveness.yml").read_text())
        canary = watchdog["jobs"]["github_only_canary"]
        self.assertEqual(canary["permissions"], {"contents": "read", "actions": "read"})
        self.assertNotIn("environment", canary)
        self.assertIn("inputs.route == 'github_only_media_canary'", canary["if"])
        steps = "\n".join(str(x.get("run", "")) for x in canary["steps"])
        self.assertIn("github_only_media_canary", steps)
        self.assertNotIn("generate video", steps)
        self.assertNotIn("upload_only", steps)

    def test_revision_rebind_uses_only_existing_liveness_and_protected_review(self):
        from pathlib import Path
        import yaml
        content = (Path(__file__).resolve().parents[1]
                   / ".github/workflows/kesher-controller-liveness.yml").read_text()
        data = yaml.safe_load(content)
        jobs = data["jobs"]
        self.assertIn("github_owner_rebind_inventory", jobs)
        self.assertIn("github_owner_rebind", jobs)
        self.assertEqual(jobs["github_owner_rebind"]["environment"], "kesher-cutover")
        self.assertEqual(jobs["github_owner_rebind"]["needs"], "github_owner_rebind_inventory")
        self.assertIn("revision_rebind", str(jobs["github_owner_rebind"]))
        self.assertNotIn("provider_create", content)


class GithubOnlyProtectedProductionWorkerTests(unittest.TestCase):
    def test_exact_canonical_nov18_article_identity_and_hardcoded_one_command(self):
        from scripts.kesher_runtime.github_only_media_production import (
            trusted_article, COMMAND_ID, SOURCE_SHA256, SOURCE_TITLE,
        )
        from scripts.kesher_runtime.github_only_owner_policy import command_identity
        source = trusted_article()
        self.assertEqual(source["content_sha256"], SOURCE_SHA256)
        self.assertEqual(
            command_identity(slot="2026-11-18", source_sha256=SOURCE_SHA256,
                             operation="article"), COMMAND_ID)
        self.assertEqual(COMMAND_ID, "149ed4c8a86a3da1a8ceca9195d782039e3458cf8553cd1647add649a473fbf9")
        self.assertTrue(SOURCE_TITLE.endswith(SOURCE_SHA256[:12]))

    def test_exact_run_refuses_any_wrong_command_event_or_sha_before_github_read(self):
        from scripts.kesher_runtime.github_only_media_production import (
            _exact_run, COMMAND_ID, WORKFLOW,
        )
        from unittest.mock import Mock
        gh = Mock()
        env = dict(
            GITHUB_REPOSITORY="yanivsa/kesher-website", GITHUB_WORKFLOW_REF=WORKFLOW,
            GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF="refs/heads/main",
            GITHUB_JOB="github_only_production", GITHUB_SHA="a" * 40,
            GITHUB_WORKFLOW_SHA="a" * 40, GITHUB_RUN_ID="444", GITHUB_RUN_ATTEMPT="1",
        )
        for field, corrupt in (
            ("GITHUB_REPOSITORY", "different/repo"),
            ("GITHUB_EVENT_NAME", "schedule"),
            ("GITHUB_REF", "refs/heads/branch"),
            ("GITHUB_JOB", "media"),
            ("GITHUB_WORKFLOW_SHA", "b" * 40),
        ):
            original = env[field]
            env[field] = corrupt
            with self.assertRaisesRegex(ValueError, "EXACT_JOB_SHA_COMMAND_REQUIRED"):
                _exact_run(gh, environment=env, expected_main="a" * 40,
                           command_id=COMMAND_ID)
            env[field] = original
        with self.assertRaisesRegex(ValueError, "EXACT_JOB_SHA_COMMAND_REQUIRED"):
            _exact_run(gh, environment=env, expected_main="a" * 40,
                       command_id="b" * 64)
        gh.request.assert_not_called()

    def test_existing_source_intent_never_causes_duplicate_post(self):
        from scripts.kesher_runtime.github_only_media_production import (
            source_once, long_once, trusted_article,
        )
        from unittest.mock import Mock, patch
        journal = Mock()
        journal.begin.return_value = ("ALREADY_RECORDED_NO_RETRY", "state")
        source = trusted_article()
        with patch("scripts.kesher_runtime.github_only_media_production._external_post_once",
                   side_effect=AssertionError("must not POST")):
            state, snap, item = source_once(
                journal, "before", run_id="123:1", source=source)
            self.assertEqual(state, "NO_REPEAT_POST")
            self.assertIsNone(item)
            with __import__("tempfile").TemporaryDirectory() as d:
                state, snap, item = long_once(
                    journal, "before", run_id="123:1", source=source,
                    source_id="a" * 8 + "-" + "b" * 4 + "-" + "c" * 4 +
                              "-" + "d" * 4 + "-" + "e" * 12,
                    folder=Path(d),
                )
                self.assertEqual(state, "NO_REPEAT_POST")

    def test_exact_source_verify_flow_persists_intent_before_one_post(self):
        from scripts.kesher_runtime.github_only_media_production import (
            source_once, trusted_article,
        )
        from unittest.mock import Mock, patch
        source = trusted_article()
        sid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        journal = Mock()
        journal.begin.return_value = ("INTENT_RECORDED", "intent")
        journal.observe.return_value = ("REMOTE_ID_OBSERVED", "observed")
        journal.verify_output.return_value = ("VERIFIED_OUTPUT", "verified")
        calls = []
        def observe(_):
            calls.append("read")
            return {"source_id": sid} if len(calls) > 2 else None
        def post(args):
            calls.append("post")
            self.assertEqual(args[:2], ["source", "add"])
            return {"source_id": sid}
        with patch("scripts.kesher_runtime.github_only_media_production._source_observer",
                   side_effect=observe), patch(
                   "scripts.kesher_runtime.github_only_media_production._external_post_once",
                   side_effect=post):
            status, snapshot, identity = source_once(
                journal, "initial", run_id="123:1", source=source)
        self.assertEqual(status, "SOURCE_VERIFIED")
        self.assertEqual(snapshot, "verified")
        self.assertEqual(identity, sid)
        self.assertEqual(calls, ["read", "post", "read"])
        journal.begin.assert_called_once()
        journal.observe.assert_called_once()
        journal.verify_output.assert_called_once()
        self.assertEqual(journal.verify_output.call_args.kwargs["evidence_kind"],
                         "source_fulltext")

    def test_provider_post_unknown_never_has_automatic_retry(self):
        from scripts.kesher_runtime.github_only_media_production import _external_post_once
        from unittest.mock import patch, Mock
        with patch("scripts.kesher_runtime.github_only_media_production.subprocess.run",
                   return_value=Mock(returncode=1, stdout="", stderr="secret")) as run:
            with self.assertRaisesRegex(ValueError, "POST_UNCERTAIN_NO_RETRY"):
                _external_post_once(["source", "add", "sample"])
            run.assert_called_once()

    def test_full_provider_catalog_no_pending_or_unknown_jobs(self):
        from scripts.kesher_runtime.github_only_media_production import (
            _observed_terminal_tasks,
        )
        from unittest.mock import patch
        videos = [{"id": f"0000000{i}-0000-0000-0000-000000000000",
                   "status": "completed"} for i in range(8)]
        with patch("scripts.kesher_runtime.github_only_media_production._provider_json",
                   return_value={"artifacts": videos}):
            read = _observed_terminal_tasks()
            self.assertEqual(len(read), 8)
            videos[0]["status"] = "generating"
            with self.assertRaisesRegex(ValueError, "UNSETTLED_OR_DUPLICATE"):
                _observed_terminal_tasks()

    def test_effect_sequence_will_not_upload_or_generate_short_before_public_long(self):
        from scripts.kesher_runtime import github_only_effects
        from scripts.kesher_runtime.github_only_media_production import run
        self.assertEqual(github_only_effects._ORDER["notebooklm_long"], "notebooklm_source")
        self.assertEqual(github_only_effects._ORDER["youtube_long"], "notebooklm_long")
        self.assertEqual(github_only_effects._ORDER["notebooklm_short"], "youtube_long")
        self.assertEqual(github_only_effects._ORDER["youtube_short"], "notebooklm_short")
        self.assertNotIn("youtube_upload_authorized", run.__code__.co_names)

    def test_genuine_protected_worker_env_and_exact_command_unchanged(self):
        import yaml
        from pathlib import Path
        path = Path(__file__).resolve().parents[1] / ".github/workflows/kesher-media-worker.yml"
        yaml_data = yaml.safe_load(path.read_text())
        self.assertEqual(set(yaml_data[True]["workflow_dispatch"]["inputs"]), {"command_id"})
        ghonly = yaml_data["jobs"]["github_only_production"]
        self.assertEqual(ghonly["environment"], "kesher-cutover")
        self.assertIn("GH_TOKEN", str(ghonly["steps"]))
        self.assertIn("github_only_media_production", str(ghonly["steps"]))
        self.assertNotIn("workflow_dispatch", ghonly.get("run", ""))

class GithubOnlyProtectedRebindDiagnosticTests(unittest.TestCase):
    def test_exposes_only_allowlisted_authentic_failure_codes(self):
        from scripts.kesher_runtime.github_only_revision_rebind import _safe_blocker_code
        for code in (
            "GHONLY_REBIND_PROVIDER_INVENTORY_CHANGED_AFTER_REVIEW",
            "GHONLY_REBIND_APPROVAL_CHAIN_STALE",
            "GHONLY_QA_HOLD_EXACT_PROVIDER_TASK_NOT_COMPLETED",
            "KESHER_GHONLY_REBIND_NOT_READY",
        ):
            self.assertEqual(_safe_blocker_code(ValueError(code)), code)

    def test_never_leaks_provider_exception_or_token(self):
        from scripts.kesher_runtime.github_only_revision_rebind import _safe_blocker_code
        for raw in (
            "GHONLY_ERROR: bearer ghp_0123456789",
            "NotebookLM auth expired\\naccess_token=abc",
            "GHONLY_REBIND_INVALID\\nSUPER_SECRET",
            "Authorization: Bearer test_value",
            "GHONLY_REBIND_X;print(token)",
            "",
        ):
            self.assertEqual(
                _safe_blocker_code(RuntimeError(raw)),
                "GHONLY_REBIND_UNCLASSIFIED_SAFE_BLOCKER",
            )


if __name__ == '__main__': unittest.main()
