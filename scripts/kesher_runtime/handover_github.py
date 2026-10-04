"""Exact Git-ref CAS adapter for the handover; never invoked implicitly.

An independent exclusive authority fence is REQUIRED. It must exclude old
external writers and changes to workflow/secret authority across the operation.
GitHub multi-ref CAS protects Git objects only; this adapter does not claim that
several API reads lock other services. There is deliberately no live CLI.
"""
import base64
import hashlib
import json

from .github import GitHubError, LoadedState, _unique_object
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid, validate_state
from .handover import PHASES, validate_journal

UPDATE_REFS = '''mutation($input: UpdateRefsInput!) {
  updateRefs(input: $input) { clientMutationId }
}'''


def validate_handover_write(previous, proposed):
    """Shared exact journal/body guard for resource adapters and Git CAS."""
    validate_journal(proposed['handover'])
    if previous.get('github_exclusion') != proposed.get('github_exclusion'):
        raise StateInvalid('HANDOVER_EXCLUSION_EVIDENCE_CHANGED')
    old, new = previous.get('handover'), proposed['handover']
    if old:
        if (old['basis'] != new['basis'] or new['journal'][:len(old['journal'])] != old['journal']
                or len(new['journal']) not in {len(old['journal']),len(old['journal'])+1}
                or old['phase'] == 'VERIFIED'):
            raise StateInvalid('HANDOVER_NONMONOTONIC_WRITE')
    elif new['phase'] != 'PREPARED' or previous.get('schema_version') != 5:
        raise StateInvalid('HANDOVER_INVALID_INITIAL_WRITE')
    if proposed.get('schema_version') == 6:
        validate_state(proposed)
        if new['phase'] not in PHASES[5:]: raise StateInvalid('HANDOVER_PREMATURE_IMPORT')
    elif (new['phase'] not in PHASES[:5] or previous.get('schema_version') != 5
          or proposed.get('schema_version') != 5):
        raise StateInvalid('HANDOVER_SCHEMA_ROLLBACK')
    # Journal transitions cannot quietly bless new provider commands, erase
    # quarantine, or replace imported receipts between durable boundaries.
    old_body = {k:v for k,v in previous.items() if k != 'handover'}
    if old:
        expected_digest = old['basis']['legacy_sha256' if previous['schema_version']==5 else 'baseline_sha256']
        if old['phase'] != 'VERIFIED' and digest(old_body) != expected_digest:
            raise StateInvalid('HANDOVER_LOADED_BODY_CHANGED')
    new_body = {k:v for k,v in proposed.items() if k != 'handover'}
    if previous['schema_version'] == 5 and proposed['schema_version'] == 6:
        if new['phase'] != 'STATE_IMPORTED' or digest(new_body) != new['basis']['baseline_sha256']:
            raise StateInvalid('HANDOVER_IMPORT_PAYLOAD_CHANGED')
    elif new['phase'] == 'VERIFIED':
        expected = json.loads(canonical_json(old_body))
        expected['migration'].update(status='complete',runtime_owner='kesher-canonical-controller')
        audit = new_body['audit'][-1]
        if (audit.get('event') != 'authority_handover_verified' or audit.get('handover_id') != new['id']
                or audit.get('public_completion_inferred') is not False):
            raise StateInvalid('HANDOVER_INVALID_VERIFICATION_RECEIPT')
        expected['audit'].append(audit)
        if expected != new_body: raise StateInvalid('HANDOVER_BODY_CHANGED')
    elif old_body != new_body:
        raise StateInvalid('HANDOVER_BODY_CHANGED')


class Snapshot(LoadedState):
    def __init__(self, state, blob_sha, store_key, commit_sha, tree_sha):
        super().__init__(state, blob_sha, store_key)
        object.__setattr__(self, 'commit_sha', commit_sha)
        object.__setattr__(self, 'tree_sha', tree_sha)


class GitHubHandover:
    """Caller holds `fence` for the entire tick, including topology observation.

    `assert_exclusive(repo)` freshly reads persistent resource-side protection;
    a cached flag, local lock or unsigned evidence file cannot establish it.
    The resource adapter permits only the independently reviewed journal/CAS
    and exact retirement operations before VERIFIED. It separately guards
    canonical state intent/claim CAS and accepted-command external effects.
    No release exists here; live adapter/actor acceptance is a separate gate.
    """
    ref = 'automation-state'
    path = '.kesher-controller/state.json'

    def __init__(self, github, repo, *, observer, fence):
        from .github import GitHubStateStore
        self.github, self.repo, self.observer, self.fence = github, repo, observer, fence
        self.store_key = GitHubStateStore(github, repo).store_key
        self.api = '/repos/' + repo

    def _fenced(self):
        if self.fence is None:
            raise StateInvalid('HANDOVER_TRUSTED_EXCLUSIVE_FENCE_REQUIRED')
        from .exclusion import validate_external
        return validate_external(self.fence.assert_exclusive(self.repo), self.repo)

    def observe(self):
        self._fenced()
        return self.observer()

    def load(self):
        self._fenced()
        return self.read_snapshot()

    def read_snapshot(self):
        """Read immutable bytes only; this does not grant write authority."""
        commit_sha = self.github.request('GET', self.api+'/git/ref/heads/'+self.ref)['object']['sha']
        require_sha(commit_sha, 40)
        commit = self.github.request('GET', self.api+'/git/commits/'+commit_sha)
        tree_sha = commit['tree']['sha']; require_sha(tree_sha,40)
        if commit.get('sha') != commit_sha:
            raise StateInvalid('HANDOVER_COMMIT_IDENTITY_MISMATCH')
        payload = self.github.request('GET', self.api+'/contents/'+self.path+'?ref='+commit_sha)
        sha = payload['sha']; require_sha(sha,40)
        if payload.get('encoding') == 'none':
            payload = self.github.request('GET', self.api+'/git/blobs/'+sha)
        if payload.get('sha') != sha or payload.get('encoding') != 'base64':
            raise StateInvalid('HANDOVER_BLOB_IDENTITY_MISMATCH')
        raw = base64.b64decode(''.join(payload['content'].split()),validate=True)
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != sha:
            raise StateInvalid('HANDOVER_BLOB_BYTES_MISMATCH')
        state = json.loads(raw,object_pairs_hook=_unique_object)
        if state.get('schema_version') == 6: validate_state(state)
        elif state.get('schema_version') != 5: raise StateInvalid('HANDOVER_LEGACY_SCHEMA_REQUIRED')
        if 'handover' in state: validate_journal(state['handover'])
        return Snapshot(state,sha,self.store_key,commit_sha,tree_sha)

    def save(self, loaded, proposed, *, main_sha):
        protection = self._fenced()
        if protection != proposed.get('handover', {}).get('basis', {}).get('environment', {}).get('external_fence'):
            raise StateInvalid('HANDOVER_RESOURCE_PROTECTION_CHANGED')
        if not isinstance(loaded,Snapshot) or loaded.store_key != self.store_key:
            raise StateInvalid('HANDOVER_SNAPSHOT_LOCATION_MISMATCH')
        require_sha(main_sha,40)
        validate_handover_write(loaded.state, proposed)
        new = proposed['handover']
        raw = (canonical_json(proposed)+'\n').encode()
        blob = self.github.request('POST',self.api+'/git/blobs',
            {'content':base64.b64encode(raw).decode(),'encoding':'base64'})['sha']
        require_sha(blob,40)
        if blob != hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest():
            raise StateInvalid('HANDOVER_WRITTEN_BLOB_MISMATCH')
        tree = self.github.request('POST',self.api+'/git/trees',{'base_tree':loaded.tree_sha,
            'tree':[{'path':self.path,'mode':'100644','type':'blob','sha':blob}]})['sha']
        require_sha(tree,40)
        commit = self.github.request('POST',self.api+'/git/commits',{
            'message':'state: Kesher handover '+new['phase'], 'tree':tree,'parents':[loaded.commit_sha]})['sha']
        require_sha(commit,40)
        repo_id = self.github.request('GET',self.api)['node_id']
        self._fenced()
        request = {'repositoryId':repo_id, 'clientMutationId':digest({'main':main_sha,'before':loaded.commit_sha,'after':commit}),
            'refUpdates':[
                {'name':'refs/heads/main','beforeOid':main_sha,'afterOid':main_sha,'force':False},
                {'name':'refs/heads/'+self.ref,'beforeOid':loaded.commit_sha,'afterOid':commit,'force':False}]}
        result = self.github.request('POST','/graphql',{'query':UPDATE_REFS,'variables':{'input':request}})
        # No transport retry. Reload the journal on a later invocation even if
        # GitHub returns an error whose acceptance is not independently known.
        if result.get('errors'):
            raise StateConflict('HANDOVER_REF_CAS_REJECTED: reload exact journal before any further operation')
        if result.get('data',{}).get('updateRefs',{}).get('clientMutationId') != request['clientMutationId']:
            raise GitHubError(None,'Handover acknowledgment missing; reload',uncertain=True)
        return Snapshot(proposed,blob,self.store_key,commit,tree)

    def disable(self, workflow_id):
        self._fenced()
        # Observe the exact registered ID again; never accept arbitrary API paths.
        row = next((w for w in self.observe()['workflows'] if w['id']==workflow_id),None)
        if row is None or row['role'] != 'retired':
            raise StateInvalid('HANDOVER_RETIREMENT_TARGET_INVALID')
        if row['state'] == 'active':
            self.github.request('PUT',self.api+f'/actions/workflows/{workflow_id}/disable')
