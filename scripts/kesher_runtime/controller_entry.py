"""One canonical controller entry point; default shadow performs no writes."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import quote

from .controller import reconcile
from .github import GitHub, GitHubError, GitHubStateStore
from .media_audit import ArchivedMediaAuditor
from .media_observer import YouTubeInventory
from .observe import RepositoryObserver, utc_now
from .outbox import ObservedRuns, deliver_command, workflow_for
from .output_artifacts import download_actions_artifact
from .state import StateConflict, StateInvalid
from .worker_entry import REPOSITORY


def execute_tick(store, observer, *, mode: str, dispatch, clock=utc_now, authority=None) -> dict:
    if mode not in {'shadow', 'live'}:
        raise StateInvalid('Controller mode must be explicit')
    loaded = store.load()
    state = loaded.state
    migrated = (state['migration'].get('status') == 'complete'
                and state['migration'].get('runtime_owner') == 'kesher-canonical-controller')
    if mode == 'live' and not migrated:
        raise StateInvalid('CANONICAL_MIGRATION_REQUIRED: retire competing writers before activation')
    if mode == 'live':
        from .authority import require_live
        require_live(store, observe=authority)
    observation = observer.read(state)
    if observation.value.get('state_revision') != state['revision']:
        raise StateConflict('Observation must bind the exact loaded canonical revision')
    decision = reconcile(state, observation, now=clock())
    command = decision.state['commands'].get(decision.command_id)
    report = {'mode': mode, 'migration_complete': migrated, 'observed_revision': state['revision'],
        'main_sha': observation.value['main_sha'], 'current_slot': observation.value['current_slot'],
        'observation': observation.value, 'action': {key: command[key] for key in ('id', 'target', 'operation')} if command else None,
        'current_complete': decision.state['slots'].get(observation.value['current_slot'], {}).get('complete', False),
        'incidents': [{key: row[key] for key in ('id', 'target', 'stage', 'failure_class', 'status')}
                      for row in decision.state['incidents'].values() if row['status'] != 'resolved']}
    if mode == 'live':
        require_live(store, observe=authority)
        saved = store.save(loaded, decision.state)
        report['written_revision'] = saved.state['revision']
        if decision.command_id:
            report['dispatch'] = dispatch(decision.command_id)
    return report


def deliver(store, observer, command_id: str) -> dict:
    from .authority import require_live
    command = require_live(store)['commands'][command_id]
    workflow = workflow_for(command)
    since = quote('>=' + command['created_at'], safe='')
    rows = observer.pages(f'actions/workflows/{workflow}/runs?event=workflow_dispatch&branch=main&created={since}', 'workflow_runs')
    main = store.github.request('GET', f'/repos/{store.repo}/git/ref/heads/main')['object']['sha']
    now = utc_now()
    result = deliver_command(store, command_id, ObservedRuns(workflow, tuple(rows), now),
        lambda workflow, inputs: store.github.request('POST', f'/repos/{store.repo}/actions/workflows/{workflow}/dispatches',
                                                     {'ref': 'main', 'inputs': inputs}),
        now=now, trusted_main_sha=main)
    return asdict(result)


def youtube_inventory(*, now: str) -> dict:
    from scripts import kesher_daily_pipeline as core
    token = core.youtube_access_token()
    return YouTubeInventory(lambda resource, params: core.youtube_get(resource, token, params)).read(now=now)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('shadow', 'live'), default='shadow')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
        github = GitHub(token)
        store = GitHubStateStore(github, REPOSITORY, allow_missing=args.mode == 'shadow')
        if args.mode == 'live':
            checkout = subprocess.run(['git', 'rev-parse', 'HEAD'], check=True, capture_output=True, text=True, timeout=15).stdout.strip()
            main_sha = github.request('GET', f'/repos/{REPOSITORY}/git/ref/heads/main')['object']['sha']
            if (checkout != main_sha or os.environ.get('GITHUB_REPOSITORY') != REPOSITORY
                    or os.environ.get('GITHUB_WORKFLOW_REF') != REPOSITORY + '/.github/workflows/kesher-content-controller.yml@refs/heads/main'):
                raise StateInvalid('Controller live execution requires trusted main and its sole workflow')
        observer = RepositoryObserver(github, REPOSITORY, inventory_reader=youtube_inventory,
            auditor=ArchivedMediaAuditor(github, REPOSITORY,
                lambda artifact_id, destination: download_actions_artifact(REPOSITORY, token, artifact_id, destination)))
        if os.environ.get('CLOUDFLARE_ACCOUNT_ID') and os.environ.get('CLOUDFLARE_API_TOKEN'):
            from .cloudflare_pages import PagesClient
            from .deployment_observer import read_deployment
            pages = PagesClient(os.environ['CLOUDFLARE_ACCOUNT_ID'], os.environ['CLOUDFLARE_API_TOKEN'])
            observer.deployment_observer = lambda state, sha: read_deployment(state, pages, github, REPOSITORY, sha)
        report = execute_tick(store, observer, mode=args.mode, dispatch=lambda command: deliver(store, observer, command))
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding='utf-8')
        print(encoded, end='')
        return 0
    except (GitHubError, StateInvalid, StateConflict, OSError, ValueError, RuntimeError) as exc:
        # API response bodies, auth material and signed URLs never enter logs.
        print(f'CANONICAL_CONTROLLER_FAILED:{type(exc).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
