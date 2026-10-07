"""Exact parent/child authority and retirement; all service effects are offline."""
import copy
import hashlib
import unittest
from pathlib import Path

from scripts.kesher_runtime.authority_topology import (check_definitions, classify_registered,
    inventory, policy, validate_registered_inventory)
from scripts.kesher_runtime.state import StateInvalid

ROOT = Path(__file__).resolve().parents[1]
DAILY = '.github/workflows/kesher-daily-video.yml'
SHORT = '.github/workflows/kesher-short-v4.yml'
PARENTS = {
    '.github/workflows/kesher-goal-dispatch.yml': 371553288,
}
CHILDREN = {DAILY:331086666, SHORT:349292838}


class DispatchBindingTests(unittest.TestCase):
    def fixture(self):
        from tests.test_kesher_authority_topology import AuthorityCapabilityTests
        text, rules = AuthorityCapabilityTests().rules(role='separate_infrastructure',
            capabilities=['read','workflow_dispatch','branch_write'], resources=['github.dispatch','github.refs'],
            dispatches=[DAILY])
        parent = rules['workflows']['.github/workflows/observed.yml']
        child = copy.deepcopy(parent)
        child['review']['dispatches'] = []
        child['registration_id'] = CHILDREN[DAILY]
        child['capabilities'].append('youtube_upload')
        child['resources'].append('youtube.objects')
        rules['workflows'][DAILY] = child
        parent['review']['dispatch_bindings'] = {DAILY:{'registration_id':CHILDREN[DAILY],
            'definition_sha256':child['definition_sha256'], 'capabilities':['read','branch_write'],
            'resources':['github.refs'], 'inputs':{'operation':'generate'}}}
        return {'.github/workflows/observed.yml':text, DAILY:text}, rules

    def test_reviewed_operation_scope_does_not_invent_unreachable_child_effects(self):
        definitions, rules = self.fixture()
        rows = check_definitions(definitions, rules)
        self.assertNotIn('youtube.objects',rows[1]['resources'])

    def test_child_identity_definition_and_target_set_changes_require_readjudication(self):
        for change in ('id','definition','target','additional','bad_id','scope'):
            definitions, rules = self.fixture()
            parent = rules['workflows']['.github/workflows/observed.yml']
            if change == 'id': rules['workflows'][DAILY]['registration_id'] += 1
            elif change == 'definition': rules['workflows'][DAILY]['definition_sha256'] = 'f'*64
            elif change == 'target': parent['review']['dispatches'] = [SHORT]
            elif change == 'additional': parent['review']['dispatches'].append(SHORT)
            elif change == 'bad_id': parent['review']['dispatch_bindings'][DAILY]['registration_id'] = True
            else: parent['review']['dispatch_bindings'][DAILY]['capabilities'].append('jules_create')
            with self.subTest(change=change), self.assertRaises(StateInvalid):
                check_definitions(definitions,rules)
            with self.subTest(change=change,api='classification'), self.assertRaises(StateInvalid):
                classify_registered([{'id':7,'path':'.github/workflows/observed.yml','state':'active'}],rules)


class ThreeDispatcherAuthorityTests(unittest.TestCase):
    def test_exact_parents_and_children_are_pinned_retirement_targets(self):
        rules = policy(ROOT)
        rows = [{'id':entry.get('registration_id',i),'path':path,'state':'active'}
                for i,(path,entry) in enumerate(rules['workflows'].items(),1)]
        rows += [{'id':entry['id'],'path':path,'state':'active'} for path,entry in rules['registrations'].items()]
        validate_registered_inventory(rows,rules,complete=True)
        for path,identity in PARENTS.items():
            with self.subTest(path=path):
                actor = classify_registered([{'id':identity,'path':path,'state':'active'}],rules,
                    active_runs=[],runs_complete=True)[0]
                self.assertEqual(actor['role'],'retired')
                self.assertEqual(actor['state'],'active')
                self.assertEqual(rules['workflows'][path]['registration_id'],identity)
                bindings = rules['workflows'][path]['review']['dispatch_bindings']
                expected = {DAILY,SHORT} if path.endswith('kesher-goal-dispatch.yml') else {DAILY}
                self.assertEqual(set(bindings),expected)
                for target,binding in bindings.items():
                    self.assertEqual(binding['registration_id'],CHILDREN[target])
                    self.assertEqual(binding['definition_sha256'],rules['workflows'][target]['definition_sha256'])
        from scripts.kesher_runtime.exclusion import ExclusionFence, REQUIRED_RESOURCES
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_git_exclusion import EpochGit
        from tests.test_kesher_external_exclusion import ProtectedService
        bindings = {key:'resource-id:'+key for key in REQUIRED_RESOURCES}
        fence = ExclusionFence('owner/repo','one','coordinator',dict.fromkeys(bindings),bindings)
        # This test checks exact retirement membership. Independent production
        # infrastructure boundaries are exercised by the cutover preflight suite.
        rules=copy.deepcopy(rules)
        rules['workflows']={p:e for p,e in rules['workflows'].items() if e['role']!='separate_infrastructure'}
        rows=[r for r in rows if r['path'] in rules['workflows'] or r['path'] in rules['registrations']]
        adapter = GitHubResourceExclusion(EpochGit(),'owner/repo',main_sha='b'*40,
            policy=fence._policy('github'),rules=rules,registered=lambda:rows,guard=ProtectedService('github'))
        self.assertTrue(set(PARENTS)|set(CHILDREN) <= {row['path'] for row in adapter.targets()})

    def test_exact_parent_and_child_rebindings_and_future_unknown_refuse(self):
        rules = policy(ROOT)
        for path,identity in (PARENTS|CHILDREN).items():
            for changes in ({'id':identity+1},{'path':'.github/workflows/ci.yml'}):
                with self.subTest(path=path,changes=changes),self.assertRaises(StateInvalid):
                    classify_registered([dict(id=identity,path=path,state='active')|changes],rules,
                        active_runs=[],runs_complete=True)
        with self.assertRaisesRegex(StateInvalid,'UNCLASSIFIED_REGISTERED'):
            classify_registered([{'id':999999999,'path':'.github/workflows/future-exact-recovery.yml','state':'active'}],rules)

    def test_parent_source_child_source_and_dispatch_changes_refuse(self):
        definitions = {str(p.relative_to(ROOT)):p.read_text() for p in (ROOT/'.github/workflows').glob('*.yml')}
        for path in PARENTS|CHILDREN:
            changed = definitions|{path:definitions.get(path,'')+'\n# changed source\n'}
            with self.subTest(path=path),self.assertRaisesRegex(StateInvalid,'UNREVIEWED_DEFINITION_CHANGE'):
                check_definitions(changed,policy(ROOT))
        for path in PARENTS:
            for changes in ([SHORT], [DAILY,SHORT,'.github/workflows/ci.yml']):
                rules = policy(ROOT); rules['workflows'][path]['review']['dispatches'] = changes
                with self.subTest(path=path,targets=changes),self.assertRaises(StateInvalid):
                    check_definitions(definitions,rules)

    def test_goal_both_trigger_routes_status_write_and_both_children_remain_authority(self):
        import yaml
        rules = policy(ROOT); entry = rules['workflows']['.github/workflows/kesher-goal-dispatch.yml']
        raw = (ROOT/entry['legacy_origin']['source_evidence_path']).read_text()
        source = yaml.safe_load(raw); events=source.get('on',source.get(True))
        self.assertEqual(set(events),{'push','workflow_dispatch'})
        self.assertEqual(events['push'],{'branches':['main'],'paths':['.github/kesher-goal-request.json']})
        self.assertEqual(source['permissions'],{'actions':'write','contents':'read','statuses':'write'})
        self.assertIn('status_write',entry['capabilities']); self.assertIn('github.statuses',entry['resources'])
        self.assertEqual(set(entry['review']['dispatches']),{DAILY,SHORT})
        for event in events:
            with self.subTest(event=event):
                actor = classify_registered([{'id':PARENTS['.github/workflows/kesher-goal-dispatch.yml'],
                    'path':'.github/workflows/kesher-goal-dispatch.yml','state':'active'}],rules,
                    active_runs=[],runs_complete=True)[0]
                self.assertEqual(actor['role'],'retired')

    def test_deleted_definitions_retain_exact_registration_and_require_live_retirement(self):
        rules = policy(ROOT)
        retired = {
            '.github/workflows/kesher-exact-marshmallow-video-resume.yml':371480791,
            '.github/workflows/kesher-exact-marshmallow-video-upload-recovery.yml':371466105,
            '.github/workflows/kesher-repair-exact-video-state.yml':360696002,
            '.github/workflows/kesher-video-evidence-repair.yml':360831498,
        }
        for path, identity in retired.items():
            self.assertFalse((ROOT/path).exists())
            self.assertEqual(rules['registrations'][path]['id'], identity)
            with self.assertRaises(StateInvalid):
                classify_registered([dict(id=identity,path=path,state='active')],rules,
                                    active_runs=[],runs_complete=True)
            self.assertEqual(classify_registered([dict(id=identity,path=path,state='disabled_manually')],
                             rules,active_runs=[],runs_complete=True)[0]['role'],'retired')
        inventory(ROOT,rules)

    def test_each_active_zero_run_parent_blocks_and_disabled_drained_can_retire(self):
        from tests.test_kesher_handover import HandoverTests
        rules = policy(ROOT)
        for path,identity in PARENTS.items():
            with self.subTest(path=path):
                case=HandoverTests();case.setUp()
                case.backend.observation['workflows'][2] = classify_registered([
                    {'id':identity,'path':path,'state':'active'}],rules,active_runs=[],runs_complete=True)[0]
                case.backend.disable=lambda i:case.backend.disables.append(i)
                c=case.coordinator();case.advance_to('LEGACY_QUIESCING',c)
                for _ in range(3): self.assertEqual(c.tick(),'LEGACY_QUIESCING')
                self.assertEqual(case.backend.document['schema_version'],5)
                self.assertEqual(case.backend.disables,[identity,identity])
                case.backend.observation['workflows'][2]['state']='disabled_manually'
                self.assertEqual(c.tick(),'LEGACY_QUIESCING'); self.assertEqual(c.tick(),'LEGACY_QUIESCED')

    def test_each_disabled_parent_requires_all_five_statuses_and_complete_inventory(self):
        from tests.test_kesher_handover import HandoverTests
        rules=policy(ROOT)
        for path,identity in PARENTS.items():
            case=HandoverTests();case.setUp()
            case.backend.observation['workflows'][2]=classify_registered([
                {'id':identity,'path':path,'state':'disabled_manually'}],rules,active_runs=[],runs_complete=True)[0]
            c=case.coordinator()
            for status in ('queued','in_progress','waiting','pending','requested'):
                case.backend.observation['active_runs']=[{'id':42,'run_attempt':1,'workflow_id':identity,
                    'path':path,'head_sha':case.params['main_sha'],'status':status}]
                with self.subTest(path=path,status=status):
                    self.assertEqual(c.tick(),'WAITING_FOR_LEGACY_DRAIN');self.assertNotIn('handover',case.backend.document)
            case.backend.observation['active_runs']=[];case.backend.observation['runs_complete']=False
            with self.subTest(path=path,complete=False),self.assertRaises(StateInvalid): c.tick()
            case.backend.observation['runs_complete']=True;case.advance_to('LEGACY_QUIESCED',c)
