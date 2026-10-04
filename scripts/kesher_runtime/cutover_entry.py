"""Main-only manual client of the independently installed cutover service.

No GitHub/provider write token, state bundle or key is sent to this runner.
Unknown POST acknowledgments stop; the next NEW invocation reconciles the exact
Git journal. No automatic retry, polling transition loop or activation exists.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

from .cutover_auth import WORKFLOW
from .github import GitHub
from .identity import require_sha
from .state import StateInvalid
from .worker_entry import REPOSITORY


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


def invoke(*, epoch, reviewed_revision, gateway_url, environ, github, checkout, opener=None):
    require_sha(reviewed_revision,40)
    if (not isinstance(epoch,str) or not epoch.strip() or len(epoch)>128
            or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in epoch)):
        raise StateInvalid('CUTOVER_EPOCH_REQUIRED')
    url=urllib.parse.urlsplit(gateway_url)
    if (url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment
            or url.path not in {'','/'}): raise StateInvalid('CUTOVER_PINNED_HTTPS_GATEWAY_REQUIRED')
    gateway_url=gateway_url.rstrip('/')
    if (environ.get('GITHUB_REPOSITORY')!=REPOSITORY or environ.get('GITHUB_REF')!='refs/heads/main'
            or environ.get('GITHUB_EVENT_NAME')!='workflow_dispatch'
            or environ.get('GITHUB_WORKFLOW_REF')!=REPOSITORY+'/'+WORKFLOW+'@refs/heads/main'
            or environ.get('GITHUB_SHA')!=reviewed_revision or checkout!=reviewed_revision
            or github.request('GET','/repos/'+REPOSITORY+'/git/ref/heads/main')['object']['sha']!=reviewed_revision):
        raise StateInvalid('CUTOVER_EXACT_REVIEWED_MAIN_REQUIRED')
    open_url=opener or urllib.request.build_opener(NoRedirect()).open
    oidc=environ.get('ACTIONS_ID_TOKEN_REQUEST_URL','')
    oidc_url=urllib.parse.urlsplit(oidc)
    # GitHub supplies this URL; restrict it to its Actions service before sending
    # its request credential. No user-provided URL is used as the OIDC endpoint.
    if (oidc_url.scheme!='https' or not oidc_url.hostname or
            not oidc_url.hostname.endswith('.actions.githubusercontent.com')
            or oidc_url.username or oidc_url.password):
        raise StateInvalid('CUTOVER_ACTIONS_OIDC_ENDPOINT_REQUIRED')
    separator='&' if oidc_url.query else '?'
    request=urllib.request.Request(oidc+separator+'audience='+urllib.parse.quote(gateway_url,safe=''),headers={
        'Authorization':'Bearer '+environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']})
    with open_url(request,timeout=45) as response: token=json.loads(response.read(65536))['value']
    request=urllib.request.Request(gateway_url+'/v1/cutover/step',method='POST',
        data=json.dumps({'epoch':epoch,'reviewed_revision':reviewed_revision}).encode(),
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
    with open_url(request,timeout=240) as response: result=json.loads(response.read(65536))
    if (result.get('production_activated') is not False or result.get('public_completion_inferred') is not False
            or set(result)-{'phase','resource','production_activated','public_completion_inferred'}):
        raise StateInvalid('CUTOVER_SAFE_RESPONSE_REQUIRED')
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epoch',required=True)
    parser.add_argument('--reviewed-revision',required=True)
    args=parser.parse_args(argv)
    try:
        checkout=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
        result=invoke(epoch=args.epoch,reviewed_revision=args.reviewed_revision,
            gateway_url=os.environ.get('KESHER_CUTOVER_GATEWAY_URL',''),environ=os.environ,
            github=GitHub(os.environ.get('GH_TOKEN','')),checkout=checkout)
        print(json.dumps(result)); return 0
    except Exception:
        print('CUTOVER_BLOCKED: inspect the exact remote journal; do not repeat an uncertain effect',file=sys.stderr)
        return 1


if __name__ == '__main__': raise SystemExit(main())
