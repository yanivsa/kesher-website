"""Read-only OIDC admission from the independently installed trusted gateway.

The gateway observes authority itself. This client supplies no state, evidence,
credentials or flags that could authorize a command or a cutover step.
"""
import json
import urllib.parse
import urllib.request

from .cutover_entry import NoRedirect
from .github import _unique_object
from .state import StateInvalid

REPOSITORY = 'yanivsa/kesher-website'
CANONICAL_WORKFLOWS = frozenset('.github/workflows/'+name for name in (
    'kesher-content-controller.yml', 'kesher-article-worker.yml',
    'kesher-article-validation.yml', 'kesher-article-merge.yml',
    'kesher-article-deploy.yml', 'kesher-media-worker.yml'))


class ActionsAuthorityObserver:
    def __init__(self, environ, *, opener=None):
        self.environ = environ
        self.open = opener or urllib.request.build_opener(NoRedirect()).open

    def __call__(self):
        from .cutover_host import https_origin
        env = self.environ
        workflow = env.get('GITHUB_WORKFLOW_REF','')
        gateway = https_origin(env.get('KESHER_CUTOVER_GATEWAY_URL',''))
        endpoint = urllib.parse.urlsplit(env.get('ACTIONS_ID_TOKEN_REQUEST_URL',''))
        if (env.get('GITHUB_REPOSITORY') != REPOSITORY or env.get('GITHUB_REF') != 'refs/heads/main'
                or env.get('GITHUB_EVENT_NAME') != 'workflow_dispatch'
                or workflow not in {REPOSITORY+'/'+p+'@refs/heads/main' for p in CANONICAL_WORKFLOWS}
                or endpoint.scheme != 'https' or not endpoint.hostname
                or not endpoint.hostname.endswith('.actions.githubusercontent.com')
                or endpoint.username or endpoint.password or endpoint.fragment
                or not env.get('ACTIONS_ID_TOKEN_REQUEST_TOKEN')):
            raise StateInvalid('CANONICAL_ACTIONS_AUTHORITY_IDENTITY_REQUIRED')
        query = urllib.parse.parse_qsl(endpoint.query, keep_blank_values=True)
        if any(k == 'audience' for k,_ in query):
            raise StateInvalid('CANONICAL_ACTIONS_AUTHORITY_IDENTITY_REQUIRED')
        url = urllib.parse.urlunsplit(endpoint._replace(query=urllib.parse.urlencode(query+[('audience',gateway)])))
        request = urllib.request.Request(url, headers={
            'Authorization':'Bearer '+env['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
        with self.open(request,timeout=20) as response:
            token = json.loads(response.read(65536),object_pairs_hook=_unique_object)['value']
        if not isinstance(token,str) or not token or len(token)>32768:
            raise StateInvalid('CANONICAL_ACTIONS_AUTHORITY_IDENTITY_REQUIRED')
        request = urllib.request.Request(gateway+'/v1/authority',headers={'Authorization':'Bearer '+token})
        with self.open(request,timeout=20) as response:
            result = json.loads(response.read(4*1024*1024),object_pairs_hook=_unique_object)
        if not isinstance(result,dict): raise StateInvalid('TRUSTED_AUTHORITY_OBSERVATION_REQUIRED')
        return result
