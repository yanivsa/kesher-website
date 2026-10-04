"""Finite deterministic recovery rules. Software exhaustion is a repair incident."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .identity import Identity, digest
from .state import StateInvalid, timestamp


@dataclass(frozen=True)
class Rule:
    operation: str | None
    attempts: int
    delays: tuple[int, ...] = (300, 900, 3600)
    deadline_seconds: int = 43200


RULES = {
    'TRANSIENT_API': Rule('reconcile', 3),
    'WORKER_FAILED': Rule('reconcile', 3),
    'WORKER_RECEIPT_MISSING': Rule('reconcile', 2),
    'PROVIDER_PENDING': Rule('reconcile', 48, (300, 900, 1800)),
    'PUBLIC_PROCESSING_PENDING': Rule('reconcile', 48, (300, 900, 1800)),
    'OUTPUT_ARCHIVE_PENDING': Rule('reconcile', 48, (300, 900, 1800)),
    'OUTPUT_ARCHIVE_REBUILD': Rule('reconcile', 3),
    'JULES_PENDING': Rule('reconcile', 48, (300, 900, 1800)),
    'JULES_OUTPUT_PENDING': Rule('reconcile', 3),
    'JULES_CREATE_UNCERTAIN': Rule('reconcile', 48, (300, 900, 1800)),
    'ARTICLE_PR_CHANGED': Rule('reconcile', 3),
    'CODE_CHANGED': Rule('reconcile', 3),
    'MERGE_RECORD_PENDING': Rule('reconcile', 3),
    'PUBLIC_METADATA_INVALID': Rule('repair_metadata', 3),
    'MEDIA_INVALID': Rule('rebuild', 2),
    'PROVIDER_MEDIA_REJECTED': Rule('publish', 3),
    'STALE_CACHE': Rule('rebuild', 2),
    'ARTICLE_NOT_PUBLIC': Rule('deploy_article', 2),
    'DEPLOY_FAILED': Rule('deploy_article', 2),
    'DEPLOY_PENDING': Rule('deploy_article', 48, (300, 900, 1800)),
    'DEPLOY_CREATE_UNCERTAIN': Rule('deploy_article', 48, (300, 900, 1800)),
    'DEPLOY_PREDECESSOR_UNCERTAIN': Rule('deploy_article', 48, (300, 900, 1800)),
    'DEPLOY_ARCHIVE_PENDING': Rule('deploy_article', 48, (300, 900, 1800)),
    'DEPLOY_ARCHIVE_REBUILD': Rule('deploy_article', 3),
    'AUTH_EXPIRED': Rule(None, 0),
    'AUTH_SCOPE_INVALID': Rule(None, 0),
}


def seconds(after: str, before: str) -> float:
    timestamp(after)
    timestamp(before)
    return (datetime.fromisoformat(after.replace('Z', '+00:00')) - datetime.fromisoformat(before.replace('Z', '+00:00'))).total_seconds()


def due_after(now: str, delay: int) -> str:
    timestamp(now)
    return (datetime.fromisoformat(now.replace('Z', '+00:00')) + timedelta(seconds=delay)).isoformat()


def incident_key(target: Identity, stage: str, failure_class: str) -> str:
    return 'incident:' + digest({'target': target.to_dict(), 'stage': stage, 'failure_class': failure_class})


def record_incident(state: dict, target: Identity, stage: str, failure_class: str, *, now: str,
                    external_blocker: dict | None = None, evidence: dict | None = None) -> dict:
    """One stable incident per exact failure. Repeated polls do not advance it."""
    key = incident_key(target, stage, failure_class)
    status = 'repair_required'
    if external_blocker is not None:
        if (failure_class not in {'AUTH_EXPIRED', 'AUTH_SCOPE_INVALID'}
                or external_blocker.get('confirmed') is not True
                or external_blocker.get('action') not in {'interactive_reauthentication', 'grant_required_permission'}
                or external_blocker.get('provider') not in {'notebooklm', 'youtube', 'github', 'jules'}):
            raise StateInvalid('External blocker requires confirmed provider-specific non-automatable action')
        status = 'external_action_required'
    row = state['incidents'].setdefault(key, {
        'id': key, 'target': target.to_dict(), 'stage': stage, 'failure_class': failure_class,
        'created_at': timestamp(now), 'status': status, 'evidence': {}, 'repair': {},
    })
    if row['status'] == 'resolved':
        row['status'] = status
        row['reopened_at'] = now
    if external_blocker:
        row['external_blocker'] = external_blocker.copy()
        row['status'] = status
    if evidence:
        row['evidence'].setdefault(digest(evidence), evidence.copy())
    return row
