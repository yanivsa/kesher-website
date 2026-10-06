"""Resource-enforced legacy exclusion contract, with no default live adapter.

Ports are trusted service adapters, not evidence-file readers. exclude() must
atomically revoke *all* predecessor grants, deny unknown grants by default and
install a command/state gate on the canonical principal at the real resource.
This includes in-flight requests and bearer capabilities independent of OAuth.
An Actions disable, process lock or lease alone cannot implement this contract.
Service protection survives coordinator crashes; no release/enable operation
exists here. Resource ACLs are enforcement, not a second controller state store.
"""
from __future__ import annotations

import copy

from .identity import digest
from .state import StateInvalid

REQUIRED_RESOURCES = {
    'github': ['workflow_tokens', 'apps', 'pats', 'deploy_keys'],
    'jules': ['session_creation', 'session_continuation', 'repository_access'],
    'notebooklm': ['provider_sessions', 'provider_credentials'],
    'youtube': ['oauth_grants', 'resumable_upload_capabilities', 'metadata_credentials'],
    'cloudflare': ['pages_credentials', 'deployment_tokens', 'configuration_credentials'],
    'image_provider': ['provider_credentials', 'inflight_generation'],
}
CANONICAL_GATE = {'state_ref': 'automation-state', 'path': '.kesher-controller/state.json',
                  'schema_version': 6, 'phase': 'VERIFIED', 'command_required': True,
                  'epoch_required': True, 'accepted_owner_required': True,
                  'trusted_code_required': True, 'current_target_required': True}
CONTROL_GATE = {'state_ref':'automation-state', 'path':'.kesher-controller/state.json',
                'operations':['handover_cas','retire_workflow','controller_cas','worker_claim_cas'],
                'authenticated_actor_required':True, 'epoch_required':True,
                'independent_code_review_required':True, 'snapshot_cas_required':True,
                'handover_journal_only_before_verified':True,
                'retirement_requires_durable_exact_intent':True,
                'provider_or_publication_effects_allowed':False}


def require_control_operation(protection, operation, *, principal, epoch, code_sha256,
                              approval, previous, previous_sha, main_sha, proposed=None,
                              workflow=None, command_id=None, run_id=None, checkout_sha=None):
    """Resource adapter authorizes ONLY the named state/retirement transaction.

    Adapters authenticate the principal/code, supply independent approval and
    read the actual state/main themselves. They must CAS the observed state and
    main at commit, restrict staging to this state's exact blob/tree/parent and
    deny all other refs/paths/API effects. This guard is not a caller JSON token.
    A controller may write intent and a worker may claim before an accepted
    command exists; neither exception permits provider/publication mutation.
    """
    from .identity import canonical_json, identity_from_dict, require_sha
    from .handover import OWNER, validate_journal
    from .state import claim_command, validate_transition
    from .git_exclusion import no_legacy_incident
    no_legacy_incident(previous)
    try:
        require_sha(previous_sha,40); require_sha(main_sha,40); require_sha(code_sha256)
        if (protection['resource'] != 'github' or protection['control_gate'] != CONTROL_GATE
                or epoch != protection['epoch'] or approval['repo'] != protection['repo']
                or code_sha256 != approval['code_sha256'] or operation not in CONTROL_GATE['operations']):
            _refuse()
        for field in ('policy_sha256','code_sha256','closed_evidence_sha256'):
            require_sha(approval[field])
        h = (proposed if operation == 'handover_cas' else previous).get('handover', {})
        validate_journal(h)
        env = h['basis']['environment']
        if (env['repo'] != protection['repo'] or env['code_sha256'] != code_sha256
                or env['policy_sha256'] != approval['policy_sha256']
                or env['closed_evidence_sha256'] != approval['closed_evidence_sha256']
                or h['basis']['closure']['retained_evidence'] != approval['closed_evidence_sha256']
                or env['external_fence']['epoch'] != epoch
                or env['external_fence']['owner'] != protection['owner']):
            _refuse()
        if operation in {'handover_cas','retire_workflow'}:
            if principal != protection['owner'] or main_sha != env['main_sha']:
                _refuse()
            if operation == 'handover_cas':
                from .handover_github import validate_handover_write
                if not previous.get('handover') and previous_sha != h['basis']['legacy_blob_sha']:
                    _refuse()
                validate_handover_write(previous,proposed)
            else:
                intent = h['retirement'].get(str(workflow['id']))
                bound = {k:workflow[k] for k in ('id','path','role')}
                if (h['phase'] != 'LEGACY_QUIESCING' or workflow['role'] != 'retired'
                        or bound not in env['workflows'] or not intent
                        or intent['workflow_id'] != workflow['id'] or intent['path'] != workflow['path']
                        or intent['desired_state'] != 'disabled_manually' or intent['observed_disabled']
                        or proposed is not None):
                    _refuse()
        else:
            if h['phase'] != 'VERIFIED': _refuse()
            validate_transition(previous,proposed)
            if operation == 'controller_cas':
                if principal != OWNER: _refuse()
            else:
                if principal != 'canonical-worker' or not isinstance(run_id,str) or not run_id:
                    _refuse()
                command = previous['commands'][command_id]
                if (command['phase'] != 'REQUESTED' or command['outcome'] != 'pending'
                        or command['owner'] is not None or command['code_sha'] != checkout_sha
                        or checkout_sha != main_sha):
                    _refuse()
                target = identity_from_dict(command['target'])
                now = proposed['commands'][command_id]['owner']['claimed_at']
                expected,_ = claim_command(previous,command_id,run_id,target,code_sha=checkout_sha,now=now)
                if canonical_json(expected) != canonical_json(proposed): _refuse()
        return operation
    except (KeyError, TypeError, ValueError, AttributeError):
        _refuse()


def require_resource_command(state, epoch, command_id, run_id, code_sha):
    """Trusted ports read the canonical state themselves, never caller JSON.

    The service must authenticate run identity and code before invoking this
    guard. Controller intent CAS uses the existing trusted state transition
    validator; provider/publication effects require an already claimed command.
    """
    from .state import validate_state, target_is_current
    from .identity import identity_from_dict
    validate_state(state)
    from .git_exclusion import no_legacy_incident
    no_legacy_incident(state)
    h = state.get('handover', {})
    c = state['commands'].get(command_id)
    if (h.get('phase') != 'VERIFIED' or
            h['basis']['environment']['external_fence']['epoch'] != epoch or
            not c or c['phase'] == 'REQUESTED' or c['outcome'] != 'pending' or
            (c.get('owner') or {}).get('run_id') != run_id or c['code_sha'] != code_sha or
            not target_is_current(state, identity_from_dict(c['target']))):
        _refuse()
    return c


def _refuse():
    raise StateInvalid('RESOURCE_ENFORCED_EXCLUSION_REQUIRED')


def _revision(resource, row, *, protected=False):
    """GitHub has a Git-ref CAS receipt, never an Actions revision counter."""
    from .identity import require_sha
    if resource != 'github':
        if type(row.get('revision')) is not int or row['revision'] < 1: _refuse()
        return
    try:
        require_sha(row['revision'],40)
        if row['revision_kind'] != 'git_ref_cas': _refuse()
        if protected:
            anchor = row['epoch_anchor']
            for name in ('commit_sha','before_oid','tree_sha','main_sha'): require_sha(anchor[name],40)
            require_sha(anchor['policy_sha256'])
            policy = {k:v for k,v in row.items() if k not in
                      {'revision','revision_kind','epoch_anchor','receipt_sha256'}}
            if (anchor['ref'] != 'refs/heads/automation-state' or anchor['commit_sha'] != row['revision']
                    or anchor['policy_sha256'] != digest(policy)
                    or any(anchor[k] != row[k] for k in ('repo','epoch','owner','resource_id'))):
                _refuse()
    except (KeyError,TypeError,ValueError): _refuse()


def validate_external(external, repo):
    """Validate structure from a trusted observer; JSON alone is not attestation."""
    try:
        bindings = external['resource_bindings']
        proofs = external['resource_proofs']
        if (external['repo'] != repo or external['complete'] is not True or
                external['fenced'] is not True or not external['epoch'] or not external['owner'] or
                set(bindings) != set(REQUIRED_RESOURCES) or set(proofs) != set(REQUIRED_RESOURCES) or
                external['binding_sha256'] != digest(bindings) or
                external['inventory_sha256'] != digest(external['writers']) or
                not isinstance(external['writers'], list)):
            _refuse()
        for resource, classes in REQUIRED_RESOURCES.items():
            proof = proofs[resource]
            _revision(resource,proof,protected=True)
            method = proof.get('protection_method')
            if (not isinstance(bindings[resource], str) or not bindings[resource] or
                    proof['resource'] != resource or proof['resource_id'] != bindings[resource] or
                    proof['repo'] != repo or proof['epoch'] != external['epoch'] or
                    proof['owner'] != external['owner'] or
                    proof['default_authority'] != 'deny' or proof.get('predecessor_authority_denied') is not True or
                    set(proof.get('covered_credential_classes', [])) != set(classes) or
                    method not in {'native_revocation','resource_enforced_denial'} or
                    (method == 'native_revocation' and proof.get('credential_revocation_complete') is not True) or
                    (method == 'resource_enforced_denial' and 'credential_revocation_complete' in proof) or
                    'revoked_credential_classes' in proof or
                    proof['canonical_gate'] != CANONICAL_GATE or
                    proof.get('control_gate') != (CONTROL_GATE if resource == 'github' else None) or
                    proof['receipt_sha256'] != digest({k:v for k,v in proof.items() if k != 'receipt_sha256'})):
                _refuse()
        from .control_planes import validate_convergence
        convergence = validate_convergence(external['control_planes'], external)
        return {'repo':repo, 'epoch':external['epoch'], 'owner':external['owner'],
                'control_planes_sha256':convergence,
                'binding_sha256':external['binding_sha256'],
                'protection_sha256':digest(proofs), 'fence':external['fence'], 'fenced':True}
    except (KeyError, TypeError, ValueError, AttributeError):
        _refuse()


class ExclusionFence:
    """Restartable exact-resource CAS contract for activation-time adapters.

    Each port implements inspect(repo) and exclude(repo, observed_revision,
    policy). Unknown/lost effects are inspected on the next invocation, never
    retried in the same invocation. A competing epoch cannot take ownership.
    Bindings are independently reviewed actual service IDs, never discovered
    from a resource chosen by the adapter after activation has begun.
    """
    def __init__(self, repo, epoch, owner, ports, bindings, *, review=None, key_binding=None,
                 resource_separation=None, protection_methods=None, control_planes=None):
        if (not all(isinstance(x,str) and x for x in (repo,epoch,owner)) or
                set(ports) != set(REQUIRED_RESOURCES) or set(bindings) != set(REQUIRED_RESOURCES)):
            _refuse()
        self.repo, self.epoch, self.owner = repo, epoch, owner
        self.control_planes = control_planes
        self.ports, self.bindings = dict(ports), copy.deepcopy(bindings)
        self.review, self.key_binding = copy.deepcopy(review), copy.deepcopy(key_binding)
        self.resource_separation = copy.deepcopy(resource_separation)
        default_methods = {name:'native_revocation' for name in REQUIRED_RESOURCES}
        self.protection_methods = copy.deepcopy(protection_methods or default_methods)
        if (set(self.protection_methods) != set(REQUIRED_RESOURCES) or
                any(method not in {'native_revocation','resource_enforced_denial'}
                    for method in self.protection_methods.values())):
            _refuse()

    def _policy(self, resource):
        method = self.protection_methods[resource]
        policy = {'repo':self.repo, 'resource':resource, 'resource_id':self.bindings[resource],
                'epoch':self.epoch, 'owner':self.owner, 'default_authority':'deny',
                'protection_method':method, 'predecessor_authority_denied':True,
                'covered_credential_classes':copy.deepcopy(REQUIRED_RESOURCES[resource]),
                'canonical_gate':copy.deepcopy(CANONICAL_GATE),
                'control_gate':copy.deepcopy(CONTROL_GATE) if resource == 'github' else None}
        if method == 'native_revocation':
            policy['credential_revocation_complete'] = True
        return policy

    def _inspect(self, resource):
        row = self.ports[resource].inspect(self.repo)
        _revision(resource,row)
        if (row.get('repo') != self.repo or row.get('resource') != resource or
                row.get('resource_id') != self.bindings[resource] or
                row.get('inventory_complete') is not True or not isinstance(row.get('actors'), list)):
            _refuse()
        return row

    def control_plane_check(self, rows, *, final=False):
        from .control_planes import ControlPlaneConvergence
        if type(self.control_planes) is not ControlPlaneConvergence:
            raise StateInvalid('CONTROL_PLANE_CONVERGENCE_PREREQUISITE')
        return self.control_planes.check(self, rows, final=final)

    def establish(self):
        self.control_plane_check({r:self._inspect(r) for r in REQUIRED_RESOURCES})
        for resource in REQUIRED_RESOURCES:
            row = self._inspect(resource)
            desired = self._policy(resource)
            if row.get('protection') is not None:
                if row['protection'] != desired:
                    _refuse()
                continue
            # No response retry. A future invocation adopts an exact readback.
            self.ports[resource].exclude(self.repo, row['revision'], desired)
            if self._inspect(resource).get('protection') != desired:
                _refuse()
        self.assert_exclusive(self.repo)

    def authority_observation(self):
        proofs, writers, rows = {}, [], {}
        for resource in REQUIRED_RESOURCES:
            row = self._inspect(resource)
            rows[resource] = row
            if row.get('protection') != self._policy(resource):
                _refuse()
            proof = {**copy.deepcopy(row['protection']), 'revision':row['revision']}
            if resource == 'github':
                proof.update(revision_kind=row['revision_kind'],epoch_anchor=copy.deepcopy(row['epoch_anchor']))
            proof['receipt_sha256'] = digest(proof)
            proofs[resource] = proof
            writers.extend({'resource':resource, **copy.deepcopy(actor)} for actor in row['actors'])
        external = {'repo':self.repo,'epoch':self.epoch,'owner':self.owner,
            'fence':digest({'repo':self.repo,'epoch':self.epoch,'owner':self.owner,'bindings':self.bindings}),
            'fenced':True,'complete':True,'writers':writers,'inventory_sha256':digest(writers),
            'resource_bindings':copy.deepcopy(self.bindings),'binding_sha256':digest(self.bindings),
            'resource_proofs':proofs, 'control_planes':self.control_plane_check(rows, final=True)}
        validate_external(external,self.repo)
        return external

    def assert_exclusive(self, repo):
        if repo != self.repo: _refuse()
        return self.authority_observation()

    def observe(self, repo):
        """Compose with GitHubAuthorityObserver using trusted review metadata.

        Activation adapters supply these from independently approved authority
        material and runtime key metadata, never from the candidate's own flags.
        No key value belongs in this object or its observation.
        """
        from .identity import require_sha
        external = self.assert_exclusive(repo)
        try:
            if self.review['repo'] != repo: _refuse()
            for name in ('policy_sha256','code_sha256','closed_evidence_sha256'):
                require_sha(self.review[name])
            if (self.key_binding['name'] != 'NOTEBOOKLM_STATE_KEY' or
                    self.key_binding['available'] is not True or not self.key_binding['updated_at']):
                _refuse()
        except (KeyError, TypeError, ValueError):
            _refuse()
        return {'external':external,'approved_revision':copy.deepcopy(self.review),
                'key_binding':copy.deepcopy(self.key_binding),
                'resource_separation':copy.deepcopy(self.resource_separation)}
