import unittest

from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.master_intent import MasterIntent, validate_master_intent
from scripts.kesher_runtime.state import StateInvalid


MAIN_SHA = 'a' * 40


class MasterIntentValidationTests(unittest.TestCase):
    def request(self, **overrides):
        values = dict(
            request_id='master-20261031-001',
            expected_main_sha=MAIN_SHA,
            expected_state_revision=7,
            target=SlotIdentity('2026-10-31'),
            operation='normalize_article',
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


if __name__ == '__main__':
    unittest.main()
