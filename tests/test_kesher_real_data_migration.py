"""Real Oct1/2/4/5/8/9 publication shape, frozen Schema5, Oct10 cutover.

Test dispositions below are explicit fixture review decisions, NOT an operator
approval or selection algorithm for production migration material.
"""
import copy
import json
from pathlib import Path
import unittest

from scripts.kesher_daily_pipeline import source_metadata
from scripts.kesher_runtime.controller import Observation,reconcile
from scripts.kesher_runtime.identity import SourceIdentity,MediaIdentity
from scripts.kesher_runtime.migration import prepare_migration
from scripts.kesher_runtime.observe import RepositoryObserver
from scripts.kesher_runtime.state import StateInvalid
from tests.test_kesher_observe import Reads
from tests.test_kesher_autonomous_controller import publication

ROOT=Path(__file__).resolve().parents[1]
NOW='2026-10-10T10:00:00+03:00'


class RealDataMigrationTests(unittest.TestCase):
    def setUp(self):
        self.posts=json.loads((ROOT/'src/data/posts.json').read_text())
        fixture=json.loads((ROOT/'tests/fixtures/kesher/schema5-freeze-20261004.json').read_text())
        self.sources=[source_metadata(p) for p in self.posts if '2026-10-01'<=p['date']<='2026-10-10']
        self.identities={s['slug']:SourceIdentity(s['date'],s['slug'],s['content_sha256']) for s in self.sources}
        self.nine=self.identities['how-to-repair-after-couple-fight']
        self.assertEqual(self.nine.key,'source:89b290e6750339224a9f978df77bace2e27828d0f3557ee44a2b8f1d249e6d26')
        approved=('jealousy-in-relationships','20-second-hug-relationship-stress',
                  'how-to-stop-repeating-arguments','how-to-repair-after-couple-fight')
        excluded=('child-refuses-homework','why-couples-fight-at-night-fatigue')
        self.boundary={'frozen_cycle':'2026-10-04','cutover_slot':'2026-10-10',
            'adopted_source_keys':sorted(self.identities[s].key for s in approved),
            'excluded_source_keys':sorted(self.identities[s].key for s in excluded)}
        self.params=dict(controller=fixture['controller'],controller_sha=fixture['legacy_blob'],
            main_sha=fixture['reviewed_main'],sources=self.sources,artifacts=[],now=NOW)

    def migrate(self):return prepare_migration(**self.params,post_freeze_boundary=self.boundary)

    def test_real_data_boundary_is_complete_and_explicit_and_preserves_all_alternatives(self):
        for day in ('2026-10-01','2026-10-02','2026-10-05','2026-10-08'):
            self.assertEqual(sum(p['date']==day for p in self.posts),2)
        with self.assertRaises(StateInvalid):prepare_migration(**self.params)
        state=self.migrate()
        self.assertEqual(state['slots']['2026-10-09']['source_key'],self.nine.key)
        self.assertEqual(state['slots']['2026-10-04']['source_key'],self.identities['jealousy-in-relationships'].key)
        self.assertIsNone(self.params['controller']['article']['slug'])
        for key in self.boundary['excluded_source_keys']:
            evidence=[q for q in state['quarantine'] if q.get('failure_class')=='REVIEWED_MIGRATION_SOURCE_EXCLUDED'
                      and SourceIdentity(q['target']['slot'],q['target']['slug'],q['target']['content_sha256']).key==key]
            self.assertEqual(len(evidence),1)
            self.assertEqual(len(evidence[0]['candidate_source_keys']),2)
        self.assertFalse(any(s['complete'] for s in state['slots'].values()))
        self.assertFalse(any(row['receipts'] for row in state['items'].values()))

    def test_incomplete_hidden_nonexistent_and_two_owner_boundaries_refuse(self):
        variants=[]
        missing=copy.deepcopy(self.boundary); missing['excluded_source_keys'].pop(); variants.append(missing)
        double=copy.deepcopy(self.boundary); key=double['excluded_source_keys'].pop()
        double['adopted_source_keys']=sorted([*double['adopted_source_keys'],key]); variants.append(double)
        absent=copy.deepcopy(self.boundary); absent['excluded_source_keys']=sorted([*absent['excluded_source_keys'],'source:missing'])
        variants.append(absent)
        frozen=copy.deepcopy(self.boundary); frozen['adopted_source_keys'].remove(self.identities['jealousy-in-relationships'].key)
        variants.append(frozen)
        for boundary in variants:
            with self.subTest(boundary=boundary),self.assertRaises(StateInvalid):
                prepare_migration(**self.params,post_freeze_boundary=boundary)

    def test_real_observer_blocked_history_cannot_starve_oct9_or_current_work(self):
        state=self.migrate(); old={day:state['slots'][day]['source_key'] for day in ('2026-10-01','2026-10-02')}
        visits=[]
        for index in range(12):
            now=f'2026-10-10T10:{index:02}:00+03:00'
            reads=Reads(self.posts); reads.heads=[self.params['main_sha']]*2
            def article(identity,*_):
                result=publication(identity)['article']; result['evidence']['verified_at']=now
                result['evidence']['deploy_sha']=self.params['main_sha']; return result
            value=RepositoryObserver(reads,'owner/repo',clock=lambda:now,window=lambda _:True,
                inventory_reader=lambda **_:None,auditor=lambda *_:None,article_observer=article).read(state).value
            dates={p['source']['slot'] for p in value['publications']}; visits.extend(sorted(dates))
            for p in value['publications']:
                # Explicit independent absence fixture, not the unknown inventory
                # returned above. Public media ownership/completion is not inferred.
                p['media']={'overview':{'status':'absent'},'short':{'status':'absent'}}
            state=reconcile(state,Observation(value),now=now).state
        for day in old:
            self.assertEqual(state['slots'][day]['blocked'],'SOURCE_AMBIGUOUS')
            self.assertEqual(state['slots'][day]['source_key'],old[day])
            self.assertTrue(any(i['failure_class']=='SOURCE_AMBIGUOUS' and i['target']['slot']==day
                                for i in state['incidents'].values()))
            self.assertFalse(any(c['target']['slot']==day for c in state['commands'].values()))
        self.assertIn('2026-10-09',visits)
        commands=list(state['commands'].values())
        self.assertTrue(any(c['operation']=='create_article' and c['target']['slot']=='2026-10-10' for c in commands))
        self.assertFalse(any(c['operation']=='create_article' and c['target']['slot']=='2026-10-09' for c in commands))
        for kind in ('overview','short'):
            self.assertTrue(any(c['operation']=='publish' and c['target']==MediaIdentity(self.nine,kind).to_dict() for c in commands))
        # Reviewed choices survive duplicate dates without choosing by order.
        for slug in ('20-second-hug-relationship-stress','how-to-stop-repeating-arguments'):
            identity=self.identities[slug]
            self.assertEqual(state['slots'][identity.slot]['source_key'],identity.key)
            self.assertNotEqual(state['slots'][identity.slot].get('blocked'),'SOURCE_AMBIGUOUS')


if __name__=='__main__':unittest.main()
