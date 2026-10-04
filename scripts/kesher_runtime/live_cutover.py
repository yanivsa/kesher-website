"""Compose the real service runner without substituting provider attestations.

The independent service administrator installs native resource observers and
their isolation/revocation boundary. Unsupported providers use PrerequisitePort;
they cannot be bypassed using a receipt file. All Git/Actions mutation credentials
stay in GuardedGitHub. The client cannot select ports or migration evidence.
"""
import base64
import copy
import hashlib
import json

from .authority_topology import GitHubAuthorityObserver, executable_digest, inventory, policy
from .cutover_gateway import GuardedGitHub
from .exclusion import ExclusionFence, REQUIRED_RESOURCES
from .git_exclusion import GitHubResourceExclusion
from .github import _unique_object
from .handover_github import GitHubHandover
from .identity import digest, require_sha
from .production_cutover import CutoverRuntime, reconcile_registrations
from .state import StateInvalid


class OriginalMigrationInputs:
    """Reconstruct frozen inputs from the journal's exact ORIGINAL Git blob.

    Sources/archives/retained floor are independently approved private custody
    material. They never come from HTTP clients. After STATE_IMPORTED, the
    current Schema-6 document is never treated as legacy migration input.
    """
    def __init__(self, github, repo, *, main_sha, material, approved_digest):
        require_sha(main_sha,40); require_sha(approved_digest)
        if (set(material)&{'controller','controller_sha','main_sha'} or digest(material)!=approved_digest):
            raise StateInvalid('CUTOVER_REVIEWED_MIGRATION_MATERIAL_REQUIRED')
        self.github,self.repo,self.main_sha=github,repo,main_sha
        self.material=copy.deepcopy(material)

    def __call__(self, loaded):
        h=loaded.state.get('handover')
        if h:
            sha=h['basis']['legacy_blob_sha']; require_sha(sha,40)
            blob=self.github.request('GET','/repos/'+self.repo+'/git/blobs/'+sha)
            if blob.get('sha') != sha or blob.get('encoding') != 'base64':
                raise StateInvalid('CUTOVER_ORIGINAL_BLOB_REQUIRED')
            raw=base64.b64decode(''.join(blob['content'].split()),validate=True)
            if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=sha:
                raise StateInvalid('CUTOVER_ORIGINAL_BLOB_BYTES_CHANGED')
            controller=json.loads(raw,object_pairs_hook=_unique_object)
        else: controller,sha=loaded.state,loaded.blob_sha
        if controller.get('schema_version') != 5 or 'handover' in controller:
            raise StateInvalid('CUTOVER_ORIGINAL_LEGACY_INPUT_REQUIRED')
        return dict(copy.deepcopy(self.material),controller=controller,controller_sha=sha,main_sha=self.main_sha)


def build_runtime(*, github, repo, root, epoch, owner, bindings, boundary,
                  external_ports, review, key_binding, registered_bindings,
                  separation_observer, material, closure, key):
    """Independent gateway bootstrap; no live effects during construction.

    review is administrator-approved code/evidence metadata, NOT a resource
    attestation. Native boundary/port observers must independently establish the
    actual service protections on each call. Neither approval metadata nor an
    authenticated caller substitutes for their proofs.
    """
    if set(external_ports)!=set(REQUIRED_RESOURCES)-{'github'} or not callable(separation_observer):
        raise StateInvalid('CUTOVER_COMPLETE_NATIVE_PORTS_REQUIRED')
    rules=policy(root); definitions=inventory(root,rules)
    if (review.get('repo')!=repo or review['policy_sha256']!=digest({'policy':rules,'definitions':definitions})
            or review['code_sha256']!=executable_digest(root)
            or review['closed_evidence_sha256']!=closure['retained_evidence']
            or review['registrations_sha256']!=digest(registered_bindings)):
        raise StateInvalid('CUTOVER_INDEPENDENT_INSTALLED_REVIEW_REQUIRED')
    pinned=copy.deepcopy(rules)
    if set(registered_bindings)!=set(rules['workflows'])|set(rules.get('registrations',{})):
        raise StateInvalid('CUTOVER_COMPLETE_REGISTRATION_BINDINGS_REQUIRED')
    for path,identity in registered_bindings.items():
        if path in rules['workflows']:
            original=rules['workflows'][path].get('registration_id')
            if original is not None and original!=identity:raise StateInvalid('CUTOVER_REGISTRATION_REBOUND')
            pinned['workflows'][path]['registration_id']=identity
        elif rules['registrations'][path]['id']!=identity:raise StateInvalid('CUTOVER_REGISTRATION_REBOUND')
    temporary=ExclusionFence(repo,epoch,owner,dict.fromkeys(bindings),bindings)
    targets={identity:path for path,identity in registered_bindings.items()
             if path in pinned.get('registrations',{}) or
             pinned['workflows'][path]['role'] in {'retired','emergency_bridge'}}
    guarded=GuardedGitHub(github,repo=repo,policy=temporary._policy('github'),approval=review,boundary=boundary,
                         retirement_targets=targets)
    reader=GitHubAuthorityObserver(guarded,repo,root,fence=None)
    def registered():return reconcile_registrations(reader.pages('actions/workflows','workflows'),pinned)
    git_port=GitHubResourceExclusion(guarded,repo,main_sha=review['main_sha'],policy=temporary._policy('github'),
        rules=pinned,registered=registered,guard=boundary,separation=separation_observer,
        separation_binding={k:review[k] for k in ('repo','policy_sha256','code_sha256')} |
                           {'resource_bindings_sha256':digest(bindings)},protected_resources=bindings)
    class LiveFence(ExclusionFence):
        def observe(self, observed_repo):
            # Fresh actual service separation readback before each observation.
            context=separation_observer()
            self.resource_separation=copy.deepcopy(context.get('proofs'))
            git_port.targets()
            return super().observe(observed_repo)
    fence=LiveFence(repo,epoch,owner,dict(external_ports,github=git_port),bindings,review=review,key_binding=key_binding)
    observer=GitHubAuthorityObserver(guarded,repo,root,fence=fence)
    backend=GitHubHandover(guarded,repo,observer=observer,fence=fence)
    supplier=OriginalMigrationInputs(guarded,repo,main_sha=review['main_sha'],material=material,
                                   approved_digest=review['migration_material_sha256'])
    return CutoverRuntime(fence=fence,backend=backend,inputs=supplier,closure=closure,key=key,
                          infrastructure_check=git_port.targets)
