import copy
import hashlib
import unittest
from pathlib import Path

from scripts.kesher_runtime.state import StateInvalid

ROOT = Path(__file__).resolve().parents[1]


class AuthorityTopologyTests(unittest.TestCase):
    def test_every_definition_has_an_explicit_role(self):
        from scripts.kesher_runtime.authority_topology import inventory, policy
        rows = inventory(ROOT, policy(ROOT))
        self.assertEqual(len(rows), len(list((ROOT/'.github/workflows').glob('*.yml'))))
        self.assertEqual(sum(r['role']=='controller' for r in rows),1)
        self.assertTrue(any(r['role']=='separate_infrastructure' for r in rows))

    def test_retired_definitions_have_no_runnable_jobs(self):
        from scripts.kesher_runtime.authority_topology import inventory, policy
        rows = inventory(ROOT, policy(ROOT))
        self.assertTrue(all(r['definition_retired'] for r in rows if r['role']=='retired'))

    def test_unknown_registered_path_blocks_instead_of_becoming_diagnostic(self):
        from scripts.kesher_runtime.authority_topology import classify_registered, policy
        with self.assertRaises(StateInvalid):
            classify_registered([{'id':1,'path':'.github/workflows/unexpected.yml','state':'active'}],policy(ROOT))

    def test_unknown_local_definition_blocks(self):
        from scripts.kesher_runtime.authority_topology import check_definitions, policy
        with self.assertRaises(StateInvalid):
            check_definitions({'.github/workflows/unexpected.yml':'name: hidden\non: workflow_dispatch\njobs: {}'},policy(ROOT))

    def test_reactivated_registered_legacy_is_not_retired_by_yaml_only(self):
        from scripts.kesher_runtime.authority_topology import classify_registered, policy
        rows=classify_registered([{'id':12,'path':'.github/workflows/kesher-daily-video.yml','state':'active'}],policy(ROOT))
        self.assertEqual(rows[0]['state'],'active')
        self.assertEqual(rows[0]['role'],'retired')


if __name__=='__main__':unittest.main()


class OwnerExactAuthorityTests(unittest.TestCase):
    PATH = '.github/workflows/kesher-owner-exact-975.yml'
    ID = 370535154
    CHILDREN = ('.github/workflows/kesher-daily-video.yml',
                '.github/workflows/kesher-short-v4.yml')

    def test_defined_registration_pin_rejects_id_change_and_rebinding_to_known_path(self):
        from scripts.kesher_runtime.authority_topology import validate_registered_inventory
        _, rules = AuthorityCapabilityTests().rules()
        path = '.github/workflows/observed.yml'
        entry = rules['workflows'][path]
        entry['registration_id'] = self.ID
        rules['workflows']['.github/workflows/other.yml'] = copy.deepcopy(entry)
        del rules['workflows']['.github/workflows/other.yml']['registration_id']
        validate_registered_inventory([{'id':self.ID,'path':path,'state':'active'}], rules)
        for changes in ({'id':self.ID+1}, {'path':'.github/workflows/other.yml'}):
            with self.subTest(changes=changes), self.assertRaisesRegex(StateInvalid, 'IDENTITY_MISMATCH'):
                validate_registered_inventory([dict(id=self.ID,path=path,state='active') | changes], rules)

    def test_invalid_or_duplicate_defined_registration_pins_refuse(self):
        from scripts.kesher_runtime.authority_topology import validate_registered_inventory
        for value in (True, 0, -1, '370535154'):
            _, rules = AuthorityCapabilityTests().rules()
            rules['workflows']['.github/workflows/observed.yml']['registration_id'] = value
            with self.subTest(value=value), self.assertRaisesRegex(StateInvalid, 'POLICY_INVALID'):
                validate_registered_inventory([], rules)
        _, rules = AuthorityCapabilityTests().rules()
        entry = rules['workflows']['.github/workflows/observed.yml']
        entry['registration_id'] = self.ID
        rules['registrations']['.github/workflows/removed.yml'] = {'id':self.ID,'definition_present':False}
        with self.assertRaisesRegex(StateInvalid, 'POLICY_INVALID'):
            validate_registered_inventory([], rules)

    def test_exact_parent_and_both_children_are_protected_mutators(self):
        from scripts.kesher_runtime.authority_topology import classify_registered, policy
        from scripts.kesher_runtime.exclusion import ExclusionFence, REQUIRED_RESOURCES
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_git_exclusion import EpochGit
        from tests.test_kesher_external_exclusion import ProtectedService
        rules = policy(ROOT)
        rows = [{'id':entry.get('registration_id',i),'path':path,'state':'active'}
                for i,(path,entry) in enumerate(rules['workflows'].items(), 1)]
        rows += [{'id':entry['id'],'path':path,'state':'active'}
                 for path,entry in rules['registrations'].items()]
        actors = classify_registered([row for row in rows if row['path'] in (self.PATH,*self.CHILDREN)], rules)
        parent = next(row for row in actors if row['id']==self.ID)
        self.assertEqual(parent['role'], 'retired')
        self.assertEqual(parent['state'], 'active')
        self.assertEqual(set(parent['capabilities']), {'read','workflow_dispatch','branch_write','pr_write',
            'capability_write','jules_create','jules_continue','provider_create','provider_continue',
            'youtube_upload','youtube_metadata'})
        self.assertEqual(set(parent['resources']), {'github.dispatch','github.pull_requests','github.refs',
            'github.state','jules.sessions','notebooklm.jobs','youtube.metadata','youtube.objects'})
        self.assertEqual(set(rules['workflows'][self.PATH]['review']['dispatches']), set(self.CHILDREN))
        bindings = {key:'resource-id:'+key for key in REQUIRED_RESOURCES}
        fence = ExclusionFence('owner/repo','one','coordinator',dict.fromkeys(bindings),bindings)
        adapter = GitHubResourceExclusion(EpochGit(),'owner/repo',main_sha='b'*40,
            policy=fence._policy('github'),rules=rules,registered=lambda:rows,guard=ProtectedService('github'))
        targets = {row['path'] for row in adapter.targets()}
        self.assertTrue({self.PATH,*self.CHILDREN} <= targets)

    def test_exact_parent_identity_changes_and_future_unknown_refuse(self):
        from scripts.kesher_runtime.authority_topology import classify_registered, policy
        rules = policy(ROOT)
        for changes in ({'id':self.ID+1}, {'path':self.CHILDREN[0]},
                        {'id':self.ID+1,'path':'.github/workflows/future-unreviewed.yml'}):
            with self.subTest(changes=changes), self.assertRaises(StateInvalid):
                classify_registered([dict(id=self.ID,path=self.PATH,state='active') | changes],rules,
                                    active_runs=[],runs_complete=True)

    def test_changed_dispatch_source_or_unknown_reviewed_target_refuses(self):
        from scripts.kesher_runtime.authority_topology import check_definitions, policy
        definitions = {str(p.relative_to(ROOT)):p.read_text()
                       for p in (ROOT/'.github/workflows').glob('*.yml')}
        rules = policy(ROOT)
        changed = dict(definitions)
        changed[self.PATH] += '\n  changed_dispatch:\n    runs-on: ubuntu-latest\n    steps:\n      - run: gh workflow run deploy.yml\n'
        with self.assertRaisesRegex(StateInvalid, 'UNREVIEWED_DEFINITION_CHANGE'):
            check_definitions(changed,rules)
        rules['workflows'][self.PATH]['review']['dispatches'].append('.github/workflows/future-unreviewed.yml')
        with self.assertRaisesRegex(StateInvalid, 'UNCLASSIFIED_INDIRECT_DISPATCH'):
            check_definitions(definitions,rules)


class AuthorityObservationTests(unittest.TestCase):
    def missing_registration(self):
        from scripts.kesher_runtime.authority_topology import policy
        rules = policy(ROOT)
        path, known = next(iter(rules['registrations'].items()))
        return rules, {'id': known['id'], 'path': path, 'state': 'disabled_manually'}

    def test_all_33_missing_yaml_identities_require_fresh_complete_drain(self):
        from scripts.kesher_runtime.authority_topology import classify_registered, policy
        rules = policy(ROOT)
        rows = [{'id': entry['id'], 'path': path, 'state': 'disabled_manually'}
                for path, entry in rules['registrations'].items()]
        self.assertEqual(len(rows), 33)
        result = classify_registered(rows, rules, active_runs=[], runs_complete=True)
        self.assertEqual(len(result), 33)
        self.assertTrue(all(row['classification'] == 'retired_missing_yaml' for row in result))
        self.assertTrue(all(row['role'] == 'retired' and not row['definition_present'] for row in result))

    def test_missing_yaml_active_registration_is_never_safe(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules, row = self.missing_registration(); row['state'] = 'active'
        with self.assertRaises(StateInvalid):
            classify_registered([row], rules, active_runs=[], runs_complete=True)

    def test_disabled_missing_yaml_cannot_hide_any_of_five_active_statuses(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules, row = self.missing_registration()
        for status in ('queued', 'in_progress', 'waiting', 'pending', 'requested'):
            with self.subTest(status=status), self.assertRaises(StateInvalid):
                classify_registered([row], rules, active_runs=[{'id': 42, 'run_attempt': 1,
                    'workflow_id': row['id'], 'path': row['path'], 'status': status}], runs_complete=True)

    def test_missing_yaml_wrong_id_wrong_path_and_incomplete_inventory_refuse(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules, row = self.missing_registration()
        for changes, complete, runs in (({'id': row['id']+1}, True, []),
                ({'path': '.github/workflows/unknown.yml'}, True, []), ({}, False, []), ({}, True, None)):
            with self.subTest(changes=changes, complete=complete, runs=runs), self.assertRaises(StateInvalid):
                classify_registered([dict(row, **changes)], rules, active_runs=runs, runs_complete=complete)

    def test_missing_yaml_unknown_or_contradictory_runs_refuse(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules, row = self.missing_registration()
        for run in ({'id':42, 'run_attempt':1, 'workflow_id':123, 'path':row['path'], 'status':'queued'},
                    {'id':42, 'run_attempt':1, 'workflow_id':row['id'], 'path':'.github/workflows/other.yml', 'status':'queued'},
                    {'id':42, 'run_attempt':1, 'workflow_id':row['id'], 'path':row['path'], 'status':'unexpected'}):
            with self.subTest(run=run), self.assertRaises(StateInvalid):
                classify_registered([row], rules, active_runs=[run], runs_complete=True)

    def test_observer_validates_runs_before_adjudication_and_rereads_races(self):
        from scripts.kesher_runtime.authority_topology import GitHubAuthorityObserver, classify_registered
        from tests.test_kesher_github_drain import Actions, Journal, PATH
        rules = {'workflows': {}, 'registrations': {PATH: {'id':9, 'definition_present':False}}}
        github = Actions(Journal()); github.workflows[0]['state'] = 'disabled_manually'
        observer = GitHubAuthorityObserver(github, 'owner/repo', ROOT, fence=None)
        rows, runs = observer.current_inventory(rules)
        self.assertEqual(classify_registered(rows, rules, active_runs=runs, runs_complete=True)[0]['classification'],
                         'retired_missing_yaml')
        self.assertEqual(sum(path.endswith('workflows?per_page=100&page=1') for _, path in github.calls), 3)
        for race in ('reenable', 'unknown', 'queued'):
            with self.subTest(race=race):
                github = Actions(Journal()); github.workflows[0]['state'] = 'disabled_manually'
                passes = 0
                def mutate(method, path):
                    nonlocal passes
                    if 'status=pending&' in path:
                        passes += 1
                        if passes != 1: return
                        if race == 'reenable': github.workflows[0]['state'] = 'active'
                        elif race == 'unknown': github.workflows.append({'id':10,
                            'path':'.github/workflows/unknown.yml','state':'active'})
                        elif race == 'queued': github.run(identity=50)
                github.hook = mutate
                observer = GitHubAuthorityObserver(github, 'owner/repo', ROOT, fence=None)
                with self.assertRaises(StateInvalid): observer.current_inventory(rules)

    def test_hidden_mutator_under_known_diagnostic_name_is_not_blessed(self):
        from scripts.kesher_runtime.authority_topology import check_definitions, policy
        definitions={str(p.relative_to(ROOT)):p.read_text() for p in (ROOT/'.github/workflows').glob('*.yml')}
        definitions['.github/workflows/kesher-content-controller-v6.yml'] += '\n  hidden:\n    runs-on: ubuntu-latest\n    steps:\n      - run: gh workflow run deploy.yml\n'
        with self.assertRaises(StateInvalid):check_definitions(definitions,policy(ROOT))

    def test_build_dependencies_and_code_are_in_authority_digest(self):
        from scripts.kesher_runtime.authority_topology import authority_path
        for path in ('package.json','package-lock.json','astro.config.mjs','src/pages/index.astro',
                     'scripts/kesher_runtime/controller.py','.github/workflows/new.yml','public/images/hidden.js'):
            self.assertTrue(authority_path(path),path)
        self.assertFalse(authority_path('src/data/posts.json'))
        self.assertFalse(authority_path('public/images/generated/blog/exact.jpg'))

    def test_paginated_api_uses_valid_path_and_requires_exact_complete_count(self):
        from scripts.kesher_runtime.authority_topology import GitHubAuthorityObserver
        from unittest.mock import Mock
        github=Mock();github.request.return_value={'total_count':1,'workflows':[{'id':7}]}
        observer=GitHubAuthorityObserver(github,'owner/repo',ROOT,fence=None)
        self.assertEqual(observer.pages('actions/workflows','workflows'),[{'id':7}])
        github.request.assert_called_once_with('GET','/repos/owner/repo/actions/workflows?per_page=100&page=1')
        github.request.return_value={'total_count':2,'workflows':[{'id':7}]}
        with self.assertRaises(StateInvalid):observer.pages('actions/workflows','workflows')
        with self.assertRaises(StateInvalid):observer()

    def test_retained_production_inventory_is_not_silently_reclassified(self):
        import json
        from scripts.kesher_runtime.authority_topology import classify_registered,policy
        evidence=json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/cutover-workflow-observation-20260927.json').read_text())
        with self.assertRaises(StateInvalid):classify_registered(evidence['workflows'],policy(ROOT))


class AuthorityCapabilityTests(unittest.TestCase):
    def rules(self, role='diagnostic', capabilities=None, resources=None, dispatches=None):
        text = 'name: observed\non: workflow_dispatch\npermissions: {contents: read}\njobs:\n  observe:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo read\n'
        path = '.github/workflows/observed.yml'
        return text, {'version': 2, 'protected_resources': ['github.refs', 'cloudflare.pages'],
                      'registrations': {}, 'workflows': {path: {
                          'role': role, 'definition_sha256': hashlib.sha256(text.encode()).hexdigest(),
                          'capabilities': capabilities or ['read'], 'resources': resources or [],
                          'review': {'call_chain': {}, 'dispatches': dispatches or [],
                                     'credentials': [], 'credential_services': {},
                                     'note': 'Exact synthetic call-chain review'}}}}

    def test_missing_capability_review_fails_closed_even_with_exact_yaml_hash(self):
        from scripts.kesher_runtime.authority_topology import check_definitions
        text, rules = self.rules()
        del rules['workflows']['.github/workflows/observed.yml']['capabilities']
        with self.assertRaises(StateInvalid): check_definitions({'.github/workflows/observed.yml':text}, rules)

    def test_false_readonly_resource_mutation_cannot_be_blessed_by_role(self):
        from scripts.kesher_runtime.authority_topology import check_definitions
        text, rules = self.rules(capabilities=['branch_write'], resources=['github.refs'])
        with self.assertRaises(StateInvalid): check_definitions({'.github/workflows/observed.yml':text}, rules)

    def test_indirect_writer_dispatch_is_not_readonly(self):
        from scripts.kesher_runtime.authority_topology import check_definitions
        text, rules = self.rules(dispatches=['.github/workflows/writer.yml'])
        writer = "name: retired\non: workflow_dispatch\njobs:\n  retire:\n    if: ${{ github.repository == '__KESHER_RETIRED__' }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo retired\n"
        entry = copy.deepcopy(rules['workflows']['.github/workflows/observed.yml'])
        entry.update(role='retired', definition_sha256=hashlib.sha256(writer.encode()).hexdigest(),
                     capabilities=['branch_write'], resources=['github.refs'])
        entry['review']['dispatches']=[]
        rules['workflows']['.github/workflows/writer.yml']=entry
        with self.assertRaises(StateInvalid):
            check_definitions({'.github/workflows/observed.yml':text,'.github/workflows/writer.yml':writer}, rules)

    def test_shared_infrastructure_defaults_to_retirement_without_separation(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        _, rules = self.rules(role='separate_infrastructure', capabilities=['cloudflare_write'], resources=['cloudflare.pages'])
        rows = classify_registered([{'id':1,'path':'.github/workflows/observed.yml','state':'active'}],rules)
        self.assertEqual(rows[0]['role'], 'retired')
        self.assertTrue(rows[0]['separation_required'])

    def test_removed_yaml_registration_stays_unresolved_even_when_disabled(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        _, rules = self.rules()
        rules['registrations']['.github/workflows/removed.yml'] = {
            'id': 9, 'disposition': 'unresolved', 'definition_present': False,
            'reason': 'Retained executions and credential authority not adjudicated'}
        with self.assertRaises(StateInvalid):
            classify_registered([{'id':9,'path':'.github/workflows/removed.yml','state':'disabled_manually'}], rules)

    def test_two_previously_missed_writers_are_explicit_retired_mutators(self):
        from scripts.kesher_runtime.authority_topology import inventory, policy
        rules=policy(ROOT)
        rows={row['path']:row for row in inventory(ROOT,rules)}
        for name in ('build-article-fallback-library','repair-existing-article-heroes'):
            path=f'.github/workflows/{name}.yml'
            self.assertIn(path, rules['workflows'])
            self.assertEqual(rows[path]['role'],'retired')
            self.assertIn('branch_write',rules['workflows'][path]['capabilities'])

    def test_call_chain_changes_require_new_review(self):
        import tempfile
        from scripts.kesher_runtime.authority_topology import inventory
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.github/workflows').mkdir(parents=True);(root/'scripts').mkdir()
            text,rules=self.rules()
            (root/'.github/workflows/observed.yml').write_text(text)
            (root/'scripts/helper.py').write_text('safe=1\n')
            rules['workflows']['.github/workflows/observed.yml']['review']['call_chain']={
                'scripts/helper.py':hashlib.sha256(b'safe=1\n').hexdigest()}
            inventory(root,rules)
            (root/'scripts/helper.py').write_text('dispatch_writer()\n')
            with self.assertRaises(StateInvalid): inventory(root,rules)

    def test_readonly_claim_cannot_hide_mutating_permissions(self):
        from scripts.kesher_runtime.authority_topology import check_definitions
        text,rules=self.rules()
        text=text.replace('contents: read','contents: write')
        rules['workflows']['.github/workflows/observed.yml']['definition_sha256']=hashlib.sha256(text.encode()).hexdigest()
        with self.assertRaises(StateInvalid): check_definitions({'.github/workflows/observed.yml':text},rules)

    def test_unknown_capability_is_not_a_separate_infrastructure_exemption(self):
        from scripts.kesher_runtime.authority_topology import check_definitions
        text,rules=self.rules(role='separate_infrastructure',capabilities=['unreviewed_cloud_write'])
        with self.assertRaises(StateInvalid): check_definitions({'.github/workflows/observed.yml':text},rules)

    def test_dispatch_review_cannot_omit_child_mutation_resources(self):
        from scripts.kesher_runtime.authority_topology import check_definitions
        text,rules=self.rules(role='separate_infrastructure',capabilities=['workflow_dispatch'],
                              resources=['github.dispatch'],dispatches=['.github/workflows/child.yml'])
        child="name: child\non: workflow_dispatch\njobs:\n  retire:\n    if: ${{ github.repository == '__KESHER_RETIRED__' }}\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo retired\n"
        entry=copy.deepcopy(rules['workflows']['.github/workflows/observed.yml'])
        entry.update(role='retired',capabilities=['cloudflare_write'],resources=['cloudflare.pages'],
                     definition_sha256=hashlib.sha256(child.encode()).hexdigest())
        entry['review']['dispatches']=[]
        rules['workflows']['.github/workflows/child.yml']=entry
        with self.assertRaises(StateInvalid):
            check_definitions({'.github/workflows/observed.yml':text,'.github/workflows/child.yml':child},rules)

    def test_mutation_capability_cannot_claim_an_unrelated_resource_scope(self):
        from scripts.kesher_runtime.authority_topology import check_definitions
        text,rules=self.rules(role='separate_infrastructure',capabilities=['branch_write'],resources=['cloudflare.pages'])
        with self.assertRaises(StateInvalid):check_definitions({'.github/workflows/observed.yml':text},rules)

    def separation(self):
        from scripts.kesher_runtime.identity import digest
        _,rules=self.rules(role='separate_infrastructure',capabilities=['cloudflare_write'],resources=['cloudflare.pages'])
        entry=rules['workflows']['.github/workflows/observed.yml']
        entry['review']['credentials']=['SCOPED_CLOUDFLARE_TOKEN']
        entry['review']['credential_services']={'SCOPED_CLOUDFLARE_TOKEN':'cloudflare'}
        protected={'cloudflare':'pages-project:kesher'}
        binding={'repo':'owner/repo','policy_sha256':'a'*64,'code_sha256':'b'*64,
                 'resource_bindings_sha256':digest(protected)}
        row={'id':1,'path':'.github/workflows/observed.yml','state':'active'}
        readback={'service':'cloudflare','resources':['cloudflare.pages'],
                  'credential_classes':['SCOPED_CLOUDFLARE_TOKEN'],'credential_ids':['token-3'],
                  'credential_bindings':{'SCOPED_CLOUDFLARE_TOKEN':['token-3']},
                  'effective_resource_ids':['worker:openclaw'],'denied_resource_ids':list(protected.values())}
        proof={'kind':'service_enforced_resource_separation','receipt_id':'scope-receipt',
               'binding':dict(binding,workflow_id=1,workflow_path=row['path'],
                              definition_sha256=entry['definition_sha256'],review_sha256=digest(entry['review']),resources=entry['resources']),
               'credentials':entry['review']['credentials'],'effective_resource_ids':['worker:openclaw'],
               'protected_resource_ids':list(protected.values()),
               'enforcements':[{'service':'cloudflare','policy_id':'token-policy','revision':'revision-7',
                                'resources':['cloudflare.pages'],
                                'credential_classes':['SCOPED_CLOUDFLARE_TOKEN'],
                                'credential_ids':['token-3'],
                                'credential_bindings':{'SCOPED_CLOUDFLARE_TOKEN':['token-3']},
                                'readback':readback,'readback_sha256':digest(readback)}]}
        return rules,row,binding,protected,{row['path']:proof}

    def rebind_separation(self, rules, row, binding, protected, proofs):
        from scripts.kesher_runtime.identity import digest
        entry=rules['workflows'][row['path']];proof=proofs[row['path']]
        binding['resource_bindings_sha256']=digest(protected)
        proof['binding']=dict(binding,workflow_id=row['id'],workflow_path=row['path'],
                              definition_sha256=entry['definition_sha256'],
                              review_sha256=digest(entry['review']),resources=entry['resources'])
        proof['credentials']=entry['review']['credentials']
        proof['protected_resource_ids']=list(protected.values())
        for enforcement in proof['enforcements']:
            enforcement['readback']['denied_resource_ids']=list(protected.values())
            enforcement['readback_sha256']=digest(enforcement['readback'])

    def test_multiservice_writer_cannot_use_only_cloudflare_enforcement(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules,row,binding,protected,proof=self.separation()
        entry=rules['workflows'][row['path']]
        entry['capabilities'].append('branch_write');entry['resources'].append('github.refs')
        entry['review']['credentials'].append('BROAD_GITHUB_TOKEN')
        entry['review']['credential_services']['BROAD_GITHUB_TOKEN']='github'
        protected['github']='repository:kesher'
        self.rebind_separation(rules,row,binding,protected,proof)
        with self.assertRaisesRegex(StateInvalid,'AUTHORITY_RESOURCE_SEPARATION_INVALID'):
            classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_complete_multiservice_enforcement_covers_every_reviewed_class(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        from scripts.kesher_runtime.identity import digest
        rules,row,binding,protected,proof=self.separation()
        entry=rules['workflows'][row['path']]
        entry['capabilities'].append('branch_write');entry['resources'].append('github.refs')
        entry['review']['credentials'].append('SCOPED_GITHUB_TOKEN')
        entry['review']['credential_services']['SCOPED_GITHUB_TOKEN']='github'
        protected['github']='repository:kesher'
        github=copy.deepcopy(proof[row['path']]['enforcements'][0])
        github.update(service='github',policy_id='installation-policy',resources=['github.refs'],
                      credential_classes=['SCOPED_GITHUB_TOKEN'],credential_ids=['installation-4'],
                      credential_bindings={'SCOPED_GITHUB_TOKEN':['installation-4']})
        github['readback'].update({field:github[field] for field in
                                  ('service','resources','credential_classes','credential_ids','credential_bindings')})
        proof[row['path']]['enforcements'].append(github)
        self.rebind_separation(rules,row,binding,protected,proof)
        result=classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)
        self.assertEqual(result[0]['role'],'separate_infrastructure')
        changed=copy.deepcopy(proof)
        changed[row['path']]['enforcements'].append(copy.deepcopy(github))
        with self.assertRaises(StateInvalid):
            classify_registered([row],rules,separation=changed,binding=binding,protected_resources=protected)

    def test_separation_requires_typed_nonempty_unique_credential_ids(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        from scripts.kesher_runtime.identity import digest
        for ids in (None,'token-3',[None],[''],['token-3','token-3']):
            with self.subTest(ids=ids):
                rules,row,binding,protected,proof=self.separation()
                enforcement=proof[row['path']]['enforcements'][0]
                enforcement['credential_ids']=ids
                enforcement['readback']['credential_ids']=ids
                enforcement['readback_sha256']=digest(enforcement['readback'])
                with self.assertRaisesRegex(StateInvalid,'AUTHORITY_RESOURCE_SEPARATION_INVALID'):
                    classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_enforcement_cannot_omit_a_reviewed_credential_class(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules,row,binding,protected,proof=self.separation()
        entry=rules['workflows'][row['path']]
        entry['review']['credentials'].append('SECOND_CLOUDFLARE_TOKEN')
        entry['review']['credential_services']['SECOND_CLOUDFLARE_TOKEN']='cloudflare'
        self.rebind_separation(rules,row,binding,protected,proof)
        with self.assertRaisesRegex(StateInvalid,'AUTHORITY_RESOURCE_SEPARATION_INVALID'):
            classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_enforcement_cannot_omit_a_reviewed_resource_scope(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules,row,binding,protected,proof=self.separation()
        rules['workflows'][row['path']]['resources'].append('cloudflare.account')
        self.rebind_separation(rules,row,binding,protected,proof)
        with self.assertRaisesRegex(StateInvalid,'AUTHORITY_RESOURCE_SEPARATION_INVALID'):
            classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_credential_classes_require_actual_id_bindings_in_the_readback(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        from scripts.kesher_runtime.identity import digest
        for bindings in ({}, {'SCOPED_CLOUDFLARE_TOKEN':None}, {'SCOPED_CLOUDFLARE_TOKEN':['']}):
            with self.subTest(bindings=bindings):
                rules,row,binding,protected,proof=self.separation()
                enforcement=proof[row['path']]['enforcements'][0]
                enforcement['credential_bindings']=bindings
                enforcement['readback']['credential_bindings']=bindings
                enforcement['readback_sha256']=digest(enforcement['readback'])
                with self.assertRaisesRegex(StateInvalid,'AUTHORITY_RESOURCE_SEPARATION_INVALID'):
                    classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_service_readback_cannot_substitute_credential_or_resource_scope(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        from scripts.kesher_runtime.identity import digest
        for field,value in (('service','github'),('resources',['github.refs']),
                            ('credential_classes',['UNREVIEWED_TOKEN']),('credential_ids',None),
                            ('credential_bindings',{'SCOPED_CLOUDFLARE_TOKEN':['different-token']})):
            with self.subTest(field=field):
                rules,row,binding,protected,proof=self.separation()
                enforcement=proof[row['path']]['enforcements'][0]
                enforcement['readback'][field]=value
                enforcement['readback_sha256']=digest(enforcement['readback'])
                with self.assertRaises(StateInvalid):
                    classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_separation_resource_ids_cannot_be_null_empty_or_duplicate(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        from scripts.kesher_runtime.identity import digest
        for ids in ([None],[''],['worker:openclaw','worker:openclaw']):
            with self.subTest(ids=ids):
                rules,row,binding,protected,proof=self.separation()
                proof[row['path']]['effective_resource_ids']=ids
                enforcement=proof[row['path']]['enforcements'][0]
                enforcement['readback']['effective_resource_ids']=ids
                enforcement['readback_sha256']=digest(enforcement['readback'])
                with self.assertRaises(StateInvalid):
                    classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_mutation_without_complete_reviewed_credential_service_map_refuses_separation(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        for services in ({}, {'SCOPED_CLOUDFLARE_TOKEN':None}, {'SCOPED_CLOUDFLARE_TOKEN':'github'}):
            with self.subTest(services=services):
                rules,row,binding,protected,proof=self.separation()
                rules['workflows'][row['path']]['review']['credential_services']=services
                self.rebind_separation(rules,row,binding,protected,proof)
                with self.assertRaisesRegex(StateInvalid,'AUTHORITY_RESOURCE_SEPARATION_INVALID'):
                    classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_only_exact_enforced_resource_separation_preserves_infrastructure_role(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules,row,binding,protected,proof=self.separation()
        result=classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)
        self.assertEqual(result[0]['role'],'separate_infrastructure')
        for field,value in [('policy_sha256','c'*64),('code_sha256','d'*64),('workflow_id',2)]:
            with self.subTest(field=field):
                changed=copy.deepcopy(proof);changed[row['path']]['binding'][field]=value
                with self.assertRaises(StateInvalid):
                    classify_registered([row],rules,separation=changed,binding=binding,protected_resources=protected)

    def test_self_selected_protected_resources_cannot_prove_separation(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules,row,binding,protected,proof=self.separation()
        proof[row['path']]['protected_resource_ids']=['unrelated-project']
        with self.assertRaises(StateInvalid):
            classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_inline_boolean_is_not_resource_separation_evidence(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        rules,row,binding,protected,proof=self.separation()
        proof[row['path']]['enforcements']=[{'enforced':True}]
        with self.assertRaises(StateInvalid):
            classify_registered([row],rules,separation=proof,binding=binding,protected_resources=protected)

    def test_retained_active_infrastructure_blocks_canonical_admission(self):
        from scripts.kesher_runtime.authority_topology import classify_registered
        from scripts.kesher_runtime.handover import require_authority
        from tests.test_kesher_handover import HandoverTests
        _,rules=self.rules(role='separate_infrastructure',capabilities=['cloudflare_write'],resources=['cloudflare.pages'])
        row=classify_registered([{'id':5,'path':'.github/workflows/observed.yml','state':'disabled_manually'}],rules)[0]
        # Finish a real handover with the classified writer, then reactivate it.
        case=HandoverTests();case.setUp();case.backend.observation['workflows'].append(row)
        state=case.finish();observation=case.backend.observe()
        observation['workflows'][-1]['state']='active'
        with self.assertRaises(StateInvalid): require_authority(state,observation)
