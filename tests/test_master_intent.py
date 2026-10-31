import unittest

from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.master_intent import MasterIntent, plan_master_command, validate_master_intent
from scripts.kesher_runtime.state import CommandConflict, StateInvalid, new_state


MAIN_SHA = 'a' * 40
NOW = '2026-10-31T20:55:00Z'


class MasterIntentValidationTests(unittest.TestCase):
    def request(self, **overrides):
        values = dict(
            request_id='master-20261031-001',
            expected_main_sha=MAIN_SHA,
            expected_state_revision=7,
            target=SlotIdentity('2026-10-31'),
            operation='normalize_article',
            inputs={'pr_number': '1264', 'pr_head_sha': 'b' * 40},
        )
        values.update(overrides)
        return MasterIntent(**values)

    def test_accepts_exact_fresh_request(self):
        request = self.request()
        self.assertEqual(request, validate_master_intent(request, main_sha=MAIN_SHA, state_revision=7))

    def test_rejects_stale_main(self):
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_STALE_MAIN'):
            validate_master_intent(self.request(), main_sha='b' * 40, state_revision=7)

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

    def test_plans_exact_command_without_dispatching(self):
        state = new_state()
        state['revision'] = 7
        request = self.request()
        proposed, command_id = plan_master_command(state, request, main_sha=MAIN_SHA, now=NOW)
        command = proposed['commands'][command_id]
        self.assertEqual(command['operation'], 'normalize_article')
        self.assertEqual(command['inputs'], request.inputs)
        self.assertEqual(command['code_sha'], MAIN_SHA)
        self.assertEqual(command['dispatch']['attempts'], [])

    def test_pending_command_blocks_second_master_intent(self):
        state = new_state()
        state['revision'] = 7
        first, _ = plan_master_command(state, self.request(), main_sha=MAIN_SHA, now=NOW)
        with self.assertRaises(CommandConflict):
            plan_master_command(first, self.request(request_id='master-20261031-002', operation='attach_image'),
                                main_sha=MAIN_SHA, now='2026-10-31T20:56:00Z')

    def test_target_operation_route_must_be_authorized(self):
        state = new_state()
        state['revision'] = 7
        with self.assertRaisesRegex(StateInvalid, 'MASTER_INTENT_ROUTE_FORBIDDEN'):
            plan_master_command(state, self.request(operation='deploy_article'), main_sha=MAIN_SHA, now=NOW)


if __name__ == '__main__':
    unittest.main()
