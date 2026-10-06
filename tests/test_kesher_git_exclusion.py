import copy
import unittest

from scripts.kesher_runtime.github import GitHubError
from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.state import StateConflict, StateInvalid
from tests.test_kesher_handover_github import GitService


class EpochGit(GitService):
    """The tested updateRefs endpoint compares actual immutable commit refs."""
    def __init__(self, state=None):
        super().__init__(state or {'schema_version':5,'cycle':'2026-09-30'}, 'b'*40)
        self.metadata = {'a'*40:{'message':'initial','parents':[]}}

    def request(self, method, path, body=None):
        if method == 'GET' and '/compare/' in path:
            self.calls.append((method,path,body))
            base,head=path.split('/compare/')[1].split('?')[0].split('...')
            sha=head; count=0; seen=set()
            while sha != base:
                if sha in seen or not self.metadata[sha]['parents']:
                    return {'status':'diverged','base_commit':{'sha':base},'merge_base_commit':{'sha':'a'*40},
                            'behind_by':1,'ahead_by':count,'permalink_url':f'https://github.com/owner/repo/compare/{base}...{head}'}
                seen.add(sha); sha=self.metadata[sha]['parents'][0]; count+=1
            return {'status':'ahead' if count else 'identical','base_commit':{'sha':base},
                    'merge_base_commit':{'sha':base},'behind_by':0,'ahead_by':count,
                    'permalink_url':f'https://github.com/owner/repo/compare/{base}...{head}',
                    'commits':[]}  # no reliance on this paginated/truncated list
        if path == '/graphql' and self.race:
            race, self.race = self.race, None
            race()
        result = super().request(method, path, body)
        if method == 'POST' and path.endswith('/git/commits'):
            self.metadata[result['sha']] = copy.deepcopy(body)
        if method == 'GET' and '/git/commits/' in path:
            meta = self.metadata[path.split('/')[-1]]
            result.update(message=meta['message'], parents=[{'sha':p} for p in meta['parents']])
        return result


class EpochTests(unittest.TestCase):
    def setUp(self):
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch
        self.service = EpochGit()
        self.params = dict(repo='owner/repo',epoch='one',owner='coordinator',
            resource_id='repository-id',main_sha='b'*40,policy_sha256='d'*64)
        self.epoch = GitExclusionEpoch(self.service, **self.params)

    def test_real_ref_cas_same_tree_anchor_and_fresh_runner(self):
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch
        observed = self.epoch.observe()
        anchor = self.epoch.acquire(observed['current_ref'])
        self.assertEqual(anchor['before_oid'], 'a'*40)
        self.assertEqual(self.service.commits[anchor['commit_sha']], self.service.commits['a'*40])
        self.assertEqual(self.service.refs['automation-state'], anchor['commit_sha'])
        self.assertEqual(GitExclusionEpoch(self.service, **self.params).authority(), anchor)
        self.assertEqual(sum(c[1]=='/graphql' for c in self.service.calls), 1)

    def test_two_epochs_race_and_stale_ref_cannot_both_acquire(self):
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch
        other = GitExclusionEpoch(self.service, **dict(self.params,epoch='two'))
        initial = self.epoch.observe()['current_ref']
        self.service.race = lambda: other.acquire(initial)
        with self.assertRaises(StateConflict): self.epoch.acquire(initial)
        self.assertEqual(other.authority()['epoch'], 'two')
        with self.assertRaises(StateInvalid): self.epoch.authority()
        with self.assertRaises(StateConflict): other.acquire(initial)

    def test_lost_response_adopts_exact_reachable_anchor_no_retry(self):
        from scripts.kesher_runtime.git_exclusion import GitExclusionEpoch
        self.service.drop = True
        with self.assertRaises(GitHubError): self.epoch.acquire('a'*40)
        self.assertEqual(GitExclusionEpoch(self.service, **self.params).authority()['epoch'],'one')
        self.assertEqual(sum(c[1]=='/graphql' for c in self.service.calls),1)

    def test_changed_main_or_unknown_ancestry_refuses(self):
        self.service.refs['main'] = 'e'*40
        with self.assertRaises(StateInvalid): self.epoch.acquire('a'*40)
        self.assertFalse(any(c[1]=='/graphql' for c in self.service.calls))
        self.setUp(); self.service.metadata['a'*40]['parents'] = ['a'*40]
        with self.assertRaises(StateInvalid): self.epoch.observe()

    def test_same_document_journal_only_changes_ledger_preserves_other_bytes(self):
        from scripts.kesher_runtime.git_exclusion import GitDrainJournal
        self.epoch.acquire('a'*40)
        journal = GitDrainJournal(self.epoch)
        loaded = journal.initialize()
        proposed = copy.deepcopy(loaded.state)
        proposed['github_exclusion']['drains']['12'] = {'epoch':'one','workflow_id':12,
            'workflow_path':'.github/workflows/removed.yml','observed_disabled':False,
            'disable':{'attempts':[]},'runs':{},'proof':None}
        saved = journal.save(loaded,proposed)
        self.assertEqual(journal.load().state,saved.state)
        with self.assertRaises(StateConflict): journal.save(loaded,proposed)
        proposed = copy.deepcopy(saved.state); proposed['cycle'] = 'other'
        with self.assertRaises(StateInvalid): journal.save(saved,proposed)
        proposed = copy.deepcopy(saved.state); proposed['github_exclusion']['drains'].clear()
        with self.assertRaises(StateInvalid): journal.save(saved,proposed)

    def test_legacy_write_attempt_records_durable_incident_preserves_schema_and_journal(self):
        from scripts.kesher_runtime.git_exclusion import GitDrainJournal, record_denied_legacy_write
        self.epoch.acquire('a'*40); journal = GitDrainJournal(self.epoch); loaded=journal.initialize()
        record_denied_legacy_write(self.epoch, actor='stale-v5', proposed={'schema_version':5},
            before_sha='a'*40, now='2026-09-30T00:00:00Z')
        state = journal.read_snapshot().state
        self.assertEqual(state['schema_version'],5)
        self.assertEqual(state['github_exclusion'],loaded.state['github_exclusion'])
        self.assertTrue(any(i['kind']=='legacy_authority_violation' for i in state['incidents'].values()))
        with self.assertRaises(StateInvalid): journal.load()

    def test_fresh_runner_adopts_after_more_than_512_valid_checkpoint_descendants(self):
        from scripts.kesher_runtime.git_exclusion import GitDrainJournal, GitExclusionEpoch
        self.epoch.acquire('a'*40); journal=GitDrainJournal(self.epoch); loaded=journal.initialize()
        # Legitimate same-document drain records, each persisted with real CAS.
        for wid in range(1,521):
            proposed=copy.deepcopy(loaded.state)
            proposed['github_exclusion']['drains'][str(wid)]={'epoch':'one','workflow_id':wid,
                'workflow_path':f'.github/workflows/retired-{wid}.yml','observed_disabled':False,
                'disable':{'attempts':[]},'runs':{},'proof':None}
            loaded=journal.save(loaded,proposed)
        before=len(self.service.calls)
        recovered=GitExclusionEpoch(self.service,**self.params).authority()
        self.assertEqual(recovered['commit_sha'],loaded.state['github_exclusion']['anchor'])
        self.assertLess(len(self.service.calls)-before,20)

    def test_anchor_addressed_readback_rejects_nonancestor_wrongbase_and_ref_race(self):
        from scripts.kesher_runtime.git_exclusion import GitDrainJournal
        self.epoch.acquire('a'*40); journal=GitDrainJournal(self.epoch); journal.initialize()
        original=self.service.request
        for change in ('status','base_commit','merge_base_commit','behind_by'):
            def faulty(method,path,body=None):
                row=original(method,path,body)
                if '/compare/' in path:
                    row[change]=({'sha':'f'*40} if change.endswith('commit') else
                        'diverged' if change=='status' else 1)
                return row
            self.service.request=faulty
            with self.subTest(field=change),self.assertRaises(StateInvalid): self.epoch.authority()
        self.service.request=original
        def racing(method,path,body=None):
            row=original(method,path,body)
            if '/compare/' in path: self.service.refs['automation-state']='a'*40
            return row
        self.service.request=racing
        with self.assertRaises(StateInvalid): self.epoch.authority()


class ResourceAdapterTests(unittest.TestCase):
    def setUp(self):
        from scripts.kesher_runtime.exclusion import ExclusionFence, REQUIRED_RESOURCES
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_external_exclusion import ProtectedService
        from tests.test_kesher_github_drain import Actions, PATH
        self.git = EpochGit()
        self.path = PATH
        self.guard = ProtectedService('github')
        self.guard.resource_id = 'repository-id'
        binding = {k:'resource-id:'+k for k in REQUIRED_RESOURCES}
        binding['github'] = 'repository-id'
        fence = ExclusionFence('owner/repo','one','coordinator',dict.fromkeys(binding),binding)
        self.policy = fence._policy('github')
        self.rules = {'workflows':{},'registrations':{PATH:{'id':9,'definition_present':False}}}
        outer=self
        class JournalView:
            @property
            def document(self): return outer.adapter.journal.read_snapshot().state
        self.actions = Actions(JournalView())
        class Service:
            def request(self,method,path,body=None):
                if '/actions/' in path:
                    if method != 'GET': outer.authorize(method,path)
                    return outer.actions.request(method,path,body)
                return outer.git.request(method,path,body)
        self.service = Service()
        from tests.test_kesher_github_ruleset import RulesetAdmin, ruleset_boundary
        self.native = RulesetAdmin(git=self.git, actions=self.actions)
        self.native_boundary = ruleset_boundary(self.native, policy=self.policy, rules=self.rules)
        self.registered = lambda:[{'id':9,'path':PATH,'state':'active'}]
        self.kwargs = dict(main_sha='b'*40,policy=self.policy,rules=self.rules,
                           registered=self.registered,guard=self.guard,ruleset_boundary=self.native_boundary)
        self.adapter = GitHubResourceExclusion(self.service,'owner/repo',**self.kwargs)

    def authorize(self,method,path):
        from scripts.kesher_runtime.git_exclusion import require_exclusion_actions
        self.assertEqual(self.guard.protection,self.policy)
        run = None
        if method == 'POST':
            identity = int(path.split('/')[-2])
            run = self.actions.runs[(identity,max(a for i,a in self.actions.runs if i==identity))]
        require_exclusion_actions(self.adapter.journal.load().state,self.adapter.epoch.authority(),
            principal='coordinator',epoch='one',authenticated_code_sha256='e'*64,
            approval={'repo':'owner/repo','main_sha':'b'*40,'code_sha256':'e'*64,
                      'resource_policy_sha256':digest(self.policy)},
            operation='disable' if method=='PUT' else 'cancel',workflow_id=9,workflow_path=self.path,current_run=run)

    def progress(self):
        observed=self.adapter.inspect('owner/repo')
        try: self.adapter.exclude('owner/repo',observed['revision'],self.policy)
        except StateInvalid as exc:
            if str(exc) != 'GITHUB_RESOURCE_DRAIN_PENDING': raise

    def test_full_git_actions_port_lost_disable_cancel_fresh_runner_and_terminal_readback(self):
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        run = self.actions.run(status='waiting')
        self.actions.disable_drop = self.actions.cancel_drop = True
        for _ in range(9): self.progress()
        self.assertIsNone(self.adapter.inspect('owner/repo')['protection'])
        self.adapter = GitHubResourceExclusion(self.service,'owner/repo',**self.kwargs)
        run.update(status='completed',conclusion='cancelled')
        for _ in range(3): self.progress()
        row = self.adapter.inspect('owner/repo')
        self.assertEqual(row['protection'],self.policy)
        self.assertEqual(row['revision_kind'],'git_ref_cas')
        self.assertEqual(sum(method=='PUT' for method,_ in self.actions.calls),1)
        self.assertEqual(sum(method=='POST' for method,_ in self.actions.calls),1)
        # One epoch acquisition, plus exact drain journal commits on SAME ref.
        anchors=[m for m in self.git.metadata.values() if m['message'].startswith('state: Kesher exclusion epoch\n')]
        self.assertEqual(len(anchors),1)
        self.actions.workflows[0]['state']='active'
        with self.assertRaises(StateInvalid): self.adapter.inspect('owner/repo')

    def test_unknown_registration_mid_handover_and_missing_gateway_refuse(self):
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        self.progress()
        self.actions.workflows.append({'id':10,'path':'.github/workflows/unknown.yml','state':'active'})
        with self.assertRaises(StateInvalid): self.progress()
        with self.assertRaises(StateInvalid):
            GitHubResourceExclusion(self.service,'owner/repo',**dict(self.kwargs,guard=None))

    def test_partial_credential_guard_blocks_actions_not_solved_by_run_list(self):
        self.guard.exclude=lambda *args: None
        with self.assertRaisesRegex(StateInvalid,'GITHUB_RESOURCE_EXCLUSION_INCOMPLETE'): self.progress()
        self.assertFalse(any(method!='GET' for method,_ in self.actions.calls))

    def test_guard_epoch_and_drain_cannot_substitute_for_absent_native_ruleset(self):
        for _ in range(8): self.progress()
        self.assertEqual(self.adapter.inspect('owner/repo')['protection'], self.policy)
        self.native.native = None
        self.assertIsNone(self.adapter.inspect('owner/repo')['protection'])
        before = len(self.git.calls)
        with self.assertRaisesRegex(StateInvalid, 'RULESET_MISSING'):
            self.progress()
        self.assertFalse(any(method != 'GET' for method, _, _ in self.git.calls[before:]))

    def test_no_native_dependency_or_synthetic_protection_refuses(self):
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from types import SimpleNamespace
        for substitute in (None, {'protected': True}, SimpleNamespace(inspect=lambda repo: {'protected': True})):
            adapter = GitHubResourceExclusion(self.service, 'owner/repo',
                         **dict(self.kwargs, ruleset_boundary=substitute))
            with self.subTest(substitute=substitute), self.assertRaisesRegex(StateInvalid, 'NATIVE_RULESET_BOUNDARY_REQUIRED'):
                adapter.inspect('owner/repo')

    def test_main_and_native_actor_drift_block_completed_drain_protection(self):
        for _ in range(8): self.progress()
        row = self.adapter.inspect('owner/repo')
        self.assertEqual(row['protection'], self.policy)
        self.assertTrue(row['ruleset_revision'])
        self.git.refs['main'] = 'c'*40
        with self.assertRaises(StateInvalid): self.adapter.inspect('owner/repo')
        self.git.refs['main'] = 'b'*40
        self.native.native['bypass_actors'].append({'actor_id': 801, 'actor_type': 'User', 'bypass_mode': 'always'})
        with self.assertRaises(StateInvalid): self.adapter.inspect('owner/repo')

    def test_denial_mode_never_claims_credential_revocation(self):
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_github_ruleset import ruleset_boundary, resource_policy
        self.policy = resource_policy()
        self.kwargs.update(policy=self.policy,
                           ruleset_boundary=ruleset_boundary(self.native, policy=self.policy, rules=self.rules))
        self.adapter = GitHubResourceExclusion(self.service, 'owner/repo', **self.kwargs)
        for _ in range(8): self.progress()
        protection = self.adapter.inspect('owner/repo')['protection']
        self.assertEqual(protection, self.policy)
        self.assertEqual(protection['protection_method'], 'resource_enforced_denial')
        self.assertNotIn('credential_revocation_complete', protection)

    def test_native_policy_binding_cannot_choose_another_epoch_or_mode(self):
        from scripts.kesher_runtime.git_exclusion import GitHubResourceExclusion
        from tests.test_kesher_github_ruleset import ruleset_boundary
        for change in ({'epoch': 'two'}, {'owner': 'other'}):
            boundary = ruleset_boundary(self.native, policy=self.policy | change, rules=self.rules)
            adapter = GitHubResourceExclusion(self.service, 'owner/repo',
                         **dict(self.kwargs, ruleset_boundary=boundary))
            with self.subTest(change=change), self.assertRaisesRegex(StateInvalid, 'RULESET_BINDING_CHANGED'):
                adapter.inspect('owner/repo')

    def test_endpoint_denies_stale_principal_and_exact_attempt_replaced_after_intent(self):
        from scripts.kesher_runtime.git_exclusion import require_exclusion_actions
        run=self.actions.run()
        for _ in range(8): self.progress()
        state=self.adapter.journal.load().state; anchor=self.adapter.epoch.authority()
        kwargs=dict(principal='stale-v5',epoch='one',authenticated_code_sha256='e'*64,
            approval={'repo':'owner/repo','main_sha':'b'*40,'code_sha256':'e'*64,'resource_policy_sha256':digest(self.policy)},
            operation='cancel',workflow_id=9,workflow_path=self.path,current_run=run)
        with self.assertRaises(StateInvalid): require_exclusion_actions(state,anchor,**kwargs)
        kwargs.update(principal='coordinator',current_run=self.actions.run(attempt=2))
        with self.assertRaises(StateInvalid): require_exclusion_actions(state,anchor,**kwargs)

    def test_import_and_worker_guard_preserve_exact_ledger_across_nine_phases(self):
        from tests import test_kesher_handover as fixtures
        case=fixtures.HandoverTests(); case.setUp()
        ledger={'epoch':'one','anchor':'a'*40,'legacy_body_sha256':'b'*64,'drains':{}}
        case.params['controller']['github_exclusion']=copy.deepcopy(ledger)
        case.backend.document=copy.deepcopy(case.params['controller'])
        state=case.finish()
        self.assertEqual(state['github_exclusion'],ledger)
        from scripts.kesher_runtime.state import validate_transition
        erased=copy.deepcopy(state); erased.pop('github_exclusion')
        with self.assertRaises(StateInvalid): validate_transition(state,erased)


if __name__ == '__main__': unittest.main()
