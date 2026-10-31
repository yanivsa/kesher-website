import unittest

from scripts.kesher_runtime.controller import Observation
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.master_intent import MasterIntent, plan_master_command, validate_master_intent
from scripts.kesher_runtime.state import CommandConflict, StateInvalid, new_state


MAIN_SHA = 'a' * 40
HEAD_SHA = 'b' * 40
BODY_SHA = 'c' * 64
NOW = '2026-10-31T22:05:00+00:00'
SLOT = '2026-11-01'


class MasterIntentValidationTests(unittest.TestCase):
    def request(self, **overrides):
        values = dict(
            request_id='master-20261031-001',
            expected_main_sha=MAIN_SHA,
            expected_state_revision=7,
            target=SlotIdentity(SLOT),
            operation='normalize_article',
            inputs={},
        )
        values.update(overrides)
        return MasterIntent(**values)

    def observation(self, *, status='normalize_required', prs=None):
        return Observation({
            'state_revision': 7,
            'main_sha': MAIN_SHA,
            'observed_at': NOW,
            'current_slot': SLOT,
            'article_creation_allowed': False,
            'publications': [],
            'runs': [],
            'article_prs': prs if prs is not None else [{
                'number': 1264,
                'head_sha': HEAD_SHA,
                'body_sha256': BODY_SHA,
                'slot': SLOT,
                'status': status,
            }],
            'merge_effects': [],
            'missing_slots': [],
        })

    def state(self):
        state = new_state()
        state['revision'] = 7
        return state

    def test_accepts_exact_fresh_request_without_worker_inputs(self):
        request = self.request()
        self.assertEqual(request, validate_master_intent(request, main_sha=MAIN_SHA, state_revision=7))

    def test_rejects_stale_main(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_STALE_MAIN'):
            validate_master_intent(self.request(), main_sha='d' * 40, state_revision=7)

    def test_rejects_stale_state_revision(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_STALE_STATE'):
            validate_master_intent(self.request(), main_sha=MAIN_SHA, state_revision=8)

    def test_rejects_controller_only_article_creation(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_OPERATION_FORBIDDEN'):
            validate_master_intent(self.request(operation='create_article'), main_sha=MAIN_SHA, state_revision=7)

    def test_rejects_unknown_operation(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_OPERATION_FORBIDDEN'):
            validate_master_intent(self.request(operation='anything'), main_sha=MAIN_SHA, state_revision=7)

    def test_request_id_is_required(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_REQUEST_ID_INVALID'):
            validate_master_intent(self.request(request_id=''), main_sha=MAIN_SHA, state_revision=7)

    def test_rejects_any_caller_supplied_worker_input(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_INPUTS_FORBIDDEN'):
            validate_master_intent(self.request(inputs={'pr_number': '9999'}), main_sha=MAIN_SHA, state_revision=7)

    def test_plans_exact_command_with_inputs_derived_from_fresh_observation(self):
        request = self.request()
        proposed, command_id = plan_master_command(
            self.state(), request, main_sha=MAIN_SHA, observation=self.observation(), now=NOW)
        command = proposed['commands'][command_id]
        self.assertEqual(command['operation'], 'normalize_article')
        self.assertEqual(command['inputs'], {'pr_number': '1264', 'pr_head_sha': HEAD_SHA})
        self.assertEqual(command['code_sha'], MAIN_SHA)
        self.assertEqual(command['dispatch']['attempts'], [])

    def test_validation_inputs_are_bound_to_observed_body_and_main(self):
        proposed, command_id = plan_master_command(
            self.state(), self.request(operation='validate_article'), main_sha=MAIN_SHA,
            observation=self.observation(status='ci_required'), now=NOW)
        self.assertEqual(proposed['commands'][command_id]['inputs'], {
            'pr_number': '1264', 'pr_head_sha': HEAD_SHA,
            'pr_body_sha256': BODY_SHA, 'validation_base_sha': MAIN_SHA,
        })

    def test_rejects_operation_that_does_not_match_fresh_pr_stage(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_OBSERVATION_MISMATCH'):
            plan_master_command(self.state(), self.request(operation='merge_article'), main_sha=MAIN_SHA,
                                observation=self.observation(status='ci_required'), now=NOW)

    def test_rejects_ambiguous_pr_observation(self):
        rows = self.observation().value['article_prs']
        rows.append({**rows[0], 'number': 1265, 'head_sha': 'd' * 40})
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_OBSERVATION_AMBIGUOUS'):
            plan_master_command(self.state(), self.request(), main_sha=MAIN_SHA,
                                observation=self.observation(prs=rows), now=NOW)

    def test_pending_command_blocks_second_master_intent(self):
        first, _ = plan_master_command(self.state(), self.request(), main_sha=MAIN_SHA,
                                       observation=self.observation(), now=NOW)
        with self.assertRaises(CommandConflict):
            plan_master_command(first, self.request(request_id='master-20261031-002', operation='attach_image'),
                                main_sha=MAIN_SHA, observation=self.observation(status='image_required'),
                                now='2026-10-31T22:06:00+00:00')

    def test_target_operation_route_must_be_authorized(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_ROUTE_FORBIDDEN'):
            plan_master_command(self.state(), self.request(operation='deploy_article'), main_sha=MAIN_SHA,
                                observation=self.observation(), now=NOW)


if __name__ == '__main__':
    unittest.main()
