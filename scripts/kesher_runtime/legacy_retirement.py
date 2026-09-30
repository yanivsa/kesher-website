"""Installed legacy entrypoints have no mutation authority after this cutover.

Old-revision processes still need external credential fencing and drain proof;
new code cannot retroactively protect them. Pure legacy reducers/readers remain
available for tests and forensic replay, never for production execution.
"""
import copy

from .identity import digest, require_sha
from .state import StateConflict, StateInvalid, timestamp, validate_state

REPOSITORY = 'yanivsa/kesher-website'
LEGACY_AUTHORITY_INCIDENT = 'legacy_authority_violation'


def validate_legacy_read(state):
    """Never feed protected state into a legacy reconstruction/migration path.

    An absent schema belongs to historical legacy documents. An authority
    journal is protected by key presence, including an empty/malformed value.
    This local guard does not revoke credentials held by old-revision actors;
    the protected resource must apply ``validate_legacy_write`` independently.
    """
    if state is None:
        return
    if not isinstance(state, dict):
        raise StateInvalid('LEGACY_STATE_INVALID')
    schema = state.get('schema_version')
    if ('handover' in state or 'github_exclusion' in state
            or (type(schema) is int and schema >= 6)):
        raise StateInvalid('LEGACY_AUTHORITY_FENCED')
    if schema is not None and (type(schema) is not int or not 1 <= schema <= 5):
        raise StateInvalid('LEGACY_STATE_SCHEMA_INVALID')


def _revision_identity(value):
    if value is not None:
        try:
            require_sha(value, 40)
        except ValueError as exc:
            raise StateInvalid('LEGACY_STATE_REVISION_INVALID') from exc


def validate_legacy_write(current, proposed, *, before_sha, current_sha):
    """Protected-endpoint hook: exact CAS *and* legacy authority are required.

    ``current`` and ``current_sha`` must be read by the resource, not supplied
    by the legacy caller. The comparison may bind a blob or an exact Git ref.
    A fresh identity alone never authorizes a schema downgrade/journal erase.
    The resource still must atomically enforce that identity while persisting.
    """
    _revision_identity(before_sha)
    _revision_identity(current_sha)
    if current is not None and current_sha is None:
        raise StateInvalid('LEGACY_STATE_REVISION_MISSING')
    if before_sha != current_sha:
        raise StateConflict('LEGACY_STATE_CAS_CONFLICT')
    validate_legacy_read(current)
    if not isinstance(proposed, dict):
        raise StateInvalid('LEGACY_STATE_INVALID')
    validate_legacy_read(proposed)


def record_legacy_rejection(current, *, actor, epoch, proposed, before_sha,
                            current_sha, now, reason='LEGACY_AUTHORITY_FENCED'):
    """Pure additive incident record; persist only through the existing Git CAS.

    The gateway supplies authenticated actor/epoch identities. Attempt data and
    identities are hashed, never copied into the incident. Current ref and
    observation time are excluded from incident identity so a lost-response
    readback/retry cannot create a second incident after the first CAS.
    No repair, import, activation or journal transition is authorized here.
    """
    if (not isinstance(current, dict) or
            not (current.get('schema_version') == 6 or 'handover' in current
                 or 'github_exclusion' in current)):
        raise StateInvalid('LEGACY_REJECTION_REQUIRES_PROTECTED_STATE')
    if current.get('schema_version') == 6:
        validate_state(current)
    elif 'handover' in current:
        from .handover import validate_journal
        validate_journal(current['handover'])
    timestamp(now)
    # The attempted CAS input can itself be malformed; retain only its digest.
    _revision_identity(current_sha)
    if not isinstance(actor, str) or not actor or not isinstance(epoch, str) or not epoch:
        raise StateInvalid('LEGACY_REJECTION_IDENTITY_REQUIRED')
    if not isinstance(reason, str) or reason not in {'LEGACY_AUTHORITY_FENCED', 'LEGACY_STATE_CAS_CONFLICT',
                      'LEGACY_STATE_SCHEMA_INVALID', 'LEGACY_STATE_INVALID',
                      'LEGACY_STATE_REVISION_INVALID', 'LEGACY_STATE_REVISION_MISSING'}:
        raise StateInvalid('LEGACY_REJECTION_REASON_INVALID')
    evidence = {'actor_sha256': digest(actor), 'epoch_sha256': digest(epoch),
                'attempt_sha256': digest(proposed), 'before_revision_sha256': digest(before_sha),
                'reason': reason}
    incident_id = 'incident:' + digest({'kind': LEGACY_AUTHORITY_INCIDENT, **evidence})
    recorded = copy.deepcopy(current)
    incidents = recorded.setdefault('incidents', {})
    audit = recorded.setdefault('audit', [])
    if not isinstance(incidents, dict) or not isinstance(audit, list):
        raise StateInvalid('LEGACY_REJECTION_LEDGER_INVALID')
    if incident_id in incidents:
        existing = incidents[incident_id]
        if (not isinstance(existing, dict) or existing.get('kind') != LEGACY_AUTHORITY_INCIDENT
                or existing.get('status') != 'open'):
            raise StateInvalid('LEGACY_REJECTION_INCIDENT_INVALID')
        return recorded
    evidence['observed_revision_sha256'] = digest(current_sha)
    incidents[incident_id] = {
        'id': incident_id, 'kind': LEGACY_AUTHORITY_INCIDENT, 'status': 'open',
        'target': {'type': 'authority', 'resource': 'automation-state'},
        'stage': 'authority', 'failure_class': reason, 'created_at': now,
        'evidence': evidence, 'repair': {},
    }
    audit.append({'at': now, 'event': 'legacy_mutation_rejected', 'incident_id': incident_id,
                  'evidence_sha256': digest(evidence)})
    if current.get('schema_version') == 6:
        validate_state(recorded)
    return recorded


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
