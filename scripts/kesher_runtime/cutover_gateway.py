"""Credential-owning GitHub control gateway; no general mutation proxy.

The raw App credential remains in this service. Independently installed native
boundary observers must prove predecessor retirement; this gateway cannot
prove that nobody possesses a token outside it. Missing observers refuse before
any effect. Git objects are staged only for the original state path/parent and
committed with the existing atomic main+automation-state CAS.
"""
import base64
import copy
import json

from .exclusion import require_control_operation
from .git_exclusion import (ANCHOR_MESSAGE, GitExclusionEpoch, require_exclusion_actions,
                            no_legacy_incident)
from .github import _unique_object
from .github_drain import validate_drain_transition
from .handover_github import GitHubHandover, UPDATE_REFS
from .identity import digest, require_sha
from .state import StateConflict, StateInvalid


class GuardedGitHub:
    """Used only by the authenticated service's reviewed CutoverRuntime.

    A remote client can request a step, never supply paths, proposed state,
    principal/code flags or API credentials. Each mutation is validated here,
    even if a future caller accidentally attempts a broader API operation.
    """
    def __init__(self, github, *, repo, policy, approval, boundary, retirement_targets=None):
        if boundary is None or approval.get('repo') != repo:
            raise StateInvalid('CUTOVER_INDEPENDENT_BOUNDARY_REQUIRED')
        for name in ('code_sha256','policy_sha256','closed_evidence_sha256'):
            require_sha(approval[name])
        require_sha(approval['main_sha'],40)
        self._native, self.repo = github, repo
        self.policy, self.approval = copy.deepcopy(policy), copy.deepcopy(approval)
        self.boundary = boundary
        self.retirement_targets = copy.deepcopy(retirement_targets or {})
        if any(type(wid) is not int or wid<=0 or not isinstance(path,str) or not path
               for wid,path in self.retirement_targets.items()):
            raise StateInvalid('CUTOVER_REVIEWED_RETIREMENT_TARGETS_REQUIRED')
        self.api = '/repos/' + repo
        self.reader = GitHubHandover(github,repo,observer=None,fence=None)
        self.transaction = None

    def _boundary(self):
        row = self.boundary.inspect(self.repo)
        if (row.get('repo') != self.repo or row.get('resource') != 'github'
                or row.get('resource_id') != self.policy['resource_id']
                or row.get('inventory_complete') is not True
                or row.get('protection') != self.policy):
            raise StateInvalid('CUTOVER_NATIVE_GITHUB_BOUNDARY_REQUIRED')
        main = self._native.request('GET',self.api+'/git/ref/heads/main')['object']['sha']
        if main != self.approval['main_sha']: raise StateInvalid('CUTOVER_REVIEWED_MAIN_CHANGED')

    def _epoch(self):
        return GitExclusionEpoch(self._native,self.repo,epoch=self.policy['epoch'],owner=self.policy['owner'],
            resource_id=self.policy['resource_id'],main_sha=self.approval['main_sha'],policy_sha256=digest(self.policy))

    def _retirement(self, workflow_id, workflow_path):
        if (type(workflow_id) is not int or
                self.retirement_targets.get(workflow_id)!=workflow_path):
            raise StateInvalid('CUTOVER_REVIEWED_RETIREMENT_TARGET_REQUIRED')

    def _document(self, loaded, proposed):
        previous = loaded.state
        no_legacy_incident(previous)
        for identity,entry in proposed.get('github_exclusion',{}).get('drains',{}).items():
            if identity!=str(entry.get('workflow_id')):
                raise StateInvalid('CUTOVER_REVIEWED_RETIREMENT_TARGET_REQUIRED')
            self._retirement(entry.get('workflow_id'),entry.get('workflow_path'))
        if 'handover' in proposed:
            require_control_operation(self.policy,'handover_cas',principal=self.policy['owner'],
                epoch=self.policy['epoch'],code_sha256=self.approval['code_sha256'],approval=self.approval,
                previous=previous,previous_sha=loaded.blob_sha,main_sha=self.approval['main_sha'],proposed=proposed)
            return
        if (previous.get('schema_version') != 5 or proposed.get('schema_version') != 5
                or 'handover' in previous):
            raise StateInvalid('CUTOVER_BOOTSTRAP_STATE_REQUIRED')
        anchor = self._epoch().authority()
        ledger = previous.get('github_exclusion')
        if ledger is None:
            expected = copy.deepcopy(previous)
            expected['github_exclusion']={'epoch':anchor['epoch'],'anchor':anchor['commit_sha'],
                'legacy_body_sha256':digest(previous),'drains':{}}
            if proposed != expected or loaded.commit_sha != anchor['commit_sha']:
                raise StateInvalid('CUTOVER_INITIAL_DRAIN_LEDGER_REQUIRED')
        else:
            updated = proposed.get('github_exclusion')
            if (not isinstance(updated,dict) or set(updated) != set(ledger)
                    or ledger['epoch'] != anchor['epoch'] or ledger['anchor'] != anchor['commit_sha']
                    or {k:v for k,v in previous.items() if k!='github_exclusion'} !=
                       {k:v for k,v in proposed.items() if k!='github_exclusion'}
                    or {k:v for k,v in ledger.items() if k!='drains'} !=
                       {k:v for k,v in updated.items() if k!='drains'}):
                raise StateInvalid('CUTOVER_DRAIN_SCOPE_VIOLATION')
            validate_drain_transition(ledger['drains'],updated['drains'])

    def request(self, method, path, body=None, **kwargs):
        if method == 'GET':
            if not path.startswith(self.api+'/') and path != self.api:
                raise StateInvalid('CUTOVER_READ_SCOPE_VIOLATION')
            return self._native.request(method,path,body,**kwargs)
        self._boundary()
        loaded = self.reader.read_snapshot()
        no_legacy_incident(loaded.state)
        tail = path.removeprefix(self.api)
        if method == 'POST' and tail == '/git/blobs':
            if set(body) != {'content','encoding'} or body['encoding'] != 'base64':
                raise StateInvalid('CUTOVER_STATE_BLOB_REQUIRED')
            proposed = json.loads(base64.b64decode(body['content'],validate=True),object_pairs_hook=_unique_object)
            self._document(loaded,proposed)
            result = self._native.request(method,path,body)
            self.transaction={'before':loaded,'proposed':proposed,'blob':result['sha']}
            return result
        tx = self.transaction
        if method == 'POST' and tail == '/git/trees':
            if (not tx or loaded.commit_sha != tx['before'].commit_sha or body !=
                    {'base_tree':loaded.tree_sha,'tree':[{'path':self.reader.path,'mode':'100644',
                     'type':'blob','sha':tx['blob']}]}):
                raise StateInvalid('CUTOVER_EXACT_STATE_TREE_REQUIRED')
            self._document(loaded,tx['proposed'])
            result=self._native.request(method,path,body); tx['tree']=result['sha']; return result
        if method == 'POST' and tail == '/git/commits':
            if isinstance(body.get('message'),str) and body['message'].startswith(ANCHOR_MESSAGE):
                anchor = json.loads(body['message'][len(ANCHOR_MESSAGE):],object_pairs_hook=_unique_object)
                expected=dict(self._epoch().identity,before_oid=loaded.commit_sha,
                              tree_sha=loaded.tree_sha,ref='refs/heads/automation-state')
                if (anchor != expected or body != {'message':body['message'],'tree':loaded.tree_sha,
                        'parents':[loaded.commit_sha]} or loaded.state.get('schema_version') != 5
                        or 'handover' in loaded.state or 'github_exclusion' in loaded.state
                        or self._epoch().observe()['anchor'] is not None):
                    raise StateInvalid('CUTOVER_EXACT_EPOCH_ANCHOR_REQUIRED')
                result=self._native.request(method,path,body)
                self.transaction={'before':loaded,'anchor':True,'commit':result['sha']}
                return result
            if (not tx or loaded.commit_sha != tx['before'].commit_sha or set(body) != {'message','tree','parents'}
                    or not isinstance(body['message'],str) or not body['message'].startswith('state: ')
                    or body['tree'] != tx.get('tree') or body['parents'] != [loaded.commit_sha]):
                raise StateInvalid('CUTOVER_EXACT_STATE_COMMIT_REQUIRED')
            self._document(loaded,tx['proposed'])
            result=self._native.request(method,path,body); tx['commit']=result['sha']; return result
        if method == 'POST' and path == '/graphql':
            if not tx or 'commit' not in tx:
                raise StateInvalid('CUTOVER_EXACT_REF_CAS_REQUIRED')
            if loaded.commit_sha != tx['before'].commit_sha:
                raise StateConflict('CUTOVER_STAGED_SNAPSHOT_CHANGED')
            if not tx.get('anchor'): self._document(loaded,tx['proposed'])
            try:
                request = body['variables']['input']
                expected=[{'name':'refs/heads/main','beforeOid':self.approval['main_sha'],
                           'afterOid':self.approval['main_sha'],'force':False},
                          {'name':'refs/heads/automation-state','beforeOid':loaded.commit_sha,
                           'afterOid':tx['commit'],'force':False}]
                repo_id=self._native.request('GET',self.api)['node_id']
                if (set(body) != {'query','variables'} or body['query'] != UPDATE_REFS
                        or set(body['variables']) != {'input'}
                        or set(request) != {'repositoryId','clientMutationId','refUpdates'}
                        or request['repositoryId'] != repo_id or repo_id != self.policy['resource_id']
                        or request['refUpdates'] != expected):
                    raise StateInvalid('CUTOVER_EXACT_REF_CAS_REQUIRED')
            except (KeyError,TypeError): raise StateInvalid('CUTOVER_EXACT_REF_CAS_REQUIRED') from None
            # Clear before transport: an uncertain effect is never replayed from
            # a cached transaction. Next invocation reloads exact remote state.
            self.transaction=None
            return self._native.request(method,path,body)
        if method in {'PUT','POST'} and tail.startswith('/actions/'):
            anchor=self._epoch().authority()
            if method == 'PUT' and tail.startswith('/actions/workflows/') and tail.endswith('/disable'):
                wid=int(tail.split('/')[-2]); run=None; operation='disable'
                workflow=self._native.request('GET',self.api+f'/actions/workflows/{wid}')
            elif method == 'POST' and tail.startswith('/actions/runs/') and tail.endswith('/cancel'):
                run=self._native.request('GET',self.api+'/actions/runs/'+tail.split('/')[-2])
                wid=run['workflow_id']; operation='cancel'
                workflow=self._native.request('GET',self.api+f'/actions/workflows/{wid}')
            else: raise StateInvalid('CUTOVER_RETIREMENT_OPERATION_REQUIRED')
            if body is not None: raise StateInvalid('CUTOVER_RETIREMENT_BODY_DENIED')
            if workflow.get('id')!=wid:
                raise StateInvalid('CUTOVER_REVIEWED_RETIREMENT_TARGET_REQUIRED')
            self._retirement(wid,workflow['path'])
            require_exclusion_actions(loaded.state,anchor,principal=self.policy['owner'],epoch=self.policy['epoch'],
                authenticated_code_sha256=self.approval['code_sha256'],approval=self.approval | {
                    'resource_policy_sha256':digest(self.policy)},operation=operation,
                workflow_id=wid,workflow_path=workflow['path'],current_run=run)
            return self._native.request(method,path)
        raise StateInvalid('CUTOVER_GENERAL_MUTATION_DENIED')
