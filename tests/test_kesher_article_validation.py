"""Trusted CI binds the immutable article candidate and actual executed jobs."""
import copy
import json
import unittest
from unittest.mock import Mock

from scripts.kesher_runtime.article_validation import inspect_validation, validation_for_pr
from scripts.kesher_runtime.identity import SlotIdentity, digest
from scripts.kesher_runtime.state import new_state, plan_command
from tests.test_kesher_canonical_state import CODE, DAY, NOW

HEAD = 'b'*40
REQUIRED = {'article-checks': ['Stage exact article data', 'Validate complete article and provenance',
                              'Run full repository quality gate'],
            'render-proof': ['Stage exact article data', 'Prove real rendering preserves source audio and signature']}


def fixture():
    state, key = plan_command(new_state(), SlotIdentity(DAY), 'validate_article', 1,
                             {'pr_number': '42', 'pr_head_sha': HEAD}, code_sha=CODE, now=NOW)
    row = state['commands'][key]
    row.update(owner={'run_id': '123/2', 'claimed_at': NOW}, phase='STARTED')
    evidence = {'pr_number': 42, 'head_sha': HEAD, 'base_sha': CODE, 'tree_sha': 'c'*40,
                'body_sha256': digest('body'), 'article_sha256': 'd'*64, 'image_sha256': 'e'*64}
    row['receipts']['article_candidate'] = {'target': row['target'], 'recorded_at': NOW,
                                          'phase': 'STARTED', 'evidence': evidence}
    run = {'id': 123, 'run_attempt': 2, 'head_sha': CODE, 'head_branch': 'main',
           'event': 'workflow_dispatch', 'path': '.github/workflows/kesher-article-validation.yml',
           'display_title': 'kesher-command:' + key, 'status': 'completed', 'conclusion': 'success'}
    jobs = [{'id': index + 1, 'run_id': 123, 'head_sha': CODE, 'name': name,
             'status': 'completed', 'conclusion': 'success',
             'steps': [{'name': step, 'status': 'completed', 'conclusion': 'success'} for step in steps]}
            for index, (name, steps) in enumerate(REQUIRED.items())]
    return state, row, run, jobs


class API:
    def __init__(self, run, jobs): self.run, self.jobs, self.calls = run, jobs, []
    def request(self, method, path, *args, **kwargs):
        self.calls.append((method, path))
        if path.endswith('/attempts/2'): return copy.deepcopy(self.run)
        if '/attempts/2/jobs?' in path: return {'total_count': len(self.jobs), 'jobs': copy.deepcopy(self.jobs)}
        raise AssertionError(path)


class ValidationEvidenceTests(unittest.TestCase):
    def test_success_requires_real_attempt_bound_jobs_not_worker_success_claim(self):
        state, command, run, jobs = fixture()
        api = API(run, jobs)
        verdict = inspect_validation(api, 'owner/repo', command)
        self.assertEqual(verdict['status'], 'verified')
        self.assertEqual(verdict['evidence']['head_sha'], HEAD)
        self.assertEqual(verdict['evidence']['run_id'], '123/2')
        self.assertEqual(verdict['evidence']['jobs'], {'article-checks': 1, 'render-proof': 2})
        self.assertTrue(all(method == 'GET' for method, _ in api.calls))
        command['outcome'] = 'succeeded'; jobs.pop()
        self.assertEqual(inspect_validation(API(run, jobs), 'owner/repo', command)['status'], 'failed')


class CandidateIsolationTests(unittest.TestCase):
    def setUp(self):
        from tests.test_kesher_article_normalize_worker import RealGitNormalizationTests
        self.fixture = RealGitNormalizationTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_article_pr_cannot_supply_replacement_test_runner_or_generators(self):
        from scripts.kesher_runtime.article_validation import GitArticleCandidate
        from scripts.kesher_runtime.jules import JulesError
        f = self.fixture
        with self.assertRaisesRegex(JulesError, 'CI_INPUT_INVALID'):
            GitArticleCandidate(f.root).inspect(f.main, f.old, DAY)
        self.assertEqual(json.loads((f.root / 'package.json').read_text()), {'trusted': True})

    def test_staging_copies_only_checked_regular_data_files_and_rejects_symlink_image(self):
        from scripts.kesher_runtime.article_validation import GitArticleCandidate
        from scripts.kesher_runtime.jules import JulesError
        from tests.test_kesher_article_image_worker import POST, candidate
        f = self.fixture; image = 'public/images/generated/blog/new-article.png'
        f.git('checkout', '-B', 'jules/article', f.main)
        post = dict(POST, image='/images/generated/blog/new-article.png', imageAlt='תמונה מתאימה של אנשים בשיחה זוגית פתוחה')
        (f.root / 'src/data/posts.json').write_text(json.dumps([post, f.base_post]))
        path = f.root / image; path.parent.mkdir(parents=True); path.write_bytes(candidate()['data'])
        f.git('add', '-f', 'src/data/posts.json', image); f.git('commit', '-m', 'Article with pixels')
        good = f.git('rev-parse', 'HEAD'); f.git('push', '--force', 'origin', 'jules/article')
        f.git('checkout', 'main')
        git = GitArticleCandidate(f.root); value = git.inspect(f.main, good, DAY)
        git.stage(value)
        self.assertEqual(path.read_bytes(), candidate()['data'])
        self.assertEqual(json.loads((f.root / 'package.json').read_text()), {'trusted': True})
        self.assertEqual(f.git('rev-parse', 'HEAD'), f.main)
        f.git('reset', '--hard', f.main)
        f.git('checkout', 'jules/article'); path.unlink(); path.symlink_to('../../../../package.json')
        f.git('add', image); f.git('commit', '-m', 'Malicious symbolic image')
        bad = f.git('rev-parse', 'HEAD'); f.git('push', 'origin', 'jules/article'); f.git('checkout', 'main')
        with self.assertRaisesRegex(JulesError, 'CI_INPUT_INVALID'): git.inspect(f.main, bad, DAY)

class ValidationAdditionalEvidenceTests(unittest.TestCase):
    def test_lost_final_observation_keeps_transient_class_for_bounded_readonly_retry(self):
        _, command, run, jobs = fixture()
        command.update(outcome='failed', failure={'class': 'TRANSIENT_API'})
        run['conclusion'] = 'failure'
        result = inspect_validation(API(run, jobs), 'owner/repo', command)
        self.assertEqual(result, {'status': 'failed', 'failure_class': 'TRANSIENT_API'})

    def test_malformed_run_or_job_inventory_fails_closed_without_crashing_observer(self):
        _, command, run, jobs = fixture()
        for invalid_run, invalid_jobs in [(None, jobs), (run, [None]), (dict(run, path=None), jobs)]:
            with self.subTest(run=invalid_run, jobs=invalid_jobs):
                self.assertEqual(inspect_validation(API(invalid_run, invalid_jobs), 'owner/repo', command)['status'], 'failed')

    def test_skipped_or_missing_required_step_does_not_pass_a_green_job(self):
        for mutation in ('skipped', 'missing', 'duplicate'):
            with self.subTest(mutation=mutation):
                _, command, run, jobs = fixture()
                if mutation == 'skipped': jobs[0]['steps'][-1]['conclusion'] = 'skipped'
                elif mutation == 'missing': jobs[0]['steps'].pop()
                else: jobs[0]['steps'].append(copy.deepcopy(jobs[0]['steps'][-1]))
                self.assertEqual(inspect_validation(API(run, jobs), 'owner/repo', command)['status'], 'failed')

    def test_wrong_workflow_code_attempt_or_candidate_cannot_supply_ci(self):
        for field, value in [('path', '.github/workflows/ci.yml'), ('run_attempt', 1),
                             ('head_sha', HEAD), ('event', 'pull_request'), ('display_title', 'verify')]:
            with self.subTest(field=field):
                _, command, run, jobs = fixture(); run[field] = value
                self.assertEqual(inspect_validation(API(run, jobs), 'owner/repo', command)['status'], 'failed')

    def test_pending_run_waits_and_expired_observation_never_means_pass(self):
        _, command, run, jobs = fixture()
        run.update(status='in_progress', conclusion=None)
        self.assertEqual(inspect_validation(API(run, jobs), 'owner/repo', command)['status'], 'pending')
        # The finishing job can independently record completed test jobs while
        # its own run is in progress, but the controller still waits for terminal.
        self.assertEqual(inspect_validation(API(run, jobs), 'owner/repo', command, require_terminal=False)['status'], 'verified')

    def test_only_current_head_base_and_body_can_adopt_completed_validation(self):
        state, command, run, jobs = fixture(); api = API(run, jobs)
        pr = {'number': 42, 'head': {'sha': HEAD}, 'body': 'body'}
        self.assertEqual(validation_for_pr(state, api, 'owner/repo', DAY, pr, CODE)['status'], 'verified')
        for changed, main in [(dict(pr, body='changed'), CODE),
                              (dict(pr, head={'sha': 'f'*40}), CODE), (pr, 'f'*40)]:
            self.assertEqual(validation_for_pr(state, api, 'owner/repo', DAY, changed, main)['status'], 'absent')

    def test_body_changed_before_candidate_checkpoint_does_not_inherit_old_failure(self):
        state, command, run, jobs = fixture()
        command['inputs']['pr_body_sha256'] = digest('original body')
        command['receipts'].clear()
        command.update(outcome='failed', failure={'class': 'CI_INPUT_CHANGED'})
        pr = {'number': 42, 'head': {'sha': HEAD}, 'body': 'changed before prepare'}
        self.assertEqual(validation_for_pr(state, API(run, jobs), 'owner/repo', DAY, pr, CODE)['status'], 'absent')

    def test_job_from_other_run_cannot_satisfy_current_validation(self):
        _, command, run, jobs = fixture(); jobs[1]['run_id'] = 999
        self.assertEqual(inspect_validation(API(run, jobs), 'owner/repo', command)['status'], 'failed')


class ValidationWorkerTests(unittest.TestCase):
    def setUp(self):
        from tests.test_article_image_contract import ArticleImageContractTests
        from tests.test_kesher_canonical_state import ContentsServer
        from scripts.kesher_runtime.github import GitHubStateStore
        from scripts.kesher_runtime.worker import WorkerContext
        from scripts.kesher_article_contract import exact_field, IMAGE_EVIDENCE_FIELDS
        f = ArticleImageContractTests(); f.setUp()
        # A real canonical image receipt precedes this validation command.
        self.pr = copy.deepcopy(f.pr)
        self.pr.update(number=42)
        self.pr['base'].update(sha=CODE, repo={'full_name': 'owner/repo'})
        self.pr['head'].update(sha=HEAD, repo={'full_name': 'owner/repo'})
        f.post['date'] = DAY; self.pr['body'] = f.proof(head=HEAD)
        proof = {label: exact_field(self.pr['body'], label) for label in IMAGE_EVIDENCE_FIELDS}
        state, image_id = plan_command(new_state(), SlotIdentity(DAY), 'attach_image', 1, {}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state); self.store = GitHubStateStore(self.server, 'owner/repo')
        image_worker = WorkerContext(self.store, image_id, '122/1', SlotIdentity(DAY), code_sha=CODE, now=lambda: NOW)
        image_worker.claim()
        request = {'image_evidence': proof, 'main_sha': CODE}
        image_worker.begin_effect('image_branch_fixture', request)
        image_worker.complete_effect('image_branch_fixture', {'pr_number': 42, 'new_head_sha': HEAD, 'image_evidence': proof})
        image_worker.checkpoint('execution_result', {'status': 'image_attached'}, phase='OUTPUT_CREATED')
        image_worker.finish()
        loaded = self.store.load()
        state, key = plan_command(loaded.state, SlotIdentity(DAY), 'validate_article', 2,
                                 {'pr_number': '42', 'pr_head_sha': HEAD}, code_sha=CODE, now=NOW)
        self.store.save(loaded, state)
        self.context = WorkerContext(self.store, key, '123/2', SlotIdentity(DAY), code_sha=CODE, now=lambda: NOW)
        self.context.claim()
        self.snapshot = {'base_sha': CODE, 'head_sha': HEAD, 'tree_sha': 'c'*40,
                         'post': f.post, 'base_posts': f.base, 'head_posts': f.base + [f.post],
                         'image_data': f.image, 'image_path': 'public' + f.post['image'],
                         'paths': [row['filename'] for row in f.files]}
        self.git = Mock()
        self.git.inspect.side_effect = lambda *args: copy.deepcopy(self.snapshot)
        self.main = CODE
        self.run, self.jobs = fixture()[2:]
        self.run.update(display_title='kesher-command:' + key, status='in_progress', conclusion=None)
        self.api = Mock()
        self.api.request.side_effect = self.read

    def read(self, method, path):
        self.assertEqual(method, 'GET')
        if path.endswith('/git/ref/heads/main'): return {'object': {'sha': self.main}}
        if path.endswith('/pulls/42'): return copy.deepcopy(self.pr)
        return API(self.run, self.jobs).request(method, path)

    def test_prepare_persists_candidate_and_other_jobs_stage_without_state_writes(self):
        from scripts.kesher_runtime import article_validation as module
        self.assertTrue(hasattr(module, 'prepare_validation'), 'Missing connected validation worker')
        evidence = module.prepare_validation(self.context, self.api, self.git)
        self.assertEqual(evidence['head_sha'], HEAD)
        writes = len(self.server.writes)
        module.stage_validation(self.context, self.api, self.git)
        module.validate_content(self.context, self.api, self.git)
        self.assertEqual(len(self.server.writes), writes)
        self.git.stage.assert_called_once_with(self.snapshot)
        self.assertEqual(self.store.load().state['commands'][self.context.command_id]['outcome'], 'pending')

    def test_changed_body_code_or_head_cannot_stage_previously_accepted_candidate(self):
        from scripts.kesher_runtime import article_validation as module
        from scripts.kesher_runtime.jules import JulesError
        self.assertTrue(hasattr(module, 'prepare_validation'), 'Missing connected validation worker')
        module.prepare_validation(self.context, self.api, self.git)
        original = copy.deepcopy(self.pr)
        for field in ('body', 'head', 'main'):
            with self.subTest(field=field):
                self.pr = copy.deepcopy(original); self.main = CODE
                if field == 'body': self.pr['body'] += '\nChanged editorial evidence'
                elif field == 'head': self.pr['head']['sha'] = 'f'*40
                else: self.main = 'f'*40
                with self.assertRaises(JulesError): module.stage_validation(self.context, self.api, self.git)
        self.git.stage.assert_not_called()

    def test_real_job_result_is_required_before_finishing_and_never_asserts_publication(self):
        from scripts.kesher_runtime import article_validation as module
        self.assertTrue(hasattr(module, 'prepare_validation'), 'Missing connected validation worker')
        module.prepare_validation(self.context, self.api, self.git)
        result = module.record_validation(self.context, self.api)
        self.assertEqual(result['status'], 'verified')
        command = self.store.load().state['commands'][self.context.command_id]
        self.assertEqual(command['outcome'], 'succeeded')
        self.assertNotIn('PUBLICLY_VERIFIED', str(command['receipts']))
        self.assertEqual(inspect_validation(self.api, 'owner/repo', command)['status'], 'pending')
        self.run.update(status='completed', conclusion='success')
        self.assertEqual(inspect_validation(self.api, 'owner/repo', command)['status'], 'verified')

    def test_failed_render_is_terminal_ci_failure_even_when_other_jobs_pass(self):
        from scripts.kesher_runtime import article_validation as module
        self.assertTrue(hasattr(module, 'prepare_validation'), 'Missing connected validation worker')
        module.prepare_validation(self.context, self.api, self.git)
        self.jobs[1]['conclusion'] = 'failure'
        self.assertEqual(module.record_validation(self.context, self.api)['status'], 'failed')
        command = self.store.load().state['commands'][self.context.command_id]
        self.assertEqual(command['outcome'], 'failed')
        self.assertEqual(command['failure']['class'], 'CI_FAILED')

    def test_observer_requires_canonical_run_even_if_named_pr_checks_claim_success(self):
        import base64
        import inspect
        from scripts.kesher_runtime import article_validation as module
        from scripts.kesher_runtime.observe import RepositoryObserver
        self.assertIn('main_sha', inspect.signature(RepositoryObserver.article_prs).parameters)
        def read(method, path):
            if '/pulls?' in path: return [copy.deepcopy(self.pr)]
            if '/files?' in path: return [{'filename': name} for name in self.snapshot['paths']]
            if '/contents/' in path:
                data = json.dumps([self.snapshot['post']]).encode() if 'posts.json' in path else self.snapshot['image_data']
                return {'encoding': 'base64', 'content': base64.b64encode(data).decode()}
            # A malicious same-name check must never even be considered.
            self.assertNotIn('check-runs', path)
            return self.read(method, path)
        api = Mock(); api.request.side_effect = read
        observer = RepositoryObserver(api, 'owner/repo', inventory_reader=Mock(), auditor=Mock())
        def status(state):
            return observer.article_prs([], DAY, state, main_sha=CODE)[0]['status']
        state = self.store.load().state
        del state['commands'][self.context.command_id]
        self.assertEqual(status(state), 'ci_required')
        module.prepare_validation(self.context, self.api, self.git)
        self.assertEqual(status(self.store.load().state), 'ci_pending')
        module.record_validation(self.context, self.api)
        self.run.update(status='completed', conclusion='success')
        self.assertEqual(status(self.store.load().state), 'ready_to_merge')
        failed_state = self.store.load().state
        failed_state['commands'][self.context.command_id].update(outcome='failed', failure={'class': 'TRANSIENT_API'})
        self.run['conclusion'] = 'failure'
        self.assertEqual(status(failed_state), 'ci_required', 'A failed API observation must use bounded CI recovery')
        self.run['conclusion'] = 'success'
        self.pr['body'] += '\nEditorial evidence changed'
        self.assertEqual(status(self.store.load().state), 'ci_required')
        stale = self.store.load().state
        for command in stale['commands'].values():
            for effect in command['effects'].values():
                effect['request']['main_sha'] = 'f'*40
                effect['request_sha256'] = digest(effect['request'])
        self.assertEqual(status(stale), 'normalize_required', 'Old-main image branch needs automatic rebasing before CI')


class ValidationWorkflowContractTests(unittest.TestCase):
    def test_quality_gate_keeps_current_suites_and_routes_legacy_through_compatibility(self):
        import os
        from pathlib import Path
        import subprocess
        import sys
        import tempfile
        import yaml

        root = Path(__file__).resolve().parents[1]
        workflow = yaml.safe_load((root / '.github/workflows/kesher-article-validation.yml').read_text())
        quality = next(step['run'] for step in workflow['jobs']['article-checks']['steps']
                       if step['name'] == 'Run full repository quality gate')
        python_gate = quality.split('python scripts/article_claim_quality.py', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            tests = fixture / 'tests'; tests.mkdir()
            (tests / '__init__.py').write_text('')
            (tests / 'kesher_daily_pipeline_suite.py').write_text(
                (root / 'tests/kesher_daily_pipeline_suite.py').read_text())
            (tests / 'test_kesher_daily_pipeline.py').write_text(
                'import unittest\n'
                'class PipelineTestCase(unittest.TestCase):\n'
                '    def test_current_pipeline(self): pass\n'
                '    def test_jules_review_parse_failure_remains_blocked_from_upload(self):\n'
                '        self.fail("obsolete parse assertion executed")\n'
                '    def test_jules_review_api_timeout_remains_blocked_from_upload(self):\n'
                '        self.fail("obsolete timeout assertion executed")\n')
            modules = ('test_video_pending_evidence_repair', 'test_video_exact_item_binding',
                       'test_video_exact_item_callers', 'test_canonical_article', 'test_canonical_media',
                       'test_canonical_controller', 'test_canonical_authority', 'test_new_publication_regression')
            for module in modules:
                (tests / (module + '.py')).write_text(
                    'import unittest\nclass CurrentTests(unittest.TestCase):\n'
                    '    def test_current_contract(self): pass\n')
            executables = fixture / 'bin'; executables.mkdir()
            for name in ('python', 'python3'):
                (executables / name).symlink_to(sys.executable)
            result = subprocess.run(['bash', '-c', python_gate], cwd=fixture, capture_output=True,
                                    text=True, timeout=30, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                                    PATH=str(executables) + os.pathsep + os.environ['PATH']))
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn('tests.test_kesher_daily_pipeline.PipelineTestCase.test_current_pipeline', output)
        for module in modules:
            self.assertIn('tests.' + module + '.CurrentTests.test_current_contract', output)
        self.assertNotIn('test_jules_review_parse_failure_remains_blocked_from_upload', output)
        self.assertNotIn('test_jules_review_api_timeout_remains_blocked_from_upload', output)


if __name__ == '__main__': unittest.main()
