"""Explicit authority transfer; no provider calls and no implicit live activation.

The backend must CAS BOTH main and the observed state revision. Workflow and
external-service exclusion is a separate trusted fence, not a multi-GET lock.
The journal occupies the existing controller state document throughout.
"""
from __future__ import annotations

import copy

from .identity import MediaIdentity, SourceIdentity, digest, require_sha
from .migration import prepare_migration
from .sealed import seal, unseal
from .state import StateInvalid, validate_state

PHASES = ('PREPARED', 'LEGACY_QUIESCING', 'LEGACY_QUIESCED', 'IMPORT_READY',
          'CAPABILITY_SEALED', 'STATE_IMPORTED', 'CANONICAL_AUTHORITY_ESTABLISHED',
          'LEGACY_RETIRED', 'VERIFIED')
OWNER = 'kesher-canonical-controller'
ROLES = {'controller', 'worker', 'retired', 'diagnostic', 'separate_infrastructure', 'handover'}
DISABLED = {'disabled_manually', 'disabled_inactivity', 'deleted'}


def _fail(reason):
    raise StateInvalid('HANDOVER_' + reason)


def observation_basis(observation: dict, repo: str) -> dict:
    """Validate a complete, trusted observation; unknown is never quiescence."""
    try:
        if any(observation.get(k) is not True for k in
               ('definitions_valid', 'inventory_complete', 'runs_complete')):
            _fail('OBSERVATION_INCOMPLETE')
        for name, length in [('main_sha', 40), ('policy_sha256', 64), ('code_sha256', 64)]:
            require_sha(observation[name], length)
        approval = observation['approved_revision']
        if (approval.get('repo') != repo or approval.get('code_sha256') != observation['code_sha256']
                or approval.get('policy_sha256') != observation['policy_sha256']):
            _fail('UNREVIEWED_AUTHORITY_REVISION')
        require_sha(approval['closed_evidence_sha256'])
        workflows = observation['workflows']
        if (not isinstance(workflows, list) or not workflows
                or len({w['id'] for w in workflows}) != len(workflows)
                or len({w['path'] for w in workflows}) != len(workflows)):
            _fail('WORKFLOW_INVENTORY_INVALID')
        for w in workflows:
            if (type(w['id']) is not int or w['id'] <= 0 or w['role'] not in ROLES
                    or not isinstance(w['path'], str) or not w['path']
                    or w['state'] not in DISABLED | {'active'}):
                _fail('UNCLASSIFIED_WORKFLOW')
        if sum(w['role'] == 'controller' for w in workflows) != 1:
            _fail('SINGLE_CONTROLLER_REQUIRED')
        if any(w['state'] != 'active' for w in workflows if w['role'] in {'controller', 'worker'}):
            _fail('CANONICAL_WORKFLOW_UNAVAILABLE')
        external = observation['external']
        from .exclusion import validate_external
        exclusion = validate_external(external, repo)
        if (external.get('complete') is not True or external.get('fenced') is not True
                or external.get('repo') != repo or not external.get('epoch') or not external.get('fence')
                or external.get('inventory_sha256') != digest(external.get('writers'))
                or not isinstance(external.get('writers'), list)):
            _fail('EXCLUSIVE_EXTERNAL_FENCE_REQUIRED')
        if not isinstance(observation['active_runs'], list):
            _fail('RUN_INVENTORY_INVALID')
        key = observation['key_binding']
        if key.get('name') != 'NOTEBOOKLM_STATE_KEY' or key.get('available') is not True or not key.get('updated_at'):
            _fail('RUNTIME_KEY_BINDING_REQUIRED')
        return {'repo': repo, 'main_sha': observation['main_sha'],
                'closed_evidence_sha256': approval['closed_evidence_sha256'],
                'policy_sha256': observation['policy_sha256'], 'code_sha256': observation['code_sha256'],
                'workflows': sorted([{k: w[k] for k in ('id', 'path', 'role')} for w in workflows], key=lambda w: w['id']),
                'external_fence': exclusion,
                'key_binding': copy.deepcopy(key)}
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, StateInvalid): raise
        _fail('MALFORMED_OBSERVATION')


def _quiescent(observation, main_sha):
    # A retained workflow filename may have run old mutating code. Neither a
    # diagnostic label nor a completed GitHub producer proves external settling.
    if observation['external']['writers']:
        return False
    roles = {w['id']: w['role'] for w in observation['workflows']}
    for run in observation['active_runs']:
        if _control_run(run, roles.get(run.get('workflow_id')), main_sha): continue
        if (run.get('workflow_id') not in roles
                or run.get('head_sha') != main_sha
                or roles[run['workflow_id']] not in {'diagnostic', 'separate_infrastructure'}):
            return False
    return True


def _control_run(run, role, main_sha):
    # This reviewed role has no provider credentials and may invoke ONLY the
    # independently authenticated, credential-owning cutover gateway. All other
    # main code and epoch/review gates remain mandatory; it is not a worker or
    # an exception for an ordinary legacy mutator. Competing steps still use CAS.
    return (role == 'handover' and run.get('head_sha') == main_sha
            and run.get('event') == 'workflow_dispatch' and run.get('head_branch') == 'main'
            and run.get('path','').split('@',1)[0] == '.github/workflows/kesher-production-cutover.yml')


def _legacy_body(document):
    return {k: copy.deepcopy(v) for k, v in document.items() if k != 'handover'}


def validate_journal(handover: dict):
    try:
        basis = handover['basis']
        if handover['id'] != digest(basis): _fail('JOURNAL_IDENTITY_CHANGED')
        journal = handover['journal']
        if not journal or len(journal) > len(PHASES): _fail('JOURNAL_INVALID')
        prior = None
        for index, row in enumerate(journal):
            if (row['phase'] != PHASES[index] or row['previous'] != prior
                    or row['sha256'] != digest({k: v for k, v in row.items() if k != 'sha256'})
                    or row['handover_id'] != handover['id']):
                _fail('JOURNAL_INVALID')
            prior = row['sha256']
        if handover['phase'] != journal[-1]['phase']: _fail('JOURNAL_INVALID')
        if handover['initial_workflow_states'] != basis['initial_workflow_states']:
            _fail('INITIAL_TOPOLOGY_CHANGED')
        phase_index = PHASES.index(handover['phase'])
        for field, boundary in [('sealed_capabilities', 4), ('retirement', 2)]:
            if phase_index >= boundary:
                if journal[boundary]['evidence'][field + '_sha256'] != digest(handover[field]):
                    _fail('DURABLE_EVIDENCE_CHANGED')
        if phase_index < 4 and handover['sealed_capabilities']:
            _fail('PREMATURE_SEALING')
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, StateInvalid): raise
        _fail('JOURNAL_INVALID')


def _transition(handover, phase, evidence):
    index = len(handover['journal'])
    if index >= len(PHASES) or PHASES[index] != phase: _fail('PHASE_ORDER')
    row = {'phase': phase, 'handover_id': handover['id'], 'evidence': copy.deepcopy(evidence),
           'previous': handover['journal'][-1]['sha256'] if index else None}
    row['sha256'] = digest(row)
    handover['journal'].append(row)
    handover['phase'] = phase


def require_authority(state: dict, observation: dict):
    """Live controller/workers must re-observe topology, never trust two flags."""
    handover = state.get('handover')
    if not isinstance(handover, dict): _fail('VERIFIED_AUTHORITY_REQUIRED')
    validate_journal(handover)
    expected = handover['basis']['environment']
    actual = observation_basis(observation, expected['repo'])
    # Main can advance after activation through canonical article publication;
    # the pinned workflow and executable-code policy must remain identical.
    if {k:v for k,v in actual.items() if k != 'main_sha'} != {k:v for k,v in expected.items() if k != 'main_sha'}:
        _fail('AUTHORITY_TOPOLOGY_CHANGED')
    if (state.get('schema_version') != 6 or handover['phase'] != 'VERIFIED'
            or state.get('migration', {}).get('status') != 'complete'
            or state['migration'].get('runtime_owner') != OWNER
            ):
        _fail('VERIFIED_AUTHORITY_REQUIRED')
    if any(w['state'] not in DISABLED for w in observation['workflows'] if w['role'] == 'retired'):
        _fail('LEGACY_RETIREMENT_INCOMPLETE')
    # Drain is an import precondition. After VERIFIED, current controller runs
    # and exact command-owned workers are the intended authority, not rivals.
    roles = {w['id']: w['role'] for w in observation['workflows']}
    from .outbox import workflow_for
    paths = {w['id']: w['path'].split('/')[-1] for w in observation['workflows']}
    for run in observation['active_runs']:
        role = roles.get(run.get('workflow_id'))
        if _control_run(run, role, observation['main_sha']): continue
        if role in {'controller', 'diagnostic', 'separate_infrastructure'} and run.get('head_sha') == observation['main_sha']:
            continue
        if role == 'worker':
            from .state import target_is_current
            from .identity import identity_from_dict
            for c in state['commands'].values():
                if (c['code_sha'] != run.get('head_sha') or workflow_for(c) != paths[run['workflow_id']]
                        or run.get('event') != 'workflow_dispatch' or run.get('head_branch') != 'main'
                        or run.get('path') != '.github/workflows/' + workflow_for(c)):
                    continue
                owned = (c.get('owner') or {}).get('run_id') == f"{run.get('id')}/{run.get('run_attempt')}"
                dispatched = (c['phase'] == 'REQUESTED' and c['outcome'] == 'pending' and c['owner'] is None
                    and target_is_current(state, identity_from_dict(c['target']))
                    and run.get('head_sha') == observation['main_sha']
                    and run.get('display_title') == 'kesher-command:' + c['id']
                    and any(a['workflow'] == workflow_for(c) and a['inputs'] == {'command_id':c['id']}
                            for a in c['dispatch']['attempts']))
                if owned or dispatched: break
            else:
                _fail('UNOWNED_ACTIVE_WRITER')
            continue
        _fail('UNOWNED_ACTIVE_WRITER')
    if observation['external']['writers']:
        _fail('UNFENCED_EXTERNAL_WRITER')


def require_legacy_writable(state: dict):
    from .legacy_retirement import validate_legacy_read
    validate_legacy_read(state)
    if not isinstance(state, dict) or state.get('schema_version') != 5:
        _fail('LEGACY_AUTHORITY_FENCED')


class Coordinator:
    """One durable transition/effect per tick, all writes snapshot-bound CAS.

    backend.observe supplies independently verified topology/exclusive-fence
    evidence. backend.save must guard both exact Git refs, not reread/rebind.
    This class never enables a workflow, dispatches work or calls a provider.
    """
    def __init__(self, backend, inputs: dict, *, closure: dict, key):
        self.backend, self.inputs, self.closure, self.key = backend, copy.deepcopy(inputs), copy.deepcopy(closure), key
        if not closure or any(not isinstance(v, str) or len(v) != 64 for v in closure.values()):
            _fail('CLOSURE_EVIDENCE_REQUIRED')
        retained = self.inputs.get('retained_evidence')
        if retained is None or closure.get('retained_evidence') != digest(retained):
            _fail('CLOSED_EVIDENCE_FLOOR_REQUIRED')
        self.baseline = prepare_migration(**self.inputs)
        if 'github_exclusion' in self.inputs['controller']:
            self.baseline['github_exclusion'] = copy.deepcopy(self.inputs['controller']['github_exclusion'])

    def _check(self, loaded, observation):
        state = loaded.state
        h = state['handover']; validate_journal(h)
        basis = h['basis']
        if (basis['input_sha256'] != digest(self.inputs) or basis['closure'] != self.closure
                or basis['environment'] != observation_basis(observation, self.backend.repo)):
            _fail('PRECONDITION_CHANGED')
        if state['schema_version'] == 5:
            if h['phase'] not in PHASES[:5]: _fail('LEGACY_PHASE_INVALID')
            if digest(_legacy_body(state)) != basis['legacy_sha256']: _fail('LEGACY_BODY_CHANGED')
        elif state['schema_version'] == 6:
            validate_state(state)
            if h['phase'] not in PHASES[5:]: _fail('IMPORTED_PHASE_INVALID')
            if h['phase'] != 'VERIFIED' and digest(_legacy_body(state)) != basis['baseline_sha256']:
                _fail('IMPORTED_BODY_CHANGED')
        else: _fail('SCHEMA_CHANGED')
        initial = h['initial_workflow_states']
        for workflow in observation['workflows']:
            wid = str(workflow['id']); expected = initial[wid]
            effect = h['retirement'].get(wid)
            if effect and effect.get('observed_disabled'):
                if workflow['state'] not in DISABLED: _fail('RETIRED_WRITER_REACTIVATED')
            elif workflow['state'] != expected and not (effect and workflow['state'] in DISABLED):
                _fail('WORKFLOW_STATE_CHANGED')
        return h

    def _save(self, loaded, state):
        # Recheck all mutable preconditions just before the atomic Git-ref CAS.
        # External fencing is a required independent trust boundary.
        fresh = self.backend.observe()
        self._check(loaded, fresh)
        if state['handover']['phase'] in PHASES[2:]:
            if (not _quiescent(fresh, self.inputs['main_sha']) or
                    any(w['state'] not in DISABLED for w in fresh['workflows'] if w['role']=='retired')):
                _fail('QUIESCENCE_LOST_BEFORE_WRITE')
        return self.backend.save(loaded, state, main_sha=self.inputs['main_sha'])

    def tick(self):
        loaded = self.backend.load(); state = loaded.state
        from .git_exclusion import no_legacy_incident
        no_legacy_incident(state)
        observation = self.backend.observe()
        environment = observation_basis(observation, self.backend.repo)
        if environment['closed_evidence_sha256'] != self.closure['retained_evidence']:
            _fail('UNREVIEWED_CLOSED_EVIDENCE')
        if 'handover' not in state:
            if (state.get('schema_version') != 5 or loaded.blob_sha != self.inputs['controller_sha']
                    or state != self.inputs['controller'] or environment['main_sha'] != self.inputs['main_sha']):
                _fail('EXACT_LEGACY_SNAPSHOT_REQUIRED')
            if not _quiescent(observation, environment['main_sha']):
                return 'WAITING_FOR_LEGACY_DRAIN'
            basis = {'environment': environment, 'legacy_blob_sha': loaded.blob_sha,
                     'legacy_sha256': digest(state), 'input_sha256': digest(self.inputs),
                     'closure': self.closure, 'baseline_sha256': digest(self.baseline),
                     'initial_workflow_states': {str(w['id']): w['state'] for w in observation['workflows']}}
            h = {'id': digest(basis), 'basis': basis, 'journal': [], 'retirement': {},
                 'initial_workflow_states': {str(w['id']): w['state'] for w in observation['workflows']},
                 'sealed_capabilities': []}
            _transition(h, 'PREPARED', {'legacy_blob_sha': loaded.blob_sha, 'observation_sha256': digest(observation)})
            state['handover'] = h
            # Before the journal exists, compare the full fresh observation too.
            if self.backend.observe() != observation: _fail('PREPARATION_OBSERVATION_CHANGED')
            self.backend.save(loaded, state, main_sha=self.inputs['main_sha'])
            return 'PREPARED'
        h = self._check(loaded, observation)
        state['handover'] = h
        phase = h['phase']
        if phase == 'VERIFIED':
            require_authority(state, observation)
            return phase
        if phase == 'PREPARED':
            next_phase = 'LEGACY_QUIESCING'
        elif phase == 'LEGACY_QUIESCING':
            for workflow in observation['workflows']:
                if workflow['role'] != 'retired': continue
                wid = str(workflow['id']); effect = h['retirement'].get(wid)
                if effect is None:
                    h['retirement'][wid] = {'workflow_id': workflow['id'], 'path': workflow['path'],
                                           'desired_state': 'disabled_manually', 'observed_disabled': False,
                                           'observations': []}
                    self._save(loaded, state)
                    return phase
                if effect['observed_disabled']: continue
                effect['observations'].append({'state': workflow['state'], 'observation_sha256': digest(observation)})
                if workflow['state'] in DISABLED:
                    effect['observed_disabled'] = True
                    self._save(loaded, state)
                else:
                    # Disable is a monotonic idempotent desired-state operation.
                    # A retry requires a fresh active read and durable evidence;
                    # successful-but-lost responses are adopted without another PUT.
                    if len(effect['observations']) > 3: _fail('RETIREMENT_UNCERTAIN')
                    self._save(loaded, state)
                    self.backend.disable(workflow['id'])
                return phase
            if not _quiescent(observation, self.inputs['main_sha']): return 'WAITING_FOR_LEGACY_DRAIN'
            next_phase = 'LEGACY_QUIESCED'
        else:
            if (not _quiescent(observation, self.inputs['main_sha'])
                    or any(w['state'] not in DISABLED for w in observation['workflows'] if w['role'] == 'retired')):
                _fail('QUIESCENCE_LOST')
            next_phase = PHASES[PHASES.index(phase) + 1]
            if phase == 'IMPORT_READY':
                secret = self.key()
                # Validate even when no capability is present: trusted runtime
                # access is an import precondition, never inferred from metadata.
                if not isinstance(secret, str) or len(secret) < 24: _fail('RUNTIME_KEY_UNAVAILABLE')
                seen = set()
                required = {digest({'target':q['target'],'item':q['legacy_item_sha256']})
                    for q in self.baseline['quarantine']
                    if q.get('failure_class') == 'LEGACY_UPLOAD_CAPABILITY_REQUIRES_SEALING'}
                for archive in self.inputs['artifacts']:
                    for item in archive['items']:
                        if not item.get('upload_session_uri'): continue
                        source = item['source']
                        kind = {'video_overview':'overview', 'article_short':'short'}.get(item['type'])
                        if kind is None: _fail('CAPABILITY_IDENTITY_INVALID')
                        target = MediaIdentity(SourceIdentity(source['date'],source['slug'],source['content_sha256']),kind)
                        candidates = [q for q in self.baseline['quarantine']
                                      if q.get('failure_class') == 'LEGACY_UPLOAD_CAPABILITY_REQUIRES_SEALING'
                                      and q.get('target') == target.to_dict() and q.get('legacy_item_sha256') == digest(item)]
                        if not candidates: _fail('CAPABILITY_NOT_EXACT_QUARANTINED_RECORD')
                        identity = digest({'target':target.to_dict(), 'item':digest(item)})
                        if identity in seen: continue
                        seen.add(identity)
                        h['sealed_capabilities'].append({'id':identity,'target':target.to_dict(),
                            'legacy_item_sha256':digest(item),'generation_attempt':item.get('fresh_generation_attempt'),
                            'origins':[q['origin'] for q in candidates], 'purpose':'youtube_upload',
                            'envelope':seal(item['upload_session_uri'],secret,target,repo=self.backend.repo,purpose='youtube_upload')})
                if seen != required: _fail('RETAINED_CAPABILITY_UNAVAILABLE_FOR_SEALING')
            elif phase == 'CAPABILITY_SEALED':
                from .identity import identity_from_dict
                secret = self.key()
                for capability in h['sealed_capabilities']:
                    unseal(capability['envelope'], secret, identity_from_dict(capability['target']),
                           repo=self.backend.repo, purpose=capability['purpose'])
                # Preserve every baseline and every quarantine, including the
                # capability quarantine. Encryption grants no new worker receipt.
                state = copy.deepcopy(self.baseline)
                if digest(state) != h['basis']['baseline_sha256']: _fail('IMPORT_PAYLOAD_CHANGED')
                state['handover'] = h
            elif phase == 'LEGACY_RETIRED':
                state['migration'].update(status='complete',runtime_owner=OWNER)
                state['audit'].append({'at':self.inputs['now'],'event':'authority_handover_verified',
                                       'handover_id':h['id'],'public_completion_inferred':False})
        _transition(h, next_phase, {'observation_sha256':digest(observation),
                                   'sealed_capabilities_sha256':digest(h['sealed_capabilities']),
                                   'retirement_sha256':digest(h['retirement'])})
        if state['schema_version'] == 6: validate_state(state)
        self._save(loaded, state)
        return next_phase
