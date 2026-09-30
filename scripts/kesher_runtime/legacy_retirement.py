"""Installed legacy entrypoints have no mutation authority after this cutover.

Old-revision processes still need external credential fencing and drain proof;
new code cannot retroactively protect them. Pure legacy reducers/readers remain
available for tests and forensic replay, never for production execution.
"""
from .state import StateInvalid

REPOSITORY = 'yanivsa/kesher-website'


def retired_entrypoint():
    raise StateInvalid('LEGACY_ENTRYPOINT_RETIRED: use the admitted canonical command runtime')


def github_mutation(repo, method, url):
    if method.upper() not in {'GET','HEAD'} and (repo == REPOSITORY or '/repos/'+REPOSITORY+'/' in url):
        retired_entrypoint()


def media_mutation(state):
    from .media_state import CanonicalMediaState
    if not isinstance(state, CanonicalMediaState):
        retired_entrypoint()
    state.context._owned(state.context.store.load().state, require_current=True)
    if state.context.store.repo == REPOSITORY:
        from .authority import require_live
        require_live(state.context.store)
    # Exact durable ownership is checked again by each canonical effect intent.
