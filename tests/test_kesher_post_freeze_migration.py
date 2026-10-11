"""Oct-4 legacy freeze, Oct-9 exact main publication, Oct-10 cutover."""
import copy
import json
from pathlib import Path
import unittest

from scripts.kesher_daily_pipeline import source_metadata
from scripts.kesher_runtime.controller import Observation, reconcile
from scripts.kesher_runtime.identity import MediaIdentity, SourceIdentity
from scripts.kesher_runtime.migration import prepare_migration
from scripts.kesher_runtime.observe import RepositoryObserver
from scripts.kesher_runtime.state import StateInvalid
from tests.test_kesher_autonomous_controller import publication
from tests.test_kesher_canonical_state import CODE
from tests.test_kesher_observe import Reads

ROOT = Path(__file__).resolve().parents[1]
NOW = '2026-10-10T10:00:00+03:00'


class PostFreezeMigrationTests(unittest.TestCase):
    def setUp(self):
        self.post = next(post for post in json.loads((ROOT/'src/data/posts.json').read_text())
                         if post['slug']=='how-to-repair-after-couple-fight')
        self.assertEqual(self.post['date'],'2026-10-09')
        self.source = source_metadata(self.post)
        self.identity = SourceIdentity('2026-10-09',self.source['slug'],self.source['content_sha256'])
        self.old = copy.deepcopy(self.source); self.old.update(date='2025-01-01',slug='unrequested-history')
        self.params = dict(controller={'schema_version':5,'cycle':'2026-10-04',
                'status':'article_image_running','backlog':[]},controller_sha='a'*40,main_sha=CODE,
                sources=[self.source,self.old],artifacts=[],now=NOW)
        self.boundary = {'frozen_cycle':'2026-10-04','cutover_slot':'2026-10-10',
                         'adopted_source_keys':[self.identity.key],'excluded_source_keys':[]}

    def migrated(self):
        return prepare_migration(**self.params,post_freeze_boundary=self.boundary)

    def test_unreviewed_post_freeze_publication_is_a_cutover_no_go(self):
        with self.assertRaisesRegex(StateInvalid,'POST_FREEZE_REVIEW_REQUIRED'):
            prepare_migration(**self.params)

    def test_reviewed_exact_oct9_survives_without_receipts_or_historical_expansion(self):
        state = self.migrated()
        self.assertEqual(state['slots']['2026-10-09']['source_key'],self.identity.key)
        self.assertNotIn('2025-01-01',state['slots'])
        self.assertEqual(state['sources'][self.identity.key]['identity'],self.identity.to_dict())
        self.assertEqual(state['sources'][self.identity.key]['article'],{})
        self.assertFalse(state['slots']['2026-10-09']['complete'])
        self.assertEqual(state['commands'],{})
        for kind in ('overview','short'):
            row = state['items'][MediaIdentity(self.identity,kind).key]
            self.assertIsNone(row['phase']); self.assertEqual(row['receipts'],{})

    def test_boundary_cannot_omit_replace_or_expand_exact_post_freeze_sources(self):
        for change in ({'adopted_source_keys':[]},{'adopted_source_keys':['other']},
                       {'frozen_cycle':'2026-10-03'},{'cutover_slot':'2026-10-11'}):
            with self.subTest(change=change),self.assertRaises(StateInvalid):
                prepare_migration(**self.params,post_freeze_boundary=self.boundary|change)

    def test_ambiguous_two_articles_in_one_catchup_slot_refuse(self):
        other=copy.deepcopy(self.source); other['slug']='other-oct9'
        self.params['sources'].append(other)
        boundary=self.boundary|{'adopted_source_keys':sorted([self.identity.key,
            SourceIdentity('2026-10-09','other-oct9',other['content_sha256']).key])}
        with self.assertRaises(StateInvalid):prepare_migration(**self.params,post_freeze_boundary=boundary)

    def test_exact_existing_cutover_day_article_is_also_bound_not_lost_after_midnight(self):
        source=copy.deepcopy(self.source); source.update(date='2026-10-10',slug='exact-current-main-publication')
        self.params['sources'].append(source)
        identity=SourceIdentity(source['date'],source['slug'],source['content_sha256'])
        boundary=self.boundary|{'adopted_source_keys':sorted([self.identity.key,identity.key])}
        state=prepare_migration(**self.params,post_freeze_boundary=boundary)
        self.assertEqual(state['slots']['2026-10-10']['source_key'],identity.key)
        self.assertEqual(state['sources'][identity.key]['article'],{})
        self.assertEqual(state['commands'],{})

    def test_incomplete_freeze_day_requires_explicit_exact_adoption(self):
        post=next(p for p in json.loads((ROOT/'src/data/posts.json').read_text())
                  if p['id']=='jealousy-in-relationships')
        source=source_metadata(post); self.params['sources'].append(source)
        self.params['controller']['article']={'slug':None,'published_date':None}
        identity=SourceIdentity(source['date'],source['slug'],source['content_sha256'])
        self.assertEqual(identity.slot,'2026-10-04')
        with self.assertRaises(StateInvalid): prepare_migration(**self.params)
        with self.assertRaises(StateInvalid): self.migrated()
        boundary=self.boundary|{'adopted_source_keys':sorted([self.identity.key,identity.key])}
        state=prepare_migration(**self.params,post_freeze_boundary=boundary)
        self.assertEqual(state['slots'][identity.slot]['source_key'],identity.key)
        self.assertEqual(state['sources'][identity.key]['article'],{})
        self.assertEqual(state['commands'],{})

    def test_explicitly_excluded_unique_source_never_acquires_ownership_on_observation(self):
        boundary=self.boundary|{'adopted_source_keys':[],'excluded_source_keys':[self.identity.key]}
        state=prepare_migration(**self.params,post_freeze_boundary=boundary)
        value=self.observe(state)
        # An excluded source is evidence, not initial observer backlog. Even an
        # unsolicited exact observation must not silently undo reviewed exclusion.
        entry=publication(self.identity); entry['article']['evidence']['verified_at']=NOW
        observed=value.value; observed['publications']=[entry]
        result=reconcile(state,Observation(observed),now=NOW).state
        self.assertIsNone(result['slots'][self.identity.slot].get('source_key'))
        self.assertEqual(result['slots'][self.identity.slot]['blocked'],'SOURCE_AMBIGUOUS')
        self.assertFalse(any(c['target']['slot']==self.identity.slot for c in result['commands'].values()))

    def test_unknown_same_day_alternative_cannot_replace_reviewed_owner(self):
        state=self.migrated(); value=self.observe(state).value
        other=SourceIdentity(self.identity.slot,'unreviewed-alternative','d'*64)
        entry=publication(other); entry['article']['evidence']['verified_at']=NOW
        value['publications'].append(entry)
        result=reconcile(state,Observation(value),now=NOW).state
        self.assertEqual(result['slots'][self.identity.slot]['source_key'],self.identity.key)
        self.assertEqual(result['slots'][self.identity.slot]['blocked'],'SOURCE_AMBIGUOUS')
        self.assertFalse(any(c['target']['slot']==self.identity.slot for c in result['commands'].values()))

    def test_excluded_historical_source_cannot_be_recreated_through_article_pr_lane(self):
        boundary=self.boundary|{'adopted_source_keys':[],'excluded_source_keys':[self.identity.key]}
        state=prepare_migration(**self.params,post_freeze_boundary=boundary)
        value=self.observe(state).value
        value['article_prs']=[{'slot':self.identity.slot,'head_sha':'d'*40,'number':1049,'status':'ready_to_merge'}]
        for _ in range(2):state=reconcile(state,Observation(value),now=NOW).state
        self.assertIsNone(state['slots'][self.identity.slot].get('source_key'))
        self.assertEqual(state['slots'][self.identity.slot]['blocked'],'SOURCE_AMBIGUOUS')
        self.assertFalse(any(c['target']['slot']==self.identity.slot for c in state['commands'].values()))

    def test_initially_empty_cutover_day_can_create_then_adopt_its_normal_main_publication(self):
        state=self.migrated(); value=self.observe(state).value
        first=reconcile(state,Observation(value),now=NOW)
        self.assertEqual(first.state['commands'][first.command_id]['operation'],'create_article')
        current=SourceIdentity('2026-10-10','normal-canonical-current-day','d'*64)
        entry=publication(current); entry['article']['evidence']['verified_at']=NOW
        value['publications'].append(entry)
        state=reconcile(first.state,Observation(value),now=NOW).state
        self.assertEqual(state['slots'][current.slot]['source_key'],current.key)
        self.assertNotIn('blocked',state['slots'][current.slot])
        self.assertFalse(any(c['operation']=='create_article' and c['target']['slot']==current.slot
                             and c['ordinal']>1 for c in state['commands'].values()))
        tomorrow='2026-10-11T10:00:00+03:00'
        value.update(current_slot='2026-10-11',observed_at=tomorrow)
        for p in value['publications']:p['article']['evidence']['verified_at']=tomorrow
        state=reconcile(state,Observation(value),now=tomorrow).state
        self.assertEqual(state['slots'][current.slot]['source_key'],current.key)
        self.assertNotIn('blocked',state['slots'][current.slot])

    def test_actual_next_day_observer_discovers_publication_from_persisted_prior_day_article_intent(self):
        state=reconcile(self.migrated(),self.observe(self.migrated()),now=NOW).state
        self.assertIsNone(state['slots']['2026-10-10'].get('source_key'))
        current=dict(self.post,id='normal-canonical-current-day',slug='normal-canonical-current-day',date='2026-10-10')
        source=source_metadata(current)
        identity=SourceIdentity(source['date'],source['slug'],source['content_sha256'])
        tomorrow='2026-10-11T10:00:00+03:00'
        visits=[]
        for _ in range(3):
            reader=Reads([self.post,current]); reader.heads=[CODE,CODE]
            value=RepositoryObserver(reader,'owner/repo',clock=lambda:tomorrow,window=lambda _:False,
                inventory_reader=lambda **_:None,auditor=lambda *_:None,
                article_observer=lambda *_:{'status':'unknown'}).read(state)
            visits.extend(p['source']['slot'] for p in value.value['publications'])
            state=reconcile(state,value,now=tomorrow).state
        self.assertIn('2026-10-10',visits)
        self.assertEqual(state['slots']['2026-10-10']['source_key'],identity.key)
        self.assertNotIn('blocked',state['slots']['2026-10-10'])
        self.assertEqual(sum(c['operation']=='create_article' and c['target']['slot']=='2026-10-10'
                             for c in state['commands'].values()),1)

    def observe(self,state):
        verdict = publication(self.identity)['article']
        verdict['evidence']['verified_at']=NOW
        reader=Reads([self.post]); reader.heads=[CODE,CODE]
        return RepositoryObserver(reader,'owner/repo',clock=lambda:NOW,window=lambda now:True,
            inventory_reader=lambda **kwargs:None,auditor=lambda *args:None,
            article_observer=lambda *args:verdict).read(state)

    def test_actual_repository_observer_sees_oct9_and_scheduler_alternates_current_and_backlog(self):
        state=self.migrated()
        value=self.observe(state).value
        self.assertEqual(value['current_slot'],'2026-10-10')
        self.assertEqual([p['source'] for p in value['publications']],[self.identity.to_dict()])
        # A separately observed empty public inventory proves absence. Missing
        # inventory itself is unknown and must never permit provider generation.
        for media in value['publications'][0]['media'].values():self.assertEqual(media['status'],'unknown')
        value['publications'][0]['media']={'overview':{'status':'absent'},'short':{'status':'absent'}}
        first=reconcile(state,Observation(value),now=NOW)
        command=first.state['commands'][first.command_id]
        self.assertEqual(command['operation'],'create_article')
        self.assertEqual(command['target']['slot'],'2026-10-10')
        value['state_revision']=first.state['revision']
        second=reconcile(first.state,Observation(value),now=NOW)
        command=second.state['commands'][second.command_id]
        self.assertEqual(command['operation'],'publish')
        self.assertEqual(command['target'],MediaIdentity(self.identity,'overview').to_dict())
        third=reconcile(second.state,Observation(value),now=NOW)
        command=third.state['commands'][third.command_id]
        self.assertEqual(command['operation'],'publish')
        self.assertEqual(command['target'],MediaIdentity(self.identity,'short').to_dict())
        self.assertFalse(any(c['operation']=='create_article' and c['target']['slot']=='2026-10-09'
                             for c in third.state['commands'].values()))

    def test_missing_public_verification_does_not_start_catchup_media(self):
        state=self.migrated(); value=self.observe(state).value
        value['publications'][0]['article']={'status':'unknown'}
        value['publications'][0]['media']={'overview':{'status':'absent'},'short':{'status':'absent'}}
        decision=reconcile(state,Observation(value),now=NOW)
        self.assertFalse(any(c['operation']=='publish' for c in decision.state['commands'].values()))

    def test_exact_existing_media_is_adopted_only_by_normal_public_observation(self):
        state=self.migrated()
        self.assertFalse(state['slots']['2026-10-09']['complete'])
        value=self.observe(state).value
        verified=publication(self.identity,overview='verified',short='verified')
        for row in verified['media'].values(): row['evidence']['verified_at']=NOW
        value['publications'][0]['media']=verified['media']
        result=reconcile(state,Observation(value),now=NOW)
        self.assertTrue(result.state['slots']['2026-10-09']['complete'])
        self.assertFalse(any(c['operation']=='publish' for c in result.state['commands'].values()))

    def test_actual_public_inventory_without_archived_lineage_cannot_certify_or_duplicate_oct9_media(self):
        from scripts.kesher_runtime.media_observer import observe_media
        from scripts.kesher_runtime.verification import YOUTUBE_CHANNEL_ID
        from unittest.mock import Mock
        state=self.migrated()
        inventory={'observed_at':NOW,'channel_id':YOUTUBE_CHANNEL_ID,'complete':True,'videos':[
            {'id':'existing-unbound-video','snippet':{'description':self.source['canonical_url']}}]}
        audit=Mock(side_effect=AssertionError('No exact archive/provider ownership exists'))
        entry=publication(self.identity); entry['article']['evidence']['verified_at']=NOW
        for kind in ('overview','short'):
            entry['media'][kind]=observe_media(state,MediaIdentity(self.identity,kind),self.source,
                inventory=inventory,now=NOW,audit=audit)
            self.assertEqual(entry['media'][kind]['failure_class'],'DUPLICATE_UPLOAD')
        value=self.observe(state).value; value['publications']=[entry]
        result=reconcile(state,Observation(value),now=NOW).state
        self.assertFalse(result['slots'][self.identity.slot]['complete'])
        self.assertFalse(any(c['operation']=='publish' for c in result['commands'].values()))
        audit.assert_not_called()

    def test_catchup_binding_preserves_legacy_retry_budget_and_closed_quarantine_floor(self):
        from tests.test_kesher_runtime_migration import inputs
        from scripts.kesher_runtime.identity import digest
        _,params=inputs()
        params['controller']['cycle']='2026-10-04'; params['now']=NOW
        floor=prepare_migration(**params,post_freeze_boundary=self.boundary|{'adopted_source_keys':[]})
        params['sources'].append(self.source)
        state=prepare_migration(**params,post_freeze_boundary=self.boundary,retained_evidence=floor)
        self.assertEqual(state['migration']['legacy_stage_budgets'],floor['migration']['legacy_stage_budgets'])
        self.assertEqual(state['migration']['legacy_stage_claims'],floor['migration']['legacy_stage_claims'])
        self.assertTrue({digest(q) for q in floor['quarantine']} <= {digest(q) for q in state['quarantine']})
        self.assertEqual(state['slots']['2026-10-09']['source_key'],self.identity.key)


if __name__ == '__main__': unittest.main()
