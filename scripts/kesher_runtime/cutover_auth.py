"""Authenticate the exact live main cutover invocation using GitHub Actions OIDC."""
import base64
import json
import time
import urllib.request

from .github import _unique_object
from .state import StateInvalid

ISSUER = 'https://token.actions.githubusercontent.com'
WORKFLOW = '.github/workflows/kesher-production-cutover.yml'


def _decode(value):
    return base64.b64decode(value + '='*((-len(value))%4),altchars=b'-_',validate=True)


def github_jwks():
    # Fixed issuer/key endpoint; caller-controlled URLs are never dereferenced.
    with urllib.request.urlopen(ISSUER+'/.well-known/jwks',timeout=20) as response:
        return json.loads(response.read(1024*1024),object_pairs_hook=_unique_object)


class ActionsIdentity:
    def __init__(self, github, *, repo, repository_id, main_sha, audience, jwks=github_jwks):
        self.github, self.repo, self.repository_id = github, repo, str(repository_id)
        self.main_sha, self.audience, self.jwks = main_sha, audience, jwks

    def verify(self, token):
        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        try:
            if not isinstance(token,str) or len(token)>32768: raise ValueError('token size')
            first, second, signature=token.split('.')
            header=json.loads(_decode(first),object_pairs_hook=_unique_object)
            claims=json.loads(_decode(second),object_pairs_hook=_unique_object)
            if header.get('alg') != 'RS256': raise ValueError('algorithm')
            keys=[k for k in self.jwks()['keys'] if k.get('kid')==header.get('kid') and k.get('kty')=='RSA']
            if len(keys)!=1: raise ValueError('key identity')
            key=keys[0]
            public=rsa.RSAPublicNumbers(int.from_bytes(_decode(key['e']),'big'),
                                       int.from_bytes(_decode(key['n']),'big')).public_key()
            public.verify(_decode(signature),(first+'.'+second).encode(),padding.PKCS1v15(),hashes.SHA256())
            now=time.time()
            expected={'iss':ISSUER,'aud':self.audience,'repository':self.repo,'repository_id':self.repository_id,
                'ref':'refs/heads/main','workflow_ref':self.repo+'/'+WORKFLOW+'@refs/heads/main',
                'workflow_sha':self.main_sha,'sha':self.main_sha,'event_name':'workflow_dispatch',
                'environment':'kesher-cutover'}
            if any(claims.get(k)!=v for k,v in expected.items()): raise ValueError('claim binding')
            if 'job_workflow_ref' in claims: raise ValueError('reusable workflow refused')
            if (any(type(claims.get(k)) is not int for k in ('exp','nbf','iat'))
                    or not claims['nbf'] <= now < claims['exp'] or claims['iat'] > now
                    or claims['exp']-claims['iat'] > 600): raise ValueError('token lifetime')
            rid, attempt=claims['run_id'],claims['run_attempt']
            if not all(isinstance(v,str) and v.isdecimal() and int(v)>0 for v in (rid,attempt)):
                raise ValueError('attempt identity')
            api='/repos/'+self.repo
            run=self.github.request('GET',api+'/actions/runs/'+rid)
            if (run['id'] != int(rid) or run['run_attempt'] != int(attempt) or run['status']!='in_progress'
                    or run['head_sha']!=self.main_sha or run['head_branch']!='main'
                    or run['event']!='workflow_dispatch' or run['path'].split('@',1)[0]!=WORKFLOW
                    or self.github.request('GET',api+'/git/ref/heads/main')['object']['sha']!=self.main_sha):
                raise ValueError('live run binding')
            return rid+'/'+attempt
        except (ValueError,KeyError,TypeError,InvalidSignature):
            raise StateInvalid('CUTOVER_ACTIONS_IDENTITY_DENIED') from None
