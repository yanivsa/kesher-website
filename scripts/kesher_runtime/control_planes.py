"""Predecessor actors share the six resource fences; no ChatGPT resource exists.

The administrator installs a fresh, independent operator/provider observer.
Repository files and task prompts are not live readback. This module neither
edits scheduled tasks nor invokes a Jules cancellation API. Unknown scope,
missing observer or unproved session retirement refuses admission.
"""
import copy

from .identity import digest
from .policy import seconds
from .state import StateInvalid

ACTOR_POLICY = {
    'version': 1,
    'actors': {
        'controller_v5': {'role': 'predecessor', 'resources': ['github', 'jules'],
                          'capabilities': ['state_write', 'workflow_dispatch', 'jules_continue']},
        'controller_v6_shadow': {'role': 'observer', 'resources': [], 'capabilities': ['read']},
        'controller_schema6': {'role': 'canonical', 'resources': ['github'],
                              'capabilities': ['state_write', 'workflow_dispatch']},
        'canonical_workers': {'role': 'canonical',
                              'resources': ['github', 'jules', 'notebooklm', 'youtube', 'cloudflare', 'image_provider'],
                              'capabilities': ['state_write', 'branch_write', 'pr_write', 'jules_create', 'provider_create',
                                               'provider_continue', 'youtube_upload', 'cloudflare_write', 'image_provider_create']},
        'jules_predecessor_sessions': {'role': 'predecessor', 'resources': ['github', 'jules'],
                                     'capabilities': ['branch_write', 'pr_write', 'merge', 'jules_continue']},
        'jules_predecessor_creators': {'role': 'predecessor', 'resources': ['github', 'jules'],
                                     'capabilities': ['jules_create', 'jules_continue', 'branch_write', 'pr_write']},
        'repository_supervisors': {'role': 'predecessor', 'resources': ['github', 'jules'],
                                  'capabilities': ['workflow_dispatch', 'state_write', 'jules_create', 'jules_continue', 'merge']},
        'external_master_active_supervisor': {'role': 'predecessor', 'resources': ['github', 'jules'],
                                             'capabilities': ['workflow_dispatch', 'state_write', 'jules_create', 'jules_continue', 'merge']},
        'manual_recovery': {'role': 'predecessor',
                            'resources': ['github', 'jules', 'notebooklm', 'youtube', 'cloudflare', 'image_provider'],
                            'capabilities': ['workflow_dispatch', 'branch_write', 'provider_create', 'youtube_upload']},
    },
}
PREDECESSORS = sorted(name for name, actor in ACTOR_POLICY['actors'].items() if actor['role'] == 'predecessor')
SUPERVISOR = 'Master Active Supervisor'


def refuse():
    raise StateInvalid('CONTROL_PLANE_CONVERGENCE_PREREQUISITE')


def validate_actor_policy(value):
    # A new actor/control path requires an independent trust-root review; no
    # filename classifier or caller-provided role can grant canonical authority.
    if value != ACTOR_POLICY:
        refuse()
    return copy.deepcopy(value)


def _readback(row, *, repo, epoch, owner, bindings, supervisor_id, fenced):
    from .jules import session_name
    try:
        required = {'repo', 'epoch', 'owner', 'resource_bindings', 'actor_policy_sha256',
                    'inventory_complete', 'unknown_actors', 'predecessor_actors', 'supervisor', 'jules'}
        if set(row) not in (required, required | {'observed_at'}): refuse()
        if (row['repo'] != repo or row['epoch'] != epoch or row['owner'] != owner
                or row['resource_bindings'] != {r: bindings[r] for r in ('github', 'jules')}
                or row['actor_policy_sha256'] != digest(ACTOR_POLICY)
                or row['inventory_complete'] is not True or row['unknown_actors'] != []
                or sorted(row['predecessor_actors']) != PREDECESSORS):
            refuse()
        supervisor = row['supervisor']
        if set(supervisor) != {'name', 'task_id', 'state', 'github_authority', 'jules_authority',
                               'direct_takeover_enabled', 'legacy_mutation_enabled'}: refuse()
        if (supervisor['name'] != SUPERVISOR or supervisor['task_id'] != supervisor_id
                or not isinstance(supervisor_id, str) or not supervisor_id
                or supervisor['state'] not in {'suspended', 'observer', 'resource_restricted'}
                or supervisor['github_authority'] != 'canonical_admission_only'
                or supervisor['jules_authority'] != 'canonical_admission_only'
                or supervisor['direct_takeover_enabled'] is not False):
            refuse()
        if supervisor['state'] == 'resource_restricted':
            if not fenced: refuse()
        elif supervisor['legacy_mutation_enabled'] is not False:
            refuse()
        jules = row['jules']
        if set(jules) != {'inventory_complete', 'unknown_authority', 'inventory_scope',
                          'future_creation', 'predecessor_sessions'}: refuse()
        if (jules['inventory_complete'] is not True or jules['unknown_authority'] != []
                or jules['inventory_scope'] != 'all_repo_capable_predecessor_sessions_and_grants'
                or jules['future_creation'] != 'canonical_command_only'
                or not isinstance(jules['predecessor_sessions'], list)):
            refuse()
        seen = set()
        for session in jules['predecessor_sessions']:
            if set(session) != {'name', 'repo', 'repository_access', 'continuation'}: refuse()
            name = session_name(session)
            if name in seen or session['repo'] != repo: refuse()
            seen.add(name)
            allowed = {'denied'} if fenced else {'legacy', 'denied'}
            if session['repository_access'] not in allowed or session['continuation'] not in allowed:
                refuse()
        # Freshness is checked on each observer call. Poll timestamps are not
        # authority identity; legitimate fresh reads do not invalidate handover.
        stable = {k: copy.deepcopy(row[k]) for k in ('repo', 'epoch', 'owner', 'resource_bindings',
                    'actor_policy_sha256', 'inventory_complete', 'unknown_actors', 'predecessor_actors', 'supervisor', 'jules')}
        stable['predecessor_actors'] = sorted(stable['predecessor_actors'])
        stable['jules']['predecessor_sessions'].sort(key=lambda s: s['name'])
        return stable
    except (KeyError, TypeError, ValueError, AttributeError, RuntimeError) as exc:
        if isinstance(exc, StateInvalid): raise
        refuse()


def _authority_identity(stable):
    """Permitted lifecycle facts are fresh checks, not immutable authority."""
    return {k:copy.deepcopy(stable[k]) for k in ('repo', 'epoch', 'owner', 'resource_bindings',
             'actor_policy_sha256', 'predecessor_actors')} | {
        'supervisor':{k:stable['supervisor'][k] for k in
                      ('name', 'task_id', 'github_authority', 'jules_authority', 'direct_takeover_enabled')},
        'jules':{k:stable['jules'][k] for k in ('inventory_scope', 'future_creation')},
    }


class ControlPlaneConvergence:
    """Trusted adapter dependency, never HTTP-client-selected evidence.

    observe must independently read the exact task/account configuration and
    the COMPLETE predecessor Jules grants/sessions inventory at the services.
    The operator must suspend/convert the task, or prove native GitHub AND Jules
    denial before claiming resource_restricted. A task prompt edit alone cannot
    prove denial. Production construction has no default observer/factory.
    """
    def __init__(self, *, repo, epoch, owner, bindings, supervisor_id, observe, clock):
        if (not callable(observe) or not callable(clock) or
                not all(isinstance(v, str) and v for v in (repo, epoch, owner, supervisor_id))):
            refuse()
        self.repo, self.epoch, self.owner = repo, epoch, owner
        self.bindings, self.supervisor_id = copy.deepcopy(bindings), supervisor_id
        self.observe, self.clock = observe, clock

    def check(self, fence, rows, *, final=False):
        if (self.repo != fence.repo or self.epoch != fence.epoch or self.owner != fence.owner
                or self.bindings != fence.bindings):
            refuse()
        fenced = all(rows[r].get('protection') == fence._policy(r) for r in ('github', 'jules'))
        if final and not fenced: refuse()
        row = self.observe()
        try:
            if not 0 <= seconds(self.clock(), row['observed_at']) <= 60: refuse()
        except (KeyError, TypeError, ValueError): refuse()
        stable = _readback(row, repo=self.repo, epoch=self.epoch, owner=self.owner, bindings=self.bindings,
                           supervisor_id=self.supervisor_id, fenced=fenced)
        return {'readback': stable, 'readback_sha256': digest(stable),
                'authority_sha256':digest(_authority_identity(stable)), 'native_fences_required': ['github', 'jules']}


def validate_convergence(proof, external):
    try:
        if (proof['native_fences_required'] != ['github', 'jules']
                or proof['readback_sha256'] != digest(proof['readback'])):
            refuse()
        stable = _readback(proof['readback'], repo=external['repo'], epoch=external['epoch'], owner=external['owner'],
                           bindings=external['resource_bindings'],
                           supervisor_id=proof['readback']['supervisor']['task_id'], fenced=True)
        if stable != proof['readback']: refuse()
        authority_sha256 = digest(_authority_identity(stable))
        if proof['authority_sha256'] != authority_sha256: refuse()
        return authority_sha256
    except (KeyError, TypeError, ValueError, AttributeError): refuse()
