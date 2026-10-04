"""Offline regressions for V5 rollback and the protected-resource rejection hook."""
import copy
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from scripts import kesher_content_controller_v5 as v5
from scripts.kesher_runtime import legacy_retirement as retirement
from scripts.kesher_runtime.github import GitHubStateStore
from scripts.kesher_runtime.state import StateConflict, StateInvalid, new_state, validate_state, validate_transition
from tests.test_kesher_canonical_state import ContentsServer, NOW, requested
from tests import test_kesher_handover as handover_fixtures
from tests.test_kesher_state_write_safety import StateServer
from tests.test_v5_shared_video_controller import FakeGitHub, FakeSite


class LegacySchemaFenceTests(unittest.TestCase):
    def hook(self, name):
        result = getattr(retirement, name, None)
        self.assertTrue(callable(result), f'Missing protected-resource hook: {name}')
        return result

    def v5(self, github):
        return v5.V5Controller(github, FakeSite(), now=datetime(2026, 8, 19, 19, 0, tzinfo=ZoneInfo('Asia/Jerusalem')))

    def test_stale_v5_waking_after_schema6_refuses_before_reconstruction_or_effect(self):
        for schema in (6, 7):
            with self.subTest(schema=schema):
                github = FakeGitHub()
                github.saved_state = {**new_state(), 'schema_version': schema}
                before = copy.deepcopy(github.saved_state)
                with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
                    self.v5(github).tick()
                self.assertEqual(github.saved_state, before)
                self.assertEqual(github.dispatches, [])

    def test_v5_refuses_any_handover_key_even_empty_or_null_before_cycle_rollover(self):
        for handover in ({}, None, {'phase': 'PREPARED'}):
            with self.subTest(handover=handover):
                github = FakeGitHub()
                github.saved_state = {'schema_version': 5, 'cycle': '2026-08-18', 'handover': handover}
                before = copy.deepcopy(github.saved_state)
                with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
                    self.v5(github).state()
                self.assertEqual(github.saved_state, before)

    def test_v5_refuses_git_exclusion_key_before_handover_is_prepared(self):
        for ledger in ({}, None, {'epoch_sha256': 'a' * 64}):
            with self.subTest(ledger=ledger):
                github = FakeGitHub()
                github.saved_state = {'schema_version': 5, 'cycle': '2026-08-19', 'github_exclusion': ledger}
                before = copy.deepcopy(github.saved_state)
                with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
                    self.v5(github).state()
                self.assertEqual(github.saved_state, before)

    def test_shared_legacy_load_never_marks_schema6_writable(self):
        client = StateServer()
        client.document = new_state()
        with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
            client.load_controller_state()
        with self.assertRaisesRegex(Exception, 'STATE_NOT_LOADED'):
            client.save_controller_state({'schema_version': 5})
        self.assertEqual(client.writes, [])

    def test_shared_save_cannot_install_a_handover_or_canonical_document(self):
        for change in ('schema6', 'handover'):
            with self.subTest(change=change):
                client = StateServer()
                proposed = client.load_controller_state()
                if change == 'schema6':
                    proposed = new_state()
                else:
                    proposed['handover'] = {}
                with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
                    client.save_controller_state(proposed)
                self.assertEqual(client.writes, [])
                self.assertEqual(client.document['schema_version'], 5)

    def test_old_request_with_newest_blob_sha_still_cannot_downgrade_schema6(self):
        guard = self.hook('validate_legacy_write')
        current = new_state()
        before = copy.deepcopy(current)
        with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
            guard(current, {'schema_version': 5}, before_sha='a' * 40, current_sha='a' * 40)
        self.assertEqual(current, before)

    def test_delayed_journal_erasure_is_denied_even_with_current_blob_sha(self):
        guard = self.hook('validate_legacy_write')
        current = {'schema_version': 5, 'handover': {'phase': 'LEGACY_QUIESCING'}}
        with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_FENCED'):
            guard(current, {'schema_version': 5}, before_sha='a' * 40, current_sha='a' * 40)
        self.assertEqual(current['handover']['phase'], 'LEGACY_QUIESCING')

    def test_legacy_gateway_compares_exact_cas_identity_without_rebinding(self):
        guard = self.hook('validate_legacy_write')
        legacy = {'schema_version': 5, 'status': 'running'}
        proposed = {**legacy, 'status': 'complete'}
        with self.assertRaises(StateConflict):
            guard(legacy, proposed, before_sha='a' * 40, current_sha='b' * 40)
        self.assertEqual(legacy['status'], 'running')
        guard(legacy, proposed, before_sha='b' * 40, current_sha='b' * 40)

    def test_stale_v5_write_after_transfer_fails_original_contents_cas(self):
        client = StateServer()
        stale = client.load_controller_state()
        client.document = new_state()
        client.sha = 'schema6-transfer-2'
        stale['status'] = 'complete'
        with self.assertRaisesRegex(Exception, '409'):
            client.save_controller_state(stale)
        self.assertEqual(client.document, new_state())
        self.assertEqual(client.writes[0]['sha'], 'observed-1')

    def test_gateway_refuses_missing_or_malformed_revision_identity(self):
        guard = self.hook('validate_legacy_write')
        for revision in (None, '', 123, False, 'short-or-forged-ref'):
            with self.subTest(revision=revision), self.assertRaises(StateInvalid):
                guard({'schema_version': 5}, {'schema_version': 5}, before_sha=revision, current_sha=revision)


class LegacyRejectionRecordTests(unittest.TestCase):
    def record(self, current, **kwargs):
        helper = getattr(retirement, 'record_legacy_rejection', None)
        self.assertTrue(callable(helper), 'Missing durable rejection hook')
        options = {'actor': 'synthetic-old-worker', 'epoch': 'synthetic-epoch',
                   'proposed': {'schema_version': 5, 'token': 'synthetic-secret-never-persist'},
                   'before_sha': 'a' * 40, 'current_sha': 'b' * 40, 'now': NOW}
        options.update(kwargs)
        return helper(current, **options)

    def test_rejection_is_canonical_copy_with_hash_only_audit_incident(self):
        current, command = requested()
        current['quarantine'] = [{'receipt': 'retained-quarantine'}]
        current['commands'][command]['receipts'] = {}
        before = copy.deepcopy(current)
        recorded = self.record(current, actor='synthetic-secret-actor', epoch='synthetic-secret-epoch')
        self.assertEqual(current, before)
        validate_state(recorded)
        validate_transition(current, recorded)
        self.assertEqual(recorded['revision'], current['revision'])
        for field in ('slots', 'sources', 'items', 'commands', 'quarantine', 'migration'):
            self.assertEqual(recorded[field], current[field])
        self.assertEqual(len(recorded['incidents']), 1)
        incident = next(iter(recorded['incidents'].values()))
        self.assertEqual(incident['status'], 'open')
        self.assertEqual(incident['kind'], 'legacy_authority_violation')
        self.assertEqual(incident['target'], {'type': 'authority', 'resource': 'automation-state'})
        self.assertEqual(recorded['audit'][-1]['event'], 'legacy_mutation_rejected')
        encoded = json.dumps(recorded)
        for secret in ('synthetic-secret-never-persist', 'synthetic-secret-actor', 'synthetic-secret-epoch'):
            self.assertNotIn(secret, encoded)

    def test_exact_rejection_retry_on_new_blob_is_idempotent(self):
        first = self.record(new_state())
        again = self.record(first, current_sha='c' * 40, now='2026-09-18T20:00:00+00:00')
        self.assertEqual(again, first)

    def test_retry_keeps_independently_added_receipts_and_quarantine(self):
        current, command = requested()
        first = self.record(current)
        first['quarantine'].append({'receipt': 'added-after-rejection'})
        first['audit'].append({'at': NOW, 'event': 'independent-checkpoint'})
        first['commands'][command]['failure'] = {'classification': 'retained-failure'}
        before = copy.deepcopy(first)
        self.assertEqual(self.record(first, current_sha='c' * 40), before)
        self.assertEqual(first, before)

    def test_malformed_caller_revision_is_hashed_into_durable_rejection(self):
        recorded = self.record(new_state(), before_sha={'attempted_secret': 'synthetic-malformed-secret'})
        self.assertEqual(len(recorded['incidents']), 1)
        self.assertEqual(next(iter(recorded['incidents'].values()))['status'], 'open')
        self.assertNotIn('synthetic-malformed-secret', json.dumps(recorded))

    def test_distinct_actor_or_attempt_cannot_replace_previous_incident(self):
        first = self.record(new_state())
        second = self.record(first, actor='other-old-worker')
        third = self.record(second, proposed={'schema_version': 5, 'status': 'different-attempt'})
        self.assertEqual(len(third['incidents']), 3)
        for key, incident in first['incidents'].items():
            self.assertEqual(third['incidents'][key], incident)
        self.assertEqual(third['audit'][:len(first['audit'])], first['audit'])

    def test_rejection_preserves_every_verified_handover_and_import_receipt(self):
        fixture = handover_fixtures.HandoverTests()
        fixture.setUp()
        current = copy.deepcopy(fixture.finish())
        before = copy.deepcopy(current)
        recorded = self.record(current)
        validate_state(recorded)
        validate_transition(current, recorded)
        self.assertEqual(recorded['handover'], before['handover'])
        self.assertEqual(recorded['migration'], before['migration'])
        self.assertEqual(recorded['quarantine'], before['quarantine'])
        self.assertEqual(recorded['items'], before['items'])
        self.assertEqual(recorded['commands'], before['commands'])

    def test_rejection_can_be_persisted_by_existing_store_and_recovered_after_lost_response(self):
        server = ContentsServer()
        store = GitHubStateStore(server, 'owner/repo')
        loaded = store.load()
        recorded = self.record(loaded.state, current_sha=loaded.blob_sha)
        server.lose_response = True
        with self.assertRaisesRegex(Exception, 'response lost'):
            store.save(loaded, recorded)
        recovered = store.load()
        retry = self.record(recovered.state, current_sha=recovered.blob_sha)
        self.assertEqual(retry, recovered.state)
        with self.assertRaisesRegex(StateInvalid, 'LEGACY_AUTHORITY_INCIDENT_OPEN'):
            store.save(recovered, retry)
        self.assertEqual(len(server.writes), 1)
        self.assertEqual(len(recovered.state['incidents']), 1)
        self.assertEqual(recovered.state['revision'], 1)

    def test_rejection_record_does_not_import_or_repair_unprotected_legacy_state(self):
        with self.assertRaises(StateInvalid):
            self.record({'schema_version': 5})

    def test_rejection_preserves_prepared_exclusion_ledger_before_handover(self):
        current = {'schema_version': 5,
                   'github_exclusion': {'epoch': 'synthetic-epoch', 'anchor': 'a' * 40,
                                        'legacy_body_sha256': 'b' * 64, 'drains': {}},
                   'history': [{'event': 'legacy_cycle'}], 'quarantine': [{'receipt': 'retained'}]}
        before = copy.deepcopy(current)
        recorded = self.record(current)
        self.assertEqual(current, before)
        self.assertEqual(recorded['github_exclusion'], before['github_exclusion'])
        self.assertEqual(recorded['quarantine'], before['quarantine'])
        self.assertEqual(recorded['history'], before['history'])
        self.assertNotIn('handover', recorded)
        self.assertEqual(len(recorded['incidents']), 1)
        self.assertEqual(next(iter(recorded['incidents'].values()))['status'], 'open')


if __name__ == '__main__':
    unittest.main()
