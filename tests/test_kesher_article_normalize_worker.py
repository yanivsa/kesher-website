"""Conditional article ref updates, including lost replies and concurrent edits."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.jules import JulesError
from scripts.kesher_runtime.state import new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from scripts.kesher_runtime.article_normalize_worker import GitNormalization, normalize_article
from scripts.kesher_article_contract import ARTICLE_PUBLICATION_PATHS
from tests.test_kesher_canonical_state import CODE, DAY, NOW, ContentsServer

OLD, NEW, TREE = 'a'*40, 'b'*40, 'd'*40


class Branch:
    def __init__(self):
        self.current = OLD
        self.pushes = []
        self.prepares = []
        self.lost = False
        self.race = False

    def prepare(self, *, main_sha, head_sha, slot, pr_number, prepared_at):
        self.prepares.append(prepared_at)
        return {'new_head_sha': NEW, 'tree_sha': TREE}

    def head(self, branch):
        return self.current

    def push(self, branch, old, new):
        self.pushes.append((branch, old, new))
        if self.race:
            self.current = 'e'*40
        if self.current != old:
            raise OSError('conditional ref update rejected')
        self.current = new
        if self.lost:
            raise OSError('response lost after accepted push')


class NormalizeWorkerTests(unittest.TestCase):
    def setUp(self):
        target = SlotIdentity(DAY)
        state, command_id = plan_command(new_state(), target, 'normalize_article', 1,
            {'pr_number': '42', 'pr_head_sha': OLD}, code_sha=CODE, now=NOW)
        self.server = ContentsServer(state); self.store = GitHubStateStore(self.server, 'owner/repo')
        self.context = WorkerContext(self.store, command_id, '1/1', target, code_sha=CODE, now=lambda: NOW)
        self.context.claim()
        self.pr = {'number': 42, 'state': 'open', 'title': 'Publish Kesher article: test',
                   'head': {'sha': OLD, 'ref': 'jules/article', 'repo': {'full_name': 'owner/repo'}},
                   'base': {'ref': 'main'}}
        self.branch = Branch()
        self.settled = []

    def run_worker(self):
        return normalize_article(self.context, self.pr, self.branch, prove_quiescent=lambda pr: self.settled.append(pr['head']['sha']))

    def test_intent_precedes_push_and_lost_reply_adopts_the_same_commit(self):
        original = self.branch.push
        def push(*args):
            effects = self.server.document['commands'][self.context.command_id]['effects']
            self.assertEqual(len(effects), 1)
            self.assertIsNone(next(iter(effects.values()))['receipt'])
            return original(*args)
        self.branch.push = push; self.branch.lost = True
        result = self.run_worker()
        self.assertEqual(result['new_head_sha'], NEW)
        self.assertEqual(self.settled, [OLD, OLD])
        self.assertEqual(len(self.branch.pushes), 1)
        self.assertEqual(self.run_worker(), result)
        self.assertEqual(len(self.branch.pushes), 1)

    def test_concurrent_pr_edit_wins_and_is_never_force_overwritten(self):
        self.branch.race = True
        with self.assertRaisesRegex(JulesError, 'ARTICLE_PR_CHANGED'):
            self.run_worker()
        self.assertEqual(self.branch.current, 'e'*40)
        self.assertEqual(self.branch.pushes, [('jules/article', OLD, NEW)])

    def test_crash_after_push_is_adopted_when_github_already_reports_the_new_head(self):
        original = self.branch.push
        def crash(*args):
            original(*args)
            raise SystemExit('process terminated before recording response')
        self.branch.push = crash
        with self.assertRaises(SystemExit): self.run_worker()
        self.pr['head']['sha'] = NEW
        self.assertEqual(self.run_worker()['new_head_sha'], NEW)
        self.assertEqual(len(self.branch.prepares), 1)
        self.assertEqual(len(self.branch.pushes), 1)

    def test_crash_after_intent_can_rebuild_exact_commit_and_retry_conditional_push(self):
        original = self.branch.push
        self.branch.push = lambda *args: (_ for _ in ()).throw(OSError('died before write'))
        with self.assertRaisesRegex(JulesError, 'TRANSIENT_API'):
            self.run_worker()
        self.context.finish(failure={'class': 'TRANSIENT_API'})
        loaded = self.store.load()
        state, command_id = plan_command(loaded.state, self.context.target, 'normalize_article', 2,
            {'pr_number': '42', 'pr_head_sha': OLD}, code_sha=CODE, now='2026-09-18T00:00:00+00:00')
        self.store.save(loaded, state)
        self.context = WorkerContext(self.store, command_id, '2/1', self.context.target, code_sha=CODE, now=lambda: NOW)
        self.context.claim(); self.branch.push = original
        self.assertEqual(self.run_worker()['new_head_sha'], NEW)
        self.assertEqual(self.branch.prepares, [NOW, NOW])

    def test_unsettled_or_wrong_pr_identity_never_prepares_or_pushes(self):
        def unsettled(pr): raise JulesError('JULES_PENDING')
        with self.assertRaisesRegex(JulesError, 'JULES_PENDING'):
            normalize_article(self.context, self.pr, self.branch, prove_quiescent=unsettled)
        self.pr['head']['sha'] = 'f'*40
        with self.assertRaisesRegex(JulesError, 'ARTICLE_PR_CHANGED'): self.run_worker()
        self.assertEqual(self.branch.prepares, [])
        self.assertEqual(self.branch.pushes, [])

    def test_session_restarting_during_generation_blocks_the_later_push(self):
        active = False
        original = self.branch.prepare
        def prepare(**kwargs):
            nonlocal active
            active = True
            return original(**kwargs)
        def settled(pr):
            if active: raise JulesError('JULES_PENDING')
        self.branch.prepare = prepare
        with self.assertRaisesRegex(JulesError, 'JULES_PENDING'):
            normalize_article(self.context, self.pr, self.branch, prove_quiescent=settled)
        self.assertEqual(self.branch.pushes, [])

    def test_rebuilt_bytes_must_equal_the_saved_commit_before_retry(self):
        self.branch.push = lambda *args: (_ for _ in ()).throw(OSError('before write'))
        with self.assertRaises(JulesError): self.run_worker()
        self.branch.prepare = lambda **kwargs: {'new_head_sha': 'f'*40, 'tree_sha': TREE}
        with self.assertRaisesRegex(JulesError, 'ARTICLE_DERIVATION_CHANGED'): self.run_worker()
        self.assertEqual(self.branch.pushes, [])


class RealGitNormalizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'checkout'; self.root.mkdir()
        self.remote = Path(self.temp.name) / 'remote.git'
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Local test')
        self.git('config', 'user.email', 'local@example.invalid')
        self.base_post = {'id': 'existing', 'date': '2026-09-16', 'title': 'Existing'}
        for path in ARTICLE_PUBLICATION_PATHS:
            output = self.root / path; output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text('original\n')
        (self.root / 'src/data/posts.json').write_text(json.dumps([self.base_post]))
        (self.root / '.gitignore').write_text('src/data/\n')
        (self.root / 'package.json').write_text('{"trusted":true}\n')
        self.git('add', '-f', '.'); self.git('commit', '-m', 'Trusted main')
        self.main = self.git('rev-parse', 'HEAD')
        self.git('init', '--bare', str(self.remote))
        self.git('remote', 'add', 'origin', str(self.remote)); self.git('push', 'origin', 'main')
        self.git('checkout', '-b', 'jules/article')
        post = {'id': 'new', 'date': DAY, 'title': 'New', 'image': '/untrusted.png', 'imageAlt': 'Untrusted'}
        (self.root / 'src/data/posts.json').write_text(json.dumps([post, dict(self.base_post, title='Tampered')]))
        (self.root / 'package.json').write_text('{"scripts":{"generate":"exit 99"}}\n')
        (self.root / 'untrusted.txt').write_text('Must never survive normalization')
        self.git('add', '-f', '.'); self.git('commit', '-m', 'Untrusted article head')
        self.old = self.git('rev-parse', 'HEAD'); self.git('push', 'origin', 'jules/article')
        self.git('checkout', 'main')

    def tearDown(self): self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def branch(self):
        def trusted_generate():
            self.assertEqual(json.loads((self.root / 'package.json').read_text()), {'trusted': True})
            posts = json.loads((self.root / 'src/data/posts.json').read_text())
            for name in ARTICLE_PUBLICATION_PATHS - {'src/data/posts.json'}:
                (self.root / name).write_text(json.dumps({'ids': [post['id'] for post in posts]}) + '\n')
        return GitNormalization(self.root, generator=trusted_generate)

    def prepare(self, branch):
        return branch.prepare(main_sha=self.main, head_sha=self.old, slot=DAY, pr_number=42,
                              prepared_at=NOW.replace('+00:00', '.123456+00:00'))

    def test_real_tree_contains_only_trusted_base_and_one_normalized_article(self):
        branch = self.branch(); result = self.prepare(branch)
        commit = result['new_head_sha']
        posts = json.loads(self.git('show', commit + ':src/data/posts.json'))
        self.assertEqual(posts[1], self.base_post)
        self.assertEqual(posts[0], {'id': 'new', 'date': DAY, 'title': 'New'})
        self.assertEqual(json.loads(self.git('show', commit + ':package.json')), {'trusted': True})
        self.assertNotIn('untrusted.txt', self.git('ls-tree', '-r', '--name-only', commit).splitlines())
        self.assertEqual(json.loads(self.git('show', commit + ':src/data/postSummaries.json'))['ids'], ['new', 'existing'])
        self.assertEqual(self.git('rev-parse', commit + '^'), self.main)
        branch.push('jules/article', self.old, commit)
        self.assertEqual(branch.head('jules/article'), commit)

    def test_real_lease_rejects_concurrent_commit_and_deterministic_retry_rebuilds_same_object(self):
        branch = self.branch(); first = self.prepare(branch)
        # This reset is confined to the disposable test checkout owned above.
        self.git('reset', '--hard', self.main)
        second = self.prepare(branch)
        self.assertEqual(first, second)
        self.git('push', '--force-with-lease=refs/heads/jules/article:' + self.old,
                 'origin', self.main + ':refs/heads/jules/article')
        with self.assertRaises(OSError): branch.push('jules/article', self.old, first['new_head_sha'])
        self.assertEqual(branch.head('jules/article'), self.main)


if __name__ == '__main__': unittest.main()
