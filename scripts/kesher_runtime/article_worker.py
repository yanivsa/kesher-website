"""Command-bound article session creation and quiescence before PR mutation.

One invocation observes once and exits. The canonical controller owns backoff,
semantic stall detection and repair. A visible PR is not permission to mutate a
branch while its Jules session is still running.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from scripts.jules_article_runner_core import build_prompt, load_policy
from scripts.jules_article_runner_v4 import SEARCH_FIRST_CONTRACT, EVIDENCE_CONTRACT
from .article_verification import GitHubArticleReader
from .github import GitHubError
from .identity import SlotIdentity, digest, require_sha
from .jules import Jules, JulesError, acquire_session, session_name
from .state import ClaimRejected, StateConflict, StateInvalid
from .worker_entry import actions_admission

REPOSITORY = 'yanivsa/kesher-website'
SOURCE_CONTEXT = {'source': 'sources/github/' + REPOSITORY, 'githubRepoContext': {'startingBranch': 'main'}}
IMAGE_CONTRACT = '''
--- TRUSTED IMAGE OWNERSHIP ---
Jules owns ARTICLE TEXT ONLY. Do not call image providers or download, generate,
inspect, add, copy, modify or delete image binaries. The new article must omit
image and imageAlt. Do not invent image provenance in the PR body. Trusted
repository automation attaches a verified image to this same PR after this
session has completed. This overrides image-generation instructions in the
article policy, and does not waive the image requirement for publication.
--- END TRUSTED IMAGE OWNERSHIP ---
'''


def article_request(slot: str, policy: str) -> dict:
    SlotIdentity(slot)
    prompt = build_prompt(slot, policy).replace(
        'or a currently open `Publish Kesher article:` PR already modifies `src/data/posts.json`',
        f'or a currently open `Publish Kesher article:` PR already contains an article with `date == {slot}`')
    # Never call the legacy V3 builder: its test-mode environment can bypass
    # same-date duplicate protection. Only immutable policy text is reused.
    return {'title': 'Kesher article ' + slot, 'prompt': prompt + IMAGE_CONTRACT + SEARCH_FIRST_CONTRACT + EVIDENCE_CONTRACT,
            'sourceContext': SOURCE_CONTEXT, 'requirePlanApproval': False, 'automationMode': 'AUTO_CREATE_PR'}


class ArticleRepository:
    def __init__(self, github, repo=REPOSITORY):
        if repo != REPOSITORY:
            raise ValueError('Unsupported article repository')
        self.github, self.repo = github, repo
        self.reader = GitHubArticleReader(github, repo)

    def pages(self, path):
        result = []
        for page in range(1, 101):
            rows = self.github.request('GET', f'/repos/{self.repo}/{path}&per_page=100&page={page}')
            if not isinstance(rows, list):
                raise StateInvalid('Invalid article PR inventory')
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise StateInvalid('Incomplete article PR inventory')

    def snapshot(self, slot: str) -> dict:
        SlotIdentity(slot)
        main = self.github.request('GET', f'/repos/{self.repo}/git/ref/heads/main')['object']['sha']
        require_sha(main, 40)
        posts = json.loads(self.reader.content(main, 'src/data/posts.json'))
        published = [post for post in posts if post.get('date') == slot]
        ids = {post['id'] for post in posts}
        prs = []
        for pr in self.pages('pulls?state=open'):
            if not str(pr.get('title', '')).startswith('Publish Kesher article:'):
                continue
            paths = [row['filename'] for row in self.pages(f'pulls/{pr["number"]}/files?')]
            if 'src/data/posts.json' not in paths:
                continue
            head = pr['head']['sha']; require_sha(head, 40)
            head_posts = json.loads(self.reader.content(head, 'src/data/posts.json'))
            candidates = [post for post in head_posts if post.get('date') == slot and post.get('id') not in ids]
            if not candidates:
                continue
            if (len(candidates) != 1 or pr.get('base', {}).get('ref') != 'main'
                    or (pr['head'].get('repo') or {}).get('full_name') != self.repo):
                raise JulesError('ARTICLE_PR_IDENTITY_MISMATCH')
            prs.append({'number': pr['number'], 'head_sha': head, 'slot': slot})
        if self.github.request('GET', f'/repos/{self.repo}/git/ref/heads/main')['object']['sha'] != main:
            raise StateConflict('Main changed during article inventory')
        return {'main_sha': main, 'published': published, 'prs': prs}


def _result(context, result: dict) -> dict:
    context.checkpoint('execution_result', result, phase='STARTED' if result['status'] == 'waiting' else 'OUTPUT_CREATED')
    return result


def _waiting(context, name: str | None, *, failure_class='JULES_PENDING') -> dict:
    return _result(context, {'status': 'waiting', 'failure_class': failure_class, 'session_name': name})


def _ready(context, pr: dict, names: list[str]) -> dict:
    context.checkpoint('article_pr_settled', {**pr, 'sessions': sorted(names)}, phase='OUTPUT_CREATED')
    return _result(context, {'status': 'pr_ready', 'pr_number': pr['number'], 'pr_head_sha': pr['head_sha']})


def _outputs(row: dict) -> list[int]:
    numbers = []
    for output in row.get('outputs') or []:
        pr = output.get('pullRequest')
        if not pr:
            continue
        match = re.fullmatch(r'https://github\.com/yanivsa/kesher-website/pull/([1-9][0-9]*)', str(pr.get('url', '')))
        if not match:
            raise JulesError('JULES_OUTPUT_IDENTITY_MISMATCH')
        numbers.append(int(match[1]))
    if len(set(numbers)) > 1:
        raise JulesError('DUPLICATE_PR')
    return sorted(set(numbers))


def assert_article_quiescent(context, api, pr: dict) -> list[str]:
    """A cached settling receipt never replaces the pre-mutation live read."""
    state = context.store.load().state
    proofs = [receipt['evidence'] for command in state['commands'].values()
              if command['target'] == context.target.to_dict() and command['outcome'] == 'succeeded'
              for name, receipt in command['receipts'].items() if name == 'article_pr_settled'
              and receipt['evidence'].get('number') == pr['number']
              and receipt['evidence'].get('head_sha') == pr['head']['sha']]
    if not proofs:
        raise JulesError('JULES_PENDING')
    names = {name for proof in proofs for name in proof['sessions']}
    names.update(session_name(row) for row in api.sessions()
                 if row.get('title') == 'Kesher article ' + context.target.slot)
    for name in sorted(names):
        row = api.get(name)
        if (session_name(row) != name or row.get('sourceContext') != SOURCE_CONTEXT
                or row.get('title') != 'Kesher article ' + context.target.slot):
            raise JulesError('JULES_IDENTITY_MISMATCH')
        if row.get('state') not in {'COMPLETED', 'FAILED'}:
            raise JulesError('JULES_PENDING')
    context.checkpoint('article_quiescence', {'number': pr['number'], 'head_sha': pr['head']['sha'],
                                            'sessions': sorted(names)}, phase='STARTED')
    return sorted(names)


def run_normalization(context, api, repository) -> dict:
    from .article_normalize_worker import GitNormalization, normalize_article
    command = context._owned(context.store.load().state)
    number = command['inputs'].get('pr_number', '')
    if not re.fullmatch(r'[1-9][0-9]*', number):
        raise StateInvalid('Normalization needs an exact PR number')
    github = repository.github
    main = github.request('GET', f'/repos/{repository.repo}/git/ref/heads/main')['object']['sha']
    if main != context.code_sha:
        raise JulesError('CODE_CHANGED')
    pr = github.request('GET', f'/repos/{repository.repo}/pulls/{number}')
    branch = GitNormalization(Path.cwd())
    if branch._git('remote', 'get-url', 'origin').removesuffix('.git') != 'https://github.com/' + REPOSITORY:
        raise StateInvalid('Unexpected production article remote')
    result = normalize_article(context, pr, branch,
        prove_quiescent=lambda current: assert_article_quiescent(context, api, current))
    return _result(context, {'status': 'normalized', **result})


def run_article(context, api, repository, *, policy: str) -> dict:
    state = context.store.load().state
    command = context._owned(state)
    if not isinstance(context.target, SlotIdentity) or command['operation'] not in {'create_article', 'settle_article'}:
        raise ClaimRejected('Unsupported article worker operation')
    snapshot = repository.snapshot(context.target.slot)
    if snapshot['main_sha'] != context.code_sha:
        raise JulesError('CODE_CHANGED')
    if len(snapshot['published']) > 1:
        raise JulesError('SOURCE_AMBIGUOUS')
    if snapshot['published']:
        return _result(context, {'status': 'article_merged', 'main_sha': snapshot['main_sha'],
                                'post_sha256': digest(snapshot['published'][0])})
    if len(snapshot['prs']) > 1:
        raise JulesError('DUPLICATE_PR')
    pr = snapshot['prs'][0] if snapshot['prs'] else None
    if pr:
        expected = command['inputs']
        if expected and (expected.get('pr_number') != str(pr['number']) or expected.get('pr_head_sha') != pr['head_sha']):
            raise JulesError('ARTICLE_PR_CHANGED')
        context.checkpoint('article_progress', pr, phase='MEANINGFUL_PROGRESS')
    owned = any(name.startswith('jules_create_') for row in state['commands'].values()
                if row['target'] == context.target.to_dict() for name in row['effects'])
    if not owned and pr:
        # An existing PR may predate canonical ownership. This is read-only
        # quiescence evidence, not a fabricated historical creation receipt.
        names = []
        for listed in api.sessions():
            if listed.get('title') != 'Kesher article ' + context.target.slot:
                continue
            row = api.get(session_name(listed))
            if row.get('sourceContext') != SOURCE_CONTEXT:
                raise JulesError('JULES_IDENTITY_MISMATCH')
            names.append(session_name(row))
            if row.get('state') not in {'COMPLETED', 'FAILED'}:
                return _waiting(context, row['name'])
        return _ready(context, pr, names)
    if not owned and command['operation'] == 'settle_article':
        raise JulesError('ARTICLE_PR_MISSING')
    row = acquire_session(context, api, article_request(context.target.slot, policy))
    name = session_name(row)
    state_name = row.get('state')
    if state_name == 'FAILED':
        raise JulesError('JULES_SESSION_FAILED')
    if state_name in {'AWAITING_USER_FEEDBACK', 'AWAITING_PLAN_APPROVAL', 'PAUSED'}:
        raise JulesError('JULES_STALLED')
    numbers = _outputs(row)
    if pr and numbers and numbers != [pr['number']]:
        raise JulesError('JULES_OUTPUT_IDENTITY_MISMATCH')
    if state_name != 'COMPLETED':
        if state_name not in {'QUEUED', 'PLANNING', 'IN_PROGRESS'}:
            raise JulesError('JULES_STATE_UNKNOWN')
        return _waiting(context, name)
    if not numbers:
        raise JulesError('JULES_NO_OUTPUT')
    if pr is None:
        return _waiting(context, name, failure_class='JULES_OUTPUT_PENDING')
    return _ready(context, pr, [name])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command_id')
    args = parser.parse_args(argv)
    context = None
    try:
        admission = actions_admission(args.command_id, attach=True)
        context = admission.context
        api = Jules(os.environ.get('JULES_API_KEY', ''))
        repository = ArticleRepository(context.store.github)
        if admission.command['operation'] == 'normalize_article':
            result = run_normalization(context, api, repository)
        else:
            result = run_article(context, api, repository, policy=load_policy())
        context.finish()
        print('ARTICLE_COMMAND_RESULT:' + result['status'])
        return 0
    except (JulesError, GitHubError, StateInvalid, StateConflict, OSError, ValueError) as exc:
        failure = exc.failure_class if isinstance(exc, JulesError) else 'TRANSIENT_API' if isinstance(exc, (GitHubError, OSError, StateConflict)) else 'WORKER_FAILED'
        if context is not None:
            try:
                context.finish(failure={'class': failure})
            except (GitHubError, StateInvalid, StateConflict):
                pass  # Controller reconciles the exact run; never report success.
        print('ARTICLE_COMMAND_FAILED:' + failure, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
