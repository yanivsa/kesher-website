"""Read-only fail-closed admission before any emergency production credentials."""
import os
import sys
import argparse

from .github import GitHub
from .handover_github import GitHubHandover
from .state import StateInvalid
from .worker_entry import REPOSITORY


PRE_CUTOVER_CONTROLLER_WORKFLOW = '.github/workflows/kesher-content-controller.yml'
PRE_CUTOVER_CONTROLLER_EVENTS = {'schedule', 'workflow_run', 'push', 'workflow_dispatch'}
PRE_CUTOVER_ADMITTED_CHILD_WORKFLOW_NAMES = {
    'Kesher Article Generation',
    'Kesher Normalize Article PR',
    'Kesher Trusted Article Image',
    'Auto-merge Kesher article PRs',
    'Deploy to Cloudflare Pages',
    'Kesher Daily NotebookLM Video Overview',
    'Kesher Daily Article Short V4',
}
WORKER_BRIDGE_WORKFLOWS = {
    '.github/workflows/kesher-article-generation.yml',
    '.github/workflows/normalize-article-pr.yml',
    '.github/workflows/kesher-article-image.yml',
    '.github/workflows/auto-merge-article-prs.yml',
    '.github/workflows/deploy.yml',
    '.github/workflows/kesher-daily-video.yml',
    '.github/workflows/kesher-short-v4.yml',
}


def require_bridge(state):
    if (
        not isinstance(state, dict)
        or type(state.get('schema_version')) is not int
        or state.get('schema_version') != 5
        or 'handover' in state
        or 'github_exclusion' in state
    ):
        raise StateInvalid('MANUAL_BRIDGE_RETIRED_BY_CUTOVER')
    from .handover import require_legacy_writable
    require_legacy_writable(state)


def require_pre_cutover_controller_invocation(environ):
    event_name = environ.get('GITHUB_EVENT_NAME')
    child_workflow = str(environ.get('KESHER_CHILD_WORKFLOW') or '').strip()
    if (
        environ.get('KESHER_PRE_CUTOVER_DAILY_AUTHORITY') != 'true'
        or environ.get('KESHER_MANUAL_EMERGENCY_BRIDGE') == 'true'
        or environ.get('GITHUB_REPOSITORY') != REPOSITORY
        or environ.get('GITHUB_REF') != 'refs/heads/main'
        or event_name not in PRE_CUTOVER_CONTROLLER_EVENTS
        or environ.get('GITHUB_WORKFLOW_REF') != f'{REPOSITORY}/{PRE_CUTOVER_CONTROLLER_WORKFLOW}@refs/heads/main'
        or (
            event_name == 'workflow_run'
            and 'KESHER_CHILD_WORKFLOW' in environ
            and child_workflow not in PRE_CUTOVER_ADMITTED_CHILD_WORKFLOW_NAMES
        )
    ):
        raise StateInvalid('PRE_CUTOVER_CONTROLLER_EXACT_INVOCATION_REQUIRED')


def require_invocation(environ, *, dispatcher=False, controller=False):
    if controller and dispatcher:
        raise StateInvalid('LEGACY_BRIDGE_EXACT_INVOCATION_REQUIRED')
    if controller:
        require_pre_cutover_controller_invocation(environ)
        return
    paths = {'.github/workflows/kesher-targeted-media-recovery-dispatch.yml'} if dispatcher else WORKER_BRIDGE_WORKFLOWS
    event = 'push' if dispatcher else 'workflow_dispatch'
    if (environ.get('GITHUB_REPOSITORY') != REPOSITORY or environ.get('GITHUB_REF') != 'refs/heads/main'
            or environ.get('GITHUB_EVENT_NAME') != event or environ.get('GITHUB_WORKFLOW_REF') not in
            {REPOSITORY + '/' + path + '@refs/heads/main' for path in paths}):
        raise StateInvalid('LEGACY_BRIDGE_EXACT_INVOCATION_REQUIRED')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dispatcher', action='store_true')
    parser.add_argument('--controller', action='store_true')
    args = parser.parse_args(argv)
    try:
        require_invocation(os.environ, dispatcher=args.dispatcher, controller=args.controller)
        github = GitHub(os.environ.get('GH_TOKEN', ''))
        require_bridge(GitHubHandover(github, REPOSITORY, observer=None, fence=None).read_snapshot().state)
        print('PRE_CUTOVER_DAILY_AUTHORITY_OBSERVED' if args.controller else 'MANUAL_BRIDGE_LEGACY_STATE_OBSERVED')
        return 0
    except (RuntimeError, ValueError, OSError):
        print('MANUAL_BRIDGE_ADMISSION_DENIED', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
