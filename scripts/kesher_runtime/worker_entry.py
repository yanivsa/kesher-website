"""Actions entry point for command-bound workers, before provider credentials.

Run with ``python3 -m scripts.kesher_runtime.worker_entry claim COMMAND_ID``.
Workflow inputs never choose a slug, media kind, source hash, or code revision.
Those values come from the durable command, checked against the actual checkout
and trusted workflow definition. Later steps attach to the same run/attempt.
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .github import GitHub, GitHubError, GitHubStateStore
from .identity import identity_from_dict, require_sha
from .outbox import workflow_for
from .state import ClaimRejected, StateInvalid
from .worker import WorkerContext

REPOSITORY = 'yanivsa/kesher-website'


@dataclass(frozen=True)
class Admission:
    execute: bool
    command: dict
    context: WorkerContext


def admit_worker(store: GitHubStateStore, command_id: str, env: Mapping[str, str], *,
                 checkout_sha: str, trusted_main_sha: str, attach: bool = False,
                 now: Callable[[], str] | None = None, authority=None) -> Admission:
    from .authority import require_live
    command = require_live(store, observe=authority)['commands'].get(command_id)
    if command is None:
        raise ClaimRejected('Worker requires an existing canonical command')
    try:
        require_sha(checkout_sha, 40)
        require_sha(trusted_main_sha, 40)
        workflow = workflow_for(command)
        target = identity_from_dict(command['target'])
    except (ValueError, KeyError) as exc:
        raise ClaimRejected('Invalid worker identity or code revision') from exc
    expected_ref = f'{store.repo}/.github/workflows/{workflow}@refs/heads/main'
    if (env.get('GITHUB_REPOSITORY') != store.repo
            or env.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
            or env.get('GITHUB_REF') != 'refs/heads/main'
            or env.get('GITHUB_WORKFLOW_REF') != expected_ref
            or env.get('GITHUB_WORKFLOW_SHA') != checkout_sha
            or command['code_sha'] != checkout_sha
            or (not attach and trusted_main_sha != checkout_sha)):
        raise ClaimRejected('Untrusted event, workflow definition, checkout, or stale command code')
    run_id, attempt = env.get('GITHUB_RUN_ID', ''), env.get('GITHUB_RUN_ATTEMPT', '')
    if not re.fullmatch(r'[1-9][0-9]*', run_id) or not re.fullmatch(r'[1-9][0-9]*', attempt):
        raise ClaimRejected('Worker requires an exact GitHub run and attempt')
    context = WorkerContext(store, command_id, f'{run_id}/{attempt}', target, code_sha=checkout_sha, now=now)
    if attach:
        context.attach()
        execute = True
    else:
        execute = context.claim().execute
    return Admission(execute, copy.deepcopy(command), context)


def write_outputs(path: Path, admission: Admission) -> None:
    # Only typed identity fields are exposed. Arbitrary persisted command inputs
    # are not interpolated into shell code or Actions output directives.
    target = admission.command['target']
    fields = {'execute': str(admission.execute).lower(), 'command_id': admission.command['id'],
              'operation': admission.command['operation'], 'target_key': admission.context.target.key,
              **{key: target.get(key, '') for key in ('slot', 'slug', 'content_sha256', 'kind')}}
    if any(not isinstance(value, str) or '\n' in value or '\r' in value for value in fields.values()):
        raise StateInvalid('Invalid Actions output value')
    with path.open('a', encoding='utf-8') as stream:
        stream.write(''.join(f'{key}={value}\n' for key, value in fields.items()))


def actions_admission(command_id: str, *, attach: bool = False) -> Admission:
    if os.environ.get('GITHUB_REPOSITORY') != REPOSITORY:
        raise ClaimRejected('Canonical production worker is restricted to its repository')
    checkout = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True, capture_output=True,
                              text=True, timeout=15).stdout.strip()
    github = GitHub(os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', ''))
    main = github.request('GET', f'/repos/{REPOSITORY}/git/ref/heads/main')['object']['sha']
    return admit_worker(GitHubStateStore(github, REPOSITORY), command_id, os.environ,
                        checkout_sha=checkout, trusted_main_sha=main, attach=attach)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('claim', 'finish'))
    parser.add_argument('command_id')
    parser.add_argument('--failure-class')
    args = parser.parse_args(argv)
    try:
        admission = actions_admission(args.command_id, attach=args.action != 'claim')
        if args.action == 'claim':
            output = os.environ.get('GITHUB_OUTPUT')
            if output:
                write_outputs(Path(output), admission)
            print('WORKER_CLAIM_ACCEPTED' if admission.execute else 'WORKER_ALREADY_CLAIMED')
        else:
            failure = {'class': args.failure_class} if args.failure_class else None
            admission.context.finish(failure=failure)
            print('WORKER_RESULT_RECORDED')
        return 0
    except (ClaimRejected, StateInvalid, GitHubError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        # External API bodies and environment values must not become log output.
        print(f'WORKER_ADMISSION_FAILED:{type(exc).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
