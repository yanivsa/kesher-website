"""Exact-tree publication fences both refs and reconciles ambiguous responses."""
import copy
import unittest
from types import SimpleNamespace

from scripts.kesher_runtime.github import GitHubError, GitHubStateStore
from scripts.kesher_runtime.identity import SlotIdentity, digest
from scripts.kesher_runtime.outbox import workflow_for
from scripts.kesher_runtime.state import plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_article_validation import API, HEAD, fixture
from tests.test_kesher_canonical_state import CODE, DAY, NOW, ContentsServer


class MergeAPI(API):
    def __init__(self, run, jobs, server, *, base=CODE, head=HEAD):
        super().__init__(run, jobs)
        self.server = server
        self.refs = {'refs/heads/main': base, 'refs/heads/jules/article': head}
        self.pr = {'number': 42, 'state': 'open', 'draft': False, 'merged': False,
                   'title': 'Publish Kesher article: today', 'body': 'body',
                   'head': {'sha': HEAD, 'ref': 'jules/article', 'repo': {'full_name': 'owner/repo'}},
                   'base': {'sha': CODE, 'ref': 'main', 'repo': {'full_name': 'owner/repo'}}}
        self.before_post = lambda: None
        self.lose_response = False
        self.deny = False
        self.protected = False
        self.rules = []
        self.posts = []

    def request(self, method, path, body=None, **kwargs):
        if method == 'POST':
            self.posts.append(copy.deepcopy(body))
            intents = [row['effects'] for row in self.server.document['commands'].values()]
            if not any(any(effect['request'].get('validation') for effect in row.values()) for row in intents):
                raise AssertionError('Publication preceded durable intent')
            self.before_post()
            updates = body['variables']['input']['refUpdates']
            if self.deny or any(self.refs.get(row['name']) != row['beforeOid'] for row in updates):
                return {'data': {'updateRefs': None}, 'errors': [{'type': 'UNPROCESSABLE'}]}
            self.refs.update({row['name']: row['afterOid'] for row in updates})
            self.pr.update(state='closed', merged=True, merge_commit_sha=self.refs['refs/heads/main'])
            if self.lose_response:
                raise GitHubError(None, 'lost', uncertain=True)
            return {'data': {'updateRefs': {'clientMutationId': body['variables']['input']['clientMutationId']}}}
        if path == '/repos/owner/repo':
            return {'node_id': 'R_test', 'default_branch': 'main', 'archived': False}
        if path == '/repos/owner/repo/branches/main':
            return {'name': 'main', 'protected': self.protected, 'commit': {'sha': self.refs['refs/heads/main']}}
        if path.startswith('/repos/owner/repo/rules/branches/main'):
            return copy.deepcopy(self.rules)
        if path == '/repos/owner/repo/git/ref/heads/main':
            return {'object': {'sha': self.refs['refs/heads/main']}}
        if path == '/repos/owner/repo/pulls/42':
            pr = copy.deepcopy(self.pr)
            pr['head']['sha'] = self.refs['refs/heads/jules/article']
            pr['base']['sha'] = self.refs['refs/heads/main']
            return pr
        if '/compare/' in path:
            return {'url': 'https://api.github.com'+path, 'base_commit': {'sha': HEAD},
                    'ahead_by': 2, 'behind_by': 0 if self.refs['refs/heads/main'] == 'f'*40 else 2,
                    'status': 'ahead' if self.refs['refs/heads/main'] == 'f'*40 else 'diverged',
                    'merge_base_commit': {'sha': HEAD if self.refs['refs/heads/main'] == 'f'*40 else CODE}}
        return super().request(method, path, body, **kwargs)


class MergeEntryTests(unittest.TestCase):
    def test_merge_entrypoint_loads_without_legacy_media_dependencies(self):
        import subprocess
        import sys
        from pathlib import Path
        result = subprocess.run([sys.executable, '-S', '-m', 'scripts.kesher_runtime.article_merge', '--help'],
                                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


class MergeTests(unittest.TestCase):
    def setUp(self):
        state, self.validation, run, jobs = fixture()
        self.validation['outcome'] = 'succeeded'
        state, self.key = plan_command(state, SlotIdentity(DAY), 'merge_article', 2,
            {'pr_number': '42', 'pr_head_sha': HEAD, 'pr_body_sha256': digest('body'), 'validation_base_sha': CODE},
            code_sha=CODE, now=NOW)
        self.server = ContentsServer(state)
        self.context = WorkerContext(GitHubStateStore(self.server, 'owner/repo'), self.key, '456/1',
                                     SlotIdentity(DAY), code_sha=CODE, now=lambda: NOW)
        self.context.claim()
        self.api = MergeAPI(run, jobs, self.server)
        self.value = {'base_sha': CODE, 'head_sha': HEAD, 'tree_sha': 'c'*40,
                      'post': {'article': 'exact'}, 'image_data': b'pixels'}
        # Preserve actual CI inspector execution. Only immutable Git object I/O
        # is substituted here; its real bare-Git coverage is in validation tests.
        self.validation['receipts']['article_candidate']['evidence'].update(
            article_sha256=digest(self.value['post']))
        import hashlib
        self.validation['receipts']['article_candidate']['evidence']['image_sha256'] = hashlib.sha256(b'pixels').hexdigest()
        self.server.document['commands'][self.validation['id']] = copy.deepcopy(self.validation)
        self.git = SimpleNamespace(inspect=lambda *args: copy.deepcopy(self.value))
        self.quiesce = lambda pr: None

    def run_merge(self):
        from scripts.kesher_runtime.article_merge import merge_article
        return merge_article(self.context, self.api, self.git, prove_quiescent=self.quiesce)

    def test_merge_command_routes_to_exact_admitted_workflow(self):
        self.assertEqual(workflow_for(self.server.document['commands'][self.key]), 'kesher-article-merge.yml')

    def test_only_exact_validated_tree_reaches_main_with_both_ref_fences(self):
        result = self.run_merge()
        self.assertEqual(self.api.refs['refs/heads/main'], HEAD)
        self.assertEqual(result['merge_sha'], HEAD)
        updates = self.api.posts[0]['variables']['input']['refUpdates']
        self.assertEqual(updates, [
            {'name': 'refs/heads/main', 'beforeOid': CODE, 'afterOid': HEAD, 'force': False},
            {'name': 'refs/heads/jules/article', 'beforeOid': HEAD, 'afterOid': HEAD, 'force': False}])
        receipt = next(effect for effect in self.server.document['commands'][self.key]['effects'].values()
                       if effect['request'].get('validation'))
        self.assertEqual(receipt['receipt']['merge_sha'], HEAD)
        self.assertNotIn('PUBLICLY_VERIFIED', str(receipt))

    def test_main_or_pr_head_race_never_publishes_or_overwrites_concurrent_work(self):
        from scripts.kesher_runtime.jules import JulesError
        for ref in ('refs/heads/main', 'refs/heads/jules/article'):
            with self.subTest(ref=ref):
                self.setUp()
                self.api.before_post = lambda: self.api.refs.__setitem__(ref, 'd'*40)
                with self.assertRaises(JulesError): self.run_merge()
                self.assertEqual(self.api.refs[ref], 'd'*40)
                self.assertNotEqual(self.api.refs['refs/heads/main'], HEAD)
                self.assertEqual(len(self.api.posts), 1)

    def test_lost_mutation_response_adopts_exact_merged_commit_without_second_post(self):
        self.api.lose_response = True
        result = self.run_merge()
        self.assertEqual(result['merge_sha'], HEAD)
        self.assertEqual(self.run_merge(), result)
        self.assertEqual(len(self.api.posts), 1)

    def test_changed_body_failed_ci_or_protected_policy_prevents_publication(self):
        from scripts.kesher_runtime.jules import JulesError
        mutations = [lambda: self.api.pr.update(body='changed'),
                     lambda: self.api.jobs[0]['steps'][0].update(conclusion='skipped'),
                     lambda: setattr(self.api, 'protected', True),
                     lambda: setattr(self.api, 'rules', [{'type': 'pull_request'}]),
                     lambda: self.value.update(tree_sha='d'*40)]
        for change in mutations:
            with self.subTest(change=change):
                self.setUp(); change()
                with self.assertRaises(JulesError): self.run_merge()
                self.assertEqual(self.api.posts, [])
                self.assertEqual(self.api.refs['refs/heads/main'], CODE)

    def test_jules_or_pr_revival_during_inspection_blocks_final_write(self):
        from scripts.kesher_runtime.jules import JulesError
        def revive(pr): self.api.pr.update(draft=True)
        self.quiesce = revive
        with self.assertRaises(JulesError): self.run_merge()
        self.assertEqual(self.api.posts, [])

    def test_second_quiescence_read_cannot_hide_a_new_draft(self):
        from scripts.kesher_runtime.jules import JulesError
        reads = []
        def revive(pr):
            reads.append(pr)
            if len(reads) == 2: self.api.pr.update(draft=True)
        self.quiesce = revive
        with self.assertRaises(JulesError): self.run_merge()
        self.assertEqual(self.api.posts, [])

    def test_readback_can_finish_after_controller_adopts_the_merged_source(self):
        from scripts.kesher_runtime.state import bind_source
        from tests.test_kesher_canonical_state import SOURCE
        result = self.run_merge()
        self.server.document = bind_source(self.server.document, SOURCE, now=NOW)
        self.assertEqual(self.run_merge(), result)
        self.assertEqual(len(self.api.posts), 1)

    def test_unreadable_accepted_response_is_reconciled_instead_of_crashing(self):
        for response in (None, [], {'data': {'updateRefs': None}}, {'data': None}):
            with self.subTest(response=response):
                self.setUp()
                original = self.api.request
                def malformed(method, path, body=None, **kwargs):
                    result = original(method, path, body, **kwargs)
                    return response if method == 'POST' else result
                self.api.request = malformed
                self.assertEqual(self.run_merge()['merge_sha'], HEAD)
                self.assertEqual(len(self.api.posts), 1)

    def test_lagging_pr_merge_record_never_resends_the_ref_transaction(self):
        from scripts.kesher_runtime.jules import JulesError
        original = self.api.request
        def lag(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if method == 'POST': self.api.pr.update(merged=False, state='open')
            return result
        self.api.request = lag
        for _ in range(2):
            with self.assertRaisesRegex(JulesError, 'MERGE_RECORD_PENDING'): self.run_merge()
        self.assertEqual(len(self.api.posts), 1)
        self.api.pr.update(merged=True, state='closed')
        self.assertEqual(self.run_merge()['merge_sha'], HEAD)
        self.assertEqual(len(self.api.posts), 1)

    def test_uncertain_send_recovery_new_command_keeps_same_request_and_budget(self):
        from scripts.kesher_runtime.jules import JulesError
        self.api.before_post = lambda: (_ for _ in ()).throw(GitHubError(None, 'uncertain', uncertain=True))
        for ordinal in range(3, 7):
            with self.assertRaises(JulesError): self.run_merge()
            self.context.finish(failure={'class': 'TRANSIENT_API'})
            inputs = self.server.document['commands'][self.key]['inputs']
            state, self.key = plan_command(self.server.document, SlotIdentity(DAY), 'merge_article', ordinal,
                                           inputs, code_sha=CODE, now=NOW)
            self.server.document = state
            self.context = WorkerContext(self.context.store, self.key, str(ordinal)+'/1', SlotIdentity(DAY),
                                         code_sha=CODE, now=lambda: NOW)
            self.context.claim()
        with self.assertRaisesRegex(JulesError, 'MERGE_ATTEMPTS_EXHAUSTED'): self.run_merge()
        self.assertEqual(len(self.api.posts), 3)
        self.assertEqual(self.api.refs['refs/heads/main'], CODE)

    def revalidate(self, *, body='new body', head=HEAD):
        self.context.finish(failure={'class': 'ARTICLE_PR_CHANGED'})
        self.api.pr.update(body=body, draft=False)
        self.api.refs['refs/heads/jules/article'] = head
        self.value['head_sha'] = head
        inputs = {'pr_number': '42', 'pr_head_sha': head, 'pr_body_sha256': digest(body), 'validation_base_sha': CODE}
        state, validation_key = plan_command(self.server.document, SlotIdentity(DAY), 'validate_article', 3,
                                            inputs, code_sha=CODE, now=NOW)
        row = state['commands'][validation_key]
        row.update(outcome='succeeded', owner={'run_id': '124/2', 'claimed_at': NOW}, phase='STARTED')
        evidence = copy.deepcopy(self.validation['receipts']['article_candidate'])
        evidence['evidence'].update(head_sha=head, body_sha256=digest(body))
        row['receipts']['article_candidate'] = evidence
        self.api.run.update(id=124, display_title='kesher-command:'+validation_key)
        for job in self.api.jobs: job['run_id'] = 124
        state, self.key = plan_command(state, SlotIdentity(DAY), 'merge_article', 4, inputs, code_sha=CODE, now=NOW)
        self.server.document = state
        self.context = WorkerContext(self.context.store, self.key, '457/1', SlotIdentity(DAY), code_sha=CODE, now=lambda: NOW)
        self.context.claim()
        self.quiesce = lambda pr: None
        self.api.before_post = lambda: None

    def test_unsent_intent_cannot_poison_a_fresh_validated_body(self):
        from scripts.kesher_runtime.jules import JulesError
        reads = []
        def revive(pr):
            reads.append(pr)
            if len(reads) == 2: self.api.pr.update(draft=True)
        self.quiesce = revive
        with self.assertRaises(JulesError): self.run_merge()
        self.assertEqual(self.api.posts, [])
        self.revalidate()
        self.assertEqual(self.run_merge()['merge_sha'], HEAD)
        self.assertEqual(len(self.api.posts), 1)

    def test_rejected_old_head_intent_does_not_block_new_validated_head(self):
        from scripts.kesher_runtime.jules import JulesError
        self.api.before_post = lambda: self.api.refs.__setitem__('refs/heads/jules/article', 'd'*40)
        with self.assertRaises(JulesError): self.run_merge()
        self.assertEqual(self.api.refs['refs/heads/main'], CODE)
        self.revalidate(head='d'*40)
        self.assertEqual(self.run_merge()['merge_sha'], 'd'*40)
        self.assertEqual(len(self.api.posts), 2)

    def test_controller_records_late_merge_proof_after_failed_worker_and_source_adoption(self):
        from scripts.kesher_runtime.article_merge_observer import observe_merge_effects
        from scripts.kesher_runtime.controller import Observation, reconcile
        from scripts.kesher_runtime.jules import JulesError
        from tests.test_kesher_autonomous_controller import observed, publication
        original = self.api.request
        def lag(method, path, body=None, **kwargs):
            result = original(method, path, body, **kwargs)
            if method == 'POST': self.api.pr.update(merged=False, state='open')
            return result
        self.api.request = lag
        with self.assertRaisesRegex(JulesError, 'MERGE_RECORD_PENDING'): self.run_merge()
        self.context.finish(failure={'class': 'MERGE_RECORD_PENDING'})
        self.api.pr.update(merged=True, state='closed')
        name, effect = next((name, effect) for name, effect in self.server.document['commands'][self.key]['effects'].items()
                            if effect['request'].get('validation'))
        obs = observed(publication(article='ARTICLE_NOT_PUBLIC')).value
        obs['main_sha'] = obs['publications'][0]['main_sha'] = HEAD
        obs['merge_effects'] = observe_merge_effects(self.server.document, self.api, 'owner/repo', HEAD)
        result = reconcile(self.server.document, Observation(obs), now=NOW)
        recorded = result.state['commands'][self.key]
        self.assertIsNotNone(recorded['effects'][name]['receipt'])
        self.assertEqual(recorded['outcome'], 'failed')  # Preserve actual worker history.
        self.assertEqual(result.state['commands'][result.command_id]['operation'], 'deploy_article')
        self.assertEqual(len(self.api.posts), 1)

    def test_readback_requires_complete_compare_and_exact_pull_identity(self):
        from scripts.kesher_runtime.article_merge_observer import observe_merge_effects
        for corruption in ('compare', 'number', 'repository', 'base'):
            with self.subTest(corruption=corruption):
                self.setUp()
                original = self.api.request
                def crash(method, path, body=None, **kwargs):
                    result = original(method, path, body, **kwargs)
                    if method == 'POST': raise RuntimeError('killed after accepted transaction')
                    return result
                self.api.request = crash
                with self.assertRaises(RuntimeError): self.run_merge()
                self.context.finish(failure={'class': 'WORKER_FAILED'})
                self.api.request = original
                if corruption == 'compare':
                    self.api.refs['refs/heads/main'] = 'f'*40
                    self.api.request = lambda method, path, *args, **kwargs: {} if '/compare/' in path else original(method, path, *args, **kwargs)
                elif corruption == 'number': self.api.pr['number'] = 999
                elif corruption == 'repository': self.api.pr['base']['repo']['full_name'] = 'someone/else'
                else: self.api.pr['base']['ref'] = 'other'
                values = observe_merge_effects(self.server.document, self.api, 'owner/repo', self.api.refs['refs/heads/main'])
                self.assertEqual([row['status'] for row in values], ['unknown'])
                self.assertEqual(len(self.api.posts), 1)

    def test_rejected_transaction_has_finite_durable_attempts_and_no_publication(self):
        from scripts.kesher_runtime.jules import JulesError
        self.api.deny = True
        for _ in range(5):
            with self.assertRaises(JulesError): self.run_merge()
        self.assertLessEqual(len(self.api.posts), 3)
        self.assertEqual(self.api.refs['refs/heads/main'], CODE)

    def test_recovery_after_newer_main_preserves_that_main_and_original_merge(self):
        result = self.run_merge()
        self.api.refs['refs/heads/main'] = 'f'*40
        self.assertEqual(self.run_merge(), result)
        self.assertEqual(self.api.refs['refs/heads/main'], 'f'*40)
        self.assertEqual(len(self.api.posts), 1)


class RealGitMergeTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        import json
        from scripts.kesher_runtime.article_validation import GitArticleCandidate
        from scripts.kesher_runtime.state import new_state
        from tests.test_kesher_article_normalize_worker import RealGitNormalizationTests
        from tests.test_kesher_article_image_worker import POST, candidate
        self.fixture = f = RealGitNormalizationTests(); f.setUp()
        self.addCleanup(f.tearDown)
        f.git('checkout', '-B', 'jules/article', f.main)
        post = dict(POST, image='/images/generated/blog/new-article.png', imageAlt='תמונה מתאימה של אנשים בשיחה זוגית פתוחה')
        (f.root / 'src/data/posts.json').write_text(json.dumps([post, f.base_post]))
        path = f.root / 'public/images/generated/blog/new-article.png'
        path.parent.mkdir(parents=True); path.write_bytes(candidate()['data'])
        f.git('add', '-f', 'src/data/posts.json', str(path)); f.git('commit', '-m', 'Validated article candidate')
        self.head = f.git('rev-parse', 'HEAD'); f.git('push', '--force', 'origin', 'jules/article')
        f.git('checkout', 'main')
        self.git = GitArticleCandidate(f.root)
        value = self.git.inspect(f.main, self.head, DAY)
        state, validation_id = plan_command(new_state(), SlotIdentity(DAY), 'validate_article', 1,
            {'pr_number': '42', 'pr_head_sha': self.head, 'pr_body_sha256': digest('body')}, code_sha=f.main, now=NOW)
        row = state['commands'][validation_id]
        row.update(owner={'run_id': '123/2', 'claimed_at': NOW}, outcome='succeeded', phase='STARTED')
        evidence = {'pr_number': 42, 'base_sha': f.main, 'head_sha': self.head, 'tree_sha': value['tree_sha'],
                    'body_sha256': digest('body'), 'article_sha256': digest(post),
                    'image_sha256': hashlib.sha256(value['image_data']).hexdigest()}
        row['receipts']['article_candidate'] = {'target': row['target'], 'recorded_at': NOW, 'phase': 'STARTED', 'evidence': evidence}
        _, _, run, jobs = fixture()
        run.update(head_sha=f.main, display_title='kesher-command:'+validation_id)
        for job in jobs: job['head_sha'] = f.main
        state, key = plan_command(state, SlotIdentity(DAY), 'merge_article', 2,
            {'pr_number': '42', 'pr_head_sha': self.head, 'pr_body_sha256': digest('body'), 'validation_base_sha': f.main},
            code_sha=f.main, now=NOW)
        server = ContentsServer(state)
        self.context = WorkerContext(GitHubStateStore(server, 'owner/repo'), key, '456/1', SlotIdentity(DAY),
                                     code_sha=f.main, now=lambda: NOW)
        self.context.claim()
        self.api = MergeAPI(run, jobs, server, base=f.main, head=self.head)
        original = self.api.request
        self.race = False

        def local_transaction(method, path, body=None, **kwargs):
            import subprocess
            for ref in self.api.refs:
                self.api.refs[ref] = f.git('--git-dir='+str(f.remote), 'rev-parse', ref)
            if method != 'POST': return original(method, path, body, **kwargs)
            self.api.posts.append(copy.deepcopy(body))
            if self.race:
                f.git('--git-dir='+str(f.remote), 'update-ref', 'refs/heads/jules/article', f.main, self.head)
            updates = body['variables']['input']['refUpdates']
            commands = ['start'] + ['update '+row['name']+' '+row['afterOid']+' '+row['beforeOid'] for row in updates]
            result = subprocess.run(['git', '--git-dir='+str(f.remote), 'update-ref', '--stdin'],
                                    input='\n'.join(commands+['prepare', 'commit'])+'\n',
                                    text=True, capture_output=True, timeout=20)
            if result.returncode:
                return {'data': {'updateRefs': None}, 'errors': [{'type': 'UNPROCESSABLE'}]}
            self.api.pr.update(merged=True, state='closed', merge_commit_sha=self.head)
            raise GitHubError(None, 'lost after real local ref commit', uncertain=True)
        self.api.request = local_transaction

    def test_real_immutable_candidate_and_local_atomic_refs_survive_lost_response(self):
        from scripts.kesher_runtime.article_merge import merge_article
        result = merge_article(self.context, self.api, self.git, prove_quiescent=lambda pr: None)
        self.assertEqual(result['merge_sha'], self.head)
        f = self.fixture
        self.assertEqual(f.git('--git-dir='+str(f.remote), 'rev-parse', 'main'), self.head)
        self.assertEqual(f.git('--git-dir='+str(f.remote), 'show', 'main:package.json'), '{"trusted":true}')
        self.assertEqual(f.git('rev-parse', 'HEAD'), f.main)
        self.assertEqual(len(self.api.posts), 1)

    def test_real_local_transaction_checks_noop_head_fence_atomically(self):
        from scripts.kesher_runtime.article_merge import merge_article
        from scripts.kesher_runtime.jules import JulesError
        self.race = True
        with self.assertRaises(JulesError):
            merge_article(self.context, self.api, self.git, prove_quiescent=lambda pr: None)
        f = self.fixture
        self.assertEqual(f.git('--git-dir='+str(f.remote), 'rev-parse', 'main'), f.main)
        self.assertEqual(f.git('--git-dir='+str(f.remote), 'rev-parse', 'jules/article'), f.main)
