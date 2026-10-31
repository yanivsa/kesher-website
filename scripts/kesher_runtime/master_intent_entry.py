"""Shadow entry point for explicit Master-owned KESHER command intents."""
from __future__ import annotations

import argparse
import json
import os
import sys

from .github import GitHub, GitHubError, GitHubStateStore
from .identity import identity_from_dict
from .master_intent import MasterIntent, plan_master_command
from .state import StateConflict, StateInvalid
from .worker_entry import REPOSITORY


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request-json', required=True)
    parser.add_argument('--mode', choices=('shadow',), default='shadow')
    args = parser.parse_args(argv)
    try:
        raw = json.loads(args.request_json)
        required = {'request_id', 'expected_main_sha', 'expected_state_revision', 'target', 'operation', 'inputs'}
        if not isinstance(raw, dict) or set(raw) != required:
            raise StateInvalid('MASTER_INTENT_REQUEST_SHAPE_INVALID')
        intent = MasterIntent(
            request_id=raw['request_id'],
            expected_main_sha=raw['expected_main_sha'],
            expected_state_revision=raw['expected_state_revision'],
            target=identity_from_dict(raw['target']),
            operation=raw['operation'],
            inputs=raw['inputs'],
        )
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
        github = GitHub(token)
        store = GitHubStateStore(github, REPOSITORY)
        loaded = store.load()
        main_sha = github.request('GET', f'/repos/{REPOSITORY}/git/ref/heads/main')['object']['sha']
        proposed, command_id = plan_master_command(loaded.state, intent, main_sha=main_sha,
                                                   now=os.environ['MASTER_INTENT_NOW'])
        command = proposed['commands'][command_id]
        print(json.dumps({
            'mode': 'shadow',
            'request_id': intent.request_id,
            'observed_state_revision': loaded.state['revision'],
            'observed_main_sha': main_sha,
            'would_plan': {key: command[key] for key in ('id', 'target', 'operation', 'inputs', 'code_sha')},
            'state_written': False,
            'dispatched': False,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except (KeyError, TypeError, ValueError, GitHubError, StateInvalid, StateConflict, json.JSONDecodeError) as exc:
        print(f'MASTER_INTENT_SHADOW_FAILED:{type(exc).__name__}:{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
