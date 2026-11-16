"""Explicit Master intent entry. Shadow is read-only; live is authority-fenced."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from .github import GitHub, GitHubError, GitHubStateStore
from .identity import identity_from_dict
from .master_intent import MasterIntent, plan_master_command
from .controller_entry import deliver as deliver_command
from .authority import require_live
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
    parser.add_argument('--mode', choices=('shadow', 'live'), default='shadow')
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
        if args.mode == 'live':
            expected_workflow = (REPOSITORY +
                '/.github/workflows/kesher-content-controller.yml@refs/heads/main')
            if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY
                    or os.environ.get('GITHUB_REF') != 'refs/heads/main'
                    or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
                    or os.environ.get('GITHUB_WORKFLOW_REF') != expected_workflow
                    or not workflow_request_id
                    or not os.environ.get('KESHER_CUTOVER_GATEWAY_URL')):
                raise StateInvalid('MASTER_LIVE_TRUSTED_INVOCATION_REQUIRED')
            checkout_sha = subprocess.run(
                ['git', 'rev-parse', 'HEAD'], check=True, capture_output=True,
                text=True, timeout=15).stdout.strip()
            main_ref_sha = github.request(
                'GET', f'/repos/{REPOSITORY}/git/ref/heads/main')['object']['sha']
            if checkout_sha != main_ref_sha:
                raise StateInvalid('MASTER_LIVE_STALE_CHECKOUT')
            require_live(store)
        loaded = store.load()
        observer = _observer(github, token, now=now)
        observation = observer.read(loaded.state)
        main_sha = observation.value['main_sha']
        proposed, command_id = plan_master_command(
            loaded.state,
            intent,
            main_sha=main_sha,
            observation=observation,
            now=now,
        )
        command = proposed['commands'][command_id]
        if args.mode == 'live':
            require_live(store)
            if observation.value['main_sha'] != checkout_sha:
                raise StateInvalid('MASTER_LIVE_STALE_OBSERVATION')
            saved = store.save(loaded, proposed)
            dispatch = deliver_command(store, observer, command_id)
            print(json.dumps({
                'mode': 'live', 'request_id': intent.request_id,
                'command_id': command_id,
                'written_revision': saved.state['revision'],
                'dispatch': dispatch,
                'public_verified': False,
            }, ensure_ascii=False, sort_keys=True))
            return 0
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
    except (KeyError, TypeError, ValueError, GitHubError, StateInvalid, StateConflict, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        print(f'MASTER_INTENT_FAILED:{type(exc).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
