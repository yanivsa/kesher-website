"""Source-derived publication metadata and independent remote observation.

YouTube limits: https://developers.google.com/youtube/v3/docs/videos#snippet
Public completion additionally requires processing/visibility and media provenance;
matching local metadata or finding a URL substring is never enough.
"""
from __future__ import annotations

from .identity import MediaIdentity, SourceIdentity, digest

SITE_URL = 'https://kesher.saharoni.com'
YOUTUBE_CHANNEL_ID = 'UCx5fEFvdVf28HLAR2dFW64Q'
VERIFIER_VERSION = 1
SHORT_TITLE_PREFIX = 'בקצרה: '


class VerificationError(ValueError):
    pass


def publication_metadata(source: dict, kind: str) -> dict:
    if kind not in {'overview', 'short'}:
        raise VerificationError('Explicit overview/short kind required')
    title = str(source.get('title') or '').strip()
    slug = str(source.get('slug') or source.get('id') or '').strip()
    url = str(source.get('canonical_url') or '').strip()
    excerpt = str(source.get('excerpt') or '').strip()
    if not title or not slug or url != f'{SITE_URL}/blog/{slug}':
        raise VerificationError('Source title and exact canonical article URL required')
    prefix = SHORT_TITLE_PREFIX if kind == 'short' else ''
    title = prefix + title[:100 - len(prefix)]
    # Reserve complete URLs first, then fit UTF-8 prose into YouTube's byte
    # limit. Cutting the whole description can silently sever an article URL.
    suffix = f'\n\nלקריאת המאמר המלא:\n{url}\n\nלאתר קשר:\n{SITE_URL}'
    available = 5000 - len(suffix.encode('utf-8'))
    if available < 0:
        raise VerificationError('Canonical links exceed YouTube description limit')
    excerpt = excerpt.encode('utf-8')[:available].decode('utf-8', errors='ignore').rstrip()
    description = (excerpt + suffix).strip()
    if any(char in title + description for char in '<>'):
        raise VerificationError('YouTube metadata contains unsupported angle brackets')
    tags = list(dict.fromkeys(str(source.get(key) or '').strip() for key in ('category', 'subcategory')))
    return {'title': title, 'description': description, 'tags': [tag for tag in tags if tag]}


def match_youtube_metadata(item: dict, row: dict) -> dict:
    """Validate both the local expectation and the remotely fetched resource."""
    kind = {'video_overview': 'overview', 'article_short': 'short'}.get(item.get('type'))
    if kind is None:
        raise VerificationError('Media kind missing or ambiguous')
    source = item.get('source') or {}
    try:
        identity = MediaIdentity(SourceIdentity(source['date'], source['slug'], source['content_sha256']), kind)
    except (KeyError, TypeError, ValueError) as exc:
        raise VerificationError('Full immutable source identity required for public verification') from exc
    expected = publication_metadata(source, kind)
    local = item.get('youtube_metadata') or {}
    if any(local.get(field) != expected[field] for field in ('title', 'description')):
        raise VerificationError('PUBLIC_METADATA_INVALID: local metadata differs from authoritative source contract')
    if not item.get('youtube_id') or row.get('id') != item['youtube_id']:
        raise VerificationError('PUBLIC_METADATA_INVALID: returned YouTube resource ID differs from requested upload')
    snippet = row.get('snippet') or {}
    if snippet.get('channelId') != YOUTUBE_CHANNEL_ID:
        raise VerificationError('PUBLIC_METADATA_INVALID: wrong YouTube channel')
    for field in ('title', 'description'):
        if snippet.get(field) != expected[field]:
            raise VerificationError(f'PUBLIC_METADATA_INVALID: remote {field} differs from authoritative metadata')
    if snippet.get('defaultLanguage') != 'he' or snippet.get('defaultAudioLanguage') != 'he':
        raise VerificationError('PUBLIC_METADATA_INVALID: remote metadata/audio language is not Hebrew')
    if sorted(snippet.get('tags') or []) != sorted(expected['tags']):
        raise VerificationError('PUBLIC_METADATA_INVALID: remote tags differ from source-derived tags')
    return {
        'verifier_version': VERIFIER_VERSION, 'identity': identity.to_dict(),
        'slug': identity.source.slug, 'content_sha256': identity.source.content_sha256, 'kind': kind,
        'remote_title': snippet['title'], 'remote_description': snippet['description'],
        'remote_tags': snippet.get('tags') or [], 'metadata_sha256': digest(expected),
        'article_url': source['canonical_url'], 'site_url': SITE_URL,
    }
