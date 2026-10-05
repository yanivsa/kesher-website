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
        rows = reconcile_registrations(self.rows(), rules)
        self.assertEqual(len(rows), 114)
        row = next(r for r in rows if r['path'] == PLUGIN)
        self.assertEqual(row['id'], 375118485)
        with self.assertRaisesRegex(StateInvalid, 'DEFINITION_MISSING'):
            classify_registered([row], rules, active_runs=[], runs_complete=True)

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
