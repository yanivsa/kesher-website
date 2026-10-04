"""Exact static/Functions build archive; a receipt requires service byte readback.

Only digests and compact bindings enter canonical state. The immutable archive
contains the complete bounded file inventory, including the public manifest.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .identity import SourceIdentity, canonical_json, digest
from .output_artifacts import sha256_file
from .state import StateInvalid

WORKFLOW = 'kesher-article-deploy.yml'
COMPATIBILITY = {'date': '2026-05-15', 'flags': []}
MAX_FILES = 20004
MAX_FILE_BYTES = 25 * 1024 ** 2
MAX_BYTES = 1024 ** 3
REQUIRED = {'dist/index.html', 'dist/.well-known/kesher-publication.json',
            'dist/_routes.json', 'functions/_worker.bundle', 'functions/routing.json'}


def effect_key(code_sha):
    return 'deployment_artifact_' + code_sha[:24]


def safe_name(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or str(PurePosixPath(name)) != name or PurePosixPath(name).is_absolute()
            or any(part in {'', '.', '..'} for part in name.split('/'))):
        raise StateInvalid('DEPLOY_BUILD_INVALID: unsafe path')
    if name in {'functions/_worker.bundle', 'functions/routing.json'}:
        return name
    if (not name.startswith('dist/') or name == 'dist/_worker.js'
            or any(part.startswith('.') for part in name.split('/')[1:])
            and name != 'dist/.well-known/kesher-publication.json'):
        raise StateInvalid('DEPLOY_BUILD_INVALID: unexpected build file')
    return name


def _inventory(root):
    if root.is_symlink() or not root.is_dir():
        raise StateInvalid('DEPLOY_BUILD_INVALID: invalid build directory')
    files = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise StateInvalid('DEPLOY_BUILD_INVALID: non-regular build path')
        if path.is_dir():
            continue
        name = path.relative_to(root).as_posix()
        if name == 'deployment.json':
            continue
        safe_name(name)
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise StateInvalid('DEPLOY_BUILD_INVALID: file too large')
        files[name] = {'sha256': sha256_file(path), 'size': size}
        if len(files) > MAX_FILES:
            raise StateInvalid('DEPLOY_BUILD_INVALID: too many files')
    if not REQUIRED <= files.keys() or sum(row['size'] for row in files.values()) > MAX_BYTES:
        raise StateInvalid('DEPLOY_BUILD_INVALID: incomplete or oversized build')
    return files


def describe(context, root):
    command = context._owned(context.store.load().state)
    if (not isinstance(context.target, SourceIdentity) or command['operation'] != 'deploy_article'
            or command['inputs'].get('deploy_sha') != context.code_sha):
        raise StateInvalid('DEPLOY_BUILD_INVALID: exact deployment command required')
    files = _inventory(root)
    try:
        manifest = json.loads((root/'dist/.well-known/kesher-publication.json').read_bytes())
        if (manifest['schema_version'] != 1 or manifest['deploy_sha'] != context.code_sha
                or manifest['articles'][context.target.slug]['identity'] != context.target.to_dict()):
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise StateInvalid('DEPLOY_BUILD_INVALID: publication source mismatch') from None
    return {'schema_version': 1, 'repository': context.store.repo, 'code_sha': context.code_sha,
            'source': context.target.to_dict(), 'compatibility': COMPATIBILITY, 'files': files}


def artifact_name(request):
    return 'kesher-deployment-' + digest(request)


def prepare(context, root):
    prior = adopt(context)
    if prior:
        if prior['receipt'] and prior['receipt'].get('status') == 'unavailable':
            raise StateInvalid('DEPLOY_ARCHIVE_REBUILD: producer stopped without an archive')
        return {'status': 'archived' if prior['receipt'] else 'uncertain',
                'name': artifact_name(prior['request']), 'receipt': prior['receipt']}
    history = _prior(context)
    if len({row['request_sha256'] for row in history}) >= 3:
        raise StateInvalid('DEPLOY_ARCHIVE_ATTEMPTS_EXHAUSTED')
    descriptor = describe(context, root)
    request = {'schema_version': 1, 'repository': context.store.repo, 'command_id': context.command_id,
               'run_id': context.run_id, 'code_sha': context.code_sha, 'source': context.target.to_dict(),
               'build_sha256': digest(descriptor), 'file_count': len(descriptor['files']),
               'publication_manifest_sha256': descriptor['files']['dist/.well-known/kesher-publication.json']['sha256'],
               'total_bytes': sum(row['size'] for row in descriptor['files'].values())}
    decision = context.begin_effect(effect_key(context.code_sha), request)
    if decision.receipt:
        return {'status': 'archived', 'name': artifact_name(request), 'receipt': decision.receipt}
    if not decision.execute:
        return {'status': 'uncertain', 'name': artifact_name(request)}
    (root/'deployment.json').write_text(canonical_json(descriptor), encoding='utf-8')
    return {'status': 'upload', 'name': artifact_name(request)}


def _effect(context):
    effect = adopt(context)
    if not effect:
        raise StateInvalid('DEPLOY_ARCHIVE_MISSING: no durable artifact intent')
    return effect


def adopt(context):
    state = context.store.load().state
    key = effect_key(context.code_sha)
    current = context._owned(state)['effects'].get(key)
    if current:
        return current
    matches = _prior(context)
    retired = {effect['request_sha256'] for effect in matches
               if effect['receipt'] and effect['receipt'].get('status') == 'unavailable'}
    matches = [effect for effect in matches if effect['request_sha256'] not in retired]
    requests = {effect['request_sha256']: effect['request'] for effect in matches}
    if len(requests) > 1:
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: conflicting build requests')
    if requests:
        context.begin_effect(key, next(iter(requests.values())))
        return context._owned(context.store.load().state)['effects'][key]
    return None


def _prior(context):
    return [effect for command in context.store.load().state['commands'].values()
            if command['target'] == context.target.to_dict() and command['code_sha'] == context.code_sha
            and (effect := command['effects'].get(effect_key(context.code_sha)))]


def _producer(request, run):
    run_id, attempt = request['run_id'].split('/')
    if (run.get('id') != int(run_id) or run.get('run_attempt') != int(attempt)
            or run.get('head_sha') != request['code_sha'] or run.get('head_branch') != 'main'
            or run.get('event') != 'workflow_dispatch'
            or run.get('display_title') != 'kesher-command:' + request['command_id']
            or run.get('path', '').split('@')[0] != '.github/workflows/' + WORKFLOW):
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: producer identity differs')


def _metadata(context, request, artifact_id):
    github = context.store.github
    api = f'/repos/{context.store.repo}/actions'
    run_id, attempt = request['run_id'].split('/')
    metadata = github.request('GET', f'{api}/artifacts/{artifact_id}')
    run = github.request('GET', f'{api}/runs/{run_id}/attempts/{attempt}')
    _producer(request, run)
    owner = metadata.get('workflow_run') or {}
    if (type(artifact_id) is not int or artifact_id < 1 or metadata.get('id') != artifact_id
            or metadata.get('name') != artifact_name(request) or metadata.get('expired') is not False
            or owner.get('id') != int(run_id) or owner.get('head_sha') != request['code_sha']
            or owner.get('head_branch') != 'main' or not owner.get('repository_id')
            or owner.get('repository_id') != owner.get('head_repository_id')
            or run.get('id') != int(run_id) or run.get('run_attempt') != int(attempt)
            or run.get('head_sha') != request['code_sha'] or run.get('head_branch') != 'main'
            or run.get('event') != 'workflow_dispatch'
            or run.get('display_title') != 'kesher-command:' + request['command_id']
            or run.get('path', '').split('@')[0] != '.github/workflows/' + WORKFLOW
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', metadata.get('digest', ''))
            or type(metadata.get('size_in_bytes')) is not int
            or not 0 < metadata['size_in_bytes'] <= MAX_BYTES):
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: wrong immutable producer or service artifact')
    return {'artifact_id': artifact_id, 'archive_sha256': metadata['digest'][7:],
            'size_bytes': metadata['size_in_bytes'], 'request_sha256': digest(request),
            'publication_manifest_sha256': request['publication_manifest_sha256'],
            'build_sha256': request['build_sha256']}


def _check_archive(archive, request, receipt, stage):
    if archive.stat().st_size != receipt['size_bytes'] or sha256_file(archive) != receipt['archive_sha256']:
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: service digest differs')
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            if (len(entries) != request['file_count'] + 1 or len(entries) > MAX_FILES + 1
                    or sum(row.file_size for row in entries) > MAX_BYTES
                    or any(row.file_size > MAX_FILE_BYTES or row.flag_bits & 1 or row.is_dir()
                           or stat.S_IFMT(row.external_attr >> 16) not in {0, stat.S_IFREG} for row in entries)):
                raise StateInvalid('DEPLOY_ARCHIVE_INVALID: unsafe archive entries')
            encoded = zipped.read('deployment.json')
            descriptor = json.loads(encoded)
            if digest(descriptor) != request['build_sha256'] or encoded != canonical_json(descriptor).encode():
                raise StateInvalid('DEPLOY_ARCHIVE_INVALID: descriptor differs from intent')
            files = descriptor['files']
            if (set(files) | {'deployment.json'} != {row.filename for row in entries}
                    or len(files) != request['file_count'] or not REQUIRED <= files.keys()
                    or sum(row['size'] for row in files.values()) != request['total_bytes']
                    or descriptor.get('code_sha') != request['code_sha']
                    or descriptor.get('repository') != request['repository']
                    or descriptor.get('source') != request['source'] or descriptor.get('compatibility') != COMPATIBILITY):
                raise StateInvalid('DEPLOY_ARCHIVE_INVALID: archive inventory or binding differs')
            if files['dist/.well-known/kesher-publication.json']['sha256'] != request['publication_manifest_sha256']:
                raise StateInvalid('DEPLOY_ARCHIVE_INVALID: public manifest differs')
            for name, row in files.items():
                path = stage/safe_name(name)
                if zipped.getinfo(name).file_size != row['size']:
                    raise StateInvalid('DEPLOY_ARCHIVE_INVALID: file size differs')
                path.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(name) as source, path.open('xb') as destination:
                    shutil.copyfileobj(source, destination, length=1024*1024)
                if sha256_file(path) != row['sha256']:
                    raise StateInvalid('DEPLOY_ARCHIVE_INVALID: file bytes differ')
            (stage/'deployment.json').write_bytes(encoded)
    except (zipfile.BadZipFile, RuntimeError, KeyError, ValueError, TypeError) as exc:
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: unreadable immutable archive') from exc


def complete(context, artifact_id, *, download):
    request = _effect(context)['request']
    receipt = _metadata(context, request, artifact_id)
    with tempfile.TemporaryDirectory(prefix='kesher-deploy-check-') as folder:
        root = Path(folder)
        download(artifact_id, root/'archive.zip')
        _check_archive(root/'archive.zip', request, receipt, root/'files')
    context.complete_effect(effect_key(context.code_sha), receipt)
    return receipt


def recover(context, *, download):
    effect = _effect(context)
    if effect['receipt']:
        return None if effect['receipt'].get('status') == 'unavailable' else effect['receipt']
    request = effect['request']
    matches = []
    seen = set()
    for page in range(1, 101):
        rows = context.store.github.request('GET',
            f'/repos/{context.store.repo}/actions/runs/{request["run_id"].split("/")[0]}/artifacts?per_page=100&page={page}')
        batch = rows.get('artifacts')
        if not isinstance(batch, list) or len(batch) > 100:
            raise StateInvalid('DEPLOY_ARCHIVE_INVALID: incomplete inventory')
        for row in batch:
            key = row.get('id')
            if type(key) is not int or key in seen:
                raise StateInvalid('DEPLOY_ARCHIVE_INVALID: repeated inventory')
            seen.add(key)
            if row.get('name') == artifact_name(request):
                matches.append(row)
        if len(batch) < 100:
            if rows.get('total_count') != len(seen):
                raise StateInvalid('DEPLOY_ARCHIVE_INVALID: inventory count differs')
            break
    else:
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: inventory exceeds bound')
    if len(matches) > 1:
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: duplicate exact artifact')
    if matches:
        return complete(context, matches[0]['id'], download=download)
    run_id, attempt = request['run_id'].split('/')
    run = context.store.github.request('GET', f'/repos/{context.store.repo}/actions/runs/{run_id}/attempts/{attempt}')
    _producer(request, run)
    if (request['run_id'] != context.run_id and run.get('status') == 'completed'
            and run.get('conclusion') in {'success', 'failure', 'cancelled', 'timed_out', 'action_required', 'skipped', 'neutral', 'stale'}):
        # This retires only a non-public byte archive, never a deployment intent.
        # A late service artifact cannot publish and will not be selected later.
        context.complete_effect(effect_key(context.code_sha), {'status': 'unavailable',
            'producer_run': request['run_id'], 'request_sha256': digest(request)})
    return None


def require_archive(context, root):
    effect = _effect(context)
    if not effect['receipt'] or effect['receipt'].get('status') == 'unavailable':
        raise StateInvalid('DEPLOY_ARCHIVE_MISSING: bytes have not been read back')
    if digest(describe(context, root)) != effect['request']['build_sha256']:
        raise StateInvalid('DEPLOY_BUILD_INVALID: build changed after archival')
    return effect['receipt']


def restore(context, destination, *, download):
    effect = _effect(context)
    receipt = recover(context, download=download)
    if not receipt:
        return False
    current = _metadata(context, effect['request'], receipt['artifact_id'])
    if current != receipt:
        raise StateInvalid('DEPLOY_ARCHIVE_INVALID: service receipt changed')
    if destination.exists() or destination.is_symlink():
        require_archive(context, destination)
        return True
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Staging shares the destination filesystem. A crash cannot expose a partial
    # build; a completed rename is safely recognized by a full byte recheck.
    with tempfile.TemporaryDirectory(prefix='.kesher-deploy-restore-', dir=destination.parent) as folder:
        root = Path(folder)
        download(receipt['artifact_id'], root/'archive.zip')
        _check_archive(root/'archive.zip', effect['request'], receipt, root/'files')
        os.replace(root/'files', destination)
    return True
