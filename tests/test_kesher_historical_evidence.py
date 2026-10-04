"""A refreshed controller may add evidence, never erase closed adjudication."""
import copy
import json
import unittest
from pathlib import Path

from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.migration import prepare_migration
from scripts.kesher_runtime.state import StateInvalid, validate_state
from tests.test_kesher_runtime_migration import inputs

FLOOR = Path(__file__).resolve().parents[1] / 'docs/forensics/2026-09-autonomous-stabilization/closed-media-evidence-floor-20260930.json'


class HistoricalEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.closed = json.loads(FLOOR.read_text())
        _, self.fresh = inputs()
        self.fresh['controller'] = {'schema_version': 5, 'cycle': '2026-09-30', 'article': {}, 'backlog': []}
        self.fresh['artifacts'] = []

    def prepare(self):
        return prepare_migration(**self.fresh, retained_evidence=self.closed)

    def test_rollover_without_old_stage_fields_preserves_closed_baselines_and_claims(self):
        before = copy.deepcopy(self.closed)
        result = self.prepare()
        for key, item in before['items'].items():
            self.assertEqual(result['items'][key], item)
        self.assertEqual(sum(bool(r.get('legacy_import')) for row in result['items'].values() for r in row['receipts'].values()), 32)
        self.assertEqual(set(result['migration']['observed_youtube_ids']), set(before['migration']['observed_youtube_ids']))
        self.assertEqual(len(result['migration']['observed_youtube_ids']), 64)
        self.assertEqual(result['quarantine'], before['quarantine'])
        self.assertEqual(result['migration']['legacy_stage_claims'], before['migration']['legacy_stage_claims'])
        self.assertEqual(result['migration']['retained_evidence']['migration'], before['migration'])
        self.assertEqual(self.closed, before)
        self.assertEqual(result['commands'], {})
        validate_state(result)

    def test_new_current_cycle_never_rebinds_retained_historical_sources(self):
        result = self.prepare()
        self.assertNotIn('2026-09-30', result['slots'])
        for key, source in self.closed['sources'].items():
            self.assertEqual(result['sources'][key]['identity'], source['identity'])
        self.assertTrue(all(row['phase'] is None for row in result['items'].values()))

    def test_refresh_can_add_exact_identity_without_removing_any_old_id(self):
        args, fresh = inputs()
        self.fresh = fresh
        result = self.prepare()
        self.assertEqual(len(result['migration']['observed_youtube_ids']), 65)
        self.assertIn(args['item']['youtube_id'], result['migration']['observed_youtube_ids'])
        self.assertEqual(len(result['items'][args['identity'].key]['receipts']), 1)
        self.assertTrue(set(self.closed['migration']['observed_youtube_ids']).issubset(result['migration']['observed_youtube_ids']))

    def test_exact_fresh_conflict_is_quarantined_and_does_not_replace_baseline(self):
        args, original = inputs()
        self.closed = prepare_migration(**original)
        self.fresh = copy.deepcopy(original)
        self.fresh['artifacts'][0]['items'][0]['youtube_id'] = 'lmnopqrstuv'
        self.fresh['controller']['short']['youtube_id'] = 'lmnopqrstuv'
        result = self.prepare()
        self.assertEqual(result['items'][args['identity'].key], self.closed['items'][args['identity'].key])
        self.assertEqual(set(result['migration']['observed_youtube_ids']), {'abcdefghijk', 'lmnopqrstuv'})
        self.assertTrue(any(q.get('failure_class') == 'LEGACY_REFRESH_CONFLICT' and q.get('target') == args['identity'].to_dict() for q in result['quarantine']))
        self.assertEqual(result['commands'], {})
        validate_state(result)

    def test_injected_active_authority_or_private_capability_is_rejected(self):
        for corruption in ('authority', 'capability'):
            with self.subTest(corruption=corruption):
                self.setUp()
                if corruption == 'authority':
                    self.closed['migration']['status'] = 'complete'
                else:
                    self.closed['migration']['upload_session_uri'] = 'synthetic-forbidden'
                with self.assertRaises(StateInvalid):
                    self.prepare()

    def test_video_id_relabelled_to_another_exact_source_stays_quarantined(self):
        args, params = inputs()
        self.fresh = params
        existing_id = next(iter(self.closed['migration']['observed_youtube_ids']))
        params['artifacts'][0]['items'][0]['youtube_id'] = existing_id
        params['controller']['short']['youtube_id'] = existing_id
        result = self.prepare()
        self.assertTrue(any(q.get('failure_class') == 'LEGACY_REFRESH_IDENTITY_CONFLICT' and
            q.get('target') == args['identity'].to_dict() for q in result['quarantine']))

    def test_closed_floor_hash_matches_the_retained_preparation(self):
        self.assertEqual(digest(self.closed), '5f2bb8d19b6ca3e9004d1e34997c9a55b05dea944f7ea901c1c33ff62a71df1c')


if __name__ == '__main__':
    unittest.main()
