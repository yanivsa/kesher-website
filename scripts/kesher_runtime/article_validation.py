"""Trusted-main article validation, with independent exact-run CI observation.

The article candidate contributes data/image files only. It cannot supply the
workflow, generators, dependencies, tests or evaluator that certify it. The
controller reads real attempt-specific jobs; PR check names are not authority.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from scripts.kesher_article_contract import ARTICLE_PUBLICATION_PATHS
from scripts.kesher_article_normalizer import ArticleNormalizationError, extract_target_article, normalized_posts
from .article_normalize_worker import GitNormalization
from .github import GitHubError
from .identity import SlotIdentity, digest, require_sha
from .jules import JulesError
from .state import ClaimRejected, StateConflict, StateInvalid

WORKFLOW = 'kesher-article-validation.yml'
REQUIRED_STEPS = {
    'article-checks': ('Stage exact article data', 'Validate complete article and provenance',
                       'Run full repository quality gate'),
    'render-proof': ('Stage exact article data', 'Prove real rendering preserves source audio and signature'),
}


class GitArticleCandidate:
    """Read PR blobs as data; never check out executable files from its tree."""
    def __init__(self, root):
        self.git = GitNormalization(root)

    def blob(self, sha, path):
        require_sha(sha, 40)
        try:
            return subprocess.run(['git', 'show', sha + ':' + path], cwd=self.git.root,
                                  capture_output=True, check=True, timeout=30).stdout
        except (subprocess.SubprocessError, OSError):
            raise JulesError('CI_INPUT_INVALID') from None

    def inspect(self, main_sha, head_sha, slot):
        require_sha(main_sha, 40); require_sha(head_sha, 40); SlotIdentity(slot)
        if self.git._git('rev-parse', 'HEAD') != main_sha:
            raise JulesError('ARTICLE_TRUSTED_CHECKOUT_REQUIRED')
        self.git._git('fetch', '--no-tags', 'origin', head_sha)
        try:
            base = json.loads(self.blob(main_sha, 'src/data/posts.json'))
            head = json.loads(self.blob(head_sha, 'src/data/posts.json'))
            post = extract_target_article(base, head, slot)
            image = post.get('image', '')
            path = 'public' + image
            if (not image.startswith('/images/generated/blog/')
                    or any(part in {'', '.', '..'} for part in path.split('/'))
                    or head != normalized_posts(base, post)):
                raise JulesError('CI_INPUT_INVALID')
            paths = self.git._git('diff', '--name-only', '--no-renames', '-z', main_sha, head_sha).rstrip('\0').split('\0')
            if ('src/data/posts.json' not in paths or path not in paths
                    or set(paths) - (ARTICLE_PUBLICATION_PATHS | {path})):
                raise JulesError('CI_INPUT_INVALID')
            # Every staged path must be a regular, non-executable Git blob. A
            # symlink at any parent is also excluded by the exact changed set.
            tree = self.git._git('ls-tree', '-rz', head_sha, '--', *paths).rstrip('\0').split('\0')
            entries = {entry.split('\t', 1)[1]: entry.split('\t', 1)[0].split() for entry in tree}
            if set(entries) != set(paths) or any(value[:2] != ['100644', 'blob'] for value in entries.values()):
                raise JulesError('CI_INPUT_INVALID')
            if self.git._git('ls-tree', main_sha, '--', path):
                raise JulesError('CI_INPUT_INVALID')  # A new article cannot replace an old image.
            return {'base_sha': main_sha, 'head_sha': head_sha,
                    'tree_sha': self.git._git('rev-parse', head_sha + '^{tree}'),
                    'paths': sorted(paths), 'base_posts': base, 'head_posts': head,
                    'post': post, 'image_path': path, 'image_data': self.blob(head_sha, path)}
        except (ArticleNormalizationError, ValueError, TypeError, KeyError, AttributeError, IndexError):
            raise JulesError('CI_INPUT_INVALID') from None

    def stage(self, candidate):
        if self.git._git('status', '--porcelain', '--untracked-files=no'):
            raise JulesError('ARTICLE_TRUSTED_CHECKOUT_REQUIRED')
        self.git._git('checkout', candidate['head_sha'], '--', *candidate['paths'])
        if self.git._git('rev-parse', 'HEAD') != candidate['base_sha']:
            raise JulesError('ARTICLE_TRUSTED_CHECKOUT_REQUIRED')


def _current_pr(context, github):
    command = context._owned(context.store.load().state)
    number = command['inputs'].get('pr_number', '')
    if (not isinstance(context.target, SlotIdentity) or command['operation'] != 'validate_article'
            or not re.fullmatch(r'[1-9][0-9]*', number)):
        raise ClaimRejected('Exact article validation command required')
    repo = context.store.repo
    if github.request('GET', f'/repos/{repo}/git/ref/heads/main')['object']['sha'] != context.code_sha:
        raise JulesError('CODE_CHANGED')
    pr = github.request('GET', f'/repos/{repo}/pulls/{number}')
    if (str(pr.get('number')) != number or pr.get('state') != 'open' or pr.get('draft')
            or not str(pr.get('title', '')).startswith('Publish Kesher article:')
            or pr.get('base', {}).get('ref') != 'main' or pr['base'].get('sha') != context.code_sha
            or pr.get('head', {}).get('sha') != command['inputs'].get('pr_head_sha')
            or (pr['head'].get('repo') or {}).get('full_name') != repo
            or (pr['base'].get('repo') or {}).get('full_name') != repo):
        raise JulesError('ARTICLE_PR_CHANGED')
    require_sha(pr['head']['sha'], 40)
    if (command['inputs'].get('pr_body_sha256', digest(pr.get('body') or '')) != digest(pr.get('body') or '')
            or command['inputs'].get('validation_base_sha', context.code_sha) != context.code_sha):
        raise JulesError('CI_INPUT_CHANGED')
    return pr


def _candidate(context, github, git, *, require_saved):
    from .article_image_worker import image_receipt_matches
    pr = _current_pr(context, github)
    value = git.inspect(context.code_sha, pr['head']['sha'], context.target.slot)
    evidence = {key: value[key] for key in ('base_sha', 'head_sha', 'tree_sha')}
    evidence.update(pr_number=pr['number'], body_sha256=digest(pr.get('body') or ''),
                    article_sha256=digest(value['post']), image_sha256=hashlib.sha256(value['image_data']).hexdigest())
    state = context.store.load().state
    if require_saved and context._owned(state)['receipts'].get('article_candidate', {}).get('evidence') != evidence:
        raise JulesError('CI_INPUT_CHANGED')
    if not image_receipt_matches(state, context.target.slot, pr['number'], pr['head']['sha'],
                                 value['post'], value['image_data'], pr.get('body') or ''):
        raise JulesError('ARTICLE_IMAGE_INVALID')
    return pr, value, evidence


def prepare_validation(context, github, git):
    _, _, evidence = _candidate(context, github, git, require_saved=False)
    context.checkpoint('article_candidate', evidence, phase='STARTED')
    return evidence


def stage_validation(context, github, git):
    _, value, evidence = _candidate(context, github, git, require_saved=True)
    git.stage(value)
    return evidence


def validate_content(context, github, git):
    pr, value, evidence = _candidate(context, github, git, require_saved=True)
    path = Path(__file__).resolve().parents[2] / '.github/scripts/validate-article-pr.py'
    spec = importlib.util.spec_from_file_location('kesher_trusted_article_gate', path)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    base_prefix = f'https://raw.githubusercontent.com/{context.store.repo}/{context.code_sha}/'

    def image_loader(entry):
        if entry.get('filename') == value['image_path']:
            return value['image_data']
        url = entry.get('raw_url', '')
        if not url.startswith(base_prefix + 'public/images/'):
            raise JulesError('CI_INPUT_INVALID')
        return git.blob(context.code_sha, url.removeprefix(base_prefix))

    errors = gate.evaluate_content(pr, [{'filename': name} for name in value['paths']],
                                   value['base_posts'], value['head_posts'], image_loader)
    if errors:
        print(json.dumps({'article_content_errors': errors}, ensure_ascii=False), file=sys.stderr)
        raise JulesError('CI_CONTENT_INVALID')
    return evidence


def record_validation(context, github):
    pr = _current_pr(context, github)
    command = context._owned(context.store.load().state)
    saved = command['receipts'].get('article_candidate', {}).get('evidence') or {}
    if saved.get('body_sha256') != digest(pr.get('body') or ''):
        raise JulesError('CI_INPUT_CHANGED')
    result = inspect_validation(github, context.store.repo, command, require_terminal=False)
    context.checkpoint('execution_result', result,
                       phase='TECHNICALLY_VALIDATED' if result['status'] == 'verified' else 'STARTED')
    context.finish(failure=None if result['status'] == 'verified' else {
        'class': result.get('failure_class', 'CI_EVIDENCE_INVALID')})
    return result


def inspect_validation(github, repo, command, *, require_terminal=True):
    pending = {'status': 'pending'}
    failed = {'status': 'failed', 'failure_class': 'CI_FAILED'}
    invalid = {'status': 'failed', 'failure_class': 'CI_EVIDENCE_INVALID'}
    # An unavailable final API read is not evidence that source/tests are bad.
    # Retrying this read-only workflow is bounded by the controller's API rule.
    if command['outcome'] == 'failed' and (command.get('failure') or {}).get('class') == 'TRANSIENT_API':
        failed = {'status': 'failed', 'failure_class': 'TRANSIENT_API'}
    if command['operation'] != 'validate_article' or not command.get('owner'):
        return pending
    candidate = command['receipts'].get('article_candidate', {}).get('evidence')
    if not candidate:
        return pending if command['outcome'] == 'pending' else failed if failed['failure_class'] == 'TRANSIENT_API' else invalid
    try:
        number, attempt = command['owner']['run_id'].split('/')
        if (candidate['head_sha'] != command['inputs']['pr_head_sha']
                or str(candidate['pr_number']) != command['inputs']['pr_number']
                or candidate['base_sha'] != command['code_sha']):
            return invalid
        path = f'/repos/{repo}/actions/runs/{number}/attempts/{attempt}'
        run = github.request('GET', path)
        if (str(run.get('id')) != number or str(run.get('run_attempt')) != attempt
                or run.get('head_sha') != command['code_sha'] or run.get('head_branch') != 'main'
                or run.get('event') != 'workflow_dispatch'
                or run.get('path', '').split('@')[0] != '.github/workflows/' + WORKFLOW
                or run.get('display_title') != 'kesher-command:' + command['id']):
            return invalid
        if require_terminal and run.get('status') != 'completed':
            return pending
        if run.get('status') == 'completed' and run.get('conclusion') != 'success':
            return failed
        jobs = []
        total = None
        for page in range(1, 101):
            response = github.request('GET', path + f'/jobs?per_page=100&page={page}')
            rows = response.get('jobs')
            if not isinstance(rows, list) or type(response.get('total_count')) is not int:
                return invalid
            if total is None: total = response['total_count']
            if total != response['total_count']: return invalid
            jobs.extend(rows)
            if len(jobs) >= total: break
            if not rows: return invalid
        if len(jobs) != total or len({row.get('id') for row in jobs}) != len(jobs):
            return invalid
        verified = {}
        for name, required in REQUIRED_STEPS.items():
            matches = [job for job in jobs if job.get('name') == name]
            if len(matches) != 1: return invalid
            job = matches[0]
            if str(job.get('run_id')) != number or job.get('head_sha') != command['code_sha']:
                return invalid
            if job.get('status') != 'completed': return pending
            if job.get('conclusion') != 'success': return failed
            for step in required:
                matches = [row for row in job.get('steps', []) if row.get('name') == step]
                if len(matches) != 1 or matches[0].get('status') != 'completed' or matches[0].get('conclusion') != 'success':
                    return invalid
            verified[name] = job['id']
        return {'status': 'verified', 'evidence': {**candidate, 'command_id': command['id'],
                'run_id': command['owner']['run_id'], 'workflow': WORKFLOW, 'jobs': verified}}
    except (KeyError, ValueError, TypeError, AttributeError):
        return invalid
    except (GitHubError, OSError):
        return {'status': 'unknown', 'failure_class': 'TRANSIENT_API'}


def validation_for_pr(state, github, repo, slot, pr, main_sha):
    require_sha(main_sha, 40)
    matches = []
    for command in state['commands'].values():
        if (command['target'] != SlotIdentity(slot).to_dict() or command['operation'] != 'validate_article'
                or command['code_sha'] != main_sha
                or command['inputs'].get('pr_number') != str(pr['number'])
                or command['inputs'].get('pr_head_sha') != pr['head']['sha']
                or command['inputs'].get('pr_body_sha256', digest(pr.get('body') or '')) != digest(pr.get('body') or '')):
            continue
        candidate = command['receipts'].get('article_candidate', {}).get('evidence')
        if candidate and candidate.get('body_sha256') != digest(pr.get('body') or ''):
            continue
        matches.append(command)
    if not matches:
        return {'status': 'absent'}
    return inspect_validation(github, repo, max(matches, key=lambda row: row['ordinal']))


def main(argv=None):
    from .worker_entry import actions_admission
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'stage', 'content', 'record'))
    parser.add_argument('command_id')
    args = parser.parse_args(argv)
    context = None
    try:
        context = actions_admission(args.command_id, attach=True).context
        github = context.store.github
        if args.action == 'record':
            result = record_validation(context, github)
            return 0 if result['status'] == 'verified' else 1
        git = GitArticleCandidate(Path.cwd())
        if git.git._git('remote', 'get-url', 'origin').removesuffix('.git') != 'https://github.com/' + context.store.repo:
            raise StateInvalid('Unexpected production article remote')
        {'prepare': prepare_validation, 'stage': stage_validation, 'content': validate_content}[args.action](context, github, git)
        print('ARTICLE_VALIDATION:' + args.action)
        return 0
    except (JulesError, GitHubError, StateInvalid, StateConflict, OSError, ValueError) as exc:
        failure = exc.failure_class if isinstance(exc, JulesError) else 'TRANSIENT_API' if isinstance(exc, (GitHubError, OSError, StateConflict)) else 'CI_EVIDENCE_INVALID'
        # The data/test jobs have read-only tokens and never write durable state.
        if context is not None and args.action in {'prepare', 'record'}:
            try:
                context.finish(failure={'class': failure})
            except (GitHubError, StateInvalid, StateConflict):
                pass
        print('ARTICLE_VALIDATION_FAILED:' + failure, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
