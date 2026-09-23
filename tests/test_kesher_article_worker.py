"""One command does one Jules observation; branch mutation waits for completion."""
import copy
import os
import unittest
from unittest.mock import patch

from scripts.kesher_runtime.article_worker import article_request, run_article, assert_article_quiescent
from scripts.kesher_runtime.jules import JulesError
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.identity import SlotIdentity
from scripts.kesher_runtime.state import new_state, plan_command
from scripts.kesher_runtime.worker import WorkerContext
from tests.test_kesher_canonical_state import CODE, DAY, NOW, ContentsServer
from tests.test_kesher_jules_sessions import JulesServer


PR = {'number': 42, 'head_sha': 'a'*40, 'slot': DAY}


class Repository:
    def __init__(self):
        self.data = {'main_sha': CODE, 'published': [], 'prs': []}

    def snapshot(self, slot):
        return copy.deepcopy(self.data)


class ArticleWorkerTests(unittest.TestCase):
    def test_mutating_worker_rechecks_live_session_even_after_a_settled_receipt(self):
        self.run_once()
        self.repo.data['prs'] = [PR]
        self.api.rows[0].update(state='COMPLETED', outputs=[{'pullRequest': {'url': 'https://github.com/yanivsa/kesher-website/pull/42'}}])
        self.run_once(self.command('settle_article'))
        worker = self.command('normalize_article')
        pr = {'number': PR['number'], 'head': {'sha': PR['head_sha']}}
        self.assertEqual(assert_article_quiescent(worker, self.api, pr), ['sessions/created'])
        self.api.rows[0]['state'] = 'IN_PROGRESS'
        with self.assertRaisesRegex(JulesError, 'JULES_PENDING'):
            assert_article_quiescent(worker, self.api, pr)

    def setUp(self):
        self.target = SlotIdentity(DAY)
        self.server = ContentsServer()
        self.store = GitHubStateStore(self.server, 'yanivsa/kesher-website')
        self.api, self.repo = JulesServer(), Repository()
        self.worker = self.command('create_article')

    def command(self, operation):
        loaded = self.store.load()
        ordinal = len(loaded.state['commands']) + 1
        state, command = plan_command(loaded.state, self.target, operation, ordinal, {}, code_sha=CODE, now=NOW)
        self.store.save(loaded, state)
        worker = WorkerContext(self.store, command, f'{ordinal}/1', self.target, code_sha=CODE, now=lambda: NOW)
        worker.claim()
        return worker

    def run_once(self, worker=None):
        worker = worker or self.worker
        result = run_article(worker, self.api, self.repo, policy='Approved article policy')
        worker.finish()
        return result

    def test_creation_is_waiting_and_does_not_claim_article_publication(self):
        result = self.run_once()
        self.assertEqual(result['status'], 'waiting')
        self.assertEqual(result['failure_class'], 'JULES_PENDING')
        self.assertEqual(self.api.creates, 1)
        self.assertFalse(self.server.document['slots'].get(DAY, {}).get('complete'))

    def test_visible_pr_cannot_settle_until_exact_jules_session_finishes(self):
        self.run_once()
        self.repo.data['prs'] = [PR]
        self.api.rows[0].update(state='IN_PROGRESS', outputs=[{'pullRequest': {'url': 'https://github.com/yanivsa/kesher-website/pull/42'}}])
        worker = self.command('settle_article')
        result = self.run_once(worker)
        self.assertEqual(result['status'], 'waiting')
        self.assertNotIn('article_pr_settled', self.server.document['commands'][worker.command_id]['receipts'])
        self.api.rows[0]['state'] = 'COMPLETED'
        worker = self.command('settle_article')
        result = self.run_once(worker)
        self.assertEqual(result['status'], 'pr_ready')
        receipt = self.server.document['commands'][worker.command_id]['receipts']['article_pr_settled']['evidence']
        self.assertEqual(receipt['head_sha'], PR['head_sha'])
        self.assertEqual(self.api.creates, 1)

    def test_existing_article_and_existing_pr_are_adopted_without_creation(self):
        self.repo.data['published'] = [{'id': 'existing', 'date': DAY}]
        self.assertEqual(self.run_once()['status'], 'article_merged')
        self.assertEqual(self.api.creates, 0)

    def test_unowned_existing_pr_requires_fresh_jules_quiescence_inventory(self):
        self.repo.data['prs'] = [PR]
        self.api.rows = [{**article_request(DAY, 'Older approved policy'), 'name': 'sessions/legacy', 'state': 'IN_PROGRESS'}]
        self.assertEqual(self.run_once()['status'], 'waiting')
        self.api.rows[0]['state'] = 'COMPLETED'
        self.assertEqual(self.run_once(self.command('settle_article'))['status'], 'pr_ready')
        self.assertEqual(self.api.creates, 0)

    def test_settle_operation_cannot_create_when_pr_disappears(self):
        self.worker.finish(failure={'class': 'TRANSIENT_API'})
        with self.assertRaisesRegex(JulesError, 'ARTICLE_PR_MISSING'):
            self.run_once(self.command('settle_article'))
        self.assertEqual(self.api.creates, 0)

    def test_completed_without_pr_is_failure_and_not_another_session(self):
        self.run_once()
        self.api.rows[0]['state'] = 'COMPLETED'
        with self.assertRaisesRegex(JulesError, 'JULES_NO_OUTPUT'):
            self.run_once(self.command('create_article'))
        self.assertEqual(self.api.creates, 1)

    def test_foreign_pr_output_cannot_settle_local_article(self):
        self.run_once()
        self.repo.data['prs'] = [PR]
        self.api.rows[0].update(state='COMPLETED', outputs=[{'pullRequest': {'url': 'https://github.com/foreign/repo/pull/42'}}])
        with self.assertRaisesRegex(JulesError, 'JULES_OUTPUT_IDENTITY_MISMATCH'):
            self.run_once(self.command('settle_article'))

    def test_duplicate_article_prs_fail_before_any_provider_mutation(self):
        self.repo.data['prs'] = [PR, dict(PR, number=43)]
        with self.assertRaisesRegex(JulesError, 'DUPLICATE_PR'):
            self.run_once()
        self.assertEqual(self.api.creates, 0)

    def test_legacy_test_environment_cannot_bypass_production_duplicate_contract(self):
        with patch.dict(os.environ, {'KESHER_TEST_MODE': 'true'}):
            request = article_request(DAY, 'Approved article policy')
        self.assertNotIn('AUTHORIZED TEST MODE', request['prompt'])
        self.assertIn('ARTICLE TEXT ONLY', request['prompt'])
        self.assertIn('SEARCH-INTENT-FIRST', request['prompt'])
        self.assertIn('ARTICLE EVIDENCE CONTRACT', request['prompt'])


if __name__ == '__main__':
    unittest.main()
