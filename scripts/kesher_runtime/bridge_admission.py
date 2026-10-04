"""Read-only fail-closed admission before any emergency media credentials."""
import os
import sys

from .github import GitHub
from .handover_github import GitHubHandover
from .state import StateInvalid
from .worker_entry import REPOSITORY


def require_bridge(state):
    if (state.get('schema_version') != 5 or 'handover' in state or 'github_exclusion' in state):
        raise StateInvalid('MANUAL_BRIDGE_RETIRED_BY_CUTOVER')
    from .handover import require_legacy_writable
    require_legacy_writable(state)


def main():
    try:
        if (os.environ.get('GITHUB_REPOSITORY') != REPOSITORY or
                os.environ.get('GITHUB_REF') != 'refs/heads/main' or
                os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'):
            raise StateInvalid('MANUAL_BRIDGE_MAIN_DISPATCH_REQUIRED')
        github = GitHub(os.environ.get('GH_TOKEN', ''))
        require_bridge(GitHubHandover(github, REPOSITORY, observer=None, fence=None).read_snapshot().state)
        print('MANUAL_BRIDGE_LEGACY_STATE_OBSERVED')
        return 0
    except (RuntimeError, ValueError, OSError):
        print('MANUAL_BRIDGE_ADMISSION_DENIED', file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
