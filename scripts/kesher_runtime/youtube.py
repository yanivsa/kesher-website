"""Repair remote metadata on an already-bound YouTube ID, then read it back.

Only the snippet part is updated; category is preserved, and visibility is not
implicitly reset. See https://developers.google.com/youtube/v3/docs/videos/update.
An ambiguous update is reconciled with a GET before any further mutation.
"""
from __future__ import annotations

from .identity import digest
from .media_state import CanonicalMediaState
from .state import StateInvalid
from .verification import VerificationError, YOUTUBE_CHANNEL_ID, match_youtube_metadata, publication_metadata


def repair_metadata(state: CanonicalMediaState, core, token: str) -> dict:
    item = state.item
    video_id = item.get('youtube_id')
    if not video_id:
        raise StateInvalid('Metadata repair requires an existing exact video ID')
    expected = publication_metadata(item['source'], state.context.target.kind)
    item['youtube_metadata'] = expected
    state.persist()
    rows = core.youtube_get('videos', token, {'part': 'snippet,status,processingDetails', 'id': video_id}).get('items') or []
    if len(rows) != 1 or rows[0].get('id') != video_id or (rows[0].get('snippet') or {}).get('channelId') != YOUTUBE_CHANNEL_ID:
        raise StateInvalid('Metadata repair cannot rebind a missing, foreign or ambiguous video')
    remote = rows[0]['snippet']
    snippet = {**expected, 'categoryId': str(remote.get('categoryId') or '22'),
               'defaultLanguage': 'he', 'defaultAudioLanguage': 'he'}
    request = {'id': video_id, 'snippet': snippet}
    try:
        match_youtube_metadata(item, rows[0])
        matches = True
    except VerificationError:
        matches = False

    def update():
        response = core.requests.put('https://www.googleapis.com/youtube/v3/videos',
                                     params={'part': 'snippet'}, json=request,
                                     headers={'Authorization': f'Bearer {token}'}, timeout=60)
        if response.status_code != 200:
            raise StateInvalid(f'YOUTUBE_METADATA_HTTP_{response.status_code}')
        if response.json().get('id') != video_id:
            raise StateInvalid('YOUTUBE_METADATA_RECEIPT_UNCERTAIN')
        return {'video_id': video_id, 'metadata_sha256': digest(expected)}

    if not matches:
        state.external('youtube_metadata', request, update)
    else:
        # Recover an accepted PUT whose response/checkpoint was lost. Avoid
        # inventing an intent when the remote video already needed no change.
        commands = state.context.store.load().state['commands'].values()
        if any(command['target'] == state.context.target.to_dict()
               and command['effects'].get('youtube_metadata', {}).get('request') == request for command in commands):
            decision = state.context.begin_effect('youtube_metadata', request)
            if decision.receipt is None:
                state.context.complete_effect('youtube_metadata', {'video_id': video_id, 'metadata_sha256': digest(expected)})

    proof = core.verify_public_upload(item, token, timeout_seconds=0)
    semantic = {key: value for key, value in proof.items() if key != 'verified_at'}
    item['youtube_verification'] = semantic
    item.update(uploaded=True, status='uploaded', youtube_url=f'https://youtu.be/{video_id}')
    item.pop('upload_session_uri', None)
    state.persist()
    state.context.checkpoint('remote_metadata_' + digest(semantic)[:40], semantic, phase='PUBLISHED')
    return proof
