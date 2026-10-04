"""Publish one exact archived main build, with a durable one-shot Pages intent.

Cloudflare creation has no documented idempotency key or conditional main fence.
An uncertain intent is observed, never replayed merely because GET is empty.
The controller separately verifies actual public article, HTML and hero bytes.
"""
from __future__ import annotations

from .cloudflare_pages import PagesError, PROJECT, PROJECT_ID
from .deployment_artifact import COMPATIBILITY, require_archive
from .identity import SourceIdentity, digest
from .state import StateInvalid


def stage_build(context, destination):
    """Only trusted-main code runs here, before any Cloudflare secret is loaded."""
    import os
    import re
    import shutil
    import subprocess
    import sys
    from pathlib import Path
    from .deployment_artifact import prepare
    from .cloudflare_pages import WRANGLER_VERSION
    if destination.exists():
        raise StateInvalid('DEPLOY_BUILD_INVALID: build destination already exists')
    dist = Path('dist')
    value = os.environ.get('VITE_GTM_CONTAINER_ID') or 'disabled'
    if value != 'disabled' and not re.fullmatch(r'(?:GTM|G)-[A-Za-z0-9]+', value):
        raise StateInvalid('DEPLOY_MEASUREMENT_INVALID')
    html = list(dist.rglob('*.html'))
    if not html:
        raise StateInvalid('DEPLOY_BUILD_INVALID: no rendered HTML')
    for path in html:
        content = path.read_text(encoding='utf-8')
        path.write_text(content.replace('%VITE_GTM_CONTAINER_ID%', value), encoding='utf-8')
    if f'data-gtm-id="{value}"' not in (dist/'index.html').read_text(encoding='utf-8'):
        raise StateInvalid('DEPLOY_MEASUREMENT_INVALID')
    subprocess.run([sys.executable, 'scripts/kesher_publication_manifest.py', '--dist', str(dist),
                    '--sha', context.code_sha], check=True, timeout=300)
    destination.mkdir()
    shutil.copytree(dist, destination/'dist', symlinks=True)
    functions = destination/'functions'
    functions.mkdir()
    # This command emits the actual multipart bundle consumed by Pages; it does
    # not deploy or read project secrets. Preserve any explicitly supplied routes.
    routes = destination/'dist/_routes.json'
    generated_routes = destination.parent/(destination.name + '-generated-routes.json')
    subprocess.run(['npx', '--offline', 'wrangler@'+WRANGLER_VERSION, 'pages', 'functions', 'build', 'functions',
                    '--outfile', str(functions/'_worker.bundle'), '--output-config-path', str(functions/'routing.json'),
                    '--output-routes-path', str(generated_routes), '--build-output-directory', str(destination/'dist'),
                    '--compatibility-date', COMPATIBILITY['date']], check=True, timeout=300)
    if not routes.exists():
        shutil.copyfile(generated_routes, routes)
    return prepare(context, destination)


def deployment_intents(state):
    found = {}
    for command in state['commands'].values():
        for name, effect in command['effects'].items():
            if not name.startswith('pages_create_'):
                continue
            request = effect['request']
            if name != effect_name(request):
                raise StateInvalid('DEPLOY_INTENT_INVALID')
            found.setdefault(digest(request), request)
    return list(found.values())


def effect_name(request):
    return 'pages_create_' + digest(request)[:32]


def saved_receipt(state, request):
    receipts = [effect['receipt'] for command in state['commands'].values()
                if (effect := command['effects'].get(effect_name(request))) and effect['receipt']]
    if len({digest(row) for row in receipts}) > 1:
        raise StateInvalid('DEPLOY_RECEIPT_CONFLICT')
    return receipts[0] if receipts else None


def settled(state, request):
    key = 'pages_settled_' + digest(request)[:24]
    for command in state['commands'].values():
        row = command['receipts'].get(key, {}).get('evidence')
        if (row and row.get('request_sha256') == digest(request) and row.get('code_sha') == request['code_sha']
                and row.get('build_sha256') == request['build_sha256'] and row.get('deployment_id')
                and row.get('status') in {'deployed', 'superseded', 'failed'}):
            return True
    return False


def record_settled(context, request, result):
    if (result.get('deployment_id') and result['status'] in {'deployed', 'superseded', 'failed'}
            and not settled(context.store.load().state, request)):
        context.checkpoint('pages_settled_' + digest(request)[:24], result, phase='OUTPUT_CREATED')


def observe_request(pages, request, inventory=None):
    rows = pages.inventory() if inventory is None else inventory
    matches = [row for row in rows if row['marker'] == request['marker']]
    if len(matches) > 1:
        raise StateInvalid('DEPLOY_DUPLICATE: exact marker identifies multiple deployments')
    if not matches:
        return {'status': 'waiting', 'failure_class': 'DEPLOY_CREATE_UNCERTAIN'}
    row = pages.deployment(matches[0]['id'])
    if (row['id'] != matches[0]['id'] or row['marker'] != request['marker']
            or row['commit_sha'] != request['code_sha'] or row['branch'] != 'main'
            or row['project_name'] != request['project_name'] or row['environment'] != 'production'
            or pages.account_id != request['account_id'] or pages.project_id != request['project_id']):
        raise StateInvalid('DEPLOY_IDENTITY_MISMATCH')
    identity = {'deployment_id': row['id'], 'code_sha': request['code_sha'],
                'build_sha256': request['build_sha256'], 'request_sha256': digest(request), 'url': row['url']}
    if row['is_skipped'] or row['status'] in {'failure', 'canceled'}:
        return {**identity, 'status': 'failed', 'failure_class': 'DEPLOY_FAILED'}
    if row['stage'] != 'deploy' or row['status'] != 'success':
        return {**identity, 'status': 'waiting', 'failure_class': 'DEPLOY_PENDING'}
    canonical = pages.project()['canonical_deployment']
    if not canonical or canonical['id'] != row['id']:
        return {**identity, 'status': 'superseded', 'failure_class': 'DEPLOY_SUPERSEDED'}
    if canonical != row:
        raise StateInvalid('DEPLOY_OBSERVATION_INVALID')
    return {**identity, 'status': 'deployed'}


def _project(pages):
    project = pages.project()
    if (project['id'] != PROJECT_ID or project['name'] != PROJECT or project['production_branch'] != 'main'
            or project['compatibility'] != COMPATIBILITY):
        raise StateInvalid('DEPLOY_CONFIG_CHANGED')


def _fresh(context, read_main):
    context._owned(context.store.load().state, require_current=True)
    if read_main() != context.code_sha:
        raise StateInvalid('CODE_CHANGED: never publish an older checkout over new main')


def _record(context, request, result):
    if result.get('deployment_id'):
        # Identity is immutable; deploy-stage status and canonical routing change
        # over time and therefore remain fresh observations, not frozen receipts.
        context.complete_effect(effect_name(request), {key: result[key] for key in
            ('deployment_id', 'code_sha', 'build_sha256', 'request_sha256', 'url')})
    record_settled(context, request, result)
    return result


def initialize(context, pages, root, *, download):
    from . import deployment_artifact as archive
    same = sorted((row for row in deployment_intents(context.store.load().state)
                   if row['code_sha'] == context.code_sha), key=lambda row: row['attempt'])
    if same:
        request = same[-1]
        saved = saved_receipt(context.store.load().state, request)
        status = 'failed' if saved and saved.get('status') == 'rejected' else observe_request(pages, request)['status']
        if status != 'failed' or len(same) >= 2:
            return {'status': 'observe'}
        # A fresh runner needs the original bytes and asset-only tooling for a
        # permitted retry. Pure observation deliberately needs neither.
        if not archive.adopt(context):
            raise StateInvalid('DEPLOY_ARCHIVE_MISSING: retry requires original archived build')
    if archive.adopt(context):
        restored = archive.restore(context, root, download=download)
        if not restored:
            receipt = archive.adopt(context)['receipt']
            failure = 'DEPLOY_ARCHIVE_REBUILD' if receipt and receipt.get('status') == 'unavailable' else 'DEPLOY_ARCHIVE_PENDING'
            context.checkpoint('execution_result', {'status': 'waiting', 'failure_class': failure}, phase='STARTED')
        return {'status': 'archived' if restored else 'waiting'}
    return {'status': 'build'}


def publish(context, pages, root, *, read_main):
    command = context._owned(context.store.load().state)
    if (not isinstance(context.target, SourceIdentity) or command['operation'] != 'deploy_article'
            or command['inputs'].get('deploy_sha') != context.code_sha):
        raise StateInvalid('DEPLOY_COMMAND_INVALID')
    intents = deployment_intents(context.store.load().state)
    same = [request for request in intents if request['code_sha'] == context.code_sha]
    same.sort(key=lambda row: row['attempt'])
    if [row['attempt'] for row in same] != list(range(1, len(same)+1)) or len(same) > 2:
        raise StateInvalid('DEPLOY_DUPLICATE: competing intents for one main revision')
    if same:
        request = same[-1]
        context.begin_effect(effect_name(request), request)
        receipt = saved_receipt(context.store.load().state, request)
        result = ({'status': 'failed', 'failure_class': receipt['failure_class']}
                  if receipt and receipt.get('status') == 'rejected' else observe_request(pages, request))
        if result['status'] != 'failed':
            return _record(context, request, result)
        record_settled(context, request, result)
        if len(same) == 2:
            return {'status': 'failed', 'failure_class': 'DEPLOY_ATTEMPTS_EXHAUSTED'}
        # Only an independently observed terminal failure (or a definite HTTP
        # rejection) permits another creation. The per-code budget is durable.
    _fresh(context, read_main)
    _project(pages)
    # An older uncertain request could still publish later. Do not put a newer
    # deployment in flight until all preceding creation requests are settled.
    inventory = pages.inventory() if intents else []
    for request in intents:
        receipt = saved_receipt(context.store.load().state, request)
        if receipt and receipt.get('status') == 'rejected' or settled(context.store.load().state, request):
            continue
        result = observe_request(pages, request, inventory)
        if result['status'] == 'waiting':
            return {'status': 'waiting', 'failure_class': 'DEPLOY_PREDECESSOR_UNCERTAIN'}
        record_settled(context, request, result)
    receipt = require_archive(context, root)
    asset_effect = 'pages_assets_' + context.code_sha[:24]
    context.begin_effect(asset_effect, {'build_sha256': receipt['build_sha256'],
        'account_id': pages.account_id, 'project_id': pages.project_id})
    manifest = pages.upload_assets(root)
    context.complete_effect(asset_effect, {'manifest_sha256': digest(manifest)})
    # Recheck every local byte after upload and recheck current authority before
    # creating the production deployment. Assets themselves are not publication.
    require_archive(context, root)
    _fresh(context, read_main)
    _project(pages)
    request = {'schema_version': 1, 'code_sha': context.code_sha, 'source': context.target.to_dict(),
               'account_id': pages.account_id, 'project_id': pages.project_id, 'project_name': pages.project_name,
               'build_sha256': receipt['build_sha256'], 'artifact': receipt,
               'publication_manifest_sha256': receipt['publication_manifest_sha256'],
               'asset_manifest_sha256': digest(manifest), 'command_id': context.command_id, 'attempt': len(same)+1}
    request['marker'] = 'kesher-deploy:' + digest(request)
    decision = context.begin_effect(effect_name(request), request)
    if decision.execute:
        try:
            pages.create(request, root, manifest)
        except PagesError as exc:
            # Even a typed HTTP error is followed by readback. The transport
            # never retries POST and a missing GET result grants no new POST.
            if exc.failure_class in {'DEPLOY_AUTH_REJECTED', 'DEPLOY_CREATE_REJECTED'}:
                result = observe_request(pages, request)
                if result.get('deployment_id'):
                    return _record(context, request, result)
                context.complete_effect(effect_name(request), {'status': 'rejected', 'failure_class': exc.failure_class})
                return {'status': 'failed', 'failure_class': exc.failure_class}
    return _record(context, request, observe_request(pages, request))


def main(argv=None):
    import argparse
    import os
    import sys
    from pathlib import Path
    from . import deployment_artifact as archive
    from .cloudflare_pages import PagesClient
    from .output_artifacts import download_actions_artifact
    from .worker_entry import actions_admission
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('init', 'prepare', 'complete', 'publish'))
    parser.add_argument('command_id')
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--artifact-id', type=int)
    args = parser.parse_args(argv)
    context = None
    try:
        context = actions_admission(args.command_id, attach=True).context
        def download(key, destination):
            download_actions_artifact(context.store.repo, os.environ['GH_TOKEN'], key, destination)
        if args.action == 'init':
            pages = PagesClient(os.environ.get('CLOUDFLARE_ACCOUNT_ID', ''), os.environ.get('CLOUDFLARE_API_TOKEN', ''))
            result = initialize(context, pages, args.root, download=download)
        elif args.action == 'prepare':
            result = stage_build(context, args.root)
        elif args.action == 'complete':
            if not args.artifact_id:
                raise StateInvalid('DEPLOY_ARCHIVE_MISSING: exact artifact ID required')
            archive.complete(context, args.artifact_id, download=download)
            result = {'status': 'archived'}
        else:
            pages = PagesClient(os.environ.get('CLOUDFLARE_ACCOUNT_ID', ''), os.environ.get('CLOUDFLARE_API_TOKEN', ''))
            result = publish(context, pages, args.root, read_main=lambda: context.store.github.request(
                'GET', f'/repos/{context.store.repo}/git/ref/heads/main')['object']['sha'])
            context.checkpoint('execution_result', result, phase='OUTPUT_CREATED' if result['status'] == 'deployed' else 'STARTED')
            if result['status'] == 'failed':
                context.finish(failure={'class': result['failure_class']})
                return 1
        if output := os.environ.get('GITHUB_OUTPUT'):
            with Path(output).open('a', encoding='utf-8') as stream:
                for key in ('status', 'name'):
                    if key in result:
                        stream.write(key + '=' + result[key] + '\n')
        print('ARTICLE_DEPLOY_' + result['status'].upper())
        return 0
    except Exception as exc:
        code = exc.failure_class if isinstance(exc, PagesError) else 'DEPLOY_WORKER_FAILED'
        if isinstance(exc, StateInvalid):
            candidate = str(exc).split(':')[0]
            if candidate.replace('_', '').isalpha() and candidate.isupper():
                code = candidate
        if context:
            try:
                context.finish(failure={'class': code})
            except Exception:
                pass  # The canonical observer also settles the terminal run.
        print('ARTICLE_DEPLOY_FAILED:' + code, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
