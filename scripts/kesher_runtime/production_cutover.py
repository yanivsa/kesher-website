"""One restartable cutover step, composed from existing authority contracts.

Runs inside the credential-owning gateway, not in an Actions runner holding a
general write token. Inputs/key/approval/ports are installed by its independent
administrator. A client supplies only epoch and reviewed main revision. No
caller-supplied resource evidence, credentials or migration inputs are accepted.
"""
import copy

from .authority_topology import validate_registered_inventory
from .exclusion import REQUIRED_RESOURCES
from .handover import Coordinator
from .state import StateInvalid


def reconcile_registrations(rows, rules):
    validate_registered_inventory(rows, rules, complete=True)
    # Every service ID is independently reviewed. A known path is not sufficient.
    for row in rows:
        entry = rules.get('registrations', {}).get(row['path'])
        expected = entry['id'] if entry is not None else rules['workflows'][row['path']].get('registration_id')
        if expected != row['id']:
            raise StateInvalid('CUTOVER_EXACT_REGISTRATION_REVIEW_REQUIRED')
    return copy.deepcopy(rows)


class CutoverRuntime:
    def __init__(self, *, fence, backend, inputs, closure, key, infrastructure_check):
        if not callable(infrastructure_check) or not callable(key):
            raise StateInvalid('CUTOVER_TRUSTED_SERVICE_OBSERVERS_REQUIRED')
        self.fence, self.backend = fence, backend
        self.inputs = inputs if callable(inputs) else copy.deepcopy(inputs)
        self.closure = copy.deepcopy(closure)
        self.key, self.infrastructure_check = key, infrastructure_check

    def step(self):
        # Inspect ALL resources before the first write. A partial bootstrap must
        # never retire Actions while an unobservable provider still has authority.
        rows = {resource: self.fence._inspect(resource) for resource in REQUIRED_RESOURCES}
        self.infrastructure_check()
        for resource, row in rows.items():
            desired = self.fence._policy(resource)
            if row.get('protection') not in (None, desired):
                raise StateInvalid('CUTOVER_COMPETING_RESOURCE_EPOCH')
        self.fence.control_plane_check(rows)
        for resource, row in rows.items():
            if row.get('protection') is not None: continue
            try:
                self.fence.ports[resource].exclude(self.fence.repo, row['revision'], self.fence._policy(resource))
            except StateInvalid as exc:
                if resource != 'github' or str(exc) != 'GITHUB_RESOURCE_DRAIN_PENDING': raise
            # A completed resource mutation is read back on the NEXT invocation.
            # Lost responses escape; no uncertain mutation is repeated here.
            return self._report('RESOURCE_PENDING', resource)
        self.fence.assert_exclusive(self.fence.repo)
        inputs=self.inputs(self.backend.read_snapshot()) if callable(self.inputs) else self.inputs
        phase = Coordinator(self.backend, inputs, closure=self.closure, key=self.key).tick()
        return self._report(phase)

    @staticmethod
    def _report(phase, resource=None):
        return {'phase': phase, 'resource': resource, 'production_activated': False,
                'public_completion_inferred': False}
