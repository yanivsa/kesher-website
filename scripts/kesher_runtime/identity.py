"""Immutable identity independent of a pipeline implementation or worker item ID."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()


def require_sha(value: str, length: int = 64) -> None:
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{' + str(length) + '}', value):
        raise ValueError(f'Expected full lowercase {length}-character SHA')


def require_slot(value: str) -> None:
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError('Expected publication slot YYYY-MM-DD')


@dataclass(frozen=True)
class SlotIdentity:
    """An article request before its one authoritative source is adopted."""
    slot: str

    def __post_init__(self) -> None:
        require_slot(self.slot)

    def to_dict(self) -> dict:
        return {'type': 'slot', 'slot': self.slot}

    @property
    def key(self) -> str:
        return 'slot:' + self.slot


@dataclass(frozen=True)
class SourceIdentity:
    slot: str
    slug: str
    content_sha256: str

    def __post_init__(self) -> None:
        require_slot(self.slot)
        require_sha(self.content_sha256)
        if (not isinstance(self.slug, str) or not self.slug or self.slug in {'.', '..'}
                or unicodedata.normalize('NFC', self.slug) != self.slug
                or any(char.isspace() or unicodedata.category(char).startswith('C')
                       or char in '/\\?#%' for char in self.slug)):
            raise ValueError('Expected canonical unencoded single-segment slug')

    def to_dict(self) -> dict:
        return {'type': 'source', 'slot': self.slot, 'slug': self.slug, 'content_sha256': self.content_sha256}

    @property
    def key(self) -> str:
        return 'source:' + digest(self.to_dict())


@dataclass(frozen=True)
class MediaIdentity:
    source: SourceIdentity
    kind: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceIdentity) or self.kind not in {'overview', 'short'}:
            raise ValueError('Media requires full source and explicit overview/short kind')

    @property
    def slot(self) -> str:
        return self.source.slot

    def to_dict(self) -> dict:
        return {**self.source.to_dict(), 'type': 'media', 'kind': self.kind}

    @property
    def key(self) -> str:
        return self.source.key + ':' + self.kind


Identity = SlotIdentity | SourceIdentity | MediaIdentity


def identity_from_dict(value: dict) -> Identity:
    if not isinstance(value, dict):
        raise ValueError('Identity must be an object')
    fields = {
        'slot': {'type', 'slot'},
        'source': {'type', 'slot', 'slug', 'content_sha256'},
        'media': {'type', 'slot', 'slug', 'content_sha256', 'kind'},
    }
    kind = value.get('type')
    if kind not in fields or set(value) != fields[kind]:
        raise ValueError('Partial or unknown identity fields')
    if kind == 'slot':
        return SlotIdentity(value['slot'])
    source = SourceIdentity(value['slot'], value['slug'], value['content_sha256'])
    return MediaIdentity(source, value['kind']) if kind == 'media' else source
