"""Normalize one exact article PR with trusted generators and an atomic ref lease.

Only article JSON is read from the untrusted head. Prepared commits have stable
author metadata so an interrupted worker can reproduce the same object. A lost
push reply is observed by exact ref; retries are conditional on the original
head, never an unconditional force push.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
from pathlib import Path

from scripts.kesher_article_contract import ARTICLE_PUBLICATION_PATHS, forbidden_article_paths
from scripts.kesher_article_normalizer import extract_target_article, normalized_posts
from .identity import SlotIdentity, digest, require_sha
from .jules import JulesError
from .state import ClaimRejected, StateInvalid


def normalize_article(context, pr: dict, branch, *, prove_quiescent) -> dict:
    state = context.store.load().state
    command = context._owned(state)
    if not isinstance(context.target, SlotIdentity) or command['operation'] != 'normalize_article':
        raise ClaimRejected('Exact normalize command required')
    expected = command['inputs']
    if (pr.get('state') != 'open' or str(pr.get('number')) != expected.get('pr_number')
            or pr.get('base', {}).get('ref') != 'main'
            or (pr.get('head', {}).get('repo') or {}).get('full_name') != context.store.repo
            or not str(pr.get('title', '')).startswith('Publish Kesher article:')):
        raise JulesError('ARTICLE_PR_CHANGED')
    old = expected.get('pr_head_sha'); require_sha(old, 40)
    ref = pr['head']['ref']
    if not isinstance(ref, str) or not ref or ref in {'main', 'automation-state'}:
        raise JulesError('ARTICLE_PR_IDENTITY_MISMATCH')
    name = 'normalize_branch_' + digest([pr['number'], old, context.code_sha])[:32]
    prior = [row['effects'][name] for row in state['commands'].values()
             if row['target'] == context.target.to_dict() and name in row['effects']]
    requests = {row['request_sha256']: row['request'] for row in prior}
    if len(requests) > 1:
        raise StateInvalid('Conflicting exact normalization intents')
    previous = copy.deepcopy(next(iter(requests.values()), None))
    if pr['head']['sha'] not in {old, previous['new_head_sha'] if previous else old}:
        raise JulesError('ARTICLE_PR_CHANGED')
    if previous:
        if previous['branch'] != ref:
            raise JulesError('ARTICLE_PR_CHANGED')
        decision = context.begin_effect(name, previous)
        if decision.receipt:
            return decision.receipt
        if branch.head(ref) == previous['new_head_sha']:
            result = {key: previous[key] for key in ('pr_number', 'old_head_sha', 'new_head_sha', 'tree_sha')}
            context.complete_effect(name, result)
            return result
    prove_quiescent(pr)
    prepared_at = previous['prepared_at'] if previous else command['created_at']
    prepared = branch.prepare(main_sha=context.code_sha, head_sha=old, slot=context.target.slot,
                              pr_number=pr['number'], prepared_at=prepared_at)
    for field in ('new_head_sha', 'tree_sha'):
        require_sha(prepared[field], 40)
    request = {'pr_number': pr['number'], 'branch': ref, 'old_head_sha': old, 'main_sha': context.code_sha,
               'prepared_at': prepared_at, **prepared}
    if previous and request != previous:
        raise JulesError('ARTICLE_DERIVATION_CHANGED')
    decision = context.begin_effect(name, request)
    if decision.receipt:
        return decision.receipt
    actual = branch.head(ref)
    if actual != prepared['new_head_sha']:
        prove_quiescent(pr)
        if actual != old:
            raise JulesError('ARTICLE_PR_CHANGED')
        try:
            # Repeating this exact conditional ref update is safe even when an
            # earlier request was accepted without a response. Only one expected
            # head can win; another head can never be overwritten by this lease.
            branch.push(ref, old, prepared['new_head_sha'])
        except OSError:
            pass  # Read back before classifying a rejection or uncertain reply.
        actual = branch.head(ref)
        if actual != prepared['new_head_sha']:
            raise JulesError('TRANSIENT_API' if actual == old else 'ARTICLE_PR_CHANGED')
    result = {'pr_number': pr['number'], 'old_head_sha': old, **prepared}
    context.complete_effect(name, result)
    return result


class GitNormalization:
    def __init__(self, root: Path, *, generator=None):
        self.root = Path(root).resolve()
        self.generator = generator or self._generate

    def _run(self, args: list[str], *, env=None, timeout=120) -> str:
        try:
            return subprocess.run(args, cwd=self.root, env=env, timeout=timeout, check=True,
                                  capture_output=True, text=True).stdout.strip()
        except (subprocess.SubprocessError, OSError):
            raise OSError('Article Git/generator operation failed') from None

    def _git(self, *args: str, env=None) -> str:
        # Credentials remain in the inherited GH_TOKEN environment. They are
        # neither command arguments nor embedded remote URLs or log output.
        return self._run(['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential', *args], env=env)

    def _generate(self):
        self._run(['npm', 'run', 'generate'], timeout=600)

    def head(self, branch: str) -> str:
        ref = 'refs/heads/' + branch
        self._git('check-ref-format', ref)
        result = self._git('ls-remote', '--exit-code', 'origin', ref).split()
        if len(result) != 2 or result[1] != ref:
            raise JulesError('ARTICLE_PR_CHANGED')
        require_sha(result[0], 40)
        return result[0]

    def push(self, branch: str, old: str, new: str) -> None:
        require_sha(old, 40); require_sha(new, 40)
        self._git('check-ref-format', 'refs/heads/' + branch)
        self._git('push', '--force-with-lease=refs/heads/' + branch + ':' + old,
                  'origin', new + ':refs/heads/' + branch)

    def prepare(self, *, main_sha: str, head_sha: str, slot: str, pr_number: int, prepared_at: str) -> dict:
        require_sha(main_sha, 40); require_sha(head_sha, 40)
        SlotIdentity(slot)
        if self._git('rev-parse', 'HEAD') != main_sha or self._git('status', '--porcelain'):
            raise JulesError('ARTICLE_TRUSTED_CHECKOUT_REQUIRED')
        self._git('fetch', '--no-tags', 'origin', head_sha)
        base_posts = json.loads(self._git('show', main_sha + ':src/data/posts.json'))
        head_posts = json.loads(self._git('show', head_sha + ':src/data/posts.json'))
        post = extract_target_article(base_posts, head_posts, slot)
        post.pop('image', None); post.pop('imageAlt', None)
        output = normalized_posts(base_posts, post)
        (self.root / 'src/data/posts.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.generator()
        paths = self._git('diff', '--name-only').splitlines()
        if forbidden_article_paths(paths) or 'src/data/posts.json' not in paths:
            raise JulesError('ARTICLE_DERIVATION_INVALID')
        with tempfile.TemporaryDirectory(prefix='kesher-article-index-') as directory:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(directory) / 'index'),
                       GIT_AUTHOR_NAME='Kesher Article Normalizer', GIT_AUTHOR_EMAIL='actions@users.noreply.github.com',
                       GIT_COMMITTER_NAME='Kesher Article Normalizer', GIT_COMMITTER_EMAIL='actions@users.noreply.github.com',
                       GIT_AUTHOR_DATE=prepared_at, GIT_COMMITTER_DATE=prepared_at)
            self._git('read-tree', main_sha, env=env)
            self._git('add', '-f', '-A', '--', *sorted(ARTICLE_PUBLICATION_PATHS), env=env)
            tree = self._git('write-tree', env=env)
            commit = self._git('commit-tree', tree, '-p', main_sha, '-m', f'Normalize Kesher article {slot} PR #{pr_number}', env=env)
        return {'new_head_sha': commit, 'tree_sha': tree}
