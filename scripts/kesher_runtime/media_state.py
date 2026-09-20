"""One exact media item projected from canonical append-only worker checkpoints.

This adapter is passed explicitly to existing media functions. It never selects
from workflow artifacts, global FIFO, a latest provider task, or another kind.
Local paths remain output references; canonical receipts are recovery authority.
"""
from __future__ import annotations

import copy

from .identity import MediaIdentity, SourceIdentity, digest
from .sealed import seal, unseal
from .state import StateInvalid
from .worker import WorkerContext, public_evidence

VOLATILE_FIELDS = {'updated_at', 'last_polled_at'}
IMMUTABLE_RECEIPTS = ('id', 'source_id', 'task_id', 'artifact_id', 'youtube_id')
ITEM_TYPES = {'overview': 'video_overview', 'short': 'article_short'}


def _validate_item(item: dict, target: MediaIdentity) -> None:
    try:
        source = item['source']
        actual = SourceIdentity(source['date'], source['slug'], source['content_sha256'])
        if actual != target.source or item['type'] != ITEM_TYPES[target.kind] or not item['id']:
            raise ValueError('Identity mismatch')
    except (KeyError, TypeError, ValueError) as exc:
        raise StateInvalid('Worker item differs from exact command source/kind') from exc


def snapshots(state: dict, target: MediaIdentity) -> list[dict]:
    found = {}
    for command in state['commands'].values():
        if command['target'] != target.to_dict():
            continue
        for name, row in command['receipts'].items():
            if not name.startswith('media_state_'):
                continue
            evidence = row['evidence']
            sequence = evidence.get('sequence')
            if type(sequence) is not int or sequence < 1:
                raise StateInvalid('Media checkpoint sequence is invalid')
            _validate_item(evidence['item'], target)
            if sequence in found and found[sequence] != evidence:
                raise StateInvalid('Conflicting media snapshots; quarantine instead of selecting newest')
            found[sequence] = evidence
    return [found[key] for key in sorted(found)]


def _phase(item: dict) -> str:
    # This describes worker execution evidence only. Public verification is
    # controller-owned and is never inferred from uploaded/status booleans.
    if item.get('youtube_id'):
        return 'UPLOADED'
    if item.get('upload_session_uri'):
        return 'UPLOAD_STARTED'
    if item.get('technical_verified') is True:
        return 'TECHNICALLY_VALIDATED'
    if item.get('raw_sha256') or item.get('final_sha256'):
        return 'OUTPUT_CREATED'
    return 'STARTED'


class CanonicalMediaState(dict):
    def __init__(self, context: WorkerContext, initial_item: dict, *, encryption_key: str = ''):
        if not isinstance(context.target, MediaIdentity):
            raise StateInvalid('Media worker requires an explicit media target')
        self.context = context
        self.encryption_key = encryption_key
        state = context.store.load().state
        history = snapshots(state, context.target)
        self._latest = copy.deepcopy(history[-1]) if history else None
        self._capabilities = copy.deepcopy(self._latest.get('capabilities', {})) if history else {}
        item = copy.deepcopy(self._latest['item'] if history else initial_item)
        _validate_item(item, context.target)
        reference = item.pop('upload_capability_sha256', None)
        if reference:
            envelope = self._capabilities.get(reference)
            if not envelope or digest(envelope) != reference:
                raise StateInvalid('Upload capability reference is missing or corrupted')
            item['upload_session_uri'] = unseal(envelope, encryption_key, context.target,
                                                 repo=context.store.repo, purpose='youtube_upload')
        self._bound = copy.deepcopy(item)
        self._uri = item.get('upload_session_uri')
        self._capability_ref = reference
        super().__init__({'version': 1, 'items': [item]})

    @property
    def item(self) -> dict:
        if not isinstance(self.get('items'), list) or len(self['items']) != 1:
            raise StateInvalid('Canonical worker projection must contain exactly one item')
        return self['items'][0]

    def external(self, name: str, request: dict, create) -> dict:
        """Persist intent, execute once, persist receipt before item mutation."""
        decision = self.context.begin_effect(name, request)
        if decision.receipt is not None:
            return copy.deepcopy(decision.receipt)
        if not decision.execute:
            raise StateInvalid('EXTERNAL_RESULT_UNCERTAIN: reconcile exact persisted request before creation')
        receipt = create()
        self.context.complete_effect(name, receipt)
        return receipt

    def external_capability(self, name: str, request: dict, create) -> str:
        if not isinstance(self.encryption_key, str) or len(self.encryption_key) < 24:
            raise StateInvalid('CAPABILITY_KEY_UNAVAILABLE: require encryption before starting upload')
        def create_encrypted():
            value = create()
            envelope = seal(value, self.encryption_key, self.context.target,
                            repo=self.context.store.repo, purpose='youtube_upload')
            return {'capability_sha256': digest(envelope), 'envelope': envelope}

        receipt = self.external(name, request, create_encrypted)
        envelope, reference = receipt['envelope'], receipt['capability_sha256']
        if digest(envelope) != reference:
            raise StateInvalid('Corrupted external capability receipt')
        value = unseal(envelope, self.encryption_key, self.context.target,
                       repo=self.context.store.repo, purpose='youtube_upload')
        self._capabilities[reference] = envelope
        self._capability_ref, self._uri = reference, value
        return value

    def persist(self) -> None:
        item = self.item
        _validate_item(item, self.context.target)
        for field in IMMUTABLE_RECEIPTS:
            if self._bound.get(field) and self._bound[field] != item.get(field):
                raise StateInvalid('Cannot erase or replace an existing provider/upload/item receipt')
        if (self._uri and self._bound.get('final_sha256')
                and self._bound['final_sha256'] != item.get('final_sha256')):
            raise StateInvalid('Cannot change render bytes after creating its upload session')
        public = {key: copy.deepcopy(value) for key, value in item.items()
                  if key not in VOLATILE_FIELDS and key != 'upload_session_uri'}
        uri = item.get('upload_session_uri')
        if self._uri and uri != self._uri:
            if uri is None and item.get('youtube_id') and item['youtube_id'] == self._bound.get('youtube_id'):
                # A durably recorded video ID replaces the need for a live
                # session. Earlier encrypted checkpoints remain recoverable.
                self._uri, self._capability_ref = None, None
            else:
                raise StateInvalid('Cannot erase or replace an unreconciled upload capability')
        if uri:
            if not self._capability_ref:
                envelope = seal(uri, self.encryption_key, self.context.target,
                                repo=self.context.store.repo, purpose='youtube_upload')
                self._capability_ref = digest(envelope)
                self._capabilities[self._capability_ref] = envelope
                self._uri = uri
            public['upload_capability_sha256'] = self._capability_ref
        public_evidence(public)
        payload = {'item': public, 'capabilities': self._capabilities}
        if self._latest and all(self._latest.get(key) == value for key, value in payload.items()):
            return
        current = snapshots(self.context.store.load().state, self.context.target)
        latest = current[-1] if current else None
        if latest != self._latest:
            raise StateInvalid('Projection is stale; reload exact canonical media state')
        payload['sequence'] = (latest['sequence'] if latest else 0) + 1
        name = 'media_state_' + digest(payload)[:40]
        self.context.checkpoint(name, payload, phase=_phase(item))
        self._latest = copy.deepcopy(payload)
        self._bound = copy.deepcopy(item)
