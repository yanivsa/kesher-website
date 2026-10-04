"""Independent Pages canonical routing plus immutable build service evidence."""
from types import SimpleNamespace

from .article_deploy import deployment_intents, observe_request, saved_receipt, settled
from .cloudflare_pages import PagesError, PROJECT_ID
from .deployment_artifact import _metadata, effect_key
from .github import GitHubError
from .identity import digest
from .state import StateInvalid


def read_deployment(state, pages, github, repo, main):
    intents = deployment_intents(state)
    requests = sorted((row for row in intents if row['code_sha'] == main),
                      key=lambda row: row['attempt'])
    if not requests:
        unresolved = [row for row in intents if not settled(state, row)
                      and not (saved_receipt(state, row) or {}).get('status') == 'rejected']
        try:
            inventory = pages.inventory() if unresolved else []
            if any(observe_request(pages, row, inventory)['status'] == 'waiting' for row in unresolved):
                return {'status': 'pending', 'failure_class': 'DEPLOY_PREDECESSOR_UNCERTAIN'}
        except (PagesError, GitHubError, OSError, StateInvalid):
            return {'status': 'unknown', 'failure_class': 'TRANSIENT_API'}
        archives = [effect for command in sorted(state['commands'].values(), key=lambda row: row['ordinal'])
                    if command['code_sha'] == main and (effect := command['effects'].get(effect_key(main)))]
        if archives:
            receipt = archives[-1]['receipt']
            if not receipt:
                return {'status': 'pending', 'failure_class': 'DEPLOY_ARCHIVE_PENDING'}
            if receipt.get('status') == 'unavailable':
                return {'status': 'pending', 'failure_class': 'DEPLOY_ARCHIVE_REBUILD'}
        return {'status': 'pending', 'failure_class': 'ARTICLE_NOT_PUBLIC'}
    if [row['attempt'] for row in requests] != list(range(1, len(requests)+1)) or len(requests) > 2:
        raise StateInvalid('DEPLOY_DUPLICATE')
    request = requests[-1]
    try:
        saved = saved_receipt(state, request)
        if saved and saved.get('status') == 'rejected':
            return {'status': 'failed', 'failure_class': saved['failure_class']}
        observed = observe_request(pages, request)
        if observed['status'] != 'deployed':
            failure = observed['failure_class']
            if failure == 'DEPLOY_FAILED' and len(requests) == 2:
                failure = 'DEPLOY_ATTEMPTS_EXHAUSTED'
            return {'status': 'pending' if observed['status'] == 'waiting' else 'failed', 'failure_class': failure}
        producer = state['commands'].get(request['command_id']) or {}
        artifact = producer.get('effects', {}).get(effect_key(main))
        if (not artifact or artifact['receipt'] != request['artifact']
                or digest(artifact['request']) != request['artifact']['request_sha256']
                or artifact['request']['code_sha'] != main
                or artifact['request']['build_sha256'] != request['build_sha256']
                or artifact['request']['publication_manifest_sha256'] != request['publication_manifest_sha256']):
            raise StateInvalid('DEPLOY_ARCHIVE_INVALID: deployment has no bound immutable archive')
        # Read the independent artifact service and original attempt again. Public
        # manifest bytes are checked by ArticlePublicVerifier against this digest.
        context = SimpleNamespace(store=SimpleNamespace(github=github, repo=repo))
        service = _metadata(context, artifact['request'], artifact['receipt']['artifact_id'])
        if service != artifact['receipt']:
            raise StateInvalid('DEPLOY_ARCHIVE_INVALID: service receipt changed')
        return {'status': 'verified', 'evidence': {
            'provider': 'cloudflare_pages', 'project_id': PROJECT_ID, 'deployment_id': observed['deployment_id'],
            'head_sha': main, 'head_branch': 'main', 'status': 'completed', 'conclusion': 'success',
            'html_url': observed['url'], 'build_sha256': request['build_sha256'],
            'publication_manifest_sha256': request['publication_manifest_sha256'],
            'artifact_id': service['artifact_id']}}
    except (PagesError, GitHubError, OSError):
        return {'status': 'unknown', 'failure_class': 'TRANSIENT_API'}
    except StateInvalid as exc:
        return {'status': 'failed', 'failure_class': str(exc).split(':')[0]}
