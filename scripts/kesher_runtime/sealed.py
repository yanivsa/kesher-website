"""Authenticated storage for a resumable-upload capability, never plaintext state.

AES-GCM authenticates the repository, immutable target and capability purpose.
Each envelope gets an independent random salt and nonce. The existing Actions
state-encryption secret is domain-separated with scrypt; it is not logged/stored.
"""
from __future__ import annotations

import base64
import hashlib
import os

from .identity import Identity, canonical_json
from .state import StateInvalid


def _key(secret: str, salt: bytes) -> bytes:
    if not isinstance(secret, str) or len(secret) < 24:
        raise StateInvalid('CAPABILITY_KEY_UNAVAILABLE: state encryption secret is required')
    return hashlib.scrypt(secret.encode(), salt=b'kesher-capability-v1:' + salt,
                          n=16384, r=8, p=1, dklen=32)


def _aad(target: Identity, repo: str, purpose: str) -> bytes:
    return canonical_json({'domain': 'kesher-capability-v1', 'repo': repo,
                           'target': target.to_dict(), 'purpose': purpose}).encode()


def seal(value: str, secret: str, target: Identity, *, repo: str, purpose: str) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not isinstance(value, str) or not value or len(value.encode()) > 16384:
        raise StateInvalid('Invalid capability payload')
    salt, nonce = os.urandom(32), os.urandom(12)
    encrypted = AESGCM(_key(secret, salt)).encrypt(nonce, value.encode(), _aad(target, repo, purpose))
    encode = lambda data: base64.b64encode(data).decode('ascii')
    return {'version': 1, 'algorithm': 'aes256gcm-scrypt-v1', 'salt': encode(salt),
            'nonce': encode(nonce), 'ciphertext': encode(encrypted)}


def unseal(envelope: dict, secret: str, target: Identity, *, repo: str, purpose: str) -> str:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        if (set(envelope) != {'version', 'algorithm', 'salt', 'nonce', 'ciphertext'}
                or envelope['version'] != 1 or envelope['algorithm'] != 'aes256gcm-scrypt-v1'):
            raise ValueError('Unknown envelope')
        salt, nonce, encrypted = [base64.b64decode(envelope[key], validate=True)
                                  for key in ('salt', 'nonce', 'ciphertext')]
        if len(salt) != 32 or len(nonce) != 12 or not 16 < len(encrypted) <= 16400:
            raise ValueError('Invalid envelope length')
        return AESGCM(_key(secret, salt)).decrypt(nonce, encrypted, _aad(target, repo, purpose)).decode()
    except (ValueError, TypeError, KeyError, InvalidTag) as exc:
        raise StateInvalid('CAPABILITY_UNREADABLE: wrong key, target, purpose or damaged encrypted evidence') from exc
