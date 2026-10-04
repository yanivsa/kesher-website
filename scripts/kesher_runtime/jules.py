"""Bounded Jules transport and durable exact-request session adoption.

Session create has no documented idempotency key. An unanswered persisted
request is read/reconciled, never sent again. A confirmed HTTP rejection permits
at most three attempts. API bodies, keys and signed URLs never enter exceptions.
Reference: https://developers.google.com/jules/api/reference/rest/v1alpha/sessions
"""
from __future__ import annotations

import copy
import http.client
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .identity import canonical_json, digest
from .state import StateInvalid


class JulesError(RuntimeError):
    def __init__(self, failure_class: str, *, status: int | None = None, uncertain: bool = False):
        self.failure_class, self.status, self.uncertain = failure_class, status, uncertain
        super().__init__(failure_class)


def session_name(row: dict) -> str:
    name = row.get('name') if isinstance(row, dict) else None
    if not isinstance(name, str) or not re.fullmatch(r'sessions/[A-Za-z0-9_-]+', name):
        raise JulesError('JULES_IDENTITY_MISMATCH')
    return name


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Jules:
    def __init__(self, api_key: str, *, opener=None, sleeper=time.sleep):
        if not api_key:
            raise JulesError('AUTH_EXPIRED')
        self._key = api_key
        self._open = opener or urllib.request.build_opener(_NoRedirect()).open
        self._sleep = sleeper

    def request(self, method: str, path: str, body: dict | None = None):
        if method not in {'GET', 'POST'} or not path.startswith('/sessions') or '\n' in path:
            raise ValueError('Unsupported Jules API operation')
        reading = method == 'GET'
        attempts = 4 if reading else 1
        for attempt in range(attempts):
            request = urllib.request.Request('https://jules.googleapis.com/v1alpha' + path,
                data=canonical_json(body).encode() if body is not None else None, method=method,
                headers={'x-goog-api-key': self._key, 'Content-Type': 'application/json'})
            try:
                with self._open(request, timeout=45) as response:
                    result = json.loads(response.read())
                if not isinstance(result, dict):
                    raise ValueError('Invalid JSON object')
                return result
            except urllib.error.HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get('Retry-After', '') if exc.headers else ''
                exc.close()
                failure = {401: 'AUTH_EXPIRED', 403: 'AUTH_SCOPE_INVALID', 404: 'JULES_SESSION_MISSING'}.get(status, 'TRANSIENT_API')
                transient = status in {408, 429, 500, 502, 503, 504}
                error = JulesError(failure, status=status, uncertain=not reading and status in {408, 500, 502, 503, 504})
                if not reading or not transient or (retry_after.isdigit() and int(retry_after) > 30):
                    raise error from None
            except (OSError, http.client.HTTPException, ValueError) as exc:
                error = JulesError('TRANSIENT_API', uncertain=not reading)
                if not reading:
                    raise error from None
                retry_after = ''
            if attempt == attempts - 1:
                raise error from None
            self._sleep(max(2**attempt, int(retry_after) if retry_after.isdigit() else 0))
        raise AssertionError('Unreachable retry loop')

    def sessions(self) -> list[dict]:
        rows, names, tokens = [], set(), set()
        token = ''
        for _ in range(100):
            query = {'pageSize': 100, **({'pageToken': token} if token else {})}
            response = self.request('GET', '/sessions?' + urllib.parse.urlencode(query))
            batch = response.get('sessions', [])
            if not isinstance(batch, list):
                raise JulesError('JULES_INVENTORY_INVALID')
            for row in batch:
                name = session_name(row)
                if name in names:
                    raise JulesError('JULES_INVENTORY_INVALID')
                names.add(name); rows.append(row)
            token = response.get('nextPageToken', '')
            if not token:
                return rows
            if not isinstance(token, str) or token in tokens:
                raise JulesError('JULES_INVENTORY_INVALID')
            tokens.add(token)
        raise JulesError('JULES_INVENTORY_INVALID')

    def get(self, name: str) -> dict:
        session_name({'name': name})
        return self.request('GET', '/' + name)

    def create(self, request: dict) -> dict:
        return self.request('POST', '/sessions', request)


def _match(row: dict, request: dict) -> None:
    session_name(row)
    # requirePlanApproval and automationMode are input-only, not required in GET.
    if any(row.get(key) != request[key] for key in ('title', 'prompt', 'sourceContext')):
        raise JulesError('JULES_IDENTITY_MISMATCH')


def _inventory(api, request: dict) -> dict | None:
    matches = []
    for row in api.sessions():
        if row.get('title') != request['title']:
            continue
        name = session_name(row)
        row = api.get(name)
        if session_name(row) != name:
            raise JulesError('JULES_IDENTITY_MISMATCH')
        _match(row, request)
        matches.append(row)
    if len(matches) > 1:
        raise JulesError('JULES_DUPLICATE_SESSIONS')
    return matches[0] if matches else None


def acquire_session(context, api, proposed_request: dict) -> dict:
    """Resume the original request even after trusted policy/code changes."""
    state = context.store.load().state
    previous = [effect for command in state['commands'].values()
                if command['target'] == context.target.to_dict()
                for name, effect in command['effects'].items() if re.fullmatch(r'jules_create_[1-3]', name)]
    requests = {effect['request_sha256']: effect['request'] for effect in previous}
    if len(requests) > 1:
        raise StateInvalid('Conflicting Jules creation requests for one target')
    request = copy.deepcopy(next(iter(requests.values()), proposed_request))
    existing = _inventory(api, request)
    for ordinal in range(1, 4):
        name = f'jules_create_{ordinal}'
        decision = context.begin_effect(name, request)
        receipt = decision.receipt
        if receipt and receipt.get('status') == 'rejected':
            continue
        if receipt:
            if receipt.get('request_sha256') != digest(request):
                raise JulesError('JULES_IDENTITY_MISMATCH')
            observed = api.get(receipt['session_name'])
            _match(observed, request)
            if session_name(observed) != receipt['session_name'] or (existing and existing['name'] != observed['name']):
                raise JulesError('JULES_DUPLICATE_SESSIONS')
            return observed
        if existing is None:
            if not decision.execute:
                raise JulesError('JULES_CREATE_UNCERTAIN', uncertain=True)
            try:
                existing = api.create(request)
                _match(existing, request)
            except JulesError as exc:
                if not exc.uncertain and exc.status is not None:
                    context.complete_effect(name, {'status': 'rejected', 'http_status': exc.status,
                                                  'failure_class': exc.failure_class})
                    raise
                # Even a malformed response may represent accepted work.
                existing = _inventory(api, request)
                if existing is None:
                    raise JulesError('JULES_CREATE_UNCERTAIN', uncertain=True) from None
        context.complete_effect(name, {'status': 'accepted', 'session_name': session_name(existing),
                                      'request_sha256': digest(request)})
        return existing
    raise JulesError('JULES_CREATE_EXHAUSTED')
