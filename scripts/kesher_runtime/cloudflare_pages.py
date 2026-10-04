"""Pinned Pages asset upload, one-shot deployment creation and safe GET evidence.

Wrangler 4.100.0's deployment command internally retries creation. We use only
its content-addressed asset uploader and issue the deployment POST ourselves.
Raw API results can contain environment secrets: callers receive projections.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from .deployment_artifact import COMPATIBILITY
from .state import timestamp

PROJECT = 'kesher-website'
PROJECT_ID = '41773648-4870-407a-b868-5f05f2a2da57'
WRANGLER_VERSION = '4.100.0'
UUID = r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}'
RESERVED = {'_headers', '_redirects', '_routes.json'}


class PagesError(RuntimeError):
    def __init__(self, failure_class):
        self.failure_class = failure_class
        super().__init__(failure_class)


def deployment_view(row):
    try:
        metadata = row['deployment_trigger']['metadata']
        stage = row['latest_stage']
        if (not re.fullmatch(UUID, row['id']) or row['project_name'] != PROJECT
                or row['environment'] not in {'production', 'preview'}
                or not re.fullmatch(r'https://[a-z0-9-]+\.kesher-website\.pages\.dev', row['url'])
                or not isinstance(metadata['branch'], str) or not isinstance(metadata['commit_message'], str)
                or not isinstance(metadata['commit_hash'], str)
                or stage['name'] not in {'queued', 'initialize', 'clone_repo', 'build', 'deploy'}
                or stage['status'] not in {'idle', 'active', 'success', 'failure', 'canceled'}
                or type(row['is_skipped']) is not bool):
            raise ValueError()
        timestamp(row['created_on'])
        return {'id': row['id'], 'project_name': PROJECT, 'environment': row['environment'], 'url': row['url'],
                'branch': metadata['branch'], 'commit_sha': metadata['commit_hash'], 'marker': metadata['commit_message'],
                'stage': stage['name'], 'status': stage['status'], 'is_skipped': row['is_skipped'],
                'created_on': row['created_on']}
    except (KeyError, ValueError, TypeError):
        raise PagesError('DEPLOY_OBSERVATION_INVALID') from None


class PagesClient:
    project_name = PROJECT
    project_id = PROJECT_ID

    def __init__(self, account_id, token, *, send=None, sleeper=time.sleep, wrangler=None):
        if not re.fullmatch(r'[a-f0-9]{32}', account_id) or not token:
            raise PagesError('DEPLOY_AUTH_MISSING')
        import requests
        self.account_id, self._token = account_id, token
        self._send, self._sleep = send or requests.request, sleeper
        self.wrangler = wrangler or ['npx', '--offline', 'wrangler@' + WRANGLER_VERSION]
        self._root = f'https://api.cloudflare.com/client/v4/accounts/{account_id}/pages/projects/{PROJECT}'

    def request(self, method, suffix='', **kwargs):
        import requests
        if method not in {'GET', 'POST'} or (suffix and not suffix.startswith('/')) or '..' in suffix:
            raise PagesError('DEPLOY_REQUEST_INVALID')
        attempts = 3 if method == 'GET' else 1
        for attempt in range(attempts):
            status = None
            try:
                response = self._send(method, self._root + suffix,
                    headers={'Authorization': 'Bearer ' + self._token}, timeout=(15, 60),
                    allow_redirects=False, **kwargs)
                status = response.status_code
                if 200 <= status < 300:
                    result = response.json()
                    if isinstance(result, dict) and result.get('success') is True and 'result' in result:
                        return result
                    raise PagesError('DEPLOY_OBSERVATION_INVALID' if method == 'GET' else 'DEPLOY_CREATE_UNCERTAIN')
                if status in {401, 403}:
                    raise PagesError('DEPLOY_AUTH_REJECTED')
                if 300 <= status < 400:
                    raise PagesError('DEPLOY_OBSERVATION_INVALID' if method == 'GET' else 'DEPLOY_CREATE_UNCERTAIN')
                if 400 <= status < 500 and status not in {408, 429}:
                    # No redirect, API body or credential is returned to logs.
                    raise PagesError('DEPLOY_OBSERVATION_INVALID' if method == 'GET' else 'DEPLOY_CREATE_REJECTED')
            except (requests.RequestException, OSError, ValueError):
                pass
            if attempt + 1 == attempts:
                raise PagesError('TRANSIENT_API' if method == 'GET' else 'DEPLOY_CREATE_UNCERTAIN') from None
            self._sleep(2 ** attempt)

    def project(self):
        row = self.request('GET')['result']
        try:
            config = row['deployment_configs']['production']
            if row['id'] != PROJECT_ID or row['name'] != PROJECT or row['production_branch'] != 'main':
                raise ValueError()
            compatibility = {'date': config['compatibility_date'], 'flags': config['compatibility_flags']}
            return {'id': row['id'], 'name': row['name'], 'production_branch': row['production_branch'],
                    'compatibility': compatibility, 'canonical_deployment':
                    deployment_view(row['canonical_deployment']) if row.get('canonical_deployment') else None}
        except (KeyError, ValueError, TypeError):
            raise PagesError('DEPLOY_OBSERVATION_INVALID') from None

    def deployment(self, deployment_id):
        if not re.fullmatch(UUID, deployment_id):
            raise PagesError('DEPLOY_OBSERVATION_INVALID')
        row = deployment_view(self.request('GET', '/deployments/' + deployment_id)['result'])
        if row['id'] != deployment_id:
            raise PagesError('DEPLOY_OBSERVATION_INVALID')
        return row

    def inventory(self):
        rows, seen, expected = [], set(), None
        for page in range(1, 101):
            response = self.request('GET', '/deployments', params={'env': 'production', 'page': page, 'per_page': 25})
            batch, info = response.get('result'), response.get('result_info') or {}
            total, pages = info.get('total_count'), info.get('total_pages')
            if (not isinstance(batch, list) or type(total) is not int or total < 0 or type(pages) is not int
                    or pages != max(1, (total+24)//25) or pages > 100
                    or info.get('page') != page or info.get('per_page') != 25 or info.get('count') != len(batch)
                    or len(batch) > 25 or expected is not None and expected != total):
                raise PagesError('DEPLOY_OBSERVATION_INVALID')
            expected = total
            for item in batch:
                row = deployment_view(item)
                if row['id'] in seen or row['environment'] != 'production':
                    raise PagesError('DEPLOY_OBSERVATION_INVALID')
                seen.add(row['id'])
                rows.append(row)
            if page == pages:
                if len(rows) != total:
                    raise PagesError('DEPLOY_OBSERVATION_INVALID')
                return rows
        raise PagesError('DEPLOY_OBSERVATION_INVALID')

    def upload_assets(self, root):
        # Only an asset JWT reaches the CLI. No Pages-create credential or GitHub
        # token is inherited. Reuploading content-addressed assets cannot publish.
        jwt = self.request('GET', '/upload-token')['result'].get('jwt')
        if not isinstance(jwt, str) or not jwt:
            raise PagesError('DEPLOY_AUTH_REJECTED')
        env = {key: value for key, value in os.environ.items() if key in {'PATH', 'HOME', 'TMPDIR', 'SYSTEMROOT'}}
        env.update(CF_PAGES_UPLOAD_JWT=jwt, WRANGLER_SEND_METRICS='false', CI='true')
        with tempfile.TemporaryDirectory(prefix='kesher-pages-assets-') as folder:
            manifest_path = Path(folder)/'manifest.json'
            try:
                subprocess.run(self.wrangler + ['pages', 'project', 'upload', str(root/'dist'),
                    '--output-manifest-path', str(manifest_path)], env=env, check=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
                manifest = json.loads(manifest_path.read_bytes())
            except (OSError, subprocess.SubprocessError, ValueError):
                raise PagesError('DEPLOY_ASSET_UPLOAD_FAILED') from None
        expected = {'/' + path.relative_to(root/'dist').as_posix() for path in (root/'dist').rglob('*')
                    if path.is_file() and path.relative_to(root/'dist').as_posix() not in RESERVED}
        if (not isinstance(manifest, dict) or set(manifest) != expected
                or any(not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value) for value in manifest.values())):
            raise PagesError('DEPLOY_ASSET_MANIFEST_INVALID')
        return manifest

    def create(self, request, root, manifest):
        fields = {'branch': 'main', 'commit_hash': request['code_sha'], 'commit_message': request['marker'],
                  'commit_dirty': 'true', 'manifest': json.dumps(manifest, separators=(',', ':'))}
        paths = {name: root/'dist'/name for name in RESERVED if (root/'dist'/name).exists()}
        paths.update({'_worker.bundle': root/'functions/_worker.bundle',
                      'functions-filepath-routing-config.json': root/'functions/routing.json'})
        files = {name: (name, path.read_bytes(), 'application/octet-stream') for name, path in paths.items()}
        self.request('POST', '/deployments', data=fields, files=files)
        # Always obtain independent GET evidence, even after a normal response.
