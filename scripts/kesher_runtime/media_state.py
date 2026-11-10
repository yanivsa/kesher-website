"""One exact media item projected from canonical append-only worker checkpoints.

This adapter is passed explicitly to existing media functions. It never selects
from workflow artifacts, global FIFO, a latest provider task, or another kind.
Local paths remain output references; canonical receipts are recovery authority.
"""
from __future__ import annotations

import copy

from .identity import MediaIdentity, SourceIdentity, digest, require_sha
from .sealed import seal, unseal
from .state import StateInvalid
from .worker import WorkerContext, public_evidence

VOLATILE_FIELDS = {'updated_at', 'last_polled_at'}
IMMUTABLE_RECEIPTS = ('id', 'source_id', 'task_id', 'artifact_id', 'youtube_id', 'fresh_generation_attempt')
ITEM_TYPES = {'overview': 'video_overview', 'short': 'article_short'}


def provider_effect_name(name: str, attempt: int) -> str:
    if name not in {'provider_source', 'provider_generation'} or type(attempt) is not int or not 1 <= attempt <= 3:
        raise StateInvalid('Invalid bounded provider attempt')
    return name if attempt == 1 else f'{name}_a{attempt}'


def next_generation_attempt(state: dict, target: MediaIdentity, *, current_command_id=None) -> int | None:
    """Only exact completed, rejected, never-archived provider output can reset.

    Every older intent and receipt remains in the same append-only journal.
    Unknown results, active predecessors, capabilities, archives and uploads
    are refusals, including those recorded outside the latest snapshot.
    """
    history = snapshots(state, target)
    if not history:
        return None
    item = history[-1]['item']
    attempt = item.get('fresh_generation_attempt', 1)
    rejection = item.get('generation_rejection')
    if (type(attempt) is not int or not 1 <= attempt < 3
            or item.get('status') != 'rejected' or item.get('technical_verified') is not False
            or item.get('last_provider_status') not in {'completed', 'complete', 'ready', 'succeeded', 'success'}
            or not isinstance(rejection, dict) or rejection.get('reason') not in {'voice', 'native_short'}
            or type(rejection.get('attempt')) is not int or rejection.get('attempt') != attempt
            or rejection.get('raw_sha256') != item.get('raw_sha256')
            or rejection.get('artifact_id') != item.get('artifact_id')
            or not all(isinstance(item.get(k), str) and item[k] for k in ('source_id', 'task_id', 'artifact_id'))):
        return None
    try:
        require_sha(item.get('raw_sha256'), 64)
    except ValueError:
        return None
    if any(row.get('capabilities') or any(row['item'].get(k) for k in
           ('youtube_id', 'uploaded', 'upload_capability_sha256', 'upload_session_uri')) for row in history):
        return None
    commands = [row for key, row in state['commands'].items()
                if row['target'] == target.to_dict() and key != current_command_id]
    if any(row['outcome'] == 'pending' or any(name == 'output_artifact' or name.startswith('youtube_')
           for name in row['effects']) for row in commands):
        return None
    settled = {}
    names = {name for row in commands for name in row['effects']
             if name.startswith(('provider_source', 'provider_generation'))}
    for name in names:
        effects = [row['effects'][name] for row in commands if name in row['effects']]
        receipts = {digest(e['receipt']): e['receipt'] for e in effects if e.get('receipt') is not None}
        # A later read-only reconciliation settles the exact lost-response
        # request without erasing the original None receipt or repeating POST.
        if len({digest(e['request']) for e in effects}) != 1 or len(receipts) != 1:
            return None
        settled[name] = {'request': effects[0]['request'], 'receipt': next(iter(receipts.values()))}
    exact = {name: settled.get(provider_effect_name(name, attempt))
             for name in ('provider_source', 'provider_generation')}
    if any(effect is None for effect in exact.values()):
        return None
    source, generation = exact['provider_source'], exact['provider_generation']
    if (source['receipt'].get('source_id') != item['source_id']
            or source['request'].get('body_sha256') != target.source.content_sha256
            or source['request'].get('notebook_id') != item.get('notebook_id')
            or source['request'].get('title') != f'kesher:{target.key}:{attempt}'
            or generation['request'].get('notebook_id') != item.get('notebook_id')
            or generation['request'].get('source_id') != item['source_id']
            or generation['receipt'].get('task_id') != item['task_id']
            or generation['receipt'].get('artifact_id') != item['artifact_id']):
        return None
    return attempt + 1


def _validate_item(item: dict, target: MediaIdentity) -> None:
    try:
        source = item['source']
        actual = SourceIdentity(source['date'], source['slug'], source['content_sha256'])
        if actual != target.source or item['type'] != ITEM_TYPES[target.kind] or not item['id']:
            raise ValueError('Identity mismatch')
    except (KeyError, TypeError, ValueError) as exc:
        raise StateInvalid('Worker item differs from exact command source/kind') from exc


def exact_item(state: dict, item_id: str, *, slug: str = '', content_sha256: str = '',
               kind: str = 'overview', generation_attempt: int | None = None) -> dict:
    """Resolve existing canonical fields; never infer an artifact from ordering."""
    if not isinstance(item_id, str) or not item_id.strip():
        raise StateInvalid('EXACT_MEDIA_ITEM_ID_REQUIRED: supply the initiating item ID')
    matches = [item for item in state.get('items', [])
               if isinstance(item, dict) and item.get('id') == item_id]
    if len(matches) != 1:
        raise StateInvalid('EXACT_MEDIA_ITEM_NOT_UNIQUE: requested item is missing or duplicated')
    item = matches[0]
    source = item.get('source') or {}
    if (kind not in ITEM_TYPES or item.get('type') != ITEM_TYPES[kind]
            or (slug and source.get('slug') != slug)
            or (content_sha256 and source.get('content_sha256') != content_sha256)
            or (generation_attempt is not None
                and item.get('fresh_generation_attempt', 1) != generation_attempt)):
        raise StateInvalid('EXACT_MEDIA_IDENTITY_MISMATCH: source, kind or attempt changed')
    if isinstance(state, CanonicalMediaState):
        _validate_item(item, state.context.target)
        if item['id'] != state._bound['id'] or item.get('fresh_generation_attempt', 1) != state._attempt:
            raise StateInvalid('UNPROVEN_MEDIA_ATTEMPT_TRANSITION')
    return item


def snapshots(state: dict, target: MediaIdentity) -> list[dict]:
    baseline = legacy_baseline(state['items'].get(target.key, {}), target)
    found = {1: baseline} if baseline else {}
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


def legacy_baseline(row: dict, target: MediaIdentity) -> dict | None:
    """A migration baseline is observed history, never a forged worker command."""
    imports = [(name, evidence) for name, evidence in row.get('receipts', {}).items() if name.startswith('legacy:')]
    if not imports:
        return None
    if len(imports) != 1:
        raise StateInvalid('Multiple migration baselines cannot own one media identity')
    name, evidence = imports[0]
    try:
        _validate_item(evidence['item'], target)
        origin = evidence['legacy_import']
        if (name != 'legacy:' + digest(evidence) or evidence['sequence'] != 1
                or origin['item_sha256'] != digest(evidence['item'])
                or origin['verified_source_sha256'] != target.source.content_sha256
                or not origin['origins']):
            raise ValueError('Corrupted import proof')
        public_evidence(evidence)
    except (KeyError, TypeError, ValueError) as exc:
        raise StateInvalid('Migration baseline lost its immutable identity or digest') from exc
    return evidence


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
        command = state['commands'][context.command_id]
        requested = command['inputs'].get('generation_attempt', str(item.get('fresh_generation_attempt', 1)))
        if requested not in {'1', '2', '3'}:
            raise StateInvalid('Invalid bounded provider attempt')
        wanted = int(requested)
        if (not self._latest and wanted != 1) or type(item.get('fresh_generation_attempt', 1)) is not int:
            raise StateInvalid('UNPROVEN_MEDIA_ATTEMPT_TRANSITION')
        if wanted != item.get('fresh_generation_attempt', 1):
            if (command['operation'] != 'publish' or not self._latest
                    or command['inputs'].get('rejected_snapshot_sha256') != digest(self._latest)
                    or next_generation_attempt(state, context.target, current_command_id=context.command_id) != wanted
                    or initial_item.get('fresh_generation_attempt') != wanted):
                raise StateInvalid('UNPROVEN_MEDIA_ATTEMPT_TRANSITION')
            item = copy.deepcopy(initial_item)
        _validate_item(item, context.target)
        reference = item.pop('upload_capability_sha256', None)
        if reference:
            envelope = self._capabilities.get(reference)
            if not envelope or digest(envelope) != reference:
                raise StateInvalid('Upload capability reference is missing or corrupted')
            item['upload_session_uri'] = unseal(envelope, encryption_key, context.target,
                                                 repo=context.store.repo, purpose='youtube_upload')
        self._bound = copy.deepcopy(item)
        self._attempt = wanted
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
        if name in {'provider_source', 'provider_generation'}:
            name = self.provider_name(name)
        decision = self.context.begin_effect(name, request)
        if decision.receipt is not None:
            return copy.deepcopy(decision.receipt)
        if not decision.execute:
            raise StateInvalid('EXTERNAL_RESULT_UNCERTAIN: reconcile exact persisted request before creation')
        receipt = create()
        self.context.complete_effect(name, receipt)
        return receipt

    def provider_name(self, name: str) -> str:
        attempt = self.item.get('fresh_generation_attempt', 1)
        if type(attempt) is not int or attempt != self._attempt:
            raise StateInvalid('UNPROVEN_MEDIA_ATTEMPT_TRANSITION')
        return provider_effect_name(name, self._attempt)

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
        self.provider_name('provider_source')
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
