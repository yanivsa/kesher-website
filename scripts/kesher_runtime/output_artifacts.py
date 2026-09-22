"""Immutable exact media bytes, persisted before opening any upload session.

The archive is evidence, not another mutable state store. Its intent/receipt is
in canonical state; restore selects that artifact ID and verifies every byte.
See https://docs.github.com/en/rest/actions/artifacts for immutable API receipts.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

from .identity import MediaIdentity, canonical_json, digest, require_sha
from .state import StateInvalid
from .worker import WorkerContext

MAX_BYTES = 4 * 1024 ** 3
MAX_FILES = 64
# No state.json, credentials, cookies or upload capabilities are archived.
FILE_FIELDS = (
    ('raw_mp4', 'raw_sha256'), ('final_mp4', 'final_sha256'),
    ('manifest_path', 'manifest_sha256'), ('motion_plan_path', 'motion_plan_sha256'),
    ('remotion_props_path', 'remotion_props_sha256'), ('signature_asset', 'signature_sha256'),
    ('signature_video_path', 'signature_video_sha256'), ('visual_review_path', 'visual_review_sha256'),
    ('transcript_path', 'transcript_sha256'), ('source_path', 'source_file_sha256'),
)
BINDINGS = ('id', 'type', 'notebook_id', 'source_id', 'task_id', 'artifact_id',
            'fresh_generation_attempt', 'render_input_sha256')


def sha256_file(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_name(value: str) -> str:
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or any(ord(char) < 32 for char in value) or ':' in value
            or PurePosixPath(value).is_absolute() or str(PurePosixPath(value)) != value
            or any(part in {'', '.', '..'} or part.startswith('.') for part in value.split('/'))):
        raise StateInvalid('Unsafe media output path')
    return value


def local_file(root: Path, name: str) -> Path:
    parts = PurePosixPath(safe_name(name)).parts
    path = root
    if root.is_symlink():
        raise StateInvalid('Output root cannot be a symbolic link')
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise StateInvalid('Output path cannot contain symbolic links')
    return path


def descriptor(target: MediaIdentity, item: dict) -> dict:
    if not isinstance(target, MediaIdentity) or item.get('technical_verified') is not True:
        raise StateInvalid('Only an exact technically validated media item may be archived')
    source = item.get('source') or {}
    if (source.get('slug') != target.source.slug or source.get('date') != target.source.slot
            or source.get('content_sha256') != target.source.content_sha256
            or item.get('type') != {'short': 'article_short', 'overview': 'video_overview'}[target.kind]):
        raise StateInvalid('Output artifact source/kind mismatch')
    files = {}
    for path_key, hash_key in FILE_FIELDS:
        name, expected = item.get(path_key), item.get(hash_key)
        if not name and path_key not in {'raw_mp4', 'final_mp4', 'manifest_path'}:
            continue
        name = safe_name(name)
        require_sha(expected, 64)
        if name in files and files[name] != expected:
            raise StateInvalid('Conflicting output file references')
        files[name] = expected
    for name in item.get('frame_paths') or []:
        expected = (item.get('frame_sha256') or {}).get(name)
        require_sha(expected, 64)
        if safe_name(name) in files and files[name] != expected:
            raise StateInvalid('Conflicting output frame reference')
        files[name] = expected
    if len(files) > MAX_FILES:
        raise StateInvalid('Too many output files')
    return {'identity': target.to_dict(), 'bindings': {key: item.get(key) for key in BINDINGS}, 'files': files}


def _verify_local(root: Path, output: dict) -> dict:
    sizes = {}
    for name, expected in output['files'].items():
        path = local_file(root, name)
        if not path.is_file() or path.stat().st_size <= 0 or sha256_file(path) != expected:
            raise StateInvalid('OUTPUT_BYTES_INVALID: immutable media file is missing or changed')
        sizes[name] = path.stat().st_size
    if sum(sizes.values()) > MAX_BYTES:
        raise StateInvalid('Media output exceeds bounded archive size')
    return sizes


def _effects(context: WorkerContext, output: dict) -> list[dict]:
    matches = []
    for command in context.store.load().state['commands'].values():
        effect = command['effects'].get('output_artifact')
        if command['target'] == context.target.to_dict() and effect and effect['request'].get('output') == output:
            matches.append(effect)
    # Reconciled commands may retain the same exact intent, never competing ones.
    unique = {effect['request_sha256']: effect for effect in matches}
    if len(unique) > 1:
        raise StateInvalid('Conflicting output artifact intents')
    receipts = {canonical_json(effect['receipt']) for effect in matches if effect['receipt'] is not None}
    if len(receipts) > 1:
        raise StateInvalid('Conflicting immutable output artifact receipts')
    return matches


def artifact_name(request: dict) -> str:
    return 'kesher-output-' + digest(request)


def prepare_bundle(context: WorkerContext, item: dict, root: Path, destination: Path) -> dict:
    """Save upload intent before Actions uploads only this declared directory."""
    output = descriptor(context.target, item)
    sizes = _verify_local(root, output)
    prior = _effects(context, output)
    request = prior[0]['request'] if prior else {
        'schema_version': 1, 'repository': context.store.repo, 'command_id': context.command_id,
        'run_id': context.run_id, 'code_sha': context.code_sha, 'output': output, 'sizes': sizes,
    }
    if request['sizes'] != sizes:
        raise StateInvalid('Same output digest has conflicting file sizes')
    decision = context.begin_effect('output_artifact', request)
    if decision.receipt:
        return {'status': 'archived', 'name': artifact_name(request), 'receipt': decision.receipt}
    if not decision.execute:
        return {'status': 'uncertain', 'name': artifact_name(request)}
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'bundle.json').write_text(canonical_json(request), encoding='utf-8')
    for name in sorted(output['files']):
        target = destination / 'files' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_file(root, name), target)
        if sha256_file(target) != output['files'][name]:
            raise StateInvalid('Media bytes changed while packaging')
    return {'status': 'upload', 'name': artifact_name(request)}


def _validate_metadata(request: dict, metadata: dict, run: dict, artifact_id: int) -> dict:
    run_id, attempt = request['run_id'].split('/')
    owner = metadata.get('workflow_run') or {}
    checksum = metadata.get('digest', '')
    if (type(artifact_id) is not int or artifact_id <= 0 or metadata.get('id') != artifact_id
            or metadata.get('name') != artifact_name(request) or metadata.get('expired') is not False
            or owner.get('id') != int(run_id) or owner.get('head_sha') != request['code_sha']
            or owner.get('head_branch') != 'main' or not owner.get('repository_id')
            or owner.get('repository_id') != owner.get('head_repository_id')
            or run.get('id') != int(run_id) or run.get('event') != 'workflow_dispatch'
            or run.get('display_title') != 'kesher-command:' + request['command_id']
            or run.get('head_sha') != request['code_sha'] or run.get('head_branch') != 'main'
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', checksum)
            or type(metadata.get('size_in_bytes')) is not int
            or not 0 < metadata['size_in_bytes'] <= MAX_BYTES):
        raise StateInvalid('OUTPUT_ARTIFACT_INVALID: wrong artifact, producer, code, digest or expiry')
    return {'artifact_id': artifact_id, 'name': metadata['name'], 'archive_sha256': checksum[7:],
            'size_bytes': metadata['size_in_bytes'], 'request_sha256': digest(request)}


def _check_archive(archive: Path, request: dict, receipt: dict, stage: Path) -> None:
    if archive.stat().st_size != receipt['size_bytes'] or sha256_file(archive) != receipt['archive_sha256']:
        raise StateInvalid('OUTPUT_ARCHIVE_INVALID: downloaded archive checksum differs')
    expected = {'files/' + name for name in request['output']['files']} | {'bundle.json'}
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            if len(entries) != len(expected) or {row.filename for row in entries} != expected:
                raise StateInvalid('OUTPUT_ARCHIVE_INVALID: missing, extra or duplicate entries')
            if sum(row.file_size for row in entries) > MAX_BYTES or any(
                    row.flag_bits & 1 or row.is_dir() or stat.S_ISLNK(row.external_attr >> 16)
                    or stat.S_IFMT(row.external_attr >> 16) not in {0, stat.S_IFREG}
                    for row in entries):
                raise StateInvalid('OUTPUT_ARCHIVE_INVALID: unsafe entry or size')
            manifest = zipped.getinfo('bundle.json')
            encoded = canonical_json(request).encode('utf-8')
            if manifest.file_size != len(encoded) or zipped.read(manifest) != encoded:
                raise StateInvalid('OUTPUT_ARCHIVE_INVALID: manifest does not match persisted intent')
            for name, checksum in request['output']['files'].items():
                entry = zipped.getinfo('files/' + safe_name(name))
                if entry.file_size != request['sizes'][name]:
                    raise StateInvalid('OUTPUT_ARCHIVE_INVALID: changed file length')
                path = local_file(stage, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(entry) as src, path.open('xb') as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                if sha256_file(path) != checksum:
                    raise StateInvalid('OUTPUT_ARCHIVE_INVALID: changed media bytes')
    except (zipfile.BadZipFile, RuntimeError, KeyError) as exc:
        raise StateInvalid('OUTPUT_ARCHIVE_INVALID: unreadable archive') from exc


def complete_bundle(context: WorkerContext, artifact_id: int, *, download) -> dict:
    """Read back service metadata AND archive bytes before saving the receipt."""
    command = context.store.load().state['commands'][context.command_id]
    effect = command['effects'].get('output_artifact')
    if not effect:
        raise StateInvalid('Artifact receipt has no persisted upload intent')
    request = effect['request']
    github = context.store.github
    api = f'/repos/{context.store.repo}/actions'
    metadata = github.request('GET', f'{api}/artifacts/{artifact_id}')
    run = github.request('GET', f"{api}/runs/{request['run_id'].split('/')[0]}")
    receipt = _validate_metadata(request, metadata, run, artifact_id)
    with tempfile.TemporaryDirectory(prefix='kesher-archive-check-') as folder:
        root = Path(folder)
        archive = root / 'archive.zip'
        download(artifact_id, archive)
        stage = root / 'verified'
        stage.mkdir()
        _check_archive(archive, request, receipt, stage)
    context.complete_effect('output_artifact', receipt)
    return receipt


def recover_bundle(context: WorkerContext, *, download) -> dict | None:
    """Recover a lost artifact response by exact producer run and manifest name."""
    effect = context.store.load().state['commands'][context.command_id]['effects'].get('output_artifact')
    if not effect:
        return None
    if effect['receipt']:
        return effect['receipt']
    request = effect['request']
    run = request['run_id'].split('/')[0]
    matches = []
    for page in range(1, 101):
        data = context.store.github.request('GET', f'/repos/{context.store.repo}/actions/runs/{run}/artifacts?per_page=100&page={page}')
        rows = data['artifacts']
        matches.extend(row for row in rows if row.get('name') == artifact_name(request))
        if len(rows) < 100:
            break
    else:
        raise StateInvalid('Artifact inventory incomplete; do not guess')
    if len(matches) > 1:
        raise StateInvalid('Duplicate exact output artifacts')
    return complete_bundle(context, matches[0]['id'], download=download) if matches else None


def require_bundle(context: WorkerContext, item: dict, root: Path) -> dict:
    output = descriptor(context.target, item)
    prior = _effects(context, output)
    receipts = [effect for effect in prior if effect['receipt']]
    if not receipts:
        raise StateInvalid('OUTPUT_NOT_DURABLE: archive exact bytes before starting or resuming upload')
    _verify_local(root, output)
    return receipts[0]['receipt']


def restore_bundle(context: WorkerContext, item: dict, root: Path, *, download) -> bool:
    """Validate every archived byte before writing; interrupted restores are safe."""
    output = descriptor(context.target, item)
    prior = _effects(context, output)
    receipts = [effect for effect in prior if effect['receipt']]
    if not receipts:
        return False
    effect = receipts[0]
    # Read the exact artifact again to detect expiry/replacement; never select latest.
    receipt = effect['receipt']
    metadata = context.store.github.request('GET', f"/repos/{context.store.repo}/actions/artifacts/{receipt['artifact_id']}")
    if (metadata.get('expired') is not False or metadata.get('id') != receipt['artifact_id']
            or metadata.get('digest') != 'sha256:' + receipt['archive_sha256']):
        raise StateInvalid('OUTPUT_ARTIFACT_UNAVAILABLE: preserve pending upload and reconcile')
    with tempfile.TemporaryDirectory(prefix='kesher-output-restore-') as folder:
        temp = Path(folder)
        archive = temp / 'archive.zip'
        download(receipt['artifact_id'], archive)
        stage = temp / 'verified'
        stage.mkdir()
        _check_archive(archive, effect['request'], receipt, stage)
        # Check every destination first; a mismatching existing file is not ours
        # to overwrite. No symlink extraction, state or credential restoration.
        for name, checksum in output['files'].items():
            path = local_file(root, name)
            if path.exists() and (not path.is_file() or sha256_file(path) != checksum):
                raise StateInvalid('OUTPUT_RESTORE_CONFLICT: existing file differs from immutable output')
        for name in sorted(output['files']):
            path = local_file(root, name)
            if path.exists():
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
                temporary = Path(handle.name)
            try:
                shutil.copyfile(stage / name, temporary)
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
    return True


def download_actions_artifact(repo: str, token: str, artifact_id: int, destination: Path) -> None:
    """Stream a bounded archive; GitHub credentials never follow the redirect."""
    import requests
    from urllib.parse import urlparse
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or type(artifact_id) is not int or artifact_id <= 0:
        raise StateInvalid('Invalid artifact download identity')
    url = f'https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip'
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28'}
    with requests.get(url, headers=headers, timeout=30, allow_redirects=False) as response:
        if response.status_code != 302:
            raise StateInvalid('OUTPUT_ARTIFACT_UNAVAILABLE: archive redirect unavailable')
        location = response.headers.get('Location', '')
    for _ in range(3):
        parsed = urlparse(location)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise StateInvalid('OUTPUT_ARTIFACT_INVALID: invalid download redirect')
        with requests.get(location, stream=True, timeout=(30, 60), allow_redirects=False) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get('Location', '')
                continue
            if response.status_code != 200:
                raise StateInvalid('OUTPUT_ARTIFACT_UNAVAILABLE: archive download failed')
            size = 0
            with destination.open('xb') as stream:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise StateInvalid('OUTPUT_ARCHIVE_INVALID: archive exceeds size limit')
                    stream.write(chunk)
            return
    raise StateInvalid('OUTPUT_ARTIFACT_INVALID: too many archive redirects')


def main(argv=None) -> int:
    import argparse
    import sys
    from .media_state import snapshots
    from .worker_entry import actions_admission
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'complete', 'restore'))
    parser.add_argument('command_id')
    parser.add_argument('--bundle-dir', type=Path)
    parser.add_argument('--artifact-id', type=int)
    args = parser.parse_args(argv)
    try:
        context = actions_admission(args.command_id, attach=True).context
        if not isinstance(context.target, MediaIdentity):
            raise StateInvalid('Output artifacts require a media identity')
        history = snapshots(context.store.load().state, context.target)
        item = history[-1]['item'] if history else None
        root = Path(os.environ['KESHER_STATE_DIR'])
        token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
        def download(artifact_id, destination):
            download_actions_artifact(context.store.repo, token, artifact_id, destination)
        result = {'status': 'absent'}
        if args.action == 'complete':
            if not args.artifact_id:
                raise StateInvalid('Exact service artifact ID required')
            complete_bundle(context, args.artifact_id, download=download)
            result = {'status': 'archived'}
        elif args.action == 'prepare':
            if not item or not args.bundle_dir:
                raise StateInvalid('Validated item and explicit bundle directory required')
            result = prepare_bundle(context, item, root, args.bundle_dir)
            if result['status'] == 'uncertain':
                receipt = recover_bundle(context, download=download)
                result['status'] = 'archived' if receipt else 'waiting'
                if receipt is None:
                    context.checkpoint('execution_result', {'status': 'waiting',
                        'reason': 'Exact output artifact upload is uncertain; reconcile producer run before publication'}, phase='STARTED')
        elif item and item.get('technical_verified') and not item.get('youtube_id'):
            # An upload can succeed while its subsequent canonical receipt write
            # is interrupted. Recover that exact producer before restoring files.
            prior = _effects(context, descriptor(context.target, item))
            if prior:
                context.begin_effect('output_artifact', prior[0]['request'])
                recover_bundle(context, download=download)
                result['status'] = 'restored' if restore_bundle(context, item, root, download=download) else 'absent'
            if result['status'] == 'absent' and item.get('upload_capability_sha256'):
                raise StateInvalid('UPLOAD_BYTES_UNAVAILABLE: pending upload requires its exact archived bytes')
        if os.environ.get('GITHUB_OUTPUT'):
            with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as stream:
                for key in ('status', 'name'):
                    if key in result:
                        stream.write(key + '=' + result[key] + '\n')
        print('MEDIA_OUTPUT_' + result['status'].upper())
        return 0
    except Exception as exc:
        print('MEDIA_OUTPUT_FAILED:' + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
