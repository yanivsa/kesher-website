"""GitHub transport and snapshot-bound canonical state persistence.

Reading state never creates a branch or migrates schema. A mutation is attempted
once; an uncertain response requires observation, not transport-level replay.
"""
from __future__ import annotations

import base64
import binascii
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .identity import canonical_json, require_sha
from .state import StateConflict, StateInvalid, new_state, validate_state, validate_transition


class GitHubError(RuntimeError):
    def __init__(self, status: int | None, message: str, *, uncertain: bool = False, retry_after: int | None = None):
        self.status = status
        self.uncertain = uncertain
        self.retry_after = retry_after
        super().__init__(f'GITHUB_{status or "NETWORK"}: {message}')


class GitHub:
    def __init__(self, token: str, *, api_root: str = 'https://api.github.com', opener=None, sleeper=time.sleep):
        if not token:
            raise ValueError('GitHub token is required')
        self._token = token
        self.api_root = api_root.rstrip('/')
        self._open = opener or urllib.request.urlopen
        self._sleep = sleeper

    def request(self, method: str, path: str, body: dict | None = None, *, allow_404: bool = False):
        method = method.upper()
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Expected repository API path')
        read_only = method in {'GET', 'HEAD'}
        data = canonical_json(body).encode('utf-8') if body is not None else None
        attempts = 4 if read_only else 1
        for attempt in range(attempts):
            request = urllib.request.Request(self.api_root + path, data=data, method=method, headers={
                'Authorization': 'Bearer ' + self._token,
                'Accept': 'application/vnd.github+json',
                'Content-Type': 'application/json',
                'X-GitHub-Api-Version': '2022-11-28',
                'User-Agent': 'kesher-canonical-controller',
            })
            retry_after = None
            try:
                with self._open(request, timeout=45) as response:
                    payload = response.read()
                try:
                    return json.loads(payload) if payload else {}
                except (ValueError, UnicodeError) as exc:
                    raise GitHubError(None, 'Invalid response; reconcile mutation receipt', uncertain=not read_only) from exc
            except urllib.error.HTTPError as exc:
                if allow_404 and read_only and exc.code == 404:
                    return None
                transient = exc.code in {408, 429, 500, 502, 503, 504}
                header = exc.headers.get('Retry-After', '') if exc.headers else ''
                retry_after = int(header) if header.isdigit() else None
                error = GitHubError(exc.code, 'API request failed', uncertain=not read_only and transient, retry_after=retry_after)
                exc.close()
                if not transient or not read_only or (retry_after is not None and retry_after > 30):
                    raise error from exc
            except (urllib.error.URLError, OSError, http.client.HTTPException) as exc:
                error = GitHubError(None, 'API connection failed', uncertain=not read_only)
                if not read_only:
                    raise error from exc
            if attempt == attempts - 1:
                raise error
            self._sleep(max(2 ** attempt, retry_after or 0))
        raise AssertionError('Unreachable retry loop')


@dataclass(frozen=True, init=False)
class LoadedState:
    """State bytes and their exact observed blob revision cannot drift apart."""
    _encoded: str
    blob_sha: str | None
    store_key: str

    def __init__(self, state: dict, blob_sha: str | None, store_key: str):
        object.__setattr__(self, '_encoded', canonical_json(state))
        object.__setattr__(self, 'blob_sha', blob_sha)
        object.__setattr__(self, 'store_key', store_key)

    @property
    def state(self) -> dict:
        return json.loads(self._encoded)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise StateInvalid('Duplicate state JSON field')
        result[key] = value
    return result


class GitHubStateStore:
    def __init__(self, github: GitHub, repo: str, *, ref: str = 'automation-state',
                 path: str = '.kesher-controller/state.json', allow_missing: bool = False):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('Expected owner/repository')
        self.github = github
        self.repo = repo
        self.ref = ref
        self.path = path
        self.allow_missing = allow_missing
        self.api_path = f'/repos/{repo}/contents/{urllib.parse.quote(path, safe="/")}'
        self.store_key = canonical_json([repo, ref, path])

    def load(self) -> LoadedState:
        payload = self.github.request('GET', self.api_path + '?ref=' + urllib.parse.quote(self.ref, safe=''), allow_404=True)
        if payload is None:
            if not self.allow_missing:
                raise StateInvalid('CANONICAL_STATE_MISSING: explicit bootstrap/migration required')
            return LoadedState(new_state(), None, self.store_key)
        try:
            sha = payload['sha']
            require_sha(sha, 40)
            if payload.get('encoding') == 'none':
                payload = self.github.request('GET', f'/repos/{self.repo}/git/blobs/{sha}')
                if payload.get('sha') != sha:
                    raise StateInvalid('State blob response identity mismatch')
            if payload['encoding'] != 'base64':
                raise StateInvalid('Canonical state is not a readable JSON blob')
            encoded = ''.join(payload['content'].split())
            raw = base64.b64decode(encoded, validate=True)
            state = json.loads(raw, object_pairs_hook=_unique_object)
            validate_state(state)
        except (KeyError, TypeError, AttributeError, ValueError, binascii.Error) as exc:
            if isinstance(exc, StateInvalid):
                raise
            raise StateInvalid('Malformed canonical state blob') from exc
        return LoadedState(state, sha, self.store_key)

    def save(self, loaded: LoadedState, proposed: dict) -> LoadedState:
        if not isinstance(loaded, LoadedState) or loaded.store_key != self.store_key:
            raise StateInvalid('Snapshot belongs to another state location')
        previous = loaded.state
        validate_transition(previous, proposed)
        if canonical_json(proposed) == canonical_json(previous):
            return loaded
        # Copy before incrementing: neither the caller's plan nor its snapshot
        # may acquire the revision of a write that has not succeeded.
        written = json.loads(canonical_json(proposed))
        written['revision'] = previous['revision'] + 1
        body = {'message': f'state: canonical Kesher revision {written["revision"]}',
                'branch': self.ref, 'content': base64.b64encode((canonical_json(written) + '\n').encode()).decode('ascii')}
        if loaded.blob_sha is not None:
            body['sha'] = loaded.blob_sha
        try:
            receipt = self.github.request('PUT', self.api_path, body)
        except GitHubError as exc:
            if exc.status == 409:
                raise StateConflict('Canonical state changed; discard plan and reconcile') from exc
            raise
        try:
            sha = receipt['content']['sha']
            require_sha(sha, 40)
        except (KeyError, TypeError, ValueError) as exc:
            raise GitHubError(None, 'State write receipt missing; reload before proceeding', uncertain=True) from exc
        return LoadedState(written, sha, self.store_key)
