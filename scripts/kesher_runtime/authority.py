"""Live admission requires a trusted observation provider, never local flags.

The caller installs a service-backed observer holding the exclusive authority
fence. No default permissive observer, environment boolean or cached evidence
file can turn production on. The offline handover supplies disposable services;
live fence/actor acceptance remains a separate, explicitly authorized step.
"""
from .handover import require_authority
from .state import StateInvalid
import os


def require_live(store, *, observe=None):
    read = observe or getattr(store, 'authority_observer', None)
    if read is None and os.environ.get('KESHER_CUTOVER_GATEWAY_URL'):
        from .authority_client import ActionsAuthorityObserver, REPOSITORY
        if getattr(store, 'repo', None) == REPOSITORY:
            read = ActionsAuthorityObserver(os.environ)
    if not callable(read):
        raise StateInvalid('TRUSTED_AUTHORITY_OBSERVER_REQUIRED')
    state = store.load().state
    require_authority(state, read())
    return state
