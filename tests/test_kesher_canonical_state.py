"""Canonical boundaries for #823-829, #849-852 and the historical 409 loop."""
import base64
import copy
import json
import unittest

from scripts.kesher_runtime.identity import MediaIdentity, SlotIdentity, SourceIdentity, identity_from_dict
from scripts.kesher_runtime.state import (
    ClaimRejected, CommandConflict, StateConflict, StateInvalid, bind_source,
    claim_command, new_state, plan_command,
)
from scripts.kesher_runtime.github import GitHubError, GitHubStateStore


DAY = '2026-09-17'
CODE = 'c' * 40
SOURCE = SourceIdentity(DAY, 'article', 'a' * 64)
OVERVIEW = MediaIdentity(SOURCE, 'overview')
SHORT = MediaIdentity(SOURCE, 'short')
NOW = '2026-09-17T20:00:00+00:00'


class ContentsServer:
    """GitHub Contents CAS, including a lost response after the accepted write."""
    def __init__(self, document=None):
        self.document = copy.deepcopy(document or new_state())
        self.sha = '1' * 40
        self.writes = []
        self.lose_response = False

    def request(self, method, path, body=None, **kwargs):
        if method == 'GET':
            return {'sha': self.sha, 'encoding': 'base64', 'content':
                    base64.b64encode(json.dumps(self.document).encode()).decode()}
        self.writes.append(copy.deepcopy(body))
        if body.get('sha') != self.sha:
            raise GitHubError(409, 'revision conflict')
        self.document = json.loads(base64.b64decode(body['content']))
        self.sha = format(len(self.writes) + 1, '040x')
        if self.lose_response:
            raise GitHubError(None, 'response lost', uncertain=True)
        return {'content': {'sha': self.sha}}


def requested(state=None, target=OVERVIEW, **kwargs):
    if state is None:
        state = bind_source(new_state(), SOURCE, now=NOW)
    return plan_command(state, target, 'publish', 1, {}, code_sha=CODE, now=NOW, **kwargs)


class CanonicalIdentityTests(unittest.TestCase):
    def test_kind_content_and_slot_are_separate_immutable_identities(self):
        variants = [OVERVIEW, SHORT,
                    MediaIdentity(SourceIdentity(DAY, 'article', 'b' * 64), 'overview'),
                    MediaIdentity(SourceIdentity('2026-09-18', 'article', 'a' * 64), 'overview')]
        self.assertEqual(len({identity.key for identity in variants}), 4)
        for identity in variants + [SOURCE, SlotIdentity(DAY)]:
            self.assertEqual(identity_from_dict(identity.to_dict()), identity)

    def test_partial_encoded_or_ambiguous_identity_fails_closed(self):
        for value in ['', 'a' * 12, 'A' * 64, 'x' * 64]:
            with self.subTest(sha=value), self.assertRaises(ValueError):
                SourceIdentity(DAY, 'article', value)
        for slug in [' article', 'article/', 'a?b', '%D7%90', 'a b', '', 'e\u0301']:
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                SourceIdentity(DAY, slug, 'a' * 64)
        with self.assertRaises(ValueError):
            MediaIdentity(SOURCE, 'video')
        with self.assertRaises(ValueError):
            identity_from_dict({'slot': DAY, 'slug': 'article', 'kind': 'short'})
        with self.assertRaises(ValueError):
            identity_from_dict({**SHORT.to_dict(), 'item_id': 'ambiguous-selector'})

    def test_hebrew_identity_survives_serialization_without_ascii_alias(self):
        source = SourceIdentity(DAY, 'זוגיות-בריאה', 'a' * 64)
        self.assertEqual(identity_from_dict(json.loads(json.dumps(source.to_dict()))), source)


class CanonicalStoreTests(unittest.TestCase):
    def setUp(self):
        self.server = ContentsServer()
        self.store = GitHubStateStore(self.server, 'owner/repo')

    def test_two_loads_on_same_store_cannot_rebind_old_state_to_new_revision(self):
        old = self.store.load()
        current = self.store.save(old, bind_source(old.state, SOURCE, now=NOW))
        newest = self.store.load()
        self.assertEqual(newest.blob_sha, current.blob_sha)
        with self.assertRaises(StateConflict):
            self.store.save(old, bind_source(old.state, SourceIdentity(DAY, 'other', 'b' * 64), now=NOW))
        self.assertEqual(self.server.document['slots'][DAY]['source_key'], SOURCE.key)
        self.assertEqual(len(self.server.writes), 2)
        self.assertEqual(self.server.writes[-1]['sha'], old.blob_sha)

    def test_loaded_snapshot_is_immutable_and_saved_revision_increments_once(self):
        original = self.store.load()
        extracted = original.state
        extracted['revision'] = 400
        self.assertEqual(original.state['revision'], 0)
        proposed = bind_source(original.state, SOURCE, now=NOW)
        saved = self.store.save(original, proposed)
        self.assertEqual(saved.state['revision'], 1)
        self.assertEqual(proposed['revision'], 0)
        self.assertEqual(original.state, new_state())
        self.assertEqual(self.store.save(saved, saved.state), saved)
        self.assertEqual(len(self.server.writes), 1)

    def test_lost_write_response_requires_reload_not_repeat_or_false_success(self):
        original = self.store.load()
        self.server.lose_response = True
        with self.assertRaises(GitHubError):
            self.store.save(original, bind_source(original.state, SOURCE, now=NOW))
        self.assertEqual(len(self.server.writes), 1)
        recovered = self.store.load()
        self.assertEqual(recovered.state['revision'], 1)
        self.assertEqual(recovered.state['slots'][DAY]['source_key'], SOURCE.key)

    def test_wrong_schema_and_snapshot_location_fail_before_mutation(self):
        self.server.document = {'schema_version': 5}
        with self.assertRaises(StateInvalid):
            self.store.load()
        self.server.document = new_state()
        original = self.store.load()
        with self.assertRaises(StateInvalid):
            GitHubStateStore(self.server, 'another/repo').save(original, original.state)
        self.assertEqual(self.server.writes, [])

    def test_command_identity_and_accepted_owner_cannot_be_rewritten(self):
        state, command_id = requested()
        self.server.document = state
        loaded = self.store.load()
        mutated = loaded.state
        mutated['commands'][command_id]['target'] = SHORT.to_dict()
        with self.assertRaises(StateInvalid):
            self.store.save(loaded, mutated)
        claimed, _ = claim_command(loaded.state, command_id, 'run-1', OVERVIEW, code_sha=CODE, now=NOW)
        accepted = self.store.save(loaded, claimed)
        mutated = accepted.state
        mutated['commands'][command_id]['owner']['run_id'] = 'run-2'
        with self.assertRaises(StateInvalid):
            self.store.save(accepted, mutated)


class CanonicalCommandTests(unittest.TestCase):
    def test_duplicate_schedulers_create_same_intent_and_claim_only_once(self):
        base = bind_source(new_state(), SOURCE, now=NOW)
        first, command_id = requested(base)
        duplicate, duplicate_id = requested(base)
        self.assertEqual(first, duplicate)
        self.assertEqual(command_id, duplicate_id)
        claimed, receipt = claim_command(first, command_id, 'run-1', OVERVIEW, code_sha=CODE, now=NOW)
        self.assertTrue(receipt.execute)
        for run in ['run-1', 'run-2']:
            unchanged, receipt = claim_command(claimed, command_id, run, OVERVIEW, code_sha=CODE, now=NOW)
            self.assertFalse(receipt.execute)
            self.assertEqual(unchanged, claimed)
        self.assertEqual(first['commands'][command_id]['phase'], 'REQUESTED')

    def test_wrong_kind_source_or_code_cannot_claim(self):
        state, command_id = requested()
        for target, code in [(SHORT, CODE), (MediaIdentity(SourceIdentity(DAY, 'article', 'b' * 64), 'overview'), CODE),
                             (OVERVIEW, 'd' * 40)]:
            with self.subTest(target=target, code=code), self.assertRaises(ClaimRejected):
                claim_command(state, command_id, 'run-1', target, code_sha=code, now=NOW)
        self.assertIsNone(state['commands'][command_id]['owner'])

    def test_changed_source_invalidates_unclaimed_old_command(self):
        state, command_id = requested()
        changed = SourceIdentity(DAY, 'article', 'b' * 64)
        with self.assertRaises(StateInvalid):
            bind_source(state, changed, now=NOW)
        updated = bind_source(state, changed, previous_source_key=SOURCE.key, now=NOW)
        with self.assertRaises(ClaimRejected):
            claim_command(updated, command_id, 'run-1', OVERVIEW, code_sha=CODE, now=NOW)
        self.assertIn(SOURCE.key, updated['sources'])
        self.assertEqual(updated['commands'][command_id]['target'], OVERVIEW.to_dict())

    def test_active_command_blocks_another_ordinal_but_not_other_kind(self):
        state, command_id = requested()
        with self.assertRaises(CommandConflict):
            plan_command(state, OVERVIEW, 'publish', 2, {}, code_sha=CODE, now=NOW)
        state, short_command_id = requested(state, target=SHORT)
        self.assertNotEqual(command_id, short_command_id)
        with self.assertRaises(CommandConflict):
            plan_command(state, OVERVIEW, 'publish', 1, {'arbitrary': 'changed'}, code_sha=CODE, now=NOW)

    def test_another_operation_cannot_race_the_same_media_resource(self):
        state, _ = requested()
        for operation in ['rebuild', 'repair_metadata', 'reconcile']:
            with self.subTest(operation=operation), self.assertRaises(CommandConflict):
                plan_command(state, OVERVIEW, operation, 1, {}, code_sha=CODE, now=NOW)

    def test_inputs_cannot_override_canonical_identity(self):
        state = bind_source(new_state(), SOURCE, now=NOW)
        for inputs in [{'target_slug': 'another'}, {'target_content_sha256': 'b' * 64}, {'command_id': 'arbitrary'}]:
            with self.subTest(inputs=inputs), self.assertRaises(StateInvalid):
                plan_command(state, OVERVIEW, 'publish', 1, inputs, code_sha=CODE, now=NOW)

    def test_prepublication_slot_cannot_create_a_second_article_after_adoption(self):
        state = new_state()
        state, command_id = plan_command(state, SlotIdentity(DAY), 'create_article', 1, {}, code_sha=CODE, now=NOW)
        adopted = bind_source(state, SOURCE, now=NOW)
        with self.assertRaises(ClaimRejected):
            claim_command(adopted, command_id, 'run-1', SlotIdentity(DAY), code_sha=CODE, now=NOW)
        with self.assertRaises(CommandConflict):
            plan_command(adopted, SlotIdentity(DAY), 'create_article', 2, {}, code_sha=CODE, now=NOW)

    def test_crash_after_intent_retains_exact_command_for_next_tick(self):
        server = ContentsServer()
        store = GitHubStateStore(server, 'owner/repo')
        loaded = store.load()
        proposed, command_id = requested()
        store.save(loaded, proposed)
        restarted = GitHubStateStore(server, 'owner/repo').load()
        same, same_id = requested(restarted.state)
        self.assertEqual(same_id, command_id)
        self.assertEqual(same, restarted.state)
        self.assertEqual(len(same['commands']), 1)


if __name__ == '__main__':
    unittest.main()
