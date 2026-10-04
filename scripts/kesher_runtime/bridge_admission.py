"""Read-only fail-closed admission before any emergency media credentials."""
import os
import sys
import argparse

from .github import GitHub
from .handover_github import GitHubHandover
from .state import StateInvalid
from .worker_entry import REPOSITORY


def require_bridge(state):
    if (state.get('schema_version') != 5 or 'handover' in state or 'github_exclusion' in state):
        raise StateInvalid('MANUAL_BRIDGE_RETIRED_BY_CUTOVER')
    from .handover import require_legacy_writable
    require_legacy_writable(state)


def require_invocation(environ, *, dispatcher=False):
    paths={'.github/workflows/kesher-targeted-media-recovery-dispatch.yml'} if dispatcher else {
        '.github/workflows/kesher-daily-video.yml','.github/workflows/kesher-short-v4.yml','.github/workflows/deploy.yml'}
    event='push' if dispatcher else 'workflow_dispatch'
    if (environ.get('GITHUB_REPOSITORY')!=REPOSITORY or environ.get('GITHUB_REF')!='refs/heads/main'
            or environ.get('GITHUB_EVENT_NAME')!=event or environ.get('GITHUB_WORKFLOW_REF') not in
            {REPOSITORY+'/'+path+'@refs/heads/main' for path in paths}):
        raise StateInvalid('LEGACY_BRIDGE_EXACT_INVOCATION_REQUIRED')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dispatcher',action='store_true')
    args=parser.parse_args(argv)
    try:
        require_invocation(os.environ,dispatcher=args.dispatcher)
        github = GitHub(os.environ.get('GH_TOKEN', ''))
        require_bridge(GitHubHandover(github, REPOSITORY, observer=None, fence=None).read_snapshot().state)
        print('MANUAL_BRIDGE_LEGACY_STATE_OBSERVED')
        return 0
    except (RuntimeError, ValueError, OSError):
        print('MANUAL_BRIDGE_ADMISSION_DENIED', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
