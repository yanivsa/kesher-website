"""Publish the exact validated article tree through an atomic two-ref CAS.

This route is for an unprotected main with no applicable branch rules. It never
interprets an indirect PR merge as proof of policy compliance. PR/body evidence
is frozen by trusted validation; the Git transaction cannot lock PR metadata.
A merged commit is only historical inclusion, never independent public delivery.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

from .article_validation import GitArticleCandidate, validation_for_pr
from .github import GitHubError
from .identity import SlotIdentity, digest, require_sha
from .jules import JulesError
from .state import ClaimRejected, StateConflict, StateInvalid

WORKFLOW = 'kesher-article-merge.yml'
UPDATE_REFS = '''mutation($input: UpdateRefsInput!) {
  updateRefs(input: $input) { clientMutationId }
}'''


def _inputs(context):
    command = context._owned(context.store.load().state)
    inputs = command['inputs']
    if (not isinstance(context.target, SlotIdentity) or command['operation'] != 'merge_article'
            or not re.fullmatch(r'[1-9][0-9]*', inputs.get('pr_number', ''))):
        raise ClaimRejected('Exact article merge command required')
    require_sha(inputs['pr_head_sha'], 40)
    require_sha(inputs['pr_body_sha256'])
    if inputs.get('validation_base_sha') != context.code_sha:
        raise JulesError('CI_INPUT_CHANGED')
    return inputs


def _pr(github, repo, inputs):
    return github.request('GET', f'/repos/{repo}/pulls/{inputs["pr_number"]}')


def _main(github, repo):
    sha = github.request('GET', f'/repos/{repo}/git/ref/heads/main')['object']['sha']
    require_sha(sha, 40)
    return sha


def _check_pr(pr, repo, inputs, main_sha):
    if (str(pr.get('number')) != inputs['pr_number'] or pr.get('state') != 'open' or pr.get('draft')
            or pr.get('merged') or not str(pr.get('title', '')).startswith('Publish Kesher article:')
            or pr.get('head', {}).get('sha') != inputs['pr_head_sha']
            or pr.get('base', {}).get('sha') != main_sha or pr['base'].get('ref') != 'main'
            or (pr['head'].get('repo') or {}).get('full_name') != repo
            or (pr['base'].get('repo') or {}).get('full_name') != repo):
        raise JulesError('ARTICLE_PR_CHANGED')
    if digest(pr.get('body') or '') != inputs['pr_body_sha256']:
        raise JulesError('CI_INPUT_CHANGED')
    # A ref is data in the GraphQL request, never a shell fragment. Still reject
    # ambiguous/non-branch names and main itself before constructing the fence.
    branch = pr['head'].get('ref', '')
    if (not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]*', branch) or branch == 'main'
            or '..' in branch or '//' in branch or branch.endswith(('/', '.', '.lock'))):
        raise JulesError('ARTICLE_PR_CHANGED')
    return branch


def _policy(github, repo, main_sha):
    repository = github.request('GET', f'/repos/{repo}')
    branch = github.request('GET', f'/repos/{repo}/branches/main')
    rules = github.request('GET', f'/repos/{repo}/rules/branches/main?per_page=100&page=1')
    # Ref publication does not enforce required-PR review semantics. Explicitly
    # refuse such policy, including unknown/malformed policy responses. The
    # workflow uses its installation token, never an administrator PAT fallback.
    if (repository.get('archived') is not False or repository.get('default_branch') != 'main'
            or not isinstance(repository.get('node_id'), str) or not repository['node_id']
            or branch.get('name') != 'main' or branch.get('protected') is not False
            or branch.get('commit', {}).get('sha') != main_sha or rules != []):
        raise JulesError('MERGE_POLICY_UNSUPPORTED')
    return repository['node_id']


def _effect_name(request):
    return 'article_merge_' + digest(request)[:32]


def _prior(context, inputs):
    # Different validated bodies/heads are distinct intents. Atomic ref CAS,
    # rather than a global creation fence, makes their delayed requests safe.
    # Prefer this worker's request, then the newest matching immutable inputs.
    commands = sorted(context.store.load().state['commands'].values(),
                      key=lambda row: (row['id'] == context.command_id, row['ordinal']), reverse=True)
    for command in commands:
        if command['target'] != context.target.to_dict():
            continue
        for name, effect in command['effects'].items():
            request = effect['request']
            if (request.get('validation') and name == _effect_name(request)
                    and request.get('pr_number') == inputs['pr_number']
                    and request.get('head_sha') == inputs['pr_head_sha']
                    and request.get('base_sha') == inputs['validation_base_sha']
                    and request.get('body_sha256') == inputs['pr_body_sha256']):
                return request
    return None


def _observed_merge(github, repo, request, *, main_sha=None):
    main = main_sha or _main(github, repo)
    require_sha(main, 40)
    if main == request['base_sha']:
        return None
    if main != request['head_sha']:
        compare_path = f'/repos/{repo}/compare/{request["head_sha"]}...{main}'
        compare = github.request('GET', compare_path)
        if (not isinstance(compare, dict)
                or compare.get('url') != 'https://api.github.com' + compare_path
                or compare.get('base_commit', {}).get('sha') != request['head_sha']
                or compare.get('status') not in {'ahead', 'behind', 'diverged'}
                or type(compare.get('ahead_by')) is not int or compare['ahead_by'] < 0
                or type(compare.get('behind_by')) is not int or compare['behind_by'] < 0):
            raise JulesError('MERGE_OBSERVATION_INVALID')
        merge_base = compare.get('merge_base_commit', {}).get('sha')
        try:
            require_sha(merge_base, 40)
        except ValueError:
            raise JulesError('MERGE_OBSERVATION_INVALID') from None
        status, ahead, behind = compare['status'], compare['ahead_by'], compare['behind_by']
        if status == 'ahead':
            if not (ahead > 0 and behind == 0 and merge_base == request['head_sha']):
                raise JulesError('MERGE_OBSERVATION_INVALID')
        elif ((status == 'behind' and ahead == 0 and behind > 0 and merge_base == main)
              or (status == 'diverged' and ahead > 0 and behind > 0
                  and merge_base not in {main, request['head_sha']})):
            raise JulesError('CODE_CHANGED')
        else:
            raise JulesError('MERGE_OBSERVATION_INVALID')
    pr = _pr(github, repo, request)
    if (not isinstance(pr, dict) or str(pr.get('number')) != request['pr_number']
            or pr.get('base', {}).get('ref') != 'main'
            or (pr['base'].get('repo') or {}).get('full_name') != repo
            or (pr.get('head', {}).get('repo') or {}).get('full_name') != repo
            or pr['head'].get('ref') != request['branch'] or pr['head'].get('sha') != request['head_sha']
            or type(pr.get('merged')) is not bool or pr.get('state') not in {'open', 'closed'}):
        raise JulesError('MERGE_OBSERVATION_INVALID')
    if (pr.get('merged') is not True or pr.get('state') != 'closed'
            or pr.get('merge_commit_sha') != request['head_sha']):
        # Main advanced. A lagging indirect-merge record cannot authorize a
        # second ref update, even if a subsequent command retries observation.
        raise JulesError('MERGE_RECORD_PENDING')
    return {'status': 'merged', 'pr_number': int(request['pr_number']),
            'merge_sha': request['head_sha'], 'tree_sha': request['tree_sha'],
            'base_sha': request['base_sha'], 'validation': request['validation']}


def _receipt(context, request, result):
    context.complete_effect(_effect_name(request), result)
    context.checkpoint('execution_result', result, phase='OUTPUT_CREATED')
    return result


def merge_article(context, github, git, *, prove_quiescent):
    inputs = _inputs(context)
    repo = context.store.repo
    saved = _prior(context, inputs)
    if saved:
        if _effect_name(saved) not in context._owned(context.store.load().state)['effects']:
            context.begin_effect(_effect_name(saved), saved)
        result = _observed_merge(github, repo, saved)
        if result:
            return _receipt(context, saved, result)
    if _main(github, repo) != context.code_sha:
        raise JulesError('CODE_CHANGED')
    pr = _pr(github, repo, inputs)
    branch = _check_pr(pr, repo, inputs, context.code_sha)
    candidate = git.inspect(context.code_sha, inputs['pr_head_sha'], context.target.slot)
    validation = validation_for_pr(context.store.load().state, github, repo, context.target.slot, pr, context.code_sha)
    if validation['status'] != 'verified':
        raise JulesError(validation.get('failure_class', 'CI_EVIDENCE_INVALID'))
    evidence = validation['evidence']
    expected = {key: candidate[key] for key in ('base_sha', 'head_sha', 'tree_sha')}
    expected.update(pr_number=int(inputs['pr_number']), body_sha256=inputs['pr_body_sha256'],
                    article_sha256=digest(candidate['post']), image_sha256=hashlib.sha256(candidate['image_data']).hexdigest())
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise JulesError('CI_INPUT_CHANGED')
    repository_id = _policy(github, repo, context.code_sha)
    request = {'pr_number': inputs['pr_number'], 'branch': branch, 'repository_id': repository_id,
               'base_sha': context.code_sha, 'head_sha': inputs['pr_head_sha'],
               'tree_sha': candidate['tree_sha'], 'body_sha256': inputs['pr_body_sha256'],
               'validation': evidence}
    prove_quiescent(pr)
    context.begin_effect(_effect_name(request), request)
    prove_quiescent(pr)
    # Narrow mutable PR/policy races with fresh reads after expensive work and
    # the durable intent. Only the two Git OIDs are atomic preconditions.
    if _check_pr(_pr(github, repo, inputs), repo, inputs, context.code_sha) != branch:
        raise JulesError('ARTICLE_PR_CHANGED')
    if _policy(github, repo, context.code_sha) != repository_id:
        raise JulesError('MERGE_POLICY_UNSUPPORTED')
    # CAS repetition of this identical desired result cannot duplicate a merge:
    # at most one transaction can match the old main. Persist a finite send
    # budget across crashes and recovery commands before each single request.
    cas = {key: request[key] for key in ('repository_id', 'base_sha', 'head_sha', 'branch')}
    cas_key = digest(cas)
    for attempt in range(1, 4):
        if context.begin_effect(f'merge_send_{cas_key[:24]}_{attempt}', cas).execute:
            break
    else:
        raise JulesError('MERGE_ATTEMPTS_EXHAUSTED')
    payload = {'query': UPDATE_REFS, 'variables': {'input': {
        'repositoryId': repository_id, 'clientMutationId': digest(request),
        'refUpdates': [
            {'name': 'refs/heads/main', 'beforeOid': request['base_sha'], 'afterOid': request['head_sha'], 'force': False},
            {'name': 'refs/heads/' + branch, 'beforeOid': request['head_sha'], 'afterOid': request['head_sha'], 'force': False},
        ]}}}
    uncertain = False
    rejected = False
    try:
        response = github.request('POST', '/graphql', payload)
        envelope = response if isinstance(response, dict) else {}
        rejected = bool(envelope.get('errors'))
        data = envelope.get('data')
        updated = data.get('updateRefs') if isinstance(data, dict) else None
        uncertain = not isinstance(updated, dict) or updated.get('clientMutationId') != digest(request)
    except GitHubError as exc:
        uncertain, rejected = exc.uncertain, not exc.uncertain
    result = _observed_merge(github, repo, request)
    if result:
        return _receipt(context, request, result)
    # A failed compare must never overwrite a newly changed PR ref.
    _check_pr(_pr(github, repo, inputs), repo, inputs, context.code_sha)
    raise JulesError('TRANSIENT_API' if uncertain else 'MERGE_REJECTED' if rejected else 'MERGE_RECORD_PENDING')


def main(argv=None):
    from .article_quiescence import assert_article_quiescent
    from .jules import Jules
    from .worker_entry import actions_admission
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command_id')
    args = parser.parse_args(argv)
    context = None
    try:
        context = actions_admission(args.command_id, attach=True).context
        git = GitArticleCandidate(Path.cwd())
        if git.git._git('remote', 'get-url', 'origin').removesuffix('.git') != 'https://github.com/' + context.store.repo:
            raise StateInvalid('Unexpected production article remote')
        api = Jules(os.environ.get('JULES_API_KEY', ''))
        result = merge_article(context, context.store.github, git,
                               prove_quiescent=lambda pr: assert_article_quiescent(context, api, pr))
        context.finish()
        print('ARTICLE_MERGE:' + result['status'])
        return 0
    except (JulesError, GitHubError, StateInvalid, StateConflict, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        failure = exc.failure_class if isinstance(exc, JulesError) else 'TRANSIENT_API' if isinstance(exc, (GitHubError, OSError, StateConflict)) else 'MERGE_EVIDENCE_INVALID'
        if context is not None:
            try:
                context.finish(failure={'class': failure})
            except (GitHubError, StateInvalid, StateConflict):
                pass
        print('ARTICLE_MERGE_FAILED:' + failure, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
