"""Master-owned KESHER intent, fact reconciliation, and article-origin contracts."""
import copy
import unittest

from scripts.kesher_runtime.article_quiescence import assert_article_quiescent
from scripts.kesher_runtime.controller import reconcile_facts
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.master_intent import plan_master_intent
from scripts.kesher_runtime.state import CommandConflict, StateConflict, StateInvalid, new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_autonomous_controller import observed, publication
from tests.test_kesher_canonical_state import CODE, NOW, SOURCE, ContentsServer


def request(target, operation, *, revision=0, main_sha=CODE, request_id='master-test-001'):
    return {
        'request_id': request_id,
        'expected_main_sha': main_sha,
        'expected_state_revision': revision,
        'target': target.to_dict(),
        'operation': operation,
    }


class ExplodingJules:
    def sessions(self):
        raise AssertionError('Master-origin article must not query Jules sessions')

    def get(self, name):
        raise AssertionError(f'Master-origin article must not query Jules session {name}')


class MasterIntentTests(unittest.TestCase):
    def test_reconcile_facts_records_reality_without_planning_a_command(self):
        state = reconcile_facts(new_state(), observed(publication()), now=NOW)
        self.assertEqual(state['commands'], {})
        self.assertEqual(state['slots'][SOURCE.slot]['source_key'], SOURCE.key)
        self.assertEqual(state['sources'][SOURCE.key]['article']['phase'], 'PUBLICLY_VERIFIED')
        self.assertFalse(state['slots'][SOURCE.slot]['complete'])

    def test_master_normalization_derives_exact_pr_inputs_from_fresh_observation(self):
        target = SlotIdentity(SOURCE.slot)
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'normalize_required'}
        result = plan_master_intent(new_state(), observed(prs=[pr]), request(target, 'normalize_article'), now=NOW)
        command = result.state['commands'][result.command_id]
        self.assertEqual(command['operation'], 'normalize_article')
        self.assertEqual(command['target'], target.to_dict())
        self.assertEqual(command['inputs'], {'pr_number': '854', 'pr_head_sha': CODE})

    def test_master_intent_rejects_stale_state_revision(self):
        target = SlotIdentity(SOURCE.slot)
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'normalize_required'}
        with self.assertRaises(StateConflict):
            plan_master_intent(new_state(), observed(prs=[pr]), request(target, 'normalize_article', revision=1), now=NOW)

    def test_master_intent_rejects_operation_that_does_not_match_observed_stage(self):
        target = SlotIdentity(SOURCE.slot)
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'image_required'}
        with self.assertRaises(StateInvalid):
            plan_master_intent(new_state(), observed(prs=[pr]), request(target, 'normalize_article'), now=NOW)

    def test_master_intent_cannot_create_a_second_pending_command_for_same_target(self):
        target = SlotIdentity(SOURCE.slot)
        pr = {'slot': SOURCE.slot, 'number': 854, 'head_sha': CODE, 'status': 'normalize_required'}
        first = plan_master_intent(new_state(), observed(prs=[pr]), request(target, 'normalize_article'), now=NOW)
        saved = copy.deepcopy(first.state)
        saved['revision'] = 1
        with self.assertRaises(CommandConflict):
            plan_master_intent(saved, observed(prs=[pr]), request(target, 'normalize_article', revision=1, request_id='master-test-002'), now=NOW)

    def test_master_origin_exact_head_quiescence_never_queries_jules(self):
        target = SlotIdentity(SOURCE.slot)
        state, command_id = plan_command(
            new_state(), target, 'normalize_article', 1,
            {'pr_number': '42', 'pr_head_sha': CODE}, code_sha=CODE, now=NOW,
        )
        store = GitHubStateStore(ContentsServer(state), 'yanivsa/kesher-website')
        context = WorkerContext(store, command_id, '1/1', target, code_sha=CODE, now=lambda: NOW)
        context.claim()
        pr = {
            'number': 42,
            'body': 'Kesher-Origin: master-active-supervisor',
            'head': {'sha': CODE, 'ref': f'master/kesher-article/{SOURCE.slot}-example'},
        }
        self.assertEqual(
            assert_article_quiescent(context, ExplodingJules(), pr, settled_head_sha=CODE),
            [],
        )


if __name__ == '__main__':
    unittest.main()
