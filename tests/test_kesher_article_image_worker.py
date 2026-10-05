"""Image recovery must retain pixels across provider, Git and PR-body failures."""
import copy
import hashlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from scripts.kesher_article_contract import image_proof_errors
from scripts.kesher_runtime.article_image_worker import select_image, attach_image
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.jules import JulesError
from scripts.kesher_runtime.state import new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, DAY, NOW, ContentsServer

OLD, NEW, TREE = 'a'*40, 'b'*40, 'd'*40
POST = {'id': 'new-article', 'slug': 'new-article', 'title': 'מאמר חדש על זוגיות', 'date': DAY}


def candidate(provider='Gemini', color='navy'):
    output = io.BytesIO(); Image.new('RGB', (640, 360), color).save(output, 'PNG')
    return {'provider': provider, 'data': output.getvalue(), 'extension': 'png',
            'source_url': 'https://example.org/image',
            'visual_match': 'שני אנשים בשיחה רגועה בסלון בית מואר באור טבעי'}


class Blobs:
    def __init__(self): self.data = {}; self.crash = False

    def get(self, sha): return self.data.get(sha)

    def put(self, data):
        sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        self.data[sha] = data
        if self.crash: raise SystemExit('crashed after durable blob creation')
        return sha


class ImageWorkerTests(unittest.TestCase):
    def setUp(self):
        target = SlotIdentity(DAY)
        state, command_id = plan_command(new_state(), target, 'attach_image', 1,
            {'pr_number': '42', 'pr_head_sha': OLD}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state); self.store = GitHubStateStore(self.server, 'owner/repo')
        self.context = WorkerContext(self.store, command_id, '1/1', target, code_sha=CODE, now=lambda: NOW)
        self.context.claim(); self.blobs = Blobs(); self.calls = []
        self.providers = {}
        for name, label in [('gemini-1', 'Gemini'), ('gemini-2', 'Gemini'), ('gemini-3', 'Gemini'),
                            ('pexels', 'Pexels'), ('pixabay', 'Pixabay'), ('local-curated', 'Local')]:
            def run(post, used, name=name, label=label):
                self.calls.append(name)
                return candidate(label)
            self.providers[name] = run

    def select(self, post=None):
        return select_image(self.context, post or POST, 42, self.providers, self.blobs, set())

    def recover(self, head=OLD):
        self.context.finish(failure={'class': 'TRANSIENT_API'})
        loaded = self.store.load()
        state, command_id = plan_command(loaded.state, self.context.target, 'attach_image', 2,
            {'pr_number': '42', 'pr_head_sha': head}, code_sha=CODE, now=NOW)
        self.store.save(loaded, state)
        self.context = WorkerContext(self.store, command_id, '2/1', self.context.target, code_sha=CODE, now=lambda: NOW)
        self.context.claim()

    def test_selected_pixels_survive_new_command_without_provider_repetition(self):
        first = self.select(); self.recover(); second = self.select()
        self.assertEqual(second, first)
        self.assertEqual(second['data'], candidate()['data'])
        self.assertEqual(self.calls, ['gemini-1'])

    def test_uncertain_generation_is_not_repeated_and_next_provider_can_finish(self):
        def crash(post, used):
            self.calls.append('gemini-1')
            self.assertTrue(self.server.document['commands'][self.context.command_id]['effects'])
            raise SystemExit('generation accepted; response lost')
        self.providers['gemini-1'] = crash
        with self.assertRaises(SystemExit): self.select()
        self.recover(); result = self.select()
        self.assertEqual(result['provider'], 'Gemini')
        self.assertEqual(result['attempts'], ['gemini-1', 'gemini-2'])
        self.assertEqual(self.calls, ['gemini-1', 'gemini-2'])

    def test_crash_after_blob_write_adopts_same_generated_image(self):
        self.blobs.crash = True
        with self.assertRaises(SystemExit): self.select()
        self.recover(); self.blobs.crash = False
        self.assertEqual(self.select()['provider'], 'Gemini')
        self.assertEqual(self.calls, ['gemini-1'])

    def test_corrupted_saved_blob_cannot_become_verified_pixels(self):
        self.select(); self.recover()
        key = next(iter(self.blobs.data)); self.blobs.data[key] += b'\0'
        with self.assertRaisesRegex(JulesError, 'ARTICLE_IMAGE_OUTPUT_INVALID'): self.select()
        self.assertEqual(self.calls, ['gemini-1'])

    def test_rejected_duplicate_pixels_fall_through_and_do_not_publish(self):
        from scripts.kesher_article_contract import image_pixel_sha256
        self.providers['gemini-2'] = lambda post, used: None
        self.providers['pexels'] = lambda post, used: candidate('Pexels', 'green')
        result = select_image(self.context, POST, 42, self.providers, self.blobs,
                              {'pixels:' + image_pixel_sha256(candidate()['data'])})
        self.assertEqual(result['provider'], 'Pexels')
        self.assertEqual(result['attempts'], ['gemini-1', 'gemini-2', 'gemini-3', 'pexels'])

    def test_no_publication_pixels_means_no_successful_selection(self):
        with self.assertRaisesRegex(JulesError, 'ARTICLE_IMAGE_UNAVAILABLE'):
            select_image(self.context, POST, 42, {name: lambda *a: None for name in self.providers}, self.blobs, set())

    def test_body_failure_recovers_same_commit_and_image_without_regeneration(self):
        branch = ImageBranch(); pull = PullRequest(); pull.branch = branch
        selected = self.select()
        def choose(post): return self.select(post)
        pull.fail_patch = True
        with self.assertRaisesRegex(JulesError, 'TRANSIENT_API'):
            attach_image(self.context, pull.get(), branch, pull, choose, prove_quiescent=lambda pr: None)
        self.assertEqual(branch.current, NEW)
        self.assertEqual(len(branch.pushes), 1)
        pull.row['head']['sha'] = NEW
        pull.fail_patch = False
        result = attach_image(self.context, pull.get(), branch, pull, choose, prove_quiescent=lambda pr: None)
        self.assertEqual(result['new_head_sha'], NEW)
        self.assertEqual(self.calls, ['gemini-1'])
        self.assertEqual(len(branch.pushes), 1)
        self.assertEqual(len(branch.prepares), 1)
        self.assertIn('Independent editorial evidence', pull.row['body'])
        self.assertEqual(image_proof_errors(branch.output_post, pull.row['body'], NEW, selected['data']), [])
        from scripts.kesher_runtime.article_image_worker import image_receipt_matches
        self.assertTrue(image_receipt_matches(self.store.load().state, DAY, 42, NEW,
                        branch.output_post, selected['data'], pull.row['body']))
        self.assertFalse(image_receipt_matches(self.store.load().state, DAY, 42, 'f'*40,
                         branch.output_post, selected['data'], pull.row['body']))

    def test_unsettled_pr_or_concurrent_head_never_overwrites_branch(self):
        branch = ImageBranch(); pull = PullRequest()
        def unsettled(pr): raise JulesError('JULES_PENDING')
        with self.assertRaisesRegex(JulesError, 'JULES_PENDING'):
            attach_image(self.context, pull.get(), branch, pull, lambda post: self.select(post), prove_quiescent=unsettled)
        self.assertEqual(self.calls, [])
        branch.current = 'e'*40
        with self.assertRaisesRegex(JulesError, 'ARTICLE_PR_CHANGED'):
            attach_image(self.context, pull.get(), branch, pull, lambda post: self.select(post), prove_quiescent=lambda pr: None)
        self.assertEqual(branch.current, 'e'*40)
        self.assertEqual(branch.pushes, [])

    def test_recovery_command_observing_new_head_repairs_only_evidence(self):
        branch = ImageBranch(); pull = PullRequest(); pull.branch = branch; pull.fail_patch = True
        with self.assertRaises(JulesError):
            attach_image(self.context, pull.get(), branch, pull, self.select, prove_quiescent=lambda pr: None)
        self.recover(head=NEW); pull.fail_patch = False
        result = attach_image(self.context, pull.get(), branch, pull, self.select, prove_quiescent=lambda pr: None)
        self.assertEqual(result['new_head_sha'], NEW)
        self.assertEqual(len(branch.prepares), 1, 'New-head recovery must adopt the saved branch intent')
        self.assertEqual(len(branch.pushes), 1)

    def test_jules_restarting_during_image_generation_blocks_the_later_ref_write(self):
        branch = ImageBranch(); pull = PullRequest(); pull.branch = branch
        active = False
        def quiescent(pr):
            if active: raise JulesError('JULES_PENDING')
        def choose(post):
            nonlocal active
            output = self.select(post); active = True
            return output
        with self.assertRaisesRegex(JulesError, 'JULES_PENDING'):
            attach_image(self.context, pull.get(), branch, pull, choose, prove_quiescent=quiescent)
        self.assertEqual(branch.current, OLD)
        self.assertEqual(branch.pushes, [])


class ImageBranch:
    def __init__(self): self.current = OLD; self.pushes = []; self.prepares = []; self.output_post = None

    def head(self, ref): return self.current

    def article(self, **kwargs): return copy.deepcopy(POST)

    def prepare(self, *, post, candidate, **kwargs):
        self.prepares.append(kwargs)
        self.output_post = dict(post, image='/images/generated/blog/new-article.png', imageAlt=candidate['visual_match'])
        return {'new_head_sha': NEW, 'tree_sha': TREE, 'post': self.output_post}

    def push(self, ref, old, new):
        if self.current != old: raise OSError('lease rejected')
        self.pushes.append((ref, old, new)); self.current = new


class PullRequest:
    def __init__(self):
        self.row = {'number': 42, 'state': 'open', 'title': 'Publish Kesher article: test',
                    'body': 'Independent editorial evidence', 'base': {'ref': 'main'},
                    'head': {'sha': OLD, 'ref': 'jules/article', 'repo': {'full_name': 'owner/repo'}}}
        self.fail_patch = False

    def get(self):
        row = copy.deepcopy(self.row)
        if hasattr(self, 'branch'): row['head']['sha'] = self.branch.current
        return row

    def patch_body(self, body):
        if self.fail_patch: raise OSError('body write failed')
        self.row['body'] = body


class RealImageGitTests(unittest.TestCase):
    def setUp(self):
        from tests.test_kesher_article_normalize_worker import RealGitNormalizationTests
        self.fixture = RealGitNormalizationTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)

    def test_untrusted_code_or_existing_article_changes_require_normalization_first(self):
        from scripts.kesher_runtime.article_image_worker import GitImageBranch
        branch = GitImageBranch(self.fixture.root)
        with self.assertRaisesRegex(JulesError, 'ARTICLE_NORMALIZATION_REQUIRED'):
            branch.article(main_sha=self.fixture.main, head_sha=self.fixture.old, slot=DAY)

    def test_real_image_commit_uses_trusted_generators_and_survives_exact_ref_readback(self):
        import json
        from scripts.kesher_runtime.article_image_worker import GitImageBranch
        f = self.fixture
        f.git('checkout', '-B', 'jules/article', f.main)
        (f.root / 'src/data/posts.json').write_text(json.dumps([POST, f.base_post]))
        f.git('add', '-f', 'src/data/posts.json'); f.git('commit', '-m', 'Normalized article')
        old = f.git('rev-parse', 'HEAD'); f.git('push', '--force', 'origin', 'jules/article')
        f.git('checkout', 'main')
        branch = GitImageBranch(f.root, generator=f.branch().generator)
        post = branch.article(main_sha=f.main, head_sha=old, slot=DAY)
        result = branch.prepare(main_sha=f.main, head_sha=old, post=post, candidate=candidate(),
                                slot=DAY, pr_number=42, prepared_at=NOW)
        path = 'public/images/generated/blog/new-article.png'
        import subprocess
        data = subprocess.check_output(['git', 'show', result['new_head_sha'] + ':' + path], cwd=f.root)
        self.assertEqual(data, candidate()['data'])
        self.assertEqual(json.loads(f.git('show', result['new_head_sha'] + ':src/data/posts.json'))[1], f.base_post)
        self.assertEqual(f.git('rev-parse', result['new_head_sha'] + '^'), f.main)
        branch.push('jules/article', old, result['new_head_sha'])
        self.assertEqual(branch.head('jules/article'), result['new_head_sha'])
        f.git('reset', '--hard', f.main)
        # Untracked rendered output belongs only to this disposable test checkout.
        (f.root / path).unlink()
        repeated = branch.prepare(main_sha=f.main, head_sha=old, post=post, candidate=candidate(),
                                  slot=DAY, pr_number=42, prepared_at=NOW)
        self.assertEqual(repeated, result)


class ApprovedProviderTests(unittest.TestCase):
    def test_stock_never_accepts_search_metadata_instead_of_pixel_verification(self):
        from scripts.kesher_runtime import article_images as images
        sample = candidate()['data']
        with patch.dict('os.environ', {'GOOGLE_API_KEY': 'test', 'PEXELS_API_KEY': 'test'}), \
             patch.object(images, 'request_json', return_value={'photos': [{'src': {'large': 'https://images.pexels.com/test'}, 'url': 'https://pexels.com/test'}]}), \
             patch.object(images, 'download', return_value=sample), \
             patch.object(images, 'google_json', return_value={'candidates': [{'content': {'parts': [{'text': 'REJECT|wrong pixels'}]}}]}):
            self.assertIsNone(images.provider_functions(Path('.'))['pexels'](POST, set()))

    def test_abstract_fallback_and_retired_provider_are_unavailable(self):
        from scripts.kesher_runtime import article_images as images
        providers = images.provider_functions(Path('.'))
        self.assertEqual(set(providers), {'gemini-1', 'gemini-2', 'gemini-3', 'pexels', 'pixabay', 'local-curated'})
        self.assertNotIn('local-editorial', providers)
        self.assertNotIn('unsplash', providers)
        self.assertFalse(hasattr(images, 'generate_editorial_fallback'))


if __name__ == '__main__': unittest.main()
