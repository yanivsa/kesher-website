"""Read-only shadow entry point for explicit Master-owned KESHER command intents."""
from __future__ import annotations

import argparse
import json
import os
import sys

from .github import GitHub, GitHubError, GitHubStateStore
from .identity import identity_from_dict
from .master_intent import MasterIntent, plan_master_command
from .media_audit import ArchivedMediaAuditor
from .media_observer import YouTubeInventory
from .observe import RepositoryObserver
from .output_artifacts import download_actions_artifact
from .state import StateConflict, StateInvalid
from .worker_entry import REPOSITORY


def _inventory_reader(*, now: str):
    """Use real public inventory when credentials exist; otherwise fail closed as unknown."""
    try:
        from scripts import kesher_daily_pipeline as core
        token = core.youtube_access_token()
        return YouTubeInventory(
            lambda resource, params: core.youtube_get(resource, token, params)
        ).read(now=now)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        raise RuntimeError('MASTER_SHADOW_MEDIA_INVENTORY_UNAVAILABLE') from exc


def _observer(github, token: str, *, now: str) -> RepositoryObserver:
    observer = RepositoryObserver(
        github,
        REPOSITORY,
        inventory_reader=_inventory_reader,
        auditor=ArchivedMediaAuditor(
            github,
            REPOSITORY,
            lambda artifact_id, destination: download_actions_artifact(
                REPOSITORY, token, artifact_id, destination),
        ),
        clock=lambda: now,
    )
    if os.environ.get('CLOUDFLARE_ACCOUNT_ID') and os.environ.get('CLOUDFLARE_API_TOKEN'):
        from .cloudflare_pages import PagesClient
        from .deployment_observer import read_deployment
        pages = PagesClient(os.environ['CLOUDFLARE_ACCOUNT_ID'], os.environ['CLOUDFLARE_API_TOKEN'])
        observer.deployment_observer = lambda state, sha: read_deployment(
            state, pages, github, REPOSITORY, sha)
    return observer


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
        if raw['inputs'] != {}:
            raise StateInvalid('MASTER_INTENT_INPUTS_FORBIDDEN')
        intent = MasterIntent(
            request_id=raw['request_id'],
            expected_main_sha=raw['expected_main_sha'],
            expected_state_revision=raw['expected_state_revision'],
            target=identity_from_dict(raw['target']),
            operation=raw['operation'],
            inputs=raw['inputs'],
        )
        workflow_request_id = os.environ.get('MASTER_REQUEST_ID')
        if workflow_request_id and workflow_request_id != intent.request_id:
            raise StateInvalid('MASTER_INTENT_REQUEST_ID_MISMATCH')
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
        now = os.environ['MASTER_INTENT_NOW']
        github = GitHub(token)
        store = GitHubStateStore(github, REPOSITORY)
        loaded = store.load()
        observation = _observer(github, token, now=now).read(loaded.state)
        main_sha = observation.value['main_sha']
        proposed, command_id = plan_master_command(
            loaded.state,
            intent,
            main_sha=main_sha,
            observation=observation,
            now=now,
        )
        command = proposed['commands'][command_id]
        print(json.dumps({
            'mode': 'shadow',
            'request_id': intent.request_id,
            'observed_state_revision': loaded.state['revision'],
            'observed_main_sha': main_sha,
            'observation_at': observation.value['observed_at'],
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
