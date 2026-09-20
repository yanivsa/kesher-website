"""Read-only reconciliation of NotebookLM creations with lost responses.

The pinned SDK disables transport retries for text-source/artifact creation.
It exposes full source text and artifact generation_prompt in read APIs. Those
bind recovery to the persisted request; timestamps/latest-task are never proof.
SDK: teng-lin/notebooklm-py@8fb61cb125be9f59dfe163561e355922967c604a.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys

from .identity import digest
from .media_state import CanonicalMediaState
from .state import StateInvalid


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def bind_generation_prompt(state: dict, item: dict, prompt: str, provider_format: str) -> str:
    if not isinstance(state, CanonicalMediaState):
        return prompt
    marker = digest({'target': state.context.target.to_dict(), 'source_id': item['source_id'],
                     'attempt': item.get('fresh_generation_attempt', 1), 'format': provider_format,
                     'instructions_sha256': text_hash(prompt)})
    return prompt + '\n\nמזהה בקרה פנימי, אין להקריא או להציג אותו בסרטון: ' + marker


async def probe_source(client, request: dict) -> dict | None:
    sources = await client.sources.list(request['notebook_id'], strict=True)
    matches = [source for source in sources if source.title == request['title']]
    if not matches:
        return None
    if len(matches) != 1:
        raise StateInvalid('DUPLICATE_PROVIDER_SOURCE: quarantine exact-marker matches')
    source = matches[0]
    full = await client.sources.get_fulltext(request['notebook_id'], source.id)
    content_matches = (text_hash(' '.join(full.content.split())) == request.get('body_normalized_sha256')
                       if request.get('body_normalized_sha256') else text_hash(full.content) == request.get('body_sha256'))
    if full.source_id != source.id or full.title != request['title'] or not content_matches:
        raise StateInvalid('PROVIDER_SOURCE_CONTENT_MISMATCH')
    return {'source_id': source.id}


async def probe_generation(client, request: dict) -> dict | None:
    artifacts = await client.artifacts.list(request['notebook_id'])
    matches = [artifact for artifact in artifacts if artifact.kind == 'video'
               and isinstance(artifact.generation_prompt, str)
               and text_hash(artifact.generation_prompt) == request['prompt_sha256']]
    if not matches:
        return None
    if len(matches) != 1:
        raise StateInvalid('DUPLICATE_PROVIDER_GENERATION: quarantine exact-prompt matches')
    return {'task_id': matches[0].id, 'artifact_id': matches[0].id}


def observe_provider(core, name: str, request: dict) -> dict | None:
    # Use the same fresh-secret auth precedence as the pinned CLI, but list via
    # the SDK once: the human CLI table omits generation_prompt from its JSON.
    result = subprocess.run([sys.executable, '-m', 'scripts.kesher_runtime.provider'],
                            input=json.dumps({'name': name, 'request': request}),
                            env=core.notebooklm_env(), capture_output=True, text=True,
                            timeout=180, check=False)
    if result.returncode != 0:
        raise StateInvalid('PROVIDER_OBSERVATION_FAILED: no new creation authorized')
    try:
        payload = json.loads(result.stdout)
        if set(payload) != {'receipt'} or (payload['receipt'] is not None and not isinstance(payload['receipt'], dict)):
            raise ValueError('Invalid observer receipt')
        return payload['receipt']
    except (TypeError, ValueError, KeyError) as exc:
        raise StateInvalid('PROVIDER_OBSERVATION_INVALID') from exc


def reconcile_provider(state: CanonicalMediaState, observe) -> bool:
    """Adopt prior exact intents/receipts, including after a code-repair command.

    Return False while an ambiguous prior creation is not observable. Lack of
    evidence is not evidence the provider failed to accept it; no new POST.
    """
    for name, fields in [('provider_source', ('source_id',)),
                         ('provider_generation', ('task_id', 'artifact_id'))]:
        commands = state.context.store.load().state['commands'].values()
        effects = [command['effects'][name] for command in commands
                   if command['target'] == state.context.target.to_dict() and name in command['effects']]
        if not effects:
            continue
        requests = {effect['request_sha256']: effect['request'] for effect in effects}
        if len(requests) != 1:
            raise StateInvalid('PROVIDER_ATTEMPT_AMBIGUOUS: explicit attempt migration required')
        request = next(iter(requests.values()))
        decision = state.context.begin_effect(name, request)
        receipt = decision.receipt
        if receipt is None:
            receipt = observe(name, request)
            if receipt is None:
                return False
        if any(not isinstance(receipt.get(field), str) or not receipt[field] for field in fields):
            raise StateInvalid('PROVIDER_RECEIPT_INVALID')
        if name == 'provider_generation' and request['source_id'] != state.item.get('source_id'):
            raise StateInvalid('PROVIDER_GENERATION_SOURCE_MISMATCH')
        if decision.receipt is None:
            state.context.complete_effect(name, receipt)
        item = state.item
        for field in fields:
            if item.get(field) and item[field] != receipt[field]:
                raise StateInvalid('PROVIDER_RECEIPT_CONFLICT: preserve both identities for quarantine')
            item[field] = receipt[field]
        if name == 'provider_source' and item['status'] == 'source_selected':
            item['status'] = 'source_added'
        if name == 'provider_generation':
            if item['status'] in {'source_selected', 'source_added'}:
                item['status'] = 'generating'
                item['generation_prompt_sha256'] = request['prompt_sha256']
                if request.get('prompt'):
                    item['generation_prompt'] = request['prompt']
                if state.context.target.kind == 'short':
                    native = request['format'] == 'short'
                    item.update(provider_video_format=request['format'], provider_native_short=native,
                                provider_short_fallback_used=not native)
        state.persist()
    return True


async def _observe(payload: dict) -> dict:
    from notebooklm import NotebookLMClient
    operation = {'provider_source': probe_source, 'provider_generation': probe_generation}.get(payload['name'])
    if operation is None:
        raise StateInvalid('Unknown read-only provider observation')
    async with NotebookLMClient.from_storage(timeout=45, rate_limit_max_retries=2, server_error_max_retries=2) as client:
        return {'receipt': await operation(client, payload['request'])}


if __name__ == '__main__':
    try:
        print(json.dumps(asyncio.run(_observe(json.load(sys.stdin))), ensure_ascii=False))
    except Exception as exc:
        print(f'PROVIDER_OBSERVATION_FAILED:{type(exc).__name__}', file=sys.stderr)
        raise SystemExit(1)
