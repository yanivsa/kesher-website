"""Actual Actions admission: exact workflow, attempt, command and checked-out code."""
import copy
import tempfile
import unittest
from pathlib import Path

from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.state import ClaimRejected
from scripts.kesher_runtime.worker_entry import admit_worker, write_outputs
from tests.test_kesher_canonical_state import CODE, NOW, ContentsServer, requested


class WorkerEntryTests(unittest.TestCase):
    def setUp(self):
        state, self.command_id = requested()
        self.server = ContentsServer(state)
        self.store = GitHubStateStore(self.server, 'owner/repo')
        from tests.test_kesher_handover import install_verified_authority
        self.authority = install_verified_authority(self.store, self.server.document)
        self.env = {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
                    'GITHUB_REF': 'refs/heads/main', 'GITHUB_RUN_ID': '123', 'GITHUB_RUN_ATTEMPT': '1',
                    'GITHUB_WORKFLOW_REF': 'owner/repo/.github/workflows/kesher-media-worker.yml@refs/heads/main',
                    'GITHUB_WORKFLOW_SHA': CODE}

    def admit(self, *, env=None, checkout=CODE, main=CODE, attach=False):
        return admit_worker(self.store, self.command_id, self.env if env is None else env,
                            checkout_sha=checkout, trusted_main_sha=main, attach=attach, now=lambda: NOW)

    def test_exact_claim_exports_only_persisted_target_and_rerun_cannot_claim(self):
        admission = self.admit()
        self.assertTrue(admission.execute)
        self.assertEqual(admission.context.run_id, '123/1')
        self.assertEqual(admission.command['target']['kind'], 'overview')
        self.assertEqual(admission.command['id'], self.command_id)
        self.assertFalse(self.admit().execute)
        self.env['GITHUB_RUN_ATTEMPT'] = '2'
        self.assertFalse(self.admit().execute)
        with self.assertRaises(ClaimRejected):
            self.admit(attach=True)

    def test_later_step_attaches_only_to_same_run_attempt_and_code(self):
        self.admit()
        attached = self.admit(attach=True)
        self.assertTrue(attached.execute)
        self.assertTrue(attached.context.begin_effect('generate', {'source_id': 'source-1'}).execute)
        with self.assertRaises(ClaimRejected):
            self.admit(attach=True, checkout='b' * 40)

    def test_stale_workflow_definition_checkout_or_main_never_claims(self):
        for overrides in [{'checkout': 'b' * 40}, {'main': 'b' * 40},
                          {'env': {**self.env, 'GITHUB_WORKFLOW_SHA': 'b' * 40}}]:
            with self.subTest(overrides=overrides), self.assertRaises(ClaimRejected):
                self.admit(**overrides)
        self.assertEqual(self.server.writes, [])

    def test_fork_pr_wrong_workflow_and_malformed_attempt_never_claim(self):
        for key, value in [('GITHUB_REPOSITORY', 'fork/repo'), ('GITHUB_EVENT_NAME', 'pull_request_target'),
                           ('GITHUB_REF', 'refs/heads/repair'), ('GITHUB_RUN_ID', '123\nexecute=true'),
                           ('GITHUB_RUN_ATTEMPT', '0'), ('GITHUB_WORKFLOW_REF',
                            'owner/repo/.github/workflows/kesher-short-v4.yml@refs/heads/main')]:
            with self.subTest(key=key), self.assertRaises(ClaimRejected):
                self.admit(env={**self.env, key: value})
        self.assertEqual(self.server.writes, [])

    def test_newer_main_does_not_prevent_owned_worker_recording_existing_receipt(self):
        admitted = self.admit()
        admitted.context.begin_effect('generate', {'source_id': 'source-1'})
        # The same running code may record an already-created response after a
        # deployment. Fresh admission remains fenced by current main.
        attached = self.admit(attach=True, main='b' * 40)
        attached.context.complete_effect('generate', {'task_id': 'existing-task'})
        self.assertEqual(self.server.document['commands'][self.command_id]['effects']['generate']['receipt'],
                         {'task_id': 'existing-task'})

    def test_actions_outputs_are_single_line_and_do_not_export_arbitrary_inputs(self):
        admitted = self.admit()
        admitted.command['inputs']['free_text'] = 'untrusted\nexecute=true'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'outputs'
            write_outputs(path, admitted)
            values = dict(line.split('=', 1) for line in path.read_text().splitlines())
        self.assertEqual(values['execute'], 'true')
        self.assertEqual(values['command_id'], self.command_id)
        self.assertEqual(values['kind'], 'overview')
        self.assertNotIn('free_text', values)


if __name__ == '__main__':
    unittest.main()
