"""Read-only channel inventory and exact canonical media observations."""
from __future__ import annotations

from .identity import MediaIdentity, identity_from_dict
from .media_publication import (MediaVerificationError, check_inventory, possible_uploads,
                                reject, verify_media_publication)
from .media_state import snapshots
from .verification import YOUTUBE_CHANNEL_ID


class YouTubeInventory:
    def __init__(self, get):
        self.get = get

    def read(self, *, now: str) -> dict:
        """Paginate the authenticated channel's uploads; never use search/latest."""
        channels = self.get('channels', {'part': 'id,contentDetails', 'mine': 'true'}).get('items') or []
        if len(channels) != 1 or channels[0].get('id') != YOUTUBE_CHANNEL_ID:
            reject('YOUTUBE_CHANNEL_MISMATCH')
        try:
            playlist = channels[0]['contentDetails']['relatedPlaylists']['uploads']
            if not isinstance(playlist, str) or not playlist:
                reject('YOUTUBE_INVENTORY_UNAVAILABLE')
            ids, tokens, page = [], set(), None
            for _ in range(200):
                params = {'part': 'contentDetails', 'playlistId': playlist, 'maxResults': '50'}
                if page:
                    params['pageToken'] = page
                response = self.get('playlistItems', params)
                ids.extend(row['contentDetails']['videoId'] for row in response['items'])
                page = response.get('nextPageToken')
                if not page:
                    break
                if page in tokens:
                    reject('YOUTUBE_INVENTORY_UNAVAILABLE')
                tokens.add(page)
            else:
                reject('YOUTUBE_INVENTORY_UNAVAILABLE')
            if len(ids) != len(set(ids)) or any(not isinstance(key, str) or not key for key in ids):
                reject('YOUTUBE_INVENTORY_UNAVAILABLE')
            videos = []
            for offset in range(0, len(ids), 50):
                batch = ids[offset:offset + 50]
                rows = self.get('videos', {'part': 'snippet,status,processingDetails,contentDetails,fileDetails',
                                          'id': ','.join(batch)}).get('items') or []
                if (len(rows) != len(batch) or {row['id'] for row in rows} != set(batch)
                        or any((row.get('snippet') or {}).get('channelId') != YOUTUBE_CHANNEL_ID for row in rows)):
                    reject('YOUTUBE_INVENTORY_UNAVAILABLE')
                videos.extend(rows)
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, MediaVerificationError):
                raise
            reject('YOUTUBE_INVENTORY_UNAVAILABLE')
        return {'observed_at': now, 'channel_id': YOUTUBE_CHANNEL_ID, 'complete': True, 'videos': videos}


def upload_assignments(state: dict) -> dict:
    """A video ID has one immutable owner across all current/historical snapshots."""
    assigned = {}
    for row in state['items'].values():
        target = identity_from_dict(row['identity'])
        for checkpoint in snapshots(state, target):
            video_id = checkpoint['item'].get('youtube_id')
            if video_id:
                if video_id in assigned and assigned[video_id] != target.to_dict():
                    reject('DUPLICATE_UPLOAD')
                assigned[video_id] = target.to_dict()
    return assigned


UNKNOWN = {'YOUTUBE_INVENTORY_UNAVAILABLE', 'YOUTUBE_CHANNEL_MISMATCH', 'REMOTE_MEDIA_UNAVAILABLE'}
PENDING = {'PUBLIC_PROCESSING_PENDING'}
INVALID_PUBLISHED = {'MEDIA_EVIDENCE_INVALID', 'MEDIA_LINEAGE_INVALID', 'REMOTE_MEDIA_MISMATCH',
                     'PROVIDER_IDENTITY_MISMATCH', 'SOURCE_IDENTITY_MISMATCH'}


def observe_media(state: dict, target: MediaIdentity, source: dict, *, inventory: dict | None,
                  now: str, audit) -> dict:
    item, technical = None, None
    try:
        if inventory is None:
            reject('YOUTUBE_INVENTORY_UNAVAILABLE')
        rows = check_inventory(inventory, now)
        assignments = upload_assignments(state)
        history = snapshots(state, target)
        item = history[-1]['item'] if history else None
        legacy_ids = {video_id for video_id, claims in state.get('migration', {}).get('observed_youtube_ids', {}).items()
                      if any(claim.get('target') == target.to_dict() for claim in claims)}
        if (any(row.get('target') == target.to_dict() for row in state.get('quarantine', []))
                or legacy_ids - ({item['youtube_id']} if item and item.get('youtube_id') else set())):
            reject('LEGACY_EVIDENCE_UNRESOLVED')
        candidates = possible_uploads(target, source, inventory, assignments, now=now)
        if not item or not item.get('youtube_id'):
            if candidates:
                reject('DUPLICATE_UPLOAD')  # Missing local binding never authorizes another insert.
            if item and item.get('status') == 'rejected':
                return {'status': 'failed', 'failure_class': 'MEDIA_INVALID'}
            return {'status': 'pending' if history else 'absent',
                    **({'failure_class': 'PROVIDER_PENDING'} if history else {})}
        remote = next((row for row in rows if row['id'] == item['youtube_id']), None)
        technical = audit(state, target, source, item)
        overview_history = snapshots(state, MediaIdentity(target.source, 'overview')) if target.kind == 'short' else []
        overview = overview_history[-1]['item'] if overview_history else None
        evidence = verify_media_publication(identity=target, source=source, item=item, technical=technical,
            overview=overview, remote=remote, inventory=inventory, assignments=assignments, verified_at=now)
        return {'status': 'verified', 'evidence': evidence, 'technical_evidence': technical}
    except MediaVerificationError as exc:
        code = exc.code
        if code in INVALID_PUBLISHED and item and item.get('youtube_id'):
            # Rebuilding or reinserting cannot fix a published artifact. Preserve
            # its ID and request incident-bound repair/adjudication instead.
            code = 'PUBLISHED_MEDIA_INVALID'
        result = {'status': 'unknown' if code in UNKNOWN else 'pending' if code in PENDING else 'failed',
                  'failure_class': code}
        if technical:
            result['technical_evidence'] = technical
        return result
