"""A blocked or completed historical slot cannot monopolize observation."""
import unittest

from scripts.kesher_daily_pipeline import source_metadata
from scripts.kesher_runtime.controller import Observation,reconcile
from scripts.kesher_runtime.identity import SourceIdentity
from scripts.kesher_runtime.migration import prepare_migration
from scripts.kesher_runtime.observe import RepositoryObserver
from tests.test_kesher_observe import POST,Reads
from tests.test_kesher_canonical_state import CODE

NOW='2026-10-10T10:00:00+03:00'


class BacklogRotationTests(unittest.TestCase):
    def setUp(self):
        self.posts=[dict(POST,id=slug,date=day) for day,slug in (
            ('2026-10-01','first'),('2026-10-01','alternative'),
            ('2026-10-02','second'),('2026-10-09','later'))]
        self.sources=[source_metadata(p) for p in self.posts]
        key=SourceIdentity('2026-10-09','later',self.sources[-1]['content_sha256']).key
        self.state=prepare_migration(controller={'schema_version':5,'cycle':'2026-10-04','article':{},
            'backlog':[{'cycle':day,'article':{'slug':slug,'published_date':day}}
                       for day,slug in (('2026-10-01','first'),('2026-10-02','second'))]},
            controller_sha='a'*40,main_sha=CODE,sources=self.sources,artifacts=[],now=NOW,
            post_freeze_boundary={'frozen_cycle':'2026-10-04','cutover_slot':'2026-10-10',
                                 'adopted_source_keys':[key],'excluded_source_keys':[]})

    def tick(self,state):
        reader=Reads(self.posts)
        observed=RepositoryObserver(reader,'owner/repo',clock=lambda:NOW,window=lambda _:True,
            inventory_reader=lambda **_:None,auditor=lambda *_:None,
            article_observer=lambda *_:{'status':'unknown'}).read(state)
        result=reconcile(state,observed,now=NOW)
        return result.state,sorted({p['source']['slot'] for p in observed.value['publications']})

    def test_ambiguous_cursor_advances_even_with_equal_clock_values_and_preserves_incident(self):
        key=self.state['slots']['2026-10-01']['source_key']
        visited=[]
        for _ in range(4):
            self.state,dates=self.tick(self.state); visited.extend(dates)
        self.assertEqual(visited,['2026-10-01','2026-10-02','2026-10-09','2026-10-01'])
        row=self.state['slots']['2026-10-01']
        self.assertEqual(row['blocked'],'SOURCE_AMBIGUOUS')
        self.assertEqual(row['source_key'],key)  # Retained evidence, no new owner.
        self.assertFalse(row['complete'])
        self.assertTrue(any(i['failure_class']=='SOURCE_AMBIGUOUS' for i in self.state['incidents'].values()))
        self.assertFalse(any(c['target']['slot']=='2026-10-01' for c in self.state['commands'].values()))

    def test_completed_backlog_is_not_polled_even_when_it_has_oldest_timestamp(self):
        self.state['slots']['2026-10-01'].update(complete=True,observed_at='')
        state,dates=self.tick(self.state)
        self.assertEqual(dates,['2026-10-02'])
        state['slots']['2026-10-02']['complete']=True
        _,dates=self.tick(state)
        self.assertEqual(dates,['2026-10-09'])

    def test_unrelated_historical_article_pr_cannot_reset_observation_cursor(self):
        self.state,dates=self.tick(self.state)
        self.assertEqual(dates,['2026-10-01'])
        reader=Reads(self.posts)
        value=RepositoryObserver(reader,'owner/repo',clock=lambda:NOW,window=lambda _:True,
            inventory_reader=lambda **_:None,auditor=lambda *_:None,
            article_observer=lambda *_:{'status':'unknown'}).read(self.state).value
        value['article_prs']=[{'slot':'2026-10-04','head_sha':'d'*40,'number':1045,'status':'ci_pending'}]
        state=reconcile(self.state,Observation(value),now=NOW).state
        self.assertEqual(state['scheduler']['last_observed_backlog_slot'],'2026-10-02')
        _,dates=self.tick(state)
        self.assertEqual(dates,['2026-10-09'])

    def test_disappeared_ambiguous_source_rotates_without_recreating_historical_article(self):
        self.state,_=self.tick(self.state)
        self.state['scheduler']['last_observed_backlog_slot']='2026-10-09'
        self.posts=self.posts[2:]
        self.state,dates=self.tick(self.state)
        self.assertEqual(dates,[])
        self.assertEqual(self.state['slots']['2026-10-01']['blocked'],'SOURCE_AMBIGUOUS')
        self.assertFalse(any(c['target']['slot']=='2026-10-01' for c in self.state['commands'].values()))
        _,dates=self.tick(self.state)
        self.assertEqual(dates,['2026-10-02'])

    def test_unrelated_pr_does_not_reopen_completed_unobserved_backlog(self):
        self.state['slots']['2026-10-01']['complete']=True
        reader=Reads(self.posts)
        value=RepositoryObserver(reader,'owner/repo',clock=lambda:NOW,window=lambda _:True,
            inventory_reader=lambda **_:None,auditor=lambda *_:None,
            article_observer=lambda *_:{'status':'unknown'}).read(self.state).value
        value['article_prs']=[{'slot':'2026-10-01','head_sha':'d'*40,'number':1001,'status':'ci_pending'}]
        state=reconcile(self.state,Observation(value),now=NOW).state
        self.assertTrue(state['slots']['2026-10-01']['complete'])
        self.assertFalse(any(i['target']['slot']=='2026-10-01' for i in state['incidents'].values()))

    def test_missing_source_with_duplicate_prs_advances_before_refusing_both_prs(self):
        self.posts=self.posts[2:]
        reader=Reads(self.posts)
        value=RepositoryObserver(reader,'owner/repo',clock=lambda:NOW,window=lambda _:True,
            inventory_reader=lambda **_:None,auditor=lambda *_:None,
            article_observer=lambda *_:{'status':'unknown'}).read(self.state).value
        self.assertEqual(value['missing_slots'],['2026-10-01'])
        value['article_prs']=[{'slot':'2026-10-01','head_sha':'d'*40,'number':n,'status':'ci_pending'}
                             for n in (1001,1002)]
        state=reconcile(self.state,Observation(value),now=NOW).state
        self.assertEqual(state['scheduler']['last_observed_backlog_slot'],'2026-10-01')
        self.assertEqual(state['slots']['2026-10-01']['blocked'],'DUPLICATE_PR')
        self.assertFalse(any(c['target']['slot']=='2026-10-01' for c in state['commands'].values()))
        _,dates=self.tick(state)
        self.assertEqual(dates,['2026-10-02'])

    def test_ambiguous_unbound_slot_never_acquires_an_owner_from_source_order(self):
        from scripts.kesher_runtime.state import new_state
        from tests.test_kesher_autonomous_controller import observed,publication
        identities=[SourceIdentity(p['date'],p['id'],s['content_sha256'])
                    for p,s in zip(self.posts[:2],self.sources[:2])]
        for order in (identities,list(reversed(identities))):
            value=observed(*(publication(s) for s in order),now=NOW,current_slot='2026-10-01')
            state=reconcile(new_state(),value,now=NOW).state
            self.assertIsNone(state['slots']['2026-10-01'].get('source_key'))
            self.assertEqual(state['slots']['2026-10-01']['blocked'],'SOURCE_AMBIGUOUS')
            self.assertEqual(state['commands'],{})


if __name__=='__main__':unittest.main()
