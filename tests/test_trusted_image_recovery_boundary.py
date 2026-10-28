import base64
import copy
import hashlib
import json
import os
import unittest
from datetime import datetime, timezone
from unittest import mock
from tests import test_article_image_contract as fixtures
load = fixtures.load
from scripts.kesher_content_controller_v4 import V4GitHubClient
from scripts import kesher_content_controller_stabilized as stabilized
from scripts import kesher_content_controller as core


class TrustedImageRecoveryBoundaryTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ArticleImageContractTests()
        fixture.setUp()
        self.image = fixture.image
        self.post = {**fixture.post, 'slug': 'couples-communication', 'date': '2026-10-27', 'controllerManaged': True}
        self.base = [{'id': 'old-article', 'date': '2026-10-20'}]
        fixture.post = self.post
        self.pr = {**fixture.pr, 'body': fixture.proof()}
        self.files = [{'filename': 'src/data/posts.json'}, {'filename': 'public' + self.post['image']}]

    def test_verified_hero_does_not_force_normalization_but_unrelated_paths_and_stale_base_do(self):
        client = V4GitHubClient('test/repo', 'test-token')
        posts = [self.post, *self.base]
        def contents(path, ref):
            return self.base if ref in ('main', self.pr['base']['sha']) else posts
        def request(method, url, **kwargs):
            if '/files?' in url:
                return self.files
            if '/contents/public' in url:
                return {'encoding': 'base64', 'content': base64.b64encode(self.image).decode()}
            raise AssertionError(url)
        with mock.patch.object(client, 'contents_json', side_effect=contents), mock.patch.object(client, 'request', side_effect=request):
            self.assertEqual(client.article_pr_normalization_required(self.pr), (False, '2026-10-27'))
            self.files.append({'filename': 'src/App.tsx'})
            self.assertTrue(client.article_pr_normalization_required(self.pr)[0])
            self.files.pop()
            posts[-1] = {**self.base[0], 'title': 'unauthorized old article change'}
            self.assertTrue(client.article_pr_normalization_required(self.pr)[0])

    def test_prior_image_recovery_allows_content_only_repair_with_same_visual_identity(self):
        client = V4GitHubClient('test/repo', 'test-token')
        prior = self.pr['head']['sha']
        current = 'd' * 40
        pr = copy.deepcopy(self.pr)
        pr['head']['sha'] = current
        current_post = {k: copy.deepcopy(v) for k, v in self.post.items() if k not in {'image', 'imageAlt'}}
        current_post['content'] = str(current_post.get('content') or '') + '<p>Bounded internal-link repair only.</p>'

        def contents(path, ref):
            self.assertEqual(path, 'src/data/posts.json')
            if ref == pr['base']['sha']:
                return copy.deepcopy(self.base)
            if ref == current:
                return [copy.deepcopy(current_post), *copy.deepcopy(self.base)]
            if ref == prior:
                return [copy.deepcopy(self.post), *copy.deepcopy(self.base)]
            raise AssertionError(ref)

        with mock.patch.object(client, '_article_pr_image_proof', return_value=(True, {'article_id': self.post['id']})), \
             mock.patch.object(client, 'contents_json', side_effect=contents):
            recoverable, _ = client.article_pr_prior_image_recoverable(pr)

        self.assertTrue(recoverable)

    def test_real_dispatch_guard_allows_bound_recovery_after_three_attempts(self):
        gh = mock.Mock()
        gh.active_workflow_run.return_value = None
        gh._controller_state_loaded = True
        ctrl = stabilized.StabilizedRuntimeV5Controller(gh, mock.Mock(), now=datetime(2026, 10, 27, 12, tzinfo=timezone.utc))
        state = {'cycle': '2026-10-27', 'status': 'article_pr_open', 'article': {'pr_number': 1227, 'current_pr_head_sha': 'd' * 40}, 'image': {'attempt_count': 3}, 'pending_dispatches': {}}
        sent = []
        inputs = {'pr_number': '1227', 'recovery_only': 'true', 'expected_head_sha': 'd' * 40}
        ctrl._guarded_dispatch(state, 'kesher-article-image.yml', inputs, lambda workflow, payload: sent.append((workflow, payload)))
        self.assertEqual(sent, [('kesher-article-image.yml', inputs)])
        self.assertEqual(state['image']['attempt_count'], 3)
        self.assertEqual(state['pending_dispatches']['kesher-article-image.yml']['status'], 'dispatched')

    def test_rebinding_status_does_not_authorize_fresh_or_unbound_generation(self):
        gh = mock.Mock()
        ctrl = stabilized.StabilizedRuntimeV5Controller(gh, mock.Mock(), now=datetime(2026, 10, 27, 12, tzinfo=timezone.utc))
        for inputs in [{'pr_number': '1227'}, {'pr_number': '1227', 'recovery_only': 'true', 'expected_head_sha': 'e' * 40}, {'pr_number': '1228', 'recovery_only': 'true', 'expected_head_sha': 'd' * 40}]:
            with self.subTest(inputs=inputs):
                state = {'cycle': '2026-10-27', 'status': 'article_image_rebinding', 'article': {'pr_number': 1227, 'current_pr_head_sha': 'd' * 40}, 'image': {'attempt_count': 3}, 'pending_dispatches': {}}
                with self.assertRaisesRegex(core.ControllerError, 'IMAGE_ATTEMPTS_EXHAUSTED'):
                    ctrl._guarded_dispatch(state, 'kesher-article-image.yml', inputs, lambda *_: self.fail('must refuse dispatch'))

    def test_recovery_dispatch_requires_a_positive_pr_identity(self):
        ctrl = stabilized.StabilizedRuntimeV5Controller(mock.Mock(), mock.Mock(), now=datetime(2026, 10, 27, 12, tzinfo=timezone.utc))
        for invalid in ['-1', 'abc', '0']:
            state = {'article': {'pr_number': invalid, 'current_pr_head_sha': 'd' * 40}, 'image': {'attempt_count': 3}}
            with self.subTest(pr=invalid), self.assertRaisesRegex(core.ControllerError, 'IMAGE_ATTEMPTS_EXHAUSTED'):
                ctrl._guarded_dispatch(state, 'kesher-article-image.yml', {'pr_number': invalid, 'recovery_only': 'true', 'expected_head_sha': 'd' * 40}, lambda *_: self.fail('must refuse malformed identity'))

    def test_worker_startup_refuses_a_moved_recovery_head(self):
        worker = load('article-image-worker-v3')
        with mock.patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token', 'KESHER_IMAGE_RECOVERY_ONLY': 'true', 'KESHER_IMAGE_EXPECTED_HEAD': 'f' * 40}), mock.patch('sys.argv', ['worker', 'test/repo', '1']), mock.patch.object(worker.core, 'request_json', return_value=self.pr), mock.patch.object(worker, 'ensure_image', side_effect=AssertionError('must refuse before work')):
            with self.assertRaisesRegex(RuntimeError, 'IMAGE_RECOVERY_HEAD_CHANGED'):
                worker.main()

    def test_worker_restores_exact_prior_pixels_without_calling_generation(self):
        self._run_worker_recovery()

    def test_worker_restores_prior_pixels_after_content_only_repair_without_generation(self):
        self._run_worker_recovery(content_changed=True)

    def test_recovery_only_refuses_changed_editorial_without_generation(self):
        with self.assertRaisesRegex(RuntimeError, "IMAGE_RECOVERY_PROOF_INVALID"):
            self._run_worker_recovery(changed=True)

    def _run_worker_recovery(self, changed=False, content_changed=False):
        worker = load('article-image-worker-v3')
        prior = self.pr['head']['sha']
        current = 'd' * 40
        stripped = {k: v for k, v in self.post.items() if k not in {'image', 'imageAlt'}}
        if changed:
            stripped['title'] = 'Different editorial article'
        if content_changed:
            stripped['content'] = str(stripped.get('content') or '') + '<p>Bounded internal-link repair only.</p>'
        pr = copy.deepcopy(self.pr)
        pr['head']['sha'] = current
        def posts_at(repo, ref, token):
            return self.base if ref == pr['base']['sha'] else [copy.deepcopy(self.post if ref == prior else stripped), *self.base]
        def content(repo, path, ref, token):
            if ref == prior and path == 'public' + self.post['image']:
                return {'encoding': 'base64', 'content': base64.b64encode(self.image).decode()}
            raise RuntimeError('not found')
        commits = []
        patched_bodies = []
        def commit(repo, candidate_pr, token, files, deletes):
            commits.append(files)
            return 'e' * 40
        def patch_body(repo, number, body, token):
            patched_bodies.append(body)
        with mock.patch.dict(os.environ, {'KESHER_IMAGE_RECOVERY_ONLY': 'true'}), mock.patch.object(worker.core, 'posts_at', side_effect=posts_at), mock.patch.object(worker.core, 'github_content', side_effect=content), mock.patch.object(worker, 'choose_candidate', side_effect=AssertionError('must not generate replacement pixels')), mock.patch.object(worker.core, 'patch_pr_body', side_effect=patch_body), mock.patch.object(worker.core, 'request_json', return_value=[]), mock.patch.object(worker, 'commit_files', side_effect=commit):
            self.assertTrue(worker.ensure_image('test/repo', pr, 'test-token'))
        self.assertEqual(commits[0]['public' + self.post['image']][0], self.image)
        restored = json.loads(commits[0]['src/data/posts.json'][0])[0]
        expected = copy.deepcopy(stripped)
        for field in ('image', 'imageAlt', 'imageProvider', 'imageSourceUrl', 'imageIsFallback', 'imageCredit', 'imageCreditUrl'):
            if field in self.post:
                expected[field] = self.post[field]
        self.assertEqual(restored, expected)
        self.assertTrue(patched_bodies)
        self.assertEqual(worker.exact_field(patched_bodies[-1], 'Image Article SHA-256'), worker.article_sha256(expected))
        self.assertEqual(worker.exact_field(patched_bodies[-1], 'Image Evidence Head'), 'e' * 40)
