"""Native protected-ref readback through an independently injected admin.

No credentials, live defaults or effects at import/construction. A real,
independently reviewed ruleset ID must already exist: missing or contradictory
configuration is never created/repaired implicitly. Enforcement only activates
that exact disabled/evaluate policy. REST ruleset PUT is not a CAS; immutable
Git ref ownership still belongs to GitExclusionEpoch. The administrator must
retain exclusive ruleset administration throughout the authority operation.

API contract: https://docs.github.com/en/rest/repos/rules
"""
import copy
import re

from .authority_topology import GitHubAuthorityObserver, validate_registered_inventory, workflow_snapshot, run_snapshot
from .cutover_service import InvocationJournal
from .exclusion import CANONICAL_GATE, CONTROL_GATE, REQUIRED_RESOURCES
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

PROTECTED_REFS = ('refs/heads/main', 'refs/heads/automation-state')
RULES = ({'type': 'creation'},
         {'type': 'update', 'parameters': {'update_allows_fetch_and_merge': False}},
         {'type': 'deletion'}, {'type': 'non_fast_forward'})
RULESET_FIELDS = {'id', 'name', 'target', 'source_type', 'source', 'enforcement',
                  'bypass_actors', 'conditions', 'rules', 'node_id', 'updated_at'}
METADATA_FIELDS = {'_links', 'created_at', 'current_user_can_bypass'}
SUMMARY_FIELDS = {'id', 'name', 'source_type', 'source', 'enforcement', 'node_id',
                  'updated_at', 'target', '_links', 'created_at'}


class GitHubRulesetBoundary:
    def __init__(self, admin, repo, *, repository_id, main_sha, canonical_app_id,
                 ruleset_id, ruleset_name, policy, rules, journal=None):
        try:
            require_sha(main_sha, 40)
            base = {'repo', 'resource', 'resource_id', 'epoch', 'owner', 'default_authority',
                    'protection_method', 'predecessor_authority_denied', 'covered_credential_classes',
                    'canonical_gate', 'control_gate'}
            method = policy.get('protection_method')
            keys = base | ({'credential_revocation_complete'} if method == 'native_revocation' else set())
            if (not callable(getattr(admin, 'request', None))
                    or not isinstance(repo, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo)
                    or any(type(value) is not int or value < 1
                           for value in (repository_id, canonical_app_id, ruleset_id))
                    or not isinstance(ruleset_name, str) or not ruleset_name.strip()
                    or set(policy) != keys or policy['repo'] != repo or policy['resource'] != 'github'
                    or not all(isinstance(policy[key], str) and policy[key].strip()
                               for key in ('resource_id', 'epoch', 'owner'))
                    or policy['default_authority'] != 'deny' or policy['predecessor_authority_denied'] is not True
                    or policy['covered_credential_classes'] != REQUIRED_RESOURCES['github']
                    or method not in {'native_revocation', 'resource_enforced_denial'}
                    or method == 'native_revocation' and policy['credential_revocation_complete'] is not True
                    or policy['canonical_gate'] != CANONICAL_GATE or policy['control_gate'] != CONTROL_GATE):
                raise ValueError('missing exact independently reviewed binding')
            # Every definition and retained registration needs a reviewed ID.
            pinned = dict(rules.get('registrations', {}))
            pinned.update({path: {'id': entry['registration_id']}
                           for path, entry in rules['workflows'].items()})
            validate_registered_inventory([{'id': entry['id'], 'path': path, 'state': 'active'}
                                           for path, entry in pinned.items()], rules, complete=True)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            raise StateInvalid('GITHUB_RULESET_REVIEWED_BINDING_REQUIRED') from exc
        self.admin, self.repo, self.api = admin, repo, '/repos/' + repo
        self._policy, self._rules = copy.deepcopy(policy), copy.deepcopy(rules)
        self.journal = journal
        self._binding = dict(repo=repo, repository_id=repository_id, resource_id=policy['resource_id'],
                             main_sha=main_sha, epoch=policy['epoch'], owner=policy['owner'],
                             policy_sha256=digest(policy), registrations_policy_sha256=digest(rules),
                             canonical_app_id=canonical_app_id, ruleset_id=ruleset_id, ruleset_name=ruleset_name)
        self._desired = {'name': ruleset_name, 'target': 'branch', 'enforcement': 'active',
                         'bypass_actors': [{'actor_id': canonical_app_id, 'actor_type': 'Integration',
                                            'bypass_mode': 'always'}],
                         'conditions': {'ref_name': {'include': list(PROTECTED_REFS), 'exclude': []}},
                         'rules': copy.deepcopy(list(RULES))}

    @property
    def binding(self):
        return copy.deepcopy(self._binding)

    def _repository(self):
        row = self.admin.request('GET', self.api)
        if (not isinstance(row, dict) or type(row.get('id')) is not int
                or row['id'] != self._binding['repository_id']
                or row.get('node_id') != self._binding['resource_id'] or row.get('full_name') != self.repo):
            raise StateInvalid('GITHUB_RULESET_REPOSITORY_CHANGED')
        return {key: row[key] for key in ('id', 'node_id', 'full_name')}

    def _main(self):
        row = self.admin.request('GET', self.api + '/git/ref/heads/main')
        if (not isinstance(row, dict) or row.get('ref') != 'refs/heads/main'
                or row.get('object', {}).get('type') != 'commit'
                or row['object'].get('sha') != self._binding['main_sha']):
            raise StateInvalid('GITHUB_RULESET_MAIN_CHANGED')
        return self._binding['main_sha']

    def _pages(self, tail):
        rows, seen = [], set()
        separator = '&' if '?' in tail else '?'
        for page in range(1, 101):
            batch = self.admin.request('GET', self.api + tail + separator + f'per_page=100&page={page}')
            if not isinstance(batch, list) or len(batch) > 100 or any(not isinstance(row, dict) for row in batch):
                raise StateInvalid('GITHUB_RULESET_INCOMPLETE_NATIVE_INVENTORY')
            fingerprint = digest(batch)
            if batch and fingerprint in seen:
                raise StateInvalid('GITHUB_RULESET_DUPLICATE_NATIVE_PAGE')
            seen.add(fingerprint); rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise StateInvalid('GITHUB_RULESET_NATIVE_INVENTORY_LIMIT')

    def _native(self):
        rows = self._pages('/rulesets?includes_parents=true')
        if len(rows) > 1:
            raise StateInvalid('GITHUB_RULESET_UNREVIEWED_NATIVE_AUTHORITY')
        identity = self._binding['ruleset_id']
        if rows:
            row = rows[0]
            if (set(row) - SUMMARY_FIELDS or type(row.get('id')) is not int or row['id'] != identity
                    or row.get('source_type') != 'Repository' or row.get('source') != self.repo):
                raise StateInvalid('GITHUB_RULESET_IDENTITY_CHANGED')
        detail = self.admin.request('GET', self.api + f'/rulesets/{identity}?includes_parents=true', allow_404=True)
        if not rows and detail is None:
            return rows, None
        if not rows or detail is None or not isinstance(detail, dict):
            raise StateInvalid('GITHUB_RULESET_INCOMPLETE_NATIVE_INVENTORY')
        if (not RULESET_FIELDS <= set(detail) or set(detail) - RULESET_FIELDS - METADATA_FIELDS
                or type(detail['id']) is not int or detail['id'] != identity
                or not isinstance(detail['node_id'], str) or not detail['node_id']
                or not isinstance(detail['updated_at'], str) or not detail['updated_at']
                or detail['source_type'] != 'Repository' or detail['source'] != self.repo
                or detail['name'] != self._desired['name'] or detail['target'] != 'branch'
                or detail['enforcement'] not in {'active', 'disabled', 'evaluate'}
                or canonical_json(detail['bypass_actors']) != canonical_json(self._desired['bypass_actors'])):
            raise StateInvalid('GITHUB_RULESET_POLICY_CONTRADICTORY')
        for key in ('id', 'name', 'source_type', 'source', 'enforcement', 'node_id', 'updated_at'):
            if rows[0].get(key) != detail[key]:
                raise StateInvalid('GITHUB_RULESET_READBACK_CHANGED')
        conditions = detail['conditions']
        if (not isinstance(conditions, dict) or set(conditions) != {'ref_name'}
                or not isinstance(conditions['ref_name'], dict) or set(conditions['ref_name']) != {'include', 'exclude'}
                or not isinstance(conditions['ref_name']['include'], list)
                or sorted(conditions['ref_name']['include']) != sorted(PROTECTED_REFS)
                or conditions['ref_name']['exclude'] != []):
            raise StateInvalid('GITHUB_RULESET_REF_CONDITIONS_CHANGED')
        self._require_rules(detail['rules'])
        return rows, detail

    @staticmethod
    def _require_rules(rules):
        if (not isinstance(rules, list) or any(not isinstance(rule, dict) for rule in rules)
                or sorted(canonical_json(rule) for rule in rules) != sorted(canonical_json(rule) for rule in RULES)):
            raise StateInvalid('GITHUB_RULESET_UPDATE_RESTRICTION_REQUIRED')

    def _snapshot(self):
        repository, main = self._repository(), self._main()
        observer = GitHubAuthorityObserver(self.admin, self.repo, '.', fence=None)
        registered, runs = observer.current_inventory(self._rules)
        summaries, detail = self._native()
        effective = {}
        for ref in PROTECTED_REFS:
            rows = self._pages('/rules/branches/' + ref.removeprefix('refs/heads/'))
            if detail is None or detail['enforcement'] != 'active':
                if rows:
                    raise StateInvalid('GITHUB_RULESET_UNREVIEWED_NATIVE_AUTHORITY')
            else:
                rules = []
                for row in rows:
                    source = {'ruleset_id', 'ruleset_source_type', 'ruleset_source'}
                    if (not source <= set(row) or type(row['ruleset_id']) is not int
                            or row['ruleset_id'] != self._binding['ruleset_id']
                            or row['ruleset_source_type'] != 'Repository' or row['ruleset_source'] != self.repo):
                        raise StateInvalid('GITHUB_RULESET_EFFECTIVE_SOURCE_CHANGED')
                    rules.append({key: value for key, value in row.items() if key not in source})
                self._require_rules(rules)
            effective[ref] = rows
        self._repository(); self._main()
        return dict(repository=repository, main_sha=main, summaries=summaries, ruleset=detail,
                    effective=effective, registrations=workflow_snapshot(registered), active_runs=run_snapshot(runs))

    def inspect(self, repo):
        if repo != self.repo:
            raise StateInvalid('GITHUB_RULESET_REPOSITORY_CHANGED')
        try:
            first, final = self._snapshot(), self._snapshot()
            if first != final:
                raise StateInvalid('GITHUB_RULESET_READBACK_CHANGED')
            protected = final['ruleset'] is not None and final['ruleset']['enforcement'] == 'active'
            return {'binding': self.binding, 'revision': digest({'binding': self._binding, 'native': final}),
                    'revision_kind': 'native_ruleset_digest', 'protected_refs': list(PROTECTED_REFS),
                    'protected': protected, 'predecessor_direct_write_denied': protected,
                    'status': 'protected' if protected else 'not_enforced', 'native': final}
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            if isinstance(exc, StateInvalid):
                raise
            raise StateInvalid('GITHUB_RULESET_NATIVE_READBACK_REQUIRED') from exc

    def enforce(self, repo, observed_revision, policy):
        if repo != self.repo or policy != self._policy:
            raise StateInvalid('GITHUB_RULESET_POLICY_IDENTITY_CHANGED')
        row = self.inspect(repo)
        if observed_revision != row['revision']:
            raise StateConflict('GITHUB_RULESET_REVISION_STALE')
        if row['protected']:
            return  # Exact native adoption, including restart after a lost reply.
        if row['native']['ruleset'] is None:
            raise StateInvalid('GITHUB_RULESET_MISSING: independently provision and review the actual ID')
        if not isinstance(self.journal, InvocationJournal):
            raise StateInvalid('GITHUB_RULESET_DURABLE_INTENT_REQUIRED')
        # Reuse the existing denial ledger; it is NOT evidence of native fencing.
        # One attempt per native resource/ruleset/epoch, even if main, owner,
        # policy or registrations are re-reviewed after an uncertain response.
        intent = 'github-ruleset:' + digest({key: self._binding[key] for key in
                                            ('repository_id', 'resource_id', 'ruleset_id', 'epoch')})
        self.journal.claim(self._binding['epoch'], intent)
        if self.inspect(repo)['revision'] != observed_revision:
            raise StateConflict('GITHUB_RULESET_REVISION_STALE')
        # Only change enforcement, never overwrite a concurrent actor/policy edit.
        # GitHub does not document ruleset PUT CAS. Fresh reads do not imply a lock.
        self.admin.request('PUT', self.api + f'/rulesets/{self._binding["ruleset_id"]}', {'enforcement': 'active'})
        if not self.inspect(repo)['protected']:
            raise StateInvalid('GITHUB_RULESET_ENFORCEMENT_INCOMPLETE')
