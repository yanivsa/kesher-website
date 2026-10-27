import base64
import copy
import hashlib
import json
import os
import unittest
from unittest import mock
from tests import test_article_image_contract as fixtures
load = fixtures.load
from scripts.kesher_content_controller_v4 import V4GitHubClient


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

    def test_worker_startup_refuses_a_moved_recovery_head(self):
        worker = load('article-image-worker-v3')
        with mock.patch.dict(os.environ, {'GITHUB_TOKEN': 'test-token', 'KESHER_IMAGE_RECOVERY_ONLY': 'true', 'KESHER_IMAGE_EXPECTED_HEAD': 'f' * 40}), mock.patch('sys.argv', ['worker', 'test/repo', '1']), mock.patch.object(worker.core, 'request_json', return_value=self.pr), mock.patch.object(worker, 'ensure_image', side_effect=AssertionError('must refuse before work')):
            with self.assertRaisesRegex(RuntimeError, 'IMAGE_RECOVERY_HEAD_CHANGED'):
                worker.main()

    def test_worker_restores_exact_prior_pixels_without_calling_generation(self):
        self._run_worker_recovery()

    def test_recovery_only_refuses_changed_editorial_without_generation(self):
        with self.assertRaisesRegex(RuntimeError, "IMAGE_RECOVERY_PROOF_INVALID"):
            self._run_worker_recovery(changed=True)

    def _run_worker_recovery(self, changed=False):
        worker = load('article-image-worker-v3')
        prior = self.pr['head']['sha']
        current = 'd' * 40
        stripped = {k: v for k, v in self.post.items() if k not in {'image', 'imageAlt'}}
        if changed:
            stripped['title'] = 'Different editorial article'
        pr = copy.deepcopy(self.pr)
        pr['head']['sha'] = current
        def posts_at(repo, ref, token):
            return self.base if ref == pr['base']['sha'] else [copy.deepcopy(self.post if ref == prior else stripped), *self.base]
        def content(repo, path, ref, token):
            if ref == prior and path == 'public' + self.post['image']:
                return {'encoding': 'base64', 'content': base64.b64encode(self.image).decode()}
            raise RuntimeError('not found')
        commits = []
        def commit(repo, candidate_pr, token, files, deletes):
            commits.append(files)
            return 'e' * 40
        with mock.patch.dict(os.environ, {'KESHER_IMAGE_RECOVERY_ONLY': 'true'}), mock.patch.object(worker.core, 'posts_at', side_effect=posts_at), mock.patch.object(worker.core, 'github_content', side_effect=content), mock.patch.object(worker, 'choose_candidate', side_effect=AssertionError('must not generate replacement pixels')), mock.patch.object(worker.core, 'patch_pr_body'), mock.patch.object(worker.core, 'request_json', return_value=[]), mock.patch.object(worker, 'commit_files', side_effect=commit):
            self.assertTrue(worker.ensure_image('test/repo', pr, 'test-token'))
        self.assertEqual(commits[0]['public' + self.post['image']][0], self.image)
        restored = json.loads(commits[0]['src/data/posts.json'][0])[0]
        self.assertEqual(restored, self.post)
