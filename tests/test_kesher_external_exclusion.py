"""Service authorization, not an empty runner list, fences stale authority."""
import copy
import unittest

from scripts.kesher_runtime.github import GitHubError
from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.state import StateInvalid
from tests import test_kesher_handover as fixtures


class ProtectedService:
    """Disposable resource ACL/CAS endpoint; mutations use its actual ACL."""
    def __init__(self, resource):
        self.resource = resource
        self.resource_id = 'resource-id:' + resource
        self.revision = 1
        self.protection = None
        self.effects = []
        self.actors = []
        self.requests = 0
        self.drop = False
        self.fail_before = False
        self.inventory_complete = True

    def inspect(self, repo):
        return {'repo': repo, 'resource': self.resource, 'resource_id': self.resource_id,
                'revision': self.revision, 'protection': copy.deepcopy(self.protection),
                'inventory_complete': self.inventory_complete, 'actors': copy.deepcopy(self.actors)}

    def exclude(self, repo, expected_revision, protection):
        if self.fail_before:
            self.fail_before = False
            raise GitHubError(None, 'crash before resource exclusion', uncertain=True)
        if expected_revision != self.revision or self.protection is not None:
            raise StateInvalid('Resource exclusion CAS lost')
        self.requests += 1
        self.protection = copy.deepcopy(protection)
        self.revision += 1
        if self.drop:
            self.drop = False
            raise GitHubError(None, 'lost exclusion acknowledgment', uncertain=True)

    def mutate(self, principal, *, epoch=None, state=None, command=None, run_id=None, code_sha=None):
        state = state or {}
        if self.protection is not None:
            p = self.protection
            if principal != 'canonical' or epoch != p['epoch']:
                raise StateInvalid('Resource rejected stale principal/epoch')
            from scripts.kesher_runtime.exclusion import require_resource_command
            require_resource_command(state, epoch, command, run_id, code_sha)
        self.effects.append(principal)


def protection_fixture():
    from scripts.kesher_runtime.exclusion import REQUIRED_RESOURCES, ExclusionFence
    services = {name: ProtectedService(name) for name in REQUIRED_RESOURCES}
    binding = {name: service.resource_id for name, service in services.items()}
    fence = ExclusionFence('owner/repo', 'exclusive-epoch', 'coordinator-one', services, binding)
    return fence, services


class ExternalExclusionTests(unittest.TestCase):
    def test_boolean_fence_is_not_accepted_by_coordinator(self):
        case = fixtures.HandoverTests(); case.setUp()
        case.backend.observation['external'].pop('resource_proofs', None)
        with self.assertRaises(StateInvalid):
            case.coordinator().tick()
        self.assertFalse(case.backend.writes)

    def test_partial_exclusion_refuses_canonical_and_handover_admission(self):
        fence, services = protection_fixture()
        next(iter(services.values())).fail_before = True
        with self.assertRaises(GitHubError): fence.establish()
        with self.assertRaises(StateInvalid): fence.assert_exclusive('owner/repo')
        case = fixtures.HandoverTests(); case.setUp()
        with self.assertRaises(StateInvalid):
            fence.authority_observation()
        self.assertFalse(case.backend.writes)

    def test_lost_acknowledgment_is_adopted_after_restart_without_repeating_effect(self):
        from scripts.kesher_runtime.exclusion import ExclusionFence
        fence, services = protection_fixture()
        first = next(iter(services.values())); first.drop = True
        with self.assertRaises(GitHubError): fence.establish()
        restarted = ExclusionFence(fence.repo, fence.epoch, fence.owner, services, fence.bindings)
        restarted.establish(); restarted.assert_exclusive('owner/repo')
        self.assertEqual(first.requests, 1)
        self.assertTrue(all(s.requests == 1 for s in services.values()))

    def test_competing_coordinator_cannot_replace_exclusion_epoch(self):
        from scripts.kesher_runtime.exclusion import ExclusionFence
        fence, services = protection_fixture(); fence.establish()
        other = ExclusionFence(fence.repo, 'competing-epoch', 'coordinator-two', services, fence.bindings)
        with self.assertRaises(StateInvalid): other.establish()
        self.assertTrue(all(s.requests == 1 for s in services.values()))

    def test_stale_dispatch_worker_session_and_credential_are_denied_by_resources(self):
        fence, services = protection_fixture(); fence.establish()
        for principal in ('new-legacy-dispatch', 'already-running-worker', 'surviving-jules-session', 'stale-credentialed-caller'):
            for service in services.values():
                with self.subTest(principal=principal, resource=service.resource):
                    with self.assertRaises(StateInvalid): service.mutate(principal)
        self.assertTrue(all(not s.effects for s in services.values()))

    def test_external_session_inventory_survives_completed_actions_run(self):
        fence, services = protection_fixture(); fence.establish()
        services['jules'].actors = [{'id': 'session-old', 'origin_run_status': 'completed', 'state': 'IN_PROGRESS'}]
        observation = fence.authority_observation()
        self.assertEqual(len(observation['writers']), 1)
        case = fixtures.HandoverTests(); case.setUp()
        case.backend.observation['external'] = observation
        self.assertEqual(case.coordinator().tick(), 'WAITING_FOR_LEGACY_DRAIN')
        self.assertFalse(case.backend.writes)

    def test_stale_legacy_after_schema6_and_restart_remains_denied(self):
        from scripts.kesher_runtime.exclusion import ExclusionFence
        fence, services = protection_fixture(); fence.establish()
        case = fixtures.HandoverTests(); case.setUp()
        case.backend.observation['external'] = fence.authority_observation()
        state = case.finish()
        restarted = ExclusionFence(fence.repo, fence.epoch, fence.owner, services, fence.bindings)
        restarted.establish()
        case.backend.observation['external'] = restarted.authority_observation()
        writes = len(case.backend.writes); case.finish()
        self.assertEqual(len(case.backend.writes), writes)
        for service in services.values():
            with self.assertRaises(StateInvalid): service.mutate('stale-credentialed-caller', epoch=fence.epoch, state=state)
            with self.assertRaises(StateInvalid): service.mutate('canonical', epoch=fence.epoch, state=state)
        self.assertTrue(all(not s.effects for s in services.values()))

    def test_incomplete_inventory_wrong_resource_or_removed_enforcement_refuses(self):
        fence, services = protection_fixture(); fence.establish()
        service = next(iter(services.values()))
        service.protection['credential_revocation_complete'] = False
        with self.assertRaises(StateInvalid): fence.assert_exclusive('owner/repo')
        service.protection['credential_revocation_complete'] = True
        service.resource_id = 'unrelated-resource'
        with self.assertRaises(StateInvalid): fence.assert_exclusive('owner/repo')

    def test_canonical_resource_requires_verified_owned_exact_command(self):
        from scripts.kesher_runtime.state import plan_command, claim_command
        fence, services = protection_fixture(); fence.establish()
        case = fixtures.HandoverTests(); case.setUp()
        case.backend.observation['external'] = fence.authority_observation()
        state = case.finish()
        target = case.args['identity']; code = case.params['main_sha']; now = case.params['now']
        state, cid = plan_command(state, target, 'generate', 1, {}, code_sha=code, now=now)
        service = services['youtube']
        with self.assertRaises(StateInvalid):
            service.mutate('canonical', epoch=fence.epoch, state=state, command=cid, run_id='456/1', code_sha=code)
        state, _ = claim_command(state, cid, '456/1', target, code_sha=code, now=now)
        for run_id, code_sha in [('other/1', code), ('456/1', 'f'*40)]:
            with self.assertRaises(StateInvalid):
                service.mutate('canonical', epoch=fence.epoch, state=state, command=cid, run_id=run_id, code_sha=code_sha)
        service.mutate('canonical', epoch=fence.epoch, state=state, command=cid, run_id='456/1', code_sha=code)
        self.assertEqual(service.effects, ['canonical'])

    def test_crash_midway_never_blesses_partial_protection(self):
        fence, services = protection_fixture()
        list(services.values())[2].fail_before = True
        with self.assertRaises(GitHubError): fence.establish()
        self.assertEqual(sum(s.protection is not None for s in services.values()), 2)
        with self.assertRaises(StateInvalid): fence.authority_observation()
        fence.establish()
        self.assertTrue(all(s.requests == 1 for s in services.values()))
        services['jules'].inventory_complete = False
        with self.assertRaises(StateInvalid): fence.assert_exclusive('owner/repo')

    def test_observer_composition_requires_independent_review_and_key_binding(self):
        fence, services = protection_fixture(); fence.establish()
        with self.assertRaises(StateInvalid): fence.observe('owner/repo')
        fence.review = {'repo':'owner/repo','policy_sha256':'a'*64,'code_sha256':'b'*64,'closed_evidence_sha256':'c'*64}
        fence.key_binding = {'name':'NOTEBOOKLM_STATE_KEY','available':True,'updated_at':'2026-08-10T13:35:14Z'}
        result = fence.observe('owner/repo')
        self.assertEqual(result['approved_revision']['closed_evidence_sha256'], 'c'*64)
        self.assertEqual(set(result['external']['resource_proofs']), set(services))


if __name__ == '__main__': unittest.main()
