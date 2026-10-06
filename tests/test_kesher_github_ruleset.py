"""Native API fixtures only; no live repository administration or credentials."""
import copy
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from scripts.kesher_runtime.cutover_service import InvocationJournal
from scripts.kesher_runtime.exclusion import ExclusionFence, REQUIRED_RESOURCES
from scripts.kesher_runtime.github import GitHubError
from scripts.kesher_runtime.github_ruleset import GitHubRulesetBoundary
from scripts.kesher_runtime.state import StateConflict, StateInvalid
from tests.test_kesher_github_drain import Actions, Journal, PATH


def resource_policy(method='resource_enforced_denial'):
    bindings = {name: 'resource-id:' + name for name in REQUIRED_RESOURCES}
    bindings['github'] = 'repository-id'
    methods = dict.fromkeys(bindings, 'native_revocation') | {'github': method}
    return ExclusionFence('owner/repo', 'one', 'coordinator', dict.fromkeys(bindings),
                          bindings, protection_methods=methods)._policy('github')


def reviewed_rules():
    return {'workflows': {}, 'registrations': {PATH: {'id': 9, 'definition_present': False}}}


class RulesetAdmin:
    """REST-shaped fixture. IDs are fixture data, never live defaults."""
    def __init__(self, *, git=None, actions=None):
        self.git = git
        self.actions = actions or Actions(Journal())
        self.repository = {'id': 101, 'node_id': 'repository-id', 'full_name': 'owner/repo'}
        self.main = 'b' * 40
        self.native = {
            'id': 42, 'node_id': 'RRS_fixture', 'name': 'Kesher epoch one',
            'target': 'branch', 'source_type': 'Repository', 'source': 'owner/repo',
            'enforcement': 'active', 'updated_at': '2026-10-05T00:00:00Z',
            'bypass_actors': [{'actor_id': 707, 'actor_type': 'Integration', 'bypass_mode': 'always'}],
            'conditions': {'ref_name': {'include': ['refs/heads/main', 'refs/heads/automation-state'],
                                        'exclude': []}},
            'rules': [{'type': 'creation'},
                      {'type': 'update', 'parameters': {'update_allows_fetch_and_merge': False}},
                      {'type': 'deletion'}, {'type': 'non_fast_forward'}],
        }
        self.extra = []
        self.calls = []
        self.hook = None
        self.effective = {}
        self.lost = None

    def request(self, method, path, body=None, *, allow_404=False):
        self.calls.append((method, path, copy.deepcopy(body)))
        if self.hook:
            self.hook(method, path, body)
        tail = urlsplit(path).path.removeprefix('/repos/owner/repo')
        if method == 'GET' and tail == '':
            return copy.deepcopy(self.repository)
        if method == 'GET' and tail.startswith('/git/ref/heads/'):
            ref = tail.removeprefix('/git/ref/heads/')
            sha = self.git.refs[ref] if self.git else self.main if ref == 'main' else 'a' * 40
            return {'ref': 'refs/heads/' + ref, 'object': {'type': 'commit', 'sha': sha}}
        if method == 'GET' and tail == '/rulesets':
            rows = ([{key: self.native[key] for key in
                      ('id', 'node_id', 'name', 'source_type', 'source', 'enforcement', 'updated_at')}]
                    if self.native else [])
            return copy.deepcopy(rows + self.extra)
        if method == 'GET' and tail == '/rulesets/42':
            return copy.deepcopy(self.native)
        if method == 'GET' and tail.startswith('/rules/branches/'):
            ref = tail.removeprefix('/rules/branches/')
            if ref in self.effective:
                return copy.deepcopy(self.effective[ref])
            if not self.native or self.native['enforcement'] != 'active':
                return []
            return [copy.deepcopy(rule) | {'ruleset_id': 42, 'ruleset_source_type': 'Repository',
                                          'ruleset_source': 'owner/repo'} for rule in self.native['rules']]
        if '/actions/' in tail:
            return self.actions.request(method, path, body)
        if method == 'PUT' and tail == '/rulesets/42':
            if self.lost == 'before':
                raise GitHubError(None, 'uncertain before effect', uncertain=True)
            self.native.update(copy.deepcopy(body))
            self.native['updated_at'] = '2026-10-05T01:00:00Z'
            if self.lost == 'after':
                raise GitHubError(None, 'uncertain after effect', uncertain=True)
            return copy.deepcopy(self.native)
        raise AssertionError((method, path))

    def mutations(self):
        return [call for call in self.calls if call[0] != 'GET']


def ruleset_boundary(admin, *, policy=None, rules=None, journal=None, **binding):
    kwargs = dict(repository_id=101, main_sha='b' * 40, canonical_app_id=707,
                  ruleset_id=42, ruleset_name='Kesher epoch one',
                  policy=policy or resource_policy(), rules=rules or reviewed_rules(), journal=journal)
    return GitHubRulesetBoundary(admin, 'owner/repo', **(kwargs | binding))


class GitHubRulesetTests(unittest.TestCase):
    def setUp(self):
        self.admin = RulesetAdmin()
        self.policy = resource_policy()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger_path = Path(self.temp.name) / 'invocations.sqlite'
        InvocationJournal.initialize(self.ledger_path)
        self.boundary = self.fresh()

    def fresh(self):
        return ruleset_boundary(self.admin, policy=self.policy, journal=InvocationJournal(self.ledger_path))

    def test_constructor_performs_no_native_calls(self):
        self.assertEqual(self.admin.calls, [])

    def test_both_exact_refs_and_only_canonical_app_have_native_protection(self):
        row = self.boundary.inspect('owner/repo')
        self.assertTrue(row['protected'])
        self.assertTrue(row['predecessor_direct_write_denied'])
        self.assertEqual(row['binding']['canonical_app_id'], 707)
        self.assertEqual(row['binding']['repository_id'], 101)
        self.assertEqual(row['binding']['resource_id'], 'repository-id')
        self.assertEqual(row['protected_refs'], ['refs/heads/main', 'refs/heads/automation-state'])
        for ref in ('main', 'automation-state'):
            self.assertTrue(any('/rules/branches/' + ref in path for _, path, _ in self.admin.calls))
        self.assertEqual(self.admin.mutations(), [])

    def test_revision_is_stable_across_fresh_instances(self):
        first = self.boundary.inspect('owner/repo')['revision']
        self.assertEqual(len(first), 64)
        self.assertEqual(first, self.fresh().inspect('owner/repo')['revision'])

    def test_wrong_repo_stable_id_node_or_name_is_refused(self):
        for field, value in [('id', 102), ('id', True), ('node_id', 'other-id'), ('full_name', 'other/repo')]:
            with self.subTest(field=field, value=value):
                original = copy.deepcopy(self.admin.repository)
                self.admin.repository[field] = value
                with self.assertRaises(StateInvalid):
                    self.boundary.inspect('owner/repo')
                self.admin.repository = original
        with self.assertRaises(StateInvalid):
            self.boundary.inspect('other/repo')

    def test_bypass_requires_exact_canonical_integration_and_no_other_actor(self):
        canonical = copy.deepcopy(self.admin.native['bypass_actors'])
        for actor_type in ('User', 'Team', 'OrganizationAdmin', 'RepositoryRole', 'DeployKey', 'Integration'):
            for actors in ([{'actor_id': 999, 'actor_type': actor_type, 'bypass_mode': 'always'}],
                           canonical + [{'actor_id': 999, 'actor_type': actor_type, 'bypass_mode': 'always'}]):
                with self.subTest(actors=actors), self.assertRaises(StateInvalid):
                    self.admin.native['bypass_actors'] = actors
                    self.boundary.inspect('owner/repo')
        self.assertEqual(self.admin.mutations(), [])

    def test_missing_hidden_duplicate_or_partial_canonical_bypass_refuses(self):
        actor = {'actor_id': 707, 'actor_type': 'Integration', 'bypass_mode': 'always'}
        for actors in ([], None, [actor, actor], [actor | {'bypass_mode': 'pull_request'}],
                       [actor | {'bypass_mode': 'exempt'}], [actor | {'actor_id': True}]):
            with self.subTest(actors=actors), self.assertRaises(StateInvalid):
                self.admin.native['bypass_actors'] = actors
                self.boundary.inspect('owner/repo')
        self.admin.native.pop('bypass_actors')
        with self.assertRaises(StateInvalid):
            self.boundary.inspect('owner/repo')

    def test_missing_update_on_either_effective_ref_is_refused(self):
        native = self.admin.native['rules']
        for ref in ('main', 'automation-state'):
            self.admin.effective = {ref: [rule | {'ruleset_id': 42, 'ruleset_source_type': 'Repository',
                                                'ruleset_source': 'owner/repo'}
                                         for rule in native if rule['type'] != 'update']}
            with self.subTest(ref=ref), self.assertRaises(StateInvalid):
                self.boundary.inspect('owner/repo')

    def test_changed_or_missing_update_and_destructive_restrictions_refuse(self):
        original = copy.deepcopy(self.admin.native['rules'])
        for removed in ('update', 'creation', 'deletion', 'non_fast_forward'):
            self.admin.native['rules'] = [r for r in original if r['type'] != removed]
            with self.subTest(removed=removed), self.assertRaises(StateInvalid):
                self.boundary.inspect('owner/repo')
        self.admin.native['rules'] = copy.deepcopy(original)
        self.admin.native['rules'][1]['parameters']['update_allows_fetch_and_merge'] = True
        with self.assertRaises(StateInvalid):
            self.boundary.inspect('owner/repo')

    def test_wrong_ruleset_id_source_ref_conditions_or_unknown_controls_refuse(self):
        original = copy.deepcopy(self.admin.native)
        changes = [{'id': 43}, {'source': 'other/repo'}, {'source_type': 'Organization'},
                   {'target': 'tag'}, {'name': 'another epoch'}, {'enforcement': 'enabled'},
                   {'protected': True}, {'bypass_actors': original['bypass_actors'] + [{}]},
                   {'conditions': {'ref_name': {'include': ['~DEFAULT_BRANCH', 'refs/heads/automation-state'], 'exclude': []}}},
                   {'conditions': {'ref_name': {'include': ['refs/heads/main'], 'exclude': []}}},
                   {'conditions': {'ref_name': {'include': ['refs/heads/main', 'refs/heads/automation-state'],
                                                'exclude': ['refs/heads/automation-state']}}}]
        for change in changes:
            self.admin.native = original | change
            with self.subTest(change=change), self.assertRaises(StateInvalid):
                self.boundary.inspect('owner/repo')

    def test_absent_disabled_or_evaluate_is_not_admission_and_absent_is_not_created(self):
        for state in ('disabled', 'evaluate'):
            self.admin.native['enforcement'] = state
            row = self.boundary.inspect('owner/repo')
            self.assertFalse(row['protected'])
            self.assertEqual(row['status'], 'not_enforced')
        self.admin.native = None
        row = self.boundary.inspect('owner/repo')
        self.assertFalse(row['protected'])
        with self.assertRaisesRegex(StateInvalid, 'RULESET_MISSING'):
            self.boundary.enforce('owner/repo', row['revision'], self.policy)
        self.assertEqual(self.admin.mutations(), [])

    def test_deleted_or_changed_ruleset_since_observation_cannot_be_enforced(self):
        self.admin.native['enforcement'] = 'disabled'
        revision = self.boundary.inspect('owner/repo')['revision']
        self.admin.native['updated_at'] = '2026-10-05T02:00:00Z'
        with self.assertRaises(StateConflict):
            self.boundary.enforce('owner/repo', revision, self.policy)
        self.admin.native = None
        with self.assertRaises((StateInvalid, StateConflict)):
            self.boundary.enforce('owner/repo', revision, self.policy)
        self.assertEqual(self.admin.mutations(), [])

    def test_native_readback_drift_during_inspection_refuses(self):
        calls = 0
        def drift(method, path, body):
            nonlocal calls
            if '/rulesets/42' in path:
                calls += 1
                if calls == 2:
                    self.admin.native['updated_at'] = '2026-10-05T02:00:00Z'
        self.admin.hook = drift
        with self.assertRaisesRegex(StateInvalid, 'READBACK_CHANGED'):
            self.boundary.inspect('owner/repo')

    def test_new_or_rebound_registration_prevents_protection_and_effect(self):
        self.admin.native['enforcement'] = 'disabled'
        revision = self.boundary.inspect('owner/repo')['revision']
        original = copy.deepcopy(self.admin.actions.workflows)
        for rows in (original + [{'id': 10, 'path': '.github/workflows/new.yml', 'state': 'active'}],
                     [original[0] | {'id': 10}], [original[0] | {'path': '.github/workflows/new.yml'}]):
            self.admin.actions.workflows = rows
            with self.subTest(rows=rows), self.assertRaises(StateInvalid):
                self.boundary.enforce('owner/repo', revision, self.policy)
        self.assertEqual(self.admin.mutations(), [])

    def test_changed_main_before_or_during_readback_refuses(self):
        revision = self.boundary.inspect('owner/repo')['revision']
        self.admin.main = 'c' * 40
        with self.assertRaisesRegex(StateInvalid, 'MAIN_CHANGED'):
            self.boundary.enforce('owner/repo', revision, self.policy)
        self.admin.main = 'b' * 40
        def drift(method, path, body):
            if '/rules/branches/automation-state' in path:
                self.admin.main = 'c' * 40
        self.admin.hook = drift
        with self.assertRaises(StateInvalid):
            self.boundary.inspect('owner/repo')
        self.assertEqual(self.admin.mutations(), [])

    def test_stale_pat_jules_or_legacy_app_cannot_establish_boundary(self):
        self.admin.native['enforcement'] = 'disabled'
        revision = self.boundary.inspect('owner/repo')['revision']
        for stale in ({'actor_id': 801, 'actor_type': 'User', 'bypass_mode': 'always'},
                      {'actor_id': 802, 'actor_type': 'Integration', 'bypass_mode': 'always'}):
            self.admin.native['bypass_actors'] = [stale]
            with self.subTest(actor=stale), self.assertRaises(StateInvalid):
                self.boundary.enforce('owner/repo', revision, self.policy)
        self.assertEqual(self.admin.mutations(), [])

    def test_exact_activation_uses_one_put_and_is_idempotent_after_readback(self):
        self.admin.native['enforcement'] = 'disabled'
        revision = self.boundary.inspect('owner/repo')['revision']
        self.boundary.enforce('owner/repo', revision, self.policy)
        self.assertEqual([(m, p) for m, p, _ in self.admin.mutations()],
                         [('PUT', '/repos/owner/repo/rulesets/42')])
        fresh = self.fresh()
        row = fresh.inspect('owner/repo')
        fresh.enforce('owner/repo', row['revision'], self.policy)
        self.assertEqual(len(self.admin.mutations()), 1)

    def test_wrong_revision_policy_repository_or_missing_durable_ledger_refuses_effect(self):
        self.admin.native['enforcement'] = 'disabled'
        revision = self.boundary.inspect('owner/repo')['revision']
        for repo, rev, policy in [('other/repo', revision, self.policy),
                                  ('owner/repo', '0' * 64, self.policy),
                                  ('owner/repo', revision, self.policy | {'epoch': 'two'}),
                                  ('owner/repo', revision, self.policy | {'owner': 'other'})]:
            with self.subTest(repo=repo, rev=rev, policy=policy), self.assertRaises((StateInvalid, StateConflict)):
                self.boundary.enforce(repo, rev, policy)
        no_ledger = ruleset_boundary(self.admin)
        with self.assertRaisesRegex(StateInvalid, 'DURABLE_INTENT_REQUIRED'):
            no_ledger.enforce('owner/repo', no_ledger.inspect('owner/repo')['revision'], self.policy)
        self.assertEqual(self.admin.mutations(), [])

    def test_uncertain_success_is_only_adopted_from_complete_native_readback(self):
        self.admin.native['enforcement'] = 'disabled'
        self.admin.lost = 'after'
        revision = self.boundary.inspect('owner/repo')['revision']
        with self.assertRaises(GitHubError):
            self.boundary.enforce('owner/repo', revision, self.policy)
        fresh = self.fresh()
        row = fresh.inspect('owner/repo')
        fresh.enforce('owner/repo', row['revision'], self.policy)
        self.assertEqual(len(self.admin.mutations()), 1)
        self.admin.native['bypass_actors'].append({'actor_id': 801, 'actor_type': 'User', 'bypass_mode': 'always'})
        with self.assertRaises(StateInvalid):
            self.fresh().inspect('owner/repo')

    def test_uncertain_no_effect_cannot_retry_on_restart_even_if_revision_changes(self):
        self.admin.native['enforcement'] = 'disabled'
        self.admin.lost = 'before'
        with self.assertRaises(GitHubError):
            self.boundary.enforce('owner/repo', self.boundary.inspect('owner/repo')['revision'], self.policy)
        self.admin.lost = None
        self.admin.native['updated_at'] = '2026-10-05T02:00:00Z'
        fresh = self.fresh()
        with self.assertRaisesRegex(StateInvalid, 'REPLAY_OR_LEDGER_UNAVAILABLE'):
            fresh.enforce('owner/repo', fresh.inspect('owner/repo')['revision'], self.policy)
        self.assertEqual(len(self.admin.mutations()), 1)

    def test_same_epoch_reconfiguration_cannot_reset_uncertain_mutation_budget(self):
        self.admin.native['enforcement'] = 'disabled'
        self.admin.lost = 'before'
        with self.assertRaises(GitHubError):
            self.boundary.enforce('owner/repo', self.boundary.inspect('owner/repo')['revision'], self.policy)
        self.admin.lost = None
        for binding, policy in (({'main_sha': 'c'*40}, self.policy), ({}, self.policy | {'owner': 'other'})):
            self.admin.main = binding.get('main_sha', 'b'*40)
            self.admin.native['enforcement'] = 'disabled'
            fresh = ruleset_boundary(self.admin, policy=policy, journal=InvocationJournal(self.ledger_path), **binding)
            with self.subTest(binding=binding, policy=policy), self.assertRaisesRegex(StateInvalid, 'REPLAY_OR_LEDGER_UNAVAILABLE'):
                fresh.enforce('owner/repo', fresh.inspect('owner/repo')['revision'], policy)
        self.assertEqual(len(self.admin.mutations()), 1)

    def test_lost_intent_ack_or_unavailable_ledger_prevents_native_effect(self):
        self.admin.native['enforcement'] = 'disabled'
        self.ledger_path.unlink()
        with self.assertRaisesRegex(StateInvalid, 'REPLAY_OR_LEDGER_UNAVAILABLE'):
            self.boundary.enforce('owner/repo', self.boundary.inspect('owner/repo')['revision'], self.policy)
        self.assertEqual(self.admin.mutations(), [])

    def test_lost_durable_intent_ack_is_not_replayed_after_restart(self):
        class LostIntentAck(InvocationJournal):
            def claim(inner, epoch, run):
                super().claim(epoch, run)
                raise GitHubError(None, 'durable intent acknowledgment lost', uncertain=True)
        self.admin.native['enforcement'] = 'disabled'
        self.boundary.journal = LostIntentAck(self.ledger_path)
        with self.assertRaises(GitHubError):
            self.boundary.enforce('owner/repo', self.boundary.inspect('owner/repo')['revision'], self.policy)
        fresh = self.fresh()
        with self.assertRaisesRegex(StateInvalid, 'REPLAY_OR_LEDGER_UNAVAILABLE'):
            fresh.enforce('owner/repo', fresh.inspect('owner/repo')['revision'], self.policy)
        self.assertEqual(self.admin.mutations(), [])

    def test_concurrent_actor_change_is_not_overwritten_or_certified_by_activation(self):
        self.admin.native['enforcement'] = 'disabled'
        revision = self.boundary.inspect('owner/repo')['revision']
        def change_actor(method, path, body):
            if method == 'PUT':
                self.admin.native['bypass_actors'].append({'actor_id': 801, 'actor_type': 'User', 'bypass_mode': 'always'})
        self.admin.hook = change_actor
        with self.assertRaises(StateInvalid):
            self.boundary.enforce('owner/repo', revision, self.policy)
        self.assertEqual(len(self.admin.mutations()), 1)
        self.assertEqual(self.admin.mutations()[0][2], {'enforcement': 'active'})
        with self.assertRaises(StateInvalid): self.fresh().inspect('owner/repo')

    def test_live_factory_requires_native_dependency_and_only_wires_selected_mode(self):
        from unittest.mock import patch
        from scripts.kesher_runtime.identity import digest
        from scripts.kesher_runtime.live_cutover import build_runtime
        from tests.test_kesher_external_exclusion import ProtectedService
        rules = reviewed_rules()
        registrations = {PATH: 9}
        closure = {'retained_evidence': 'f'*64}
        bindings = {name: 'resource-id:' + name for name in REQUIRED_RESOURCES}
        bindings['github'] = 'repository-id'
        methods = dict.fromkeys(bindings, 'native_revocation') | {'github': 'resource_enforced_denial'}
        review = {'repo': 'owner/repo', 'main_sha': 'b'*40, 'code_sha256': 'd'*64,
                  'policy_sha256': digest({'policy': rules, 'definitions': []}),
                  'closed_evidence_sha256': closure['retained_evidence'],
                  'registrations_sha256': digest(registrations), 'migration_material_sha256': digest({})}
        kwargs = dict(github=self.admin, repo='owner/repo', root='unused-fixture-root', epoch='one',
                      owner='coordinator', bindings=bindings, boundary=ProtectedService('github'),
                      ruleset_boundary=self.boundary, external_ports={name: object() for name in bindings if name != 'github'},
                      review=review, key_binding=None, registered_bindings=registrations,
                      separation_observer=lambda: {}, material={}, closure=closure, key=lambda: {},
                      protection_methods=methods)
        for substitute in (None, {'protected': True}):
            with self.subTest(substitute=substitute), self.assertRaisesRegex(StateInvalid, 'NATIVE_RULESET_BOUNDARY_REQUIRED'):
                build_runtime(**(kwargs | {'ruleset_boundary': substitute}))
        self.assertEqual(self.admin.calls, [])
        # This unit isolates private review installation; native readback is
        # exercised by the real adapter in every other test, never patched.
        with patch('scripts.kesher_runtime.live_cutover.policy', return_value=rules), \
             patch('scripts.kesher_runtime.live_cutover.inventory', return_value=[]), \
             patch('scripts.kesher_runtime.live_cutover.executable_digest', return_value='d'*64):
            runtime = build_runtime(**kwargs)
        port = runtime.fence.ports['github']
        self.assertIs(port.ruleset_boundary, self.boundary)
        self.assertEqual(port.policy, self.policy)
        self.assertEqual(runtime.fence._policy('github'), self.policy)
        self.assertNotIn('credential_revocation_complete', port.policy)
        self.assertTrue(all(method == 'GET' and '/actions/workflows?' in path for method, path, _ in self.admin.calls))
        self.assertEqual(self.admin.mutations(), [])

    def test_local_json_or_protected_flag_is_never_native_readback(self):
        with self.assertRaises(StateInvalid):
            ruleset_boundary({'protected': True})
        original = self.admin.request
        self.admin.request = lambda *args, **kwargs: {'protected': True}
        with self.assertRaises(StateInvalid):
            self.boundary.inspect('owner/repo')
        self.admin.request = original
        self.admin.extra.append({'id': 43, 'name': 'unreviewed', 'source_type': 'Repository',
                                 'source': 'owner/repo', 'enforcement': 'active'})
        with self.assertRaises(StateInvalid):
            self.boundary.inspect('owner/repo')


if __name__ == '__main__':
    unittest.main()
