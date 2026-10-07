"""Fresh registration identity never grants mutation or substitutes for drain."""
import copy
import json
import unittest
from pathlib import Path

from scripts.kesher_runtime.authority_topology import classify_registered, policy, validate_registered_inventory
from scripts.kesher_runtime.production_cutover import reconcile_registrations
from scripts.kesher_runtime.state import StateInvalid

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = '.github/workflows/refresh-kesher-plugin-resources-once.yml'
CUTOVER = '.github/workflows/kesher-production-cutover.yml'


class CurrentAuthorityTests(unittest.TestCase):
    def rows(self):
        evidence = ROOT/'docs/forensics/2026-09-autonomous-stabilization/resume-registrations-20261005.json'
        return json.loads(evidence.read_text())['workflows']

    def test_exact_current_inventory_reconciles_but_active_missing_definition_is_denied(self):
        rules = policy(ROOT)
        del rules['workflows']['.github/workflows/kesher-exact-short-metadata-recovery-20261006.yml']
        # Replay the immutable October 5 inventory; current 124-row admission is tested below.
        historical_paths={row["path"] for row in self.rows()}
        rules["registrations"]={p:r for p,r in rules["registrations"].items() if p in historical_paths}
        rows = reconcile_registrations(self.rows(), rules)
        self.assertEqual(len(rows), 114)
        row = next(r for r in rows if r['path'] == PLUGIN)
        self.assertEqual(row['id'], 375118485)
        with self.assertRaisesRegex(StateInvalid, 'DEFINITION_MISSING'):
            classify_registered([row], rules, active_runs=[], runs_complete=True)

    def test_task4a_124_inventory_pins_new_actors_without_granting_authority(self):
        rules=policy(ROOT)
        del rules['workflows']['.github/workflows/kesher-exact-short-metadata-recovery-20261006.yml']
        rows=json.loads((ROOT/'docs/forensics/2026-09-autonomous-stabilization/task4a-native-readback-20261006.json').read_text())['workflows']
        rules['registrations']={p:r for p,r in rules['registrations'].items() if p in {row['path'] for row in rows}}
        self.assertEqual(len(reconcile_registrations(rows,rules)),124)
        previous={r['path'] for r in self.rows()}
        new=[r for r in rows if r['path'] not in previous]
        self.assertEqual(len(new),10)
        for row in new:
            with self.subTest(path=row['path']):
                with self.assertRaises(StateInvalid):
                    classify_registered([row],rules,active_runs=[],runs_complete=True)
                with self.assertRaises(StateInvalid):
                    validate_registered_inventory([row | {'id':999999999}],rules)
                retired=row | {'state':'disabled_manually'}
                self.assertEqual(classify_registered([retired],rules,active_runs=[],runs_complete=True)[0]['role'],'retired')
        with self.assertRaises(StateInvalid):reconcile_registrations(self.rows(),rules)

    def test_current_129_inventory_preserves_new_oneoffs_without_admitting_active_writers(self):
        rules=policy(ROOT)
        evidence=json.loads((ROOT/'docs/forensics/2026-10-07-durable-stabilization/current-registrations.json').read_text())
        self.assertEqual(len(reconcile_registrations(evidence['workflows'],rules)),129)
        drift=json.loads((ROOT/'docs/forensics/2026-10-07-durable-stabilization/registration-drift.json').read_text())
        self.assertEqual(len(drift),4)
        for row in drift:
            with self.subTest(path=row['path']), self.assertRaises(StateInvalid):
                classify_registered([{k:row[k] for k in ('id','path','state')}],rules,active_runs=[],runs_complete=True)
            changed={k:row[k] for k in ('id','path','state')};changed['id']+=1
            with self.assertRaises(StateInvalid):validate_registered_inventory([changed],rules)

    def test_registered_cutover_id_cannot_rebind_even_to_another_known_path(self):
        rules = policy(ROOT)
        for changed in (
            {'id': 374799893, 'path': CUTOVER, 'state': 'active'},
            {'id': 374799892, 'path': '.github/workflows/ci.yml', 'state': 'active'},
        ):
            with self.subTest(changed=changed), self.assertRaisesRegex(StateInvalid, 'IDENTITY_MISMATCH'):
                validate_registered_inventory([changed], rules)

    def test_new_retained_id_cannot_rebind_or_hide_any_active_run_status(self):
        rules = policy(ROOT)
        row = {'id': 375118485, 'path': PLUGIN, 'state': 'disabled_manually'}
        for changed in ({'id': 375118486}, {'path': '.github/workflows/ci.yml'}):
            with self.subTest(changed=changed), self.assertRaises(StateInvalid):
                validate_registered_inventory([row | changed], rules)
        for status in ('queued', 'in_progress', 'waiting', 'pending', 'requested'):
            run = {'id': 37270996849, 'run_attempt': 2, 'workflow_id': 375118485,
                   'path': PLUGIN, 'status': status}
            with self.subTest(status=status), self.assertRaises(StateInvalid):
                classify_registered([row], rules, active_runs=[run], runs_complete=True)
        result = classify_registered([row], rules, active_runs=[], runs_complete=True)
        self.assertEqual(result[0]['classification'], 'retired_missing_yaml')
        self.assertEqual(result[0]['role'], 'retired')

    def test_a_later_unknown_registration_still_blocks_complete_reconciliation(self):
        rules = policy(ROOT)
        rows = copy.deepcopy(self.rows())
        rows.append({'id': 999999999, 'path': '.github/workflows/new-writer.yml', 'state': 'active'})
        with self.assertRaises(StateInvalid):
            reconcile_registrations(rows, rules)

    def test_completed_native_fence_does_not_admit_new_or_rebound_workflow_writer(self):
        from tests.test_kesher_git_exclusion import ResourceAdapterTests
        for change in ('new', 'rebound'):
            case = ResourceAdapterTests(); case.setUp()
            for _ in range(8): case.progress()
            self.assertEqual(case.adapter.inspect('owner/repo')['protection'], case.policy)
            if change == 'new':
                case.actions.workflows.append({'id': 10, 'path': '.github/workflows/new.yml', 'state': 'active'})
            else:
                case.actions.workflows[0]['id'] = 10
            before = len(case.git.calls)
            with self.subTest(change=change), self.assertRaises(StateInvalid):
                case.adapter.inspect('owner/repo')
            self.assertFalse(any(method != 'GET' for method, _, _ in case.git.calls[before:]))

    def test_final_native_revision_drift_refuses_completed_drain_protection(self):
        from tests.test_kesher_git_exclusion import ResourceAdapterTests
        case = ResourceAdapterTests(); case.setUp()
        for _ in range(8): case.progress()
        calls = 0
        def drift(method, path, body):
            nonlocal calls
            if '/rulesets?' in path:
                calls += 1
                if calls == 3:
                    case.native.native['updated_at'] = '2026-10-05T03:00:00Z'
        case.native.hook = drift
        with self.assertRaisesRegex(StateInvalid, 'RULESET_CHANGED'):
            case.adapter.inspect('owner/repo')

    def test_main_or_guard_change_in_last_registration_pass_refuses_protection(self):
        from tests.test_kesher_git_exclusion import ResourceAdapterTests
        for change in ('main', 'guard'):
            case = ResourceAdapterTests(); case.setUp()
            for _ in range(8): case.progress()
            native_reads = 0
            def native_read(method, path, body):
                nonlocal native_reads
                if '/rulesets?' in path: native_reads += 1
            case.native.hook = native_read
            original = case.service.request
            def drift(method, path, body=None):
                if native_reads >= 4 and '/actions/workflows' in path:
                    if change == 'main': case.git.refs['main'] = 'c'*40
                    else: case.guard.protection = None
                return original(method, path, body)
            case.service.request = drift
            with self.subTest(change=change), self.assertRaises(StateInvalid):
                case.adapter.inspect('owner/repo')
