"""Real admission/recovery regressions; native/operator reads are disposable."""
import copy
import unittest

from scripts.kesher_runtime.state import StateInvalid, bind_source, new_state
from tests.test_kesher_autonomous_controller import SOURCE, NOW, later, observed, publication
from tests.test_kesher_external_exclusion import protection_fixture


class ControlPlaneTests(unittest.TestCase):
    def test_missing_external_operator_observer_blocks_before_resource_effect(self):
        from tests.test_kesher_production_cutover import ProductionCutoverTests
        runtime, case, services = ProductionCutoverTests().runtime()
        runtime.fence.control_planes = None
        with self.assertRaises(StateInvalid):
            runtime.step()
        self.assertEqual(sum(s.requests for s in services.values()), 0)
        self.assertEqual(case.backend.writes, [])

    def test_terminal_exact_incident_cannot_restart_by_changing_failure_label(self):
        from scripts.kesher_runtime.controller import reconcile
        state = new_state()
        for index in range(8):
            now = later(index * 4000)
            result = reconcile(state, observed(publication(overview='verified', short='PUBLIC_METADATA_INVALID'), now=now), now=now)
            state = result.state
            if result.command_id:
                c = state['commands'][result.command_id]
                c['outcome'] = 'failed'; c['failure'] = {'class': 'PUBLIC_METADATA_INVALID'}
        self.assertEqual(len(state['commands']), 3)
        for index in range(8, 16):
            now = later(index * 4000)
            # Restart uses only persisted state; new hourly rescue labels give no budget.
            result = reconcile(copy.deepcopy(state), observed(publication(overview='verified', short='MEDIA_INVALID'), now=now), now=now)
            self.assertIsNone(result.command_id)
            self.assertEqual(len(result.state['commands']), 3)
            self.assertEqual(len(result.state['incidents']), 1)
            state = result.state

    def test_terminal_deployment_budget_is_bound_to_exact_main_revision(self):
        from scripts.kesher_runtime.controller import Observation, reconcile
        from scripts.kesher_runtime.identity import digest
        from scripts.kesher_runtime.policy import record_incident
        from scripts.kesher_runtime.state import plan_command
        from tests.test_kesher_canonical_state import CODE
        state = bind_source(new_state(), SOURCE, now=NOW)
        state, cid = plan_command(state, SOURCE, 'deploy_article', 1, {'deploy_sha':CODE}, code_sha=CODE, now=NOW)
        state['commands'][cid]['outcome'] = 'failed'; state['commands'][cid]['failure'] = {'class':'DEPLOY_FAILED'}
        record_incident(state, SOURCE, 'deploy_article', 'DEPLOY_FAILED', now=NOW,
                        evidence={'last_command_id':cid, 'recovery_inputs_sha256':digest({'deploy_sha':CODE})})
        when = later(4000)
        old = reconcile(state, observed(publication(article='ARTICLE_NOT_PUBLIC', overview='verified', short='verified'), now=when), now=when)
        self.assertIsNone(old.command_id)  # symptom change cannot reopen the old exact revision
        obs = observed(publication(article='ARTICLE_NOT_PUBLIC', overview='verified', short='verified'), now=when).value
        obs['main_sha'] = 'e'*40; obs['publications'][0]['main_sha'] = 'e'*40
        result = reconcile(copy.deepcopy(state), Observation(obs), now=when)
        self.assertIsNotNone(result.command_id)
        self.assertEqual(result.state['commands'][result.command_id]['inputs'], {'deploy_sha':'e'*40})
        again = reconcile(result.state, Observation(obs), now=when)
        self.assertEqual(len(again.state['commands']), 2)  # one intent per immutable revision

    def test_later_observer_conversion_and_denied_session_cleanup_preserve_authority(self):
        from tests import test_kesher_handover as fixtures
        from scripts.kesher_runtime.handover import require_authority
        case = fixtures.HandoverTests(); case.setUp()
        row = case.backend.fence.control_planes.observe()
        row['jules']['predecessor_sessions'] = [{'name':'sessions/retired', 'repo':case.backend.repo,
                                               'repository_access':'denied', 'continuation':'denied'}]
        case.backend.fence.control_planes.observe = lambda: copy.deepcopy(row)
        case.backend.observation['external'] = case.backend.fence.authority_observation()
        state = case.finish()
        row['supervisor']['state'] = 'observer'
        row['jules']['predecessor_sessions'] = []
        observation = case.backend.observe(); observation['external'] = case.backend.fence.authority_observation()
        require_authority(state, observation)
        row['supervisor']['state'] = 'legacy_active'
        with self.assertRaises(StateInvalid): case.backend.fence.authority_observation()

    def test_terminal_overview_does_not_block_independent_short(self):
        from scripts.kesher_runtime.controller import reconcile
        from scripts.kesher_runtime.identity import MediaIdentity
        from scripts.kesher_runtime.policy import record_incident
        state = bind_source(new_state(), SOURCE, now=NOW)
        record_incident(state, MediaIdentity(SOURCE, 'overview'), 'publish', 'IDENTITY_MISMATCH', now=NOW)
        result = reconcile(state, observed(publication(overview='IDENTITY_MISMATCH')), now=NOW)
        self.assertEqual(result.state['commands'][result.command_id]['target']['kind'], 'short')

    def test_v5_reconstruction_refuses_schema6_before_any_legacy_effect(self):
        from scripts.kesher_content_controller_v5 import V5Controller
        controller = object.__new__(V5Controller)
        class ProtectedState:
            def load_controller_state(self): return new_state()
        controller.github = ProtectedState()
        with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
            controller.state()

    def test_external_actor_cannot_use_canonical_control_principal(self):
        from scripts.kesher_runtime.exclusion import require_control_operation
        from scripts.kesher_runtime.handover import OWNER
        from tests import test_kesher_handover as fixtures
        case = fixtures.HandoverTests(); case.setUp(); state = case.finish()
        fence, _ = protection_fixture(); fence.establish()
        approval = state['handover']['basis']['environment']
        kwargs = dict(epoch=fence.epoch, code_sha256=approval['code_sha256'], approval=approval,
                      previous=state, previous_sha='1'*40, main_sha=approval['main_sha'], proposed=state)
        with self.assertRaises(StateInvalid):
            require_control_operation(fence._policy('github'), 'controller_cas', principal='external_master_active_supervisor', **kwargs)
        self.assertEqual(require_control_operation(fence._policy('github'), 'controller_cas', principal=OWNER, **kwargs), 'controller_cas')

    def test_actor_inventory_keeps_six_resources_and_explicit_jules_predecessors(self):
        from scripts.kesher_runtime.control_planes import ACTOR_POLICY, validate_actor_policy
        from scripts.kesher_runtime.exclusion import REQUIRED_RESOURCES
        validate_actor_policy(ACTOR_POLICY)
        self.assertEqual(set(REQUIRED_RESOURCES), {'github','jules','notebooklm','youtube','cloudflare','image_provider'})
        actor = ACTOR_POLICY['actors']['external_master_active_supervisor']
        self.assertEqual(actor['role'], 'predecessor')
        self.assertEqual(actor['resources'], ['github', 'jules'])
        self.assertEqual(ACTOR_POLICY['actors']['jules_predecessor_sessions']['role'], 'predecessor')
        changed = copy.deepcopy(ACTOR_POLICY); changed['actors']['unknown'] = actor
        with self.assertRaises(StateInvalid): validate_actor_policy(changed)

    def test_unresolved_jules_or_active_external_task_blocks_before_effect(self):
        from tests.test_kesher_production_cutover import ProductionCutoverTests
        for mutation in ('unknown_jules', 'incomplete_jules', 'active_supervisor', 'wrong_task', 'missing_actor', 'stale', 'undeclared_authority'):
            runtime, case, services = ProductionCutoverTests().runtime()
            observer = runtime.fence.control_planes
            row = observer.observe()
            if mutation == 'unknown_jules': row['jules']['unknown_authority'] = ['session-unclassified']
            elif mutation == 'incomplete_jules': row['jules']['inventory_complete'] = False
            elif mutation == 'active_supervisor': row['supervisor']['state'] = 'legacy_active'
            elif mutation == 'wrong_task': row['supervisor']['task_id'] = 'different'
            elif mutation == 'missing_actor': row['predecessor_actors'].pop()
            elif mutation == 'stale': row['observed_at'] = '2000-01-01T00:00:00Z'
            else: row['supervisor']['unreviewed_mutation_route'] = 'enabled'
            observer.observe = lambda: copy.deepcopy(row)
            with self.subTest(mutation=mutation), self.assertRaises(StateInvalid): runtime.step()
            self.assertEqual(sum(s.requests for s in services.values()), 0)
            self.assertEqual(case.backend.writes, [])

    def test_unknown_session_denial_or_missing_native_proof_blocks_final_exclusivity(self):
        from scripts.kesher_runtime.exclusion import validate_external
        fence, _ = protection_fixture(); fence.establish()
        row = fence.control_planes.observe()
        row['jules']['predecessor_sessions'] = [{'name':'sessions/old','repo':fence.repo,'repository_access':'unknown','continuation':'denied'}]
        fence.control_planes.observe = lambda: copy.deepcopy(row)
        with self.assertRaises(StateInvalid): fence.assert_exclusive(fence.repo)
        fresh, _ = protection_fixture(); fresh.establish()
        external = fresh.authority_observation()
        external.pop('control_planes')
        with self.assertRaises(StateInvalid): validate_external(external, fresh.repo)

    def test_fresh_observer_readback_is_required_even_after_verified_restart(self):
        from tests import test_kesher_handover as fixtures
        from scripts.kesher_runtime.handover import require_authority
        case = fixtures.HandoverTests(); case.setUp(); state = case.finish()
        require_authority(state, case.backend.observe())
        row = case.backend.fence.control_planes.observe()
        row['supervisor']['state'] = 'legacy_active'
        case.backend.fence.control_planes.observe = lambda: row
        with self.assertRaises(StateInvalid): case.backend.fence.assert_exclusive(case.backend.repo)
        observation = case.backend.observe(); observation['external'].pop('control_planes')
        with self.assertRaises(StateInvalid): require_authority(state, observation)

    def test_native_restriction_can_replace_task_suspension_only_with_both_real_fences(self):
        fence, services = protection_fixture()
        row = fence.control_planes.observe(); row['supervisor']['state'] = 'resource_restricted'
        fence.control_planes.observe = lambda: row
        with self.assertRaises(StateInvalid): fence.establish()
        self.assertEqual(sum(s.requests for s in services.values()), 0)
        suspended, services = protection_fixture(); suspended.establish()
        row = suspended.control_planes.observe(); row['supervisor']['state'] = 'resource_restricted'
        suspended.control_planes.observe = lambda: row
        self.assertTrue(suspended.assert_exclusive(suspended.repo)['fenced'])
        services['jules'].protection = None
        with self.assertRaises(StateInvalid): suspended.assert_exclusive(suspended.repo)

    def test_no_canonical_session_can_be_smuggled_into_predecessor_retirement(self):
        fence, _ = protection_fixture(); fence.establish()
        row = fence.control_planes.observe()
        row['jules']['predecessor_sessions'] = [{'name':'sessions/old','repo':fence.repo,'repository_access':'canonical','continuation':'denied'}]
        fence.control_planes.observe = lambda: row
        with self.assertRaises(StateInvalid): fence.authority_observation()


if __name__ == '__main__': unittest.main()
