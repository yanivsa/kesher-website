"""Independent public media evidence from archived bytes and fresh YouTube reads.

YouTube does not expose an uploaded-file checksum. The durable single upload
session binds the bytes; owner-only fileDetails independently checks their size,
streams and duration. Complete channel inventory detects unbound duplicate work.
https://developers.google.com/youtube/v3/docs/videos#fileDetails
"""
from __future__ import annotations

import math
import re
from urllib.parse import unquote

from .identity import MediaIdentity, SourceIdentity, digest, identity_from_dict, require_sha
from .media_state import _validate_item
from .output_artifacts import descriptor
from .policy import seconds
from .state import timestamp
from .verification import VerificationError, YOUTUBE_CHANNEL_ID, match_youtube_metadata


class MediaVerificationError(VerificationError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def reject(code: str):
    raise MediaVerificationError(code)


def check_inventory(inventory: dict, now: str) -> list[dict]:
    try:
        rows = inventory['videos']
        if (inventory['complete'] is not True or inventory['channel_id'] != YOUTUBE_CHANNEL_ID
                or not 0 <= seconds(now, inventory['observed_at']) <= 300 or not isinstance(rows, list)
                or any(not isinstance(row, dict) or not row.get('id') for row in rows)
                or len({row['id'] for row in rows}) != len(rows)):
            raise ValueError('Incomplete inventory')
    except (KeyError, TypeError, ValueError):
        reject('YOUTUBE_INVENTORY_UNAVAILABLE')
    return rows


def possible_uploads(identity: MediaIdentity, source: dict, inventory: dict,
                     assignments: dict, *, now: str) -> list[str]:
    """Unknown same-article uploads are conflicts, never adopted by title/date."""
    rows = check_inventory(inventory, now)
    matches = []
    for row in rows:
        assigned = assignments.get(row['id'])
        if assigned:
            # Only full canonical history may disambiguate another kind/version.
            other = identity_from_dict(assigned)
            if not isinstance(other, MediaIdentity):
                reject('SOURCE_IDENTITY_MISMATCH')
            if other == identity:
                matches.append(row['id'])
            continue
        snippet = row.get('snippet') or {}
        urls = re.findall(r'https?://[^\s<>]+', str(snippet.get('description') or ''))
        if any(unquote(url).rstrip('/') == source['canonical_url'] for url in urls):
            matches.append(row['id'])
    return sorted(matches)


def _remote_file(remote: dict, technical: dict) -> None:
    details = remote.get('fileDetails')
    if not isinstance(details, dict) or not details:
        reject('REMOTE_MEDIA_UNAVAILABLE')
    try:
        media = technical['media']
        streams = details['videoStreams']
        duration = float(details['durationMs']) / 1000
        public_duration = re.fullmatch(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?',
                                      remote.get('contentDetails', {}).get('duration', ''))
        if not public_duration or not any(public_duration.groups()):
            raise ValueError('Missing public playback duration')
        playback = sum(float(value or 0) * scale for value, scale in zip(public_duration.groups(), (86400, 3600, 60, 1)))
        if (int(details['fileSize']) != technical['final_size_bytes']
                or not math.isfinite(duration) or abs(duration - float(media['duration'])) > .15
                # YouTube reports playback duration rounded to seconds. Checking
                # it also catches later editor trims of the original upload.
                or abs(playback - float(media['duration'])) > 1.0
                or len(streams) != 1 or streams[0]['widthPixels'] != media['width']
                or streams[0]['heightPixels'] != media['height']
                or streams[0].get('rotation', 'none') != 'none'
                or len(details['audioStreams']) != 1 or details['audioStreams'][0]['channelCount'] <= 0):
            raise ValueError('Different remote file')
    except (KeyError, ValueError, TypeError, IndexError, OverflowError):
        reject('REMOTE_MEDIA_MISMATCH')


def verify_media_publication(*, identity: MediaIdentity, source: dict, item: dict,
                             technical: dict, overview: dict | None, remote: dict | None,
                             inventory: dict, assignments: dict, verified_at: str) -> dict:
    from scripts.kesher_e2e_delivery_guard import _short_origin_verified, _signature_verified
    timestamp(verified_at)
    try:
        actual = SourceIdentity(source['date'], source['slug'], source['content_sha256'])
        _validate_item(item, identity)
        if actual != identity.source or source != item['source']:
            raise ValueError('Different authoritative source')
    except (KeyError, TypeError, ValueError):
        reject('SOURCE_IDENTITY_MISMATCH')
    try:
        require_sha(technical['verifier_sha256'])
        if (technical['schema_version'] != 1 or technical['identity'] != identity.to_dict()
                or technical['output_sha256'] != digest(descriptor(identity, item))
                or technical['media'] != item['media']
                or any(technical[field] != item[field] for field in ('raw_sha256', 'final_sha256'))
                or technical['audio_sha256'] != item['audio_provenance']['raw_audio_sha256']
                or not _signature_verified(item)):
            raise ValueError('Missing exact independent byte audit')
    except (KeyError, TypeError, ValueError):
        reject('MEDIA_EVIDENCE_INVALID')
    if identity.kind == 'short':
        fields = ('notebook_id', 'source_id', 'task_id', 'artifact_id', 'raw_sha256')
        if (not overview or overview.get('source') != source or overview.get('type') != 'video_overview'
                or item.get('overview_provider_identity') != {key: overview.get(key) for key in fields}
                or not _short_origin_verified(item)):
            reject('PROVIDER_IDENTITY_MISMATCH')
    video_id = item.get('youtube_id')
    if not video_id or remote is None:
        reject('YOUTUBE_UPLOAD_MISSING')
    try:
        metadata = match_youtube_metadata(item, remote)
    except VerificationError:
        reject('PUBLIC_METADATA_INVALID')
    status, processing = remote.get('status') or {}, remote.get('processingDetails') or {}
    if status.get('uploadStatus') in {'failed', 'rejected', 'deleted'} or processing.get('processingStatus') in {'failed', 'terminated'}:
        reject('YOUTUBE_PROCESSING_FAILED')
    if processing.get('processingStatus') != 'succeeded' or status.get('uploadStatus') != 'processed':
        reject('PUBLIC_PROCESSING_PENDING')
    if status.get('privacyStatus') != 'public':
        reject('YOUTUBE_NOT_PUBLIC')
    _remote_file(remote, technical)
    ids = possible_uploads(identity, source, inventory, assignments, now=verified_at)
    if video_id not in ids:
        reject('YOUTUBE_INVENTORY_UNAVAILABLE')
    if ids != [video_id]:
        reject('DUPLICATE_UPLOAD')
    return {**metadata, 'public_url': f'https://youtu.be/{video_id}', 'video_id': video_id,
            'verified_at': verified_at, 'upload_count': 1, 'technical_sha256': digest(technical),
            'final_sha256': item['final_sha256'], 'channel_id': YOUTUBE_CHANNEL_ID,
            'privacy_status': 'public', 'processing_status': 'succeeded',
            'remote_file_sha256': digest(remote['fileDetails'])}
