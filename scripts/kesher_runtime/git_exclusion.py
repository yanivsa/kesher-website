"""Offline-capable GitHub exclusion port. No default live credential gateway.

    Epoch acquisition uses documented atomic GraphQL updateRefs beforeOid CAS on
the existing automation-state ref, with a no-op main comparison. Actions PUT
disable/POST cancel have no CAS: they are subordinate durable reconciliation.
Git ownership does not revoke PATs/apps/keys or protect an external provider.
Activation still requires an independently installed resource-side gateway.
"""
import base64
import copy
import hashlib
import json

from .github import GitHubError, _unique_object
from .handover_github import GitHubHandover, Snapshot, UPDATE_REFS
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

ANCHOR_MESSAGE = 'state: Kesher exclusion epoch\n'


def no_legacy_incident(state):
    if any(i.get('kind') == 'legacy_authority_violation' and i.get('status') == 'open'
           for i in state.get('incidents', {}).values()):
        raise StateInvalid('LEGACY_AUTHORITY_INCIDENT_OPEN')


def require_exclusion_actions(state, anchor, *, principal, epoch, authenticated_code_sha256,
                              approval, operation, workflow_id, workflow_path, current_run=None):
    """Resource-side bootstrap Actions guard; arguments come from the gateway.

    The gateway reads actual state/anchor/run, authenticates principal+code and
    independently installs approval. Caller-supplied state/review is forbidden.
    It denies all non-retirement effects. Cancel is checked against the latest
    exact attempt at the actual endpoint, never just a caller's prior GET.
    """
    from .authority_topology import run_identity
    no_legacy_incident(state)
    try:
        require_sha(authenticated_code_sha256)
        require_sha(approval['code_sha256']); require_sha(approval['resource_policy_sha256'])
        ledger = state['github_exclusion']
        entry = ledger['drains'][str(workflow_id)]
        if (principal != anchor['owner'] or epoch != anchor['epoch'] or ledger['epoch'] != epoch
                or ledger['anchor'] != anchor['commit_sha'] or approval['repo'] != anchor['repo']
                or approval['main_sha'] != anchor['main_sha']
                or approval['resource_policy_sha256'] != anchor['policy_sha256']
                or authenticated_code_sha256 != approval['code_sha256']
                or 'handover' in state or state.get('schema_version') != 5
                or entry['workflow_id'] != workflow_id or entry['workflow_path'] != workflow_path
                or entry['epoch'] != epoch or entry['proof'] is not None):
            raise StateInvalid('GITHUB_EXCLUSION_ACTION_DENIED')
        if operation == 'disable':
            if (entry['observed_disabled'] or not entry['disable']['attempts']
                    or entry['disable']['attempts'][-1] != {'outcome':'intent'}):
                raise StateInvalid('GITHUB_EXCLUSION_DISABLE_INTENT_REQUIRED')
        elif operation == 'cancel':
            exact = run_identity(current_run)
            row = entry['runs'][f"{exact['id']}:{exact['run_attempt']}"]
            if (row['identity'] != exact or row['cancel'] != {'outcome':'intent'}
                    or exact['workflow_id'] != workflow_id or exact['path'] != workflow_path
                    or current_run['status'] == 'completed'):
                raise StateInvalid('GITHUB_EXCLUSION_CANCEL_INTENT_REQUIRED')
        else: raise StateInvalid('GITHUB_EXCLUSION_OPERATION_DENIED')
    except (KeyError,TypeError,ValueError) as exc:
        raise StateInvalid('GITHUB_EXCLUSION_ACTION_DENIED') from exc
    return operation


class GitExclusionEpoch:
    """Exact Git authority anchor, recovered by immutable anchor and ancestry.

    Acquisition adds one commit with the SAME state tree and a canonical
    identity in its message. The actual CAS winner, not a dangling candidate
    commit or an Actions acknowledgment, owns the epoch. No new branch/store.
    A trusted gateway must prohibit ref rewrites and unauthorized descendants;
    a Git record alone is not a credential-revocation receipt.
    """
    def __init__(self, github, repo, *, epoch, owner, resource_id, main_sha, policy_sha256):
        require_sha(main_sha,40); require_sha(policy_sha256)
        if not all(isinstance(x,str) and x for x in (repo,epoch,owner,resource_id)):
            raise StateInvalid('GITHUB_EPOCH_IDENTITY_REQUIRED')
        self.github, self.repo = github, repo
        self.identity = dict(repo=repo,epoch=epoch,owner=owner,resource_id=resource_id,
                             main_sha=main_sha,policy_sha256=policy_sha256)
        self.api = '/repos/' + repo
        self.reader = GitHubHandover(github,repo,observer=None,fence=None)

    def _commit(self, sha):
        require_sha(sha,40)
        row = self.github.request('GET',self.api+'/git/commits/'+sha)
        if row.get('sha') != sha or not isinstance(row.get('parents'),list):
            raise StateInvalid('GITHUB_EPOCH_COMMIT_INVALID')
        require_sha(row['tree']['sha'],40)
        for p in row['parents']: require_sha(p['sha'],40)
        return row

    def _anchor(self, sha, row=None):
        row = row or self._commit(sha)
        message = row.get('message')
        if not isinstance(message,str) or not message.startswith(ANCHOR_MESSAGE):
            raise StateInvalid('GITHUB_EPOCH_ANCHOR_INVALID')
        record = json.loads(message[len(ANCHOR_MESSAGE):],object_pairs_hook=_unique_object)
        if (set(record) != set(self.identity) | {'before_oid','tree_sha','ref'}
                or record['ref'] != 'refs/heads/automation-state'
                or [p['sha'] for p in row['parents']] != [record['before_oid']]
                or record['tree_sha'] != row['tree']['sha']
                or self._commit(record['before_oid'])['tree']['sha'] != row['tree']['sha']):
            raise StateInvalid('GITHUB_EPOCH_ANCHOR_INVALID')
        for key,value in self.identity.items():
            if record[key] != value: raise StateInvalid('GITHUB_EPOCH_ALREADY_OWNED')
        return dict(record,commit_sha=sha)

    def observe(self):
        if self.github.request('GET',self.api)['node_id'] != self.identity['resource_id']:
            raise StateInvalid('GITHUB_EPOCH_RESOURCE_ID_MISMATCH')
        main = self.github.request('GET',self.api+'/git/ref/heads/main')['object']['sha']
        if main != self.identity['main_sha']: raise StateInvalid('GITHUB_EPOCH_MAIN_CHANGED')
        current = self.github.request('GET',self.api+'/git/ref/heads/automation-state')['object']['sha']
        require_sha(current,40)
        loaded = self.reader.read_snapshot()
        if loaded.commit_sha != current: raise StateInvalid('GITHUB_EPOCH_REF_CHANGED_DURING_READBACK')
        if 'github_exclusion' in loaded.state:
            ledger = loaded.state['github_exclusion']
            if (not isinstance(ledger,dict) or ledger.get('epoch') != self.identity['epoch']):
                raise StateInvalid('GITHUB_EPOCH_LEDGER_IDENTITY_INVALID')
            anchor = self._anchor(ledger['anchor'])
            # GitHub computes ancestry for exact immutable IDs. This proof does
            # not depend on the paginated commits list (250 by default), nor on
            # the number of valid controller/drain descendants. The API's
            # permalink uses abbreviated IDs and is deliberately not authority.
            comparison = self.github.request('GET',self.api+'/compare/'+anchor['commit_sha']+'...'+current+'?per_page=1&page=1')
            if (comparison.get('base_commit',{}).get('sha') != anchor['commit_sha']
                    or comparison.get('merge_base_commit',{}).get('sha') != anchor['commit_sha']
                    or type(comparison.get('behind_by')) is not int or comparison['behind_by'] != 0
                    or type(comparison.get('ahead_by')) is not int
                    or (current == anchor['commit_sha'] and
                        (comparison.get('status') != 'identical' or comparison['ahead_by'] != 0))
                    or (current != anchor['commit_sha'] and
                        (comparison.get('status') != 'ahead' or comparison['ahead_by'] < 1))):
                raise StateInvalid('GITHUB_EPOCH_ANCHOR_NOT_ANCESTOR')
            if (self.github.request('GET',self.api+'/git/ref/heads/automation-state')['object']['sha'] != current
                    or self.github.request('GET',self.api+'/git/ref/heads/main')['object']['sha'] != self.identity['main_sha']):
                raise StateInvalid('GITHUB_EPOCH_REF_CHANGED_DURING_READBACK')
            return {'current_ref':current,'anchor':anchor}
        sha, seen = current, set()
        for _ in range(512):
            if sha in seen: raise StateInvalid('GITHUB_EPOCH_ANCESTRY_INVALID')
            seen.add(sha); row = self._commit(sha)
            message = row.get('message')
            if not isinstance(message,str): raise StateInvalid('GITHUB_EPOCH_COMMIT_INVALID')
            if message.startswith(ANCHOR_MESSAGE):
                return {'current_ref':current,'anchor':self._anchor(sha,row)}
            if len(row['parents']) > 1: raise StateInvalid('GITHUB_EPOCH_MERGE_ANCESTRY_REFUSED')
            if not row['parents']: return {'current_ref':current,'anchor':None}
            sha = row['parents'][0]['sha']
        raise StateInvalid('GITHUB_EPOCH_ANCESTRY_INCOMPLETE')

    def authority(self):
        row = self.observe()
        if row['anchor'] is None: raise StateInvalid('GITHUB_EPOCH_NOT_ACQUIRED')
        return row['anchor']

    def _cas(self, before, after):
        repo_id = self.github.request('GET',self.api)['node_id']
        if repo_id != self.identity['resource_id']: raise StateInvalid('GITHUB_EPOCH_RESOURCE_ID_MISMATCH')
        request = {'repositoryId':repo_id,
            'clientMutationId':digest({'before':before,'after':after,'identity':self.identity}),
            'refUpdates':[
                {'name':'refs/heads/main','beforeOid':self.identity['main_sha'],
                 'afterOid':self.identity['main_sha'],'force':False},
                {'name':'refs/heads/automation-state','beforeOid':before,'afterOid':after,'force':False}]}
        result = self.github.request('POST','/graphql',{'query':UPDATE_REFS,'variables':{'input':request}})
        if result.get('errors'): raise StateConflict('GITHUB_EXCLUSION_REF_CAS_REJECTED')
        if result.get('data',{}).get('updateRefs',{}).get('clientMutationId') != request['clientMutationId']:
            raise GitHubError(None,'Git exclusion acknowledgment missing; inspect exact ref',uncertain=True)

    def acquire(self, observed_ref):
        require_sha(observed_ref,40)
        row = self.observe()
        if row['current_ref'] != observed_ref: raise StateConflict('GITHUB_EPOCH_REF_STALE')
        if row['anchor']: return row['anchor']
        loaded = self.reader.read_snapshot()
        no_legacy_incident(loaded.state)
        if (loaded.commit_sha != observed_ref or loaded.state.get('schema_version') != 5
                or 'handover' in loaded.state or 'github_exclusion' in loaded.state):
            raise StateInvalid('GITHUB_EPOCH_INITIAL_SNAPSHOT_INVALID')
        record = dict(self.identity,before_oid=observed_ref,tree_sha=loaded.tree_sha,
                      ref='refs/heads/automation-state')
        commit = self.github.request('POST',self.api+'/git/commits',{
            'message':ANCHOR_MESSAGE+canonical_json(record),'tree':loaded.tree_sha,'parents':[observed_ref]})['sha']
        require_sha(commit,40)
        self._cas(observed_ref,commit)
        anchor = self.authority()
        if anchor['commit_sha'] != commit: raise StateInvalid('GITHUB_EPOCH_READBACK_CHANGED')
        return anchor

    def write_document(self, loaded, proposed, *, message):
        """Internal primitive. Gateway must authorize the supplied narrow intent.

        Journal and incident callers validate exact allowed differences first.
        Fresh anchor read plus atomic ref/main CAS rejects stale descendants.
        """
        if not isinstance(loaded,Snapshot) or loaded.store_key != self.reader.store_key:
            raise StateInvalid('GITHUB_EXCLUSION_SNAPSHOT_INVALID')
        self.authority()
        raw = (canonical_json(proposed)+'\n').encode()
        blob = self.github.request('POST',self.api+'/git/blobs',
            {'content':base64.b64encode(raw).decode(),'encoding':'base64'})['sha']
        if blob != hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest():
            raise StateInvalid('GITHUB_EXCLUSION_WRITTEN_BLOB_INVALID')
        tree = self.github.request('POST',self.api+'/git/trees',{'base_tree':loaded.tree_sha,
            'tree':[{'path':self.reader.path,'mode':'100644','type':'blob','sha':blob}]})['sha']
        require_sha(tree,40)
        commit = self.github.request('POST',self.api+'/git/commits',{
            'message':message,'tree':tree,'parents':[loaded.commit_sha]})['sha']
        require_sha(commit,40); self.authority(); self._cas(loaded.commit_sha,commit)
        return Snapshot(copy.deepcopy(proposed),blob,loaded.store_key,commit,tree)


class GitDrainJournal:
    """Only drain ledger changes before PREPARED, on the original state path."""
    def __init__(self, epoch): self.epoch = epoch

    def read_snapshot(self): return self.epoch.reader.read_snapshot()

    def initialize(self):
        anchor = self.epoch.authority(); loaded = self.read_snapshot()
        no_legacy_incident(loaded.state)
        if 'github_exclusion' in loaded.state: return self.load()
        if loaded.commit_sha != anchor['commit_sha']:
            raise StateInvalid('GITHUB_EXCLUSION_UNEXPECTED_PRE_LEDGER_WRITE')
        proposed = copy.deepcopy(loaded.state)
        proposed['github_exclusion'] = {'epoch':anchor['epoch'],'anchor':anchor['commit_sha'],
            'legacy_body_sha256':digest(loaded.state),'drains':{}}
        return self.epoch.write_document(loaded,proposed,message='state: Kesher exclusion drain initialized')

    def load(self):
        anchor = self.epoch.authority(); loaded = self.read_snapshot()
        no_legacy_incident(loaded.state)
        ledger = loaded.state.get('github_exclusion',{})
        if (ledger.get('epoch') != anchor['epoch'] or ledger.get('anchor') != anchor['commit_sha']
                or not isinstance(ledger.get('drains'),dict)):
            raise StateInvalid('GITHUB_EXCLUSION_LEDGER_INVALID')
        if 'handover' not in loaded.state and digest({k:v for k,v in loaded.state.items()
                if k != 'github_exclusion'}) != ledger.get('legacy_body_sha256'):
            raise StateInvalid('GITHUB_EXCLUSION_UNEXPECTED_LEGACY_MUTATION')
        return loaded

    def save(self, loaded, proposed):
        # Re-read the ledger and owned epoch; never rebind a stale snapshot.
        fresh = self.load()
        if fresh.commit_sha != loaded.commit_sha: raise StateConflict('GITHUB_DRAIN_SNAPSHOT_STALE')
        old, new = loaded.state.get('github_exclusion'), proposed.get('github_exclusion')
        if ('handover' in loaded.state or loaded.state.get('schema_version') != 5
                or {k:v for k,v in loaded.state.items() if k != 'github_exclusion'} !=
                   {k:v for k,v in proposed.items() if k != 'github_exclusion'}
                or not isinstance(new,dict) or set(new) != set(old)
                or {k:v for k,v in old.items() if k != 'drains'} != {k:v for k,v in new.items() if k != 'drains'}
                or not isinstance(new['drains'],dict) or not set(old['drains']) <= set(new['drains'])):
            raise StateInvalid('GITHUB_DRAIN_WRITE_OUT_OF_SCOPE')
        for wid,entry in old['drains'].items():
            updated = new['drains'][wid]
            if (updated.get('epoch') != entry.get('epoch') or
                    updated.get('workflow_id') != entry.get('workflow_id')):
                raise StateInvalid('GITHUB_DRAIN_IDENTITY_CHANGED')
        from .github_drain import validate_drain_transition
        validate_drain_transition(old['drains'],new['drains'])
        return self.epoch.write_document(loaded,proposed,message='state: Kesher exclusion drain checkpoint')


def record_denied_legacy_write(epoch, *, actor, proposed, before_sha, now):
    """Trusted gateway hook after authenticated legacy write denial.

    It does not execute or retry the attempted write. An incident CAS response
    loss is reconciled by stable incident identity on a later invocation. CAS
    conflict blocks the gateway until exact incident persistence is read back.
    """
    from .legacy_retirement import record_legacy_rejection
    epoch.authority(); loaded = epoch.reader.read_snapshot()
    if 'github_exclusion' not in loaded.state and 'handover' not in loaded.state:
        loaded = GitDrainJournal(epoch).initialize()
    recorded = record_legacy_rejection(loaded.state,actor=actor,epoch=epoch.identity['epoch'],
        proposed=proposed,before_sha=before_sha,current_sha=loaded.commit_sha,now=now)
    if recorded == loaded.state: return loaded
    return epoch.write_document(loaded,recorded,message='state: rejected legacy authority incident')


class GitHubResourceExclusion:
    """Compose real epoch CAS, exact Actions drain and a trusted deny gateway.

    ``guard`` is an independently installed, authenticated resource endpoint
    implementing inspect/exclude; it must revoke old workflow/app/PAT/deploy-key
    grants and enforce narrow Git/Actions operations at the actual endpoints.
    Nothing in this adapter fabricates that enforcement. No guard, partial
    revocation, unknown registration or stale run means no exclusion receipt.
    ``registered`` returns independently reviewed exact ID/path bindings; the
    Actions reader compares its complete inventory against them on every step.
    """
    def __init__(self, github, repo, *, main_sha, policy, rules, registered, guard, separation=None,
                 separation_binding=None, protected_resources=None):
        from .github_drain import GithubDrain
        from .authority_topology import validate_registered_inventory
        from .exclusion import REQUIRED_RESOURCES, CANONICAL_GATE, CONTROL_GATE
        expected_keys = {'repo','resource','resource_id','epoch','owner','default_authority',
                         'credential_revocation_complete','revoked_credential_classes','canonical_gate','control_gate'}
        if (guard is None or not callable(registered) or set(policy) != expected_keys
                or policy['repo'] != repo or policy['resource'] != 'github'
                or policy['default_authority'] != 'deny' or policy['credential_revocation_complete'] is not True
                or policy['revoked_credential_classes'] != REQUIRED_RESOURCES['github']
                or policy['canonical_gate'] != CANONICAL_GATE or policy['control_gate'] != CONTROL_GATE):
            raise StateInvalid('GITHUB_TRUSTED_RESOURCE_GATEWAY_REQUIRED')
        self.github, self.repo, self.guard = github, repo, guard
        self.policy = copy.deepcopy(policy); self.rules = copy.deepcopy(rules)
        self.registered = registered
        self.separation = separation
        self.separation_binding = copy.deepcopy(separation_binding)
        self.protected_resources = copy.deepcopy(protected_resources)
        self.epoch = GitExclusionEpoch(github,repo,epoch=policy['epoch'],owner=policy['owner'],
            resource_id=policy['resource_id'],main_sha=main_sha,policy_sha256=digest(policy))
        self.journal = GitDrainJournal(self.epoch)
        self.drain = GithubDrain(github,repo,journal=self.journal,
            authority=lambda:self.journal.load().state['github_exclusion']['epoch'],registered=self._registered)
        validate_registered_inventory(self._registered(),rules,complete=True)

    def _registered(self):
        from .authority_topology import validate_registered_inventory
        rows = self.registered()
        validate_registered_inventory(rows,self.rules,complete=True)
        return rows

    def targets(self):
        from .authority_topology import _separated
        from .exclusion import REQUIRED_RESOURCES
        rows = self._registered()
        targets=[]
        # Infrastructure is never silently retired merely because a proof is
        # unavailable. The trusted callback freshly reads real service scopes.
        context = self.separation() if callable(self.separation) else {}
        for row in rows:
            if row['path'] in self.rules.get('registrations',{}): targets.append(row); continue
            entry=self.rules['workflows'][row['path']]
            if entry['role'] == 'separate_infrastructure':
                binding,resources=self.separation_binding,self.protected_resources
                if (not isinstance(binding,dict) or set(binding)!=
                        {'repo','policy_sha256','code_sha256','resource_bindings_sha256'}
                        or binding['repo']!=self.repo or not isinstance(resources,dict)
                        or set(resources)!=set(REQUIRED_RESOURCES)
                        or resources['github']!=self.policy['resource_id']
                        or binding['resource_bindings_sha256']!=digest(resources)
                        or context.get('binding')!=binding or context.get('protected_resources')!=resources
                        or not _separated(row,entry,context.get('proofs'),binding,resources)):
                    raise StateInvalid('CUTOVER_INFRASTRUCTURE_BOUNDARY_MISSING:'+row['path'])
            elif entry['role'] in {'retired','emergency_bridge','retiring_dispatcher'}: targets.append(row)
        return targets

    def _guard(self):
        row = self.guard.inspect(self.repo)
        if (row.get('repo') != self.repo or row.get('resource') != 'github'
                or row.get('resource_id') != self.policy['resource_id']
                or row.get('inventory_complete') is not True or not isinstance(row.get('actors'),list)):
            raise StateInvalid('GITHUB_RESOURCE_GATEWAY_READBACK_REQUIRED')
        if row.get('protection') not in (None,self.policy):
            raise StateInvalid('GITHUB_RESOURCE_GATEWAY_CHANGED')
        return row

    def _current_inventory(self):
        from .authority_topology import GitHubAuthorityObserver
        from .github_drain import GithubDrain
        rows, _ = GitHubAuthorityObserver(self.github,self.repo,'.',fence=None).current_inventory(self.rules)
        GithubDrain._known(rows,{row['id']:row['path'] for row in self._registered()})

    def inspect(self, repo):
        if repo != self.repo: raise StateInvalid('GITHUB_RESOURCE_REPO_MISMATCH')
        self.targets()
        self._current_inventory()
        self._registered(); epoch = self.epoch.observe(); row = self._guard()
        protected = False
        if epoch['anchor'] and row.get('protection') == self.policy:
            # A fresh process must recognize the owned same-tree anchor even
            # when interruption preceded drain-ledger initialization.
            if 'github_exclusion' not in self.journal.read_snapshot().state:
                return {'repo':repo,'resource':'github','resource_id':self.policy['resource_id'],
                    'revision_kind':'git_ref_cas','revision':epoch['anchor']['commit_sha'],
                    'epoch_anchor':epoch['anchor'],'protection':None,
                    'inventory_complete':True,'actors':copy.deepcopy(row['actors'])}
            loaded = self.journal.load()
            targets = self.targets()
            ready = all(loaded.state['github_exclusion']['drains'].get(str(t['id']),{}).get('proof')
                        for t in targets)
            if not ready:
                return {'repo':repo,'resource':'github','resource_id':self.policy['resource_id'],
                    'revision_kind':'git_ref_cas','revision':epoch['anchor']['commit_sha'],
                    'epoch_anchor':epoch['anchor'],'protection':None,
                    'inventory_complete':True,'actors':copy.deepcopy(row['actors'])}
            self.drain.observe_many([(target['id'],target['path']) for target in targets])
            # Final gateway/ref observation after mutable Actions reads.
            if self._guard().get('protection') != self.policy: raise StateInvalid('GITHUB_RESOURCE_GATEWAY_CHANGED')
            if self.epoch.authority() != epoch['anchor']: raise StateInvalid('GITHUB_EPOCH_CHANGED')
            protected = True
        return {'repo':repo,'resource':'github','resource_id':self.policy['resource_id'],
            'revision_kind':'git_ref_cas','revision':epoch['anchor']['commit_sha'] if epoch['anchor'] else epoch['current_ref'],
            'epoch_anchor':epoch['anchor'],'protection':copy.deepcopy(self.policy) if protected else None,
            'inventory_complete':True,'actors':copy.deepcopy(row['actors'])}

    def exclude(self, repo, observed_revision, policy):
        if repo != self.repo or policy != self.policy: raise StateInvalid('GITHUB_RESOURCE_POLICY_MISMATCH')
        self.targets(); self._current_inventory(); observed = self.epoch.observe()
        # Before acquisition, the supplied revision MUST be the current ref.
        # After acquisition it MUST be the stable anchored authority commit.
        expected = observed['anchor']['commit_sha'] if observed['anchor'] else observed['current_ref']
        if observed_revision != expected: raise StateConflict('GITHUB_RESOURCE_EXCLUSION_STALE')
        row = self._guard()
        if row.get('protection') is None:
            # Enforce deny/intent guards BEFORE reconciling Actions. The gateway
            # authenticates exact run attempts at cancel, closing the REST
            # run-ID-only check/use gap independently of workflow disablement.
            self.guard.exclude(repo,row['revision'],copy.deepcopy(policy))
            if self._guard().get('protection') != self.policy:
                raise StateInvalid('GITHUB_RESOURCE_EXCLUSION_INCOMPLETE')
            raise StateInvalid('GITHUB_RESOURCE_DRAIN_PENDING')
        if not observed['anchor']:
            self.epoch.acquire(observed['current_ref'])
            raise StateInvalid('GITHUB_RESOURCE_DRAIN_PENDING')
        if 'github_exclusion' not in self.journal.read_snapshot().state:
            self.journal.initialize()
            raise StateInvalid('GITHUB_RESOURCE_DRAIN_PENDING')
        self.epoch.authority()
        drains=self.journal.load().state['github_exclusion']['drains']
        for target in self.targets():
            if not drains.get(str(target['id']),{}).get('proof'):
                self.drain.step(target['id'],target['path'])
                raise StateInvalid('GITHUB_RESOURCE_DRAIN_PENDING')
        if self.inspect(repo)['protection'] != self.policy:
            raise StateInvalid('GITHUB_RESOURCE_EXCLUSION_INCOMPLETE')
