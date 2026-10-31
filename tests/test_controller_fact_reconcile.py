import unittest
from unittest import mock

from scripts.kesher_runtime import controller
from scripts.kesher_runtime.controller import Observation, reconcile, reconcile_facts
from scripts.kesher_runtime.state import new_state


MAIN_SHA = 'a' * 40
HEAD_SHA = 'b' * 40
NOW = '2026-10-31T22:05:00+00:00'
SLOT = '2026-11-01'


def observation(status='normalize_required'):
    return Observation({
        'state_revision': 0,
        'main_sha': MAIN_SHA,
        'observed_at': NOW,
        'current_slot': SLOT,
        'article_creation_allowed': False,
        'publications': [],
        'runs': [],
        'article_prs': [{
            'number': 1264,
            'head_sha': HEAD_SHA,
            'body_sha256': 'c' * 64,
            'slot': SLOT,
            'status': status,
        }],
        'merge_effects': [],
        'missing_slots': [],
    })


class FactReconciliationTests(unittest.TestCase):
    def test_fact_only_path_never_calls_action_eligibility_or_plans_command(self):
        state = new_state()
        with mock.patch.object(controller, '_eligible', side_effect=AssertionError('decision path called')):
            proposed = reconcile_facts(state, observation(), now=NOW)
        self.assertEqual(proposed['slots'][SLOT]['article_pr'], {'number': 1264, 'head_sha': HEAD_SHA})
        self.assertEqual(proposed['commands'], {})

    def test_legacy_decision_wrapper_still_plans_from_same_observation(self):
        decision = reconcile(new_state(), observation(), now=NOW)
        self.assertIsNotNone(decision.command_id)
        self.assertIn(decision.command_id, decision.state['commands'])


if __name__ == '__main__':
    unittest.main()
