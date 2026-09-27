"""Prepare a canonical import from independently retained legacy evidence.

This is a pure preparation step. It never activates the runtime, writes GitHub,
certifies public delivery, or invents historical external-effect intents.
"""
from __future__ import annotations

import copy

from .identity import MediaIdentity, SourceIdentity, digest, require_sha
from .media_state import ITEM_TYPES
from .provider import text_hash
from .state import StateInvalid, bind_source, new_state, timestamp, validate_state
from .worker import public_evidence

VOLATILE = {'updated_at', 'last_polled_at', 'large_media_pruned_at'}
BUDGET_FIELDS = ('attempt_count', 'same_failure_streak', 'failure_count_by_type', 'attempts',
                 'deploy_attempts', 'resume_dispatches', 'watchdog')
STAGE_IDS = ('item_id', 'source_id', 'task_id', 'artifact_id', 'youtube_id', 'provider_id',
             'run_id', 'processed_run_id', 'adopted_from_long_item_id')


def _stage_claim(stage: dict) -> dict:
    return {key: copy.deepcopy(stage[key]) for key in (*STAGE_IDS, *BUDGET_FIELDS, 'status') if key in stage}


def _unresolved_record(record: dict) -> dict:
    article = record.get('article') or {}
    return {'legacy_record_sha256': digest(record), 'slot': article.get('published_date') or record.get('cycle'),
            'article': {key: copy.deepcopy(article[key]) for key in
                        ('slug', 'published_date', 'quality_content_sha256', 'pr_number', 'run_id', 'provider_id', 'status')
                        if key in article},
            'stages': {name: _stage_claim(record.get(name) or {}) for name in ('long_video', 'short')}}


def _identity(source: dict) -> SourceIdentity:
    return SourceIdentity(source['date'], source['slug'], source['content_sha256'])


def prepare_migration(*, controller: dict, controller_sha: str, main_sha: str,
                      sources: list[dict], artifacts: list[dict], now: str, capability_sealer=None,
                      historical_sources: list[dict] | None = None) -> dict:
    timestamp(now); require_sha(controller_sha, 40); require_sha(main_sha, 40)
    if controller.get('schema_version') != 5:
        raise StateInvalid('Migration input must be the explicitly inspected legacy schema')
    state = new_state()
    migration = state['migration']
    migration.update(status='prepared', controller_sha256=digest(controller), controller_blob_sha=controller_sha,
        main_sha=main_sha, prepared_at=now, observed_youtube_ids={}, legacy_stage_budgets={}, artifacts=[],
        legacy_stage_claims={}, unresolved_controller_records=[])
    authoritative, source_origins = {}, {}
    for source in sources:
        identity = _identity(source)
        if text_hash(source['body']) != identity.content_sha256 or identity.key in authoritative:
            raise StateInvalid('Migration requires unique independently fetched exact source bodies')
        authoritative[identity.key] = copy.deepcopy(source)
        source_origins[identity.key] = {'commit_sha': main_sha, 'path': 'src/data/posts.json'}
    # Historical source bodies explain old uploads; only current-main sources
    # may establish the active daily binding. The caller must read these exact
    # Git blobs and verify main ancestry before providing the provenance.
    current_sources = copy.deepcopy(authoritative)
    for historical in historical_sources or []:
        require_sha(historical['commit_sha'], 40); require_sha(historical['blob_sha'], 40)
        source = historical['source']; identity = _identity(source)
        if text_hash(source['body']) != identity.content_sha256:
            raise StateInvalid('Historical Git source body does not match its exact identity')
        if identity.key in authoritative:
            if authoritative[identity.key] != source:
                raise StateInvalid('One source hash has conflicting metadata; explicit adjudication required')
            continue
        authoritative[identity.key] = copy.deepcopy(source)
        source_origins[identity.key] = {key: historical[key] for key in ('commit_sha', 'blob_sha')}
        source_origins[identity.key]['path'] = 'src/data/posts.json'
    migration['source_git_origins'] = copy.deepcopy(source_origins)
    expected_items = {}
    records = [(controller, None), *((record, None) for record in (controller.get('backlog') or []))]
    targeted = controller.get('targeted_media_recovery')
    if targeted is not None:
        if not isinstance(targeted, dict):
            raise StateInvalid('Malformed targeted media recovery claim')
        # Targeted recovery bypasses the daily article cycle. Its root media
        # belongs only to the independently matched full source, never the
        # unrelated in-progress daily article PR or the current cycle date.
        daily = copy.deepcopy(controller)
        for name in ('long_video', 'short', 'media'):
            daily.pop(name, None)
        records[0] = (daily, None)
        source_claim = {name: targeted.get(name) for name in ('slug', 'content_sha256')}
        matches = [source for source in authoritative.values()
                   if source['slug'] == source_claim['slug'] and source['content_sha256'] == source_claim['content_sha256']]
        if len(matches) != 1:
            unresolved = _unresolved_record(controller)
            unresolved.update(failure_class='LEGACY_TARGETED_SOURCE_UNRESOLVED', source_claim=source_claim)
            state['quarantine'].append(unresolved)
            for kind, name in [('overview', 'long_video'), ('short', 'short')]:
                stage = controller.get(name) or {}
                if stage.get('youtube_id'):
                    migration['observed_youtube_ids'].setdefault(stage['youtube_id'], []).append({
                        'origin': 'controller', 'source_claim': source_claim, 'kind': kind, 'item_id': stage.get('item_id')})
        else:
            source = matches[0]
            media_record = {name: copy.deepcopy(controller.get(name) or {}) for name in ('long_video', 'short')}
            media_record['article'] = {'slug': source['slug'], 'published_date': source['date'],
                                       'quality_content_sha256': source['content_sha256']}
            records.append((media_record, source))
    for record, exact_source in records:
        article = record.get('article') or {}
        slot = article.get('published_date') or record.get('cycle')
        slug = article.get('slug')
        matches = [(key, source) for key, source in current_sources.items() if source['date'] == slot and source['slug'] == slug]
        if not matches and exact_source is None:
            unresolved = _unresolved_record(record)
            if article or any(unresolved['stages'].values()):
                migration['unresolved_controller_records'].append(unresolved)
            if slug or any(any(stage.get(field) for field in STAGE_IDS) for stage in unresolved['stages'].values()):
                state['quarantine'].append({'failure_class': 'LEGACY_SOURCE_UNRESOLVED', 'slot': slot, 'slug': slug,
                                            **unresolved})
            continue
        if len(matches) > 1:
            raise StateInvalid('Ambiguous authoritative migration slot/source')
        source = matches[0][1] if matches else exact_source
        identity = _identity(source)
        if matches:
            active = state['slots'].get(identity.slot, {}).get('source_key')
            if active and active != identity.key:
                raise StateInvalid('Legacy records disagree about the adopted daily article')
            state = bind_source(state, identity, now=now, previous_source_key=active)
            migration = state['migration']
            state['slots'][identity.slot]['complete'] = False
        quality_hash = article.get('quality_content_sha256') or identity.content_sha256
        require_sha(quality_hash)
        claimed_source = SourceIdentity(identity.slot, identity.slug, quality_hash)
        media = record.get('media') or {}
        for kind, legacy_name in [('overview', 'long_video'), ('short', 'short')]:
            stage = record.get(legacy_name) or media.get(legacy_name) or media.get(kind) or {}
            target = MediaIdentity(claimed_source, kind)
            migration['legacy_stage_budgets'][target.key] = {name: copy.deepcopy(stage[name]) for name in BUDGET_FIELDS if name in stage}
            if any(stage.get(name) for name in STAGE_IDS):
                migration['legacy_stage_claims'].setdefault(target.key, []).append({'target': target.to_dict(), **_stage_claim(stage)})
            if stage.get('item_id'):
                expected = MediaIdentity(claimed_source, kind).to_dict()
                if stage['item_id'] in expected_items and expected_items[stage['item_id']] != expected:
                    raise StateInvalid('One legacy item is claimed by multiple source/kind stages')
                expected_items[stage['item_id']] = expected
            if stage.get('youtube_id'):
                migration['observed_youtube_ids'].setdefault(stage['youtube_id'], []).append({
                    'origin': 'controller', 'target': MediaIdentity(claimed_source, kind).to_dict(), 'item_id': stage.get('item_id')})
    groups, sealed = {}, {}
    for artifact in artifacts:
        require_sha(artifact['archive_sha256'])
        if type(artifact['artifact_id']) is not int or artifact['artifact_id'] <= 0 or not artifact.get('run_id'):
            raise StateInvalid('Legacy archive must have an exact service ID/digest/producer')
        origin = {key: artifact[key] for key in ('artifact_id', 'archive_sha256', 'run_id')}
        migration['artifacts'].append(origin)
        for original in artifact['items']:
            item_id = original.get('id')
            candidate = {'origin': origin, 'item_id': item_id, 'legacy_item_sha256': digest(original)}
            if original.get('youtube_id'):
                migration['observed_youtube_ids'].setdefault(original['youtube_id'], []).append(copy.deepcopy(candidate))
            try:
                unresolved_reason = 'invalid_source_or_kind'
                source_identity = _identity(original['source'])
                kind = {value: key for key, value in ITEM_TYPES.items()}[original['type']]
                target = MediaIdentity(source_identity, kind)
                candidate['target'] = target.to_dict()
                if original.get('youtube_id'):
                    migration['observed_youtube_ids'][original['youtube_id']][-1]['target'] = target.to_dict()
                unresolved_reason = 'exact_git_source_missing'
                source = authoritative[source_identity.key]
                unresolved_reason = 'controller_worker_identity_disagreement'
                if item_id in expected_items and expected_items[item_id] != target.to_dict():
                    raise ValueError('Controller/worker identity disagreement')
                for field in ('id', 'slug', 'date', 'title', 'category', 'subcategory', 'excerpt', 'canonical_url', 'content_sha256'):
                    if field in original['source'] and original['source'][field] != source[field]:
                        unresolved_reason = 'source_metadata_changed:' + field
                        raise ValueError('Legacy source metadata differs from exact Git source')
                item = {name: copy.deepcopy(value) for name, value in original.items() if name not in VOLATILE}
                capabilities = {}
                if item.get('upload_session_uri'):
                    if capability_sealer is None:
                        state['quarantine'].append({'failure_class': 'LEGACY_UPLOAD_CAPABILITY_REQUIRES_SEALING', **candidate})
                        continue
                    uri = item.pop('upload_session_uri')
                    cache_key = (target.key, digest(uri))
                    if cache_key not in sealed:
                        sealed[cache_key] = capability_sealer(uri, target)
                    envelope = sealed[cache_key]
                    reference = digest(envelope)
                    item['upload_capability_sha256'] = reference
                    capabilities[reference] = envelope
                else:
                    item.pop('upload_session_uri', None)
                item['source'] = copy.deepcopy(source)
                public_evidence(item)
            except StateInvalid:
                raise
            except (ValueError, KeyError, TypeError):
                state['quarantine'].append({'failure_class': 'LEGACY_IDENTITY_UNRESOLVED', 'reason': unresolved_reason, **candidate})
                continue
            if original.get('youtube_id'):
                migration['observed_youtube_ids'][original['youtube_id']][-1]['target'] = target.to_dict()
            candidate.update(target=target.to_dict(), item=item, capabilities=capabilities)
            groups.setdefault(target.key, []).append(candidate)
    for key, candidates in groups.items():
        target_data = candidates[0]['target']
        source = authoritative[_identity(candidates[0]['item']['source']).key]
        identity = _identity(source); target = MediaIdentity(identity, target_data['kind'])
        # Untracked historical uploads still need an immutable ownership registry;
        # they do not become scheduled backlog or acquire an active slot binding.
        state['sources'].setdefault(identity.key, {'identity': identity.to_dict(), 'adopted_at': now, 'article': {}})
        state['items'].setdefault(key, {'identity': target_data, 'phase': None, 'receipts': {}})
        uploaded = [candidate for candidate in candidates if candidate['item'].get('youtube_id')]
        video_ids = {candidate['item']['youtube_id'] for candidate in uploaded}
        if len(video_ids) > 1:
            state['quarantine'].append({'failure_class': 'DUPLICATE_UPLOAD', 'target': target_data,
                                        'youtube_ids': sorted(video_ids)})
            continue
        selected = uploaded if uploaded else candidates
        variants = {digest(candidate['item']): candidate for candidate in selected}
        if len(variants) != 1:
            state['quarantine'].append({'failure_class': 'LEGACY_MEDIA_AMBIGUOUS', 'target': target_data,
                                        'item_sha256': sorted(variants)})
            continue
        candidate = next(iter(variants.values()))
        evidence = {'sequence': 1, 'item': candidate['item'], 'capabilities': candidate['capabilities'], 'legacy_import': {
            'origins': [{**row['origin'], 'legacy_item_sha256': row['legacy_item_sha256'], 'item_id': row['item_id']}
                        for row in selected], 'item_sha256': digest(candidate['item']),
            'controller_blob_sha': controller_sha, 'verified_source_sha256': identity.content_sha256}}
        evidence['legacy_import']['source_git_origin'] = source_origins[identity.key]
        state['items'][key]['receipts']['legacy:' + digest(evidence)] = evidence
    # A controller-only provider/upload claim is not permission to start anew.
    # Even an otherwise valid archive cannot hide a conflicting remote identity.
    for key, claims in migration['legacy_stage_claims'].items():
        receipts = state['items'].get(key, {}).get('receipts', {}).values()
        baselines = [row['item'] for row in receipts if row.get('legacy_import')]
        for claim in claims:
            ids = {('id' if name == 'item_id' else name): claim[name]
                   for name in ('item_id', 'source_id', 'task_id', 'artifact_id', 'youtube_id') if claim.get(name)}
            if not baselines or not any(all(item.get(name) == value for name, value in ids.items()) for item in baselines):
                state['quarantine'].append({'failure_class': 'LEGACY_STAGE_EVIDENCE_UNRESOLVED',
                                            'target': claim['target'], 'claim_sha256': digest(claim)})
    state['audit'].append({'at': now, 'event': 'legacy_migration_prepared', 'controller_blob_sha': controller_sha,
                           'public_completion_inferred': False})
    validate_state(state)
    return state
