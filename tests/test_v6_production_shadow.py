import copy
import base64
import io
import json
import unittest
import zipfile
from scripts.kesher_daily_pipeline import source_metadata
from scripts.kesher_runtime.verification import publication_metadata,YOUTUBE_CHANNEL_ID

POST=dict(id='example',title='טיפול זוגי ושיחה משותפת',date='2026-10-07',category='זוגיות',excerpt='איך לדבר יחד',content='<p>שיחה זוגית מאפשרת הקשבה וכבוד הדדי.</p>')

class ShadowTests(unittest.TestCase):
    def setUp(self):
        from scripts import kesher_v6_production_shadow as shadow
        self.shadow=shadow;self.source=source_metadata(POST)
        self.snapshot=dict(target_slug='example',target_content_sha256=self.source['content_sha256'],
                           post=POST,main_sha='a'*40,public_status=200,
                           public_url=self.source['canonical_url'],public_body='<link rel="canonical" href="'+self.source['canonical_url']+'"><h1>'+POST['title']+'</h1>'+POST['content'],
                           state={'source':self.source,'article':{'status':'running'},'long_video':{'status':'pending'}},
                           media_items=[],youtube_rows={},pr=None,check_runs=[],workflow_runs=[],timestamp='2026-10-07T00:00:00Z')
    def verdict(self,**changes):return self.shadow.reconcile_snapshot(**(self.snapshot|changes))
    def item(self,kind='short'):
        source=self.source;item=dict(id='immutable-item',type='article_short' if kind=='short' else 'video_overview',source=source,youtube_id='video123456',youtube_metadata=publication_metadata(source,kind),uploaded=True)
        row=dict(id=item['youtube_id'],snippet=item['youtube_metadata']|dict(channelId=YOUTUBE_CHANNEL_ID,defaultLanguage='he',defaultAudioLanguage='he'),status={'privacyStatus':'public'},processingDetails={'processingStatus':'succeeded'})
        return item,row
    def test_source_and_route_are_independently_verified(self):
        self.assertEqual(self.verdict()['article_public_state']['status'],'healthy')
        self.assertEqual(self.verdict(public_status=404)['article_public_state']['status'],'source_exists_not_deployed')
        self.assertEqual(self.verdict(post=None)['article_source_state']['status'],'missing')
        self.assertEqual(self.verdict(public_url='https://kesher.saharoni.com/')['article_public_state']['status'],'route_mismatch')
        self.assertNotEqual(self.verdict(public_body='<h1>'+POST['title']+'</h1>')['article_public_state']['status'],'healthy')
    def test_delivered_missing_and_public_state_behind(self):
        state=copy.deepcopy(self.snapshot['state']);state['article']['status']='delivered'
        self.assertIn('article_delivered_public_missing',self.verdict(state=state,public_status=404)['detected_drift'])
        r=self.verdict();self.assertIn('article_public_state_behind',r['detected_drift']);self.assertIn('upstream_complete_downstream_waiting',r['detected_drift'])
    def test_orphan_and_source_hash_conflict(self):
        r=self.verdict(state={'source':None})
        self.assertIn('orphaned_state',r['detected_drift'])
        self.assertEqual(self.verdict(target_content_sha256='f'*64)['article_source_state']['status'],'identity_mismatch')
    def test_exact_head_approval_gate(self):
        pr={'number':1083,'state':'open','draft':True,'head':{'sha':'b'*40},'target_matches':True}
        r=self.verdict(pr=pr,workflow_runs=[{'head_sha':'b'*40,'conclusion':'action_required'}])
        self.assertIn('blocked_pr_checks',r['detected_drift']);self.assertEqual(r['v6_recommended_decision'],'wait_for_maintainer')
        r=self.verdict(pr=pr,workflow_runs=[{'head_sha':'c'*40,'conclusion':'action_required'}])
        self.assertNotIn('blocked_pr_checks',r['detected_drift'])
    def test_wrong_pr_identity_cannot_hijack(self):
        self.assertIn('stale_pr',self.verdict(pr={'number':1,'target_matches':False})['detected_drift'])
    def test_closed_unmerged_pr_is_stale_not_an_approval_blocker(self):
        pr={'number':1083,'state':'closed','draft':False,'merged':False,'head':{'sha':'b'*40},'target_matches':True}
        r=self.verdict(pr=pr,workflow_runs=[{'head_sha':'b'*40,'conclusion':'action_required'}],
                       check_runs=[{'head_sha':'b'*40,'conclusion':'failure'}])
        self.assertIn('stale_pr',r['detected_drift'])
        self.assertNotIn('blocked_pr_checks',r['detected_drift'])
        self.assertEqual(r['v6_recommended_decision'],'reconcile_authoritative_state')
        self.assertEqual(r['github_pr_state']['check_conclusions'],['action_required','failure'])
        self.assertFalse(r['production_state_written'])
        self.assertFalse(r['production_dispatch_enabled'])
    def test_merged_pr_historical_failure_does_not_block_current_delivery(self):
        state=copy.deepcopy(self.snapshot['state']);state['article']['status']='delivered'
        pr={'number':1083,'state':'closed','draft':False,'merged':True,'head':{'sha':'b'*40},'target_matches':True}
        r=self.verdict(state=state,pr=pr,workflow_runs=[{'head_sha':'b'*40,'conclusion':'failure'}])
        self.assertNotIn('stale_pr',r['detected_drift'])
        self.assertNotIn('blocked_pr_checks',r['detected_drift'])
        self.assertEqual(r['v6_recommended_decision'],'reconcile_authoritative_state')
    def test_media_exact_identity_metadata_privacy_and_geometry(self):
        item,row=self.item();r=self.verdict(media_items=[item],youtube_rows={item['youtube_id']:row})
        self.assertEqual(r['short_state']['status'],'public_geometry_unproven')
        row['fileDetails']={'videoStreams':[{'widthPixels':1080,'heightPixels':1920}]}
        self.assertEqual(self.verdict(media_items=[item],youtube_rows={item['youtube_id']:row})['short_state']['status'],'public_metadata_verified')
        row['status']['privacyStatus']='unlisted'
        self.assertEqual(self.verdict(media_items=[item],youtube_rows={item['youtube_id']:row})['short_state']['status'],'unlisted')
    def test_wrong_media_source_and_duplicate_ids_fail_closed(self):
        item,row=self.item();item['source']=self.source|{'content_sha256':'wrong'}
        self.assertEqual(self.verdict(media_items=[item],youtube_rows={item['youtube_id']:row})['short_state']['status'],'identity_unproven')
        item,row=self.item();other=copy.deepcopy(item);other['youtube_id']='differentID'
        self.assertEqual(self.verdict(media_items=[item,other])['short_state']['status'],'conflicting_exact_receipts')
    def test_wrong_remote_metadata_not_public_completion(self):
        item,row=self.item();row['snippet']['title']='wrong'
        self.assertEqual(self.verdict(media_items=[item],youtube_rows={item['youtube_id']:row})['short_state']['status'],'metadata_mismatch')
    def test_observation_does_not_modify_input_state(self):
        before=json.dumps(self.snapshot,sort_keys=True);r=self.verdict()
        self.assertEqual(json.dumps(self.snapshot,sort_keys=True),before)
        self.assertFalse(r['production_state_written']);self.assertFalse(r['production_dispatch_enabled'])
    def test_client_refuses_mutations_and_credential_hosts(self):
        calls=[]
        client=self.shadow.ReadOnlyClient('yanivsa/kesher-website',transport=lambda request: calls.append(request))
        for method in ('POST','PUT','PATCH','DELETE'):
            with self.assertRaises(ValueError):client.request(method,'https://api.github.com/repos/yanivsa/kesher-website/actions/workflows/1/dispatches')
        with self.assertRaises(ValueError):client.request('GET','https://api.github.com/repos/other/repo/contents/x')
        self.assertEqual(calls,[])
    def test_summary_and_recommendation_comparison(self):
        state=copy.deepcopy(self.snapshot['state']);state['last_action']='reconcile_authoritative_state'
        r=self.verdict(state=state);self.assertTrue(r['agreement'])
        self.assertIn('NO production dispatch or state writes',self.shadow.summary(r))

    def test_delivered_receipt_not_returned_by_public_lookup_is_drift(self):
        item,row=self.item();state=copy.deepcopy(self.snapshot['state']);state['short']={'status':'delivered'}
        r=self.verdict(state=state,media_items=[item],youtube_rows={'_lookup_complete':True})
        self.assertIn('short_delivered_public_missing',r['detected_drift'])

    def test_complete_observer_reads_exact_archived_receipt_only_with_get(self):
        calls=[];item,row=self.item();row['fileDetails']={'videoStreams':[{'widthPixels':1080,'heightPixels':1920}]}
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as archive:archive.writestr('state.json',json.dumps({'items':[item]}))
        def contents(value):return {'encoding':'base64','content':base64.b64encode(json.dumps(value).encode()).decode()}
        api='https://api.github.com/repos/yanivsa/kesher-website'
        def transport(request):
            calls.append(request)
            url=request.full_url
            if '/commits/main' in url:payload={'sha':'a'*40}
            elif '/contents/src/data/posts.json' in url:payload=contents([POST])
            elif '/contents/src/data/postsRecent.json' in url:payload=contents([])
            elif '/contents/.kesher-controller/' in url:payload=contents(self.snapshot['state'])
            elif '/actions/artifacts?name=kesher-short' in url:payload={'total_count':1,'artifacts':[{'id':5,'expired':False}]}
            elif '/actions/artifacts?name=' in url:payload={'total_count':0,'artifacts':[]}
            elif url==api+'/actions/artifacts/5/zip':return 200,stream.getvalue(),url
            elif '/youtube/v3/videos?' in url:payload={'items':[row]}
            elif url==self.source['canonical_url']:return 200,self.snapshot['public_body'].encode(),url
            else:self.fail('Unexpected read '+url)
            return 200,json.dumps(payload).encode(),url
        client=self.shadow.ReadOnlyClient('yanivsa/kesher-website',youtube_token='test-owner-token',transport=transport)
        r=self.shadow.observe(client,slug='example',content_sha256=self.source['content_sha256'])
        self.assertEqual(r['short_state']['status'],'public_metadata_verified')
        self.assertEqual(r['short_state']['id'],item['youtube_id'])
        self.assertEqual({c.get_method() for c in calls},{'GET'})
        self.assertNotIn('test-owner-token',json.dumps(r))

    def test_large_catalog_reads_exact_git_blob(self):
        calls=[]
        def transport(request):
            calls.append(request.full_url)
            payload={'encoding':'none','sha':'b'*40} if '/contents/' in request.full_url else {'encoding':'base64','content':base64.b64encode(json.dumps([POST]).encode()).decode()}
            return 200,json.dumps(payload).encode(),request.full_url
        client=self.shadow.ReadOnlyClient('yanivsa/kesher-website',transport=transport)
        self.assertEqual(client.contents('src/data/posts.json','a'*40),[POST])
        self.assertTrue(calls[-1].endswith('/git/blobs/'+'b'*40))

    def test_public_metadata_does_not_certify_producer_lineage_or_forged_source(self):
        item,row=self.item();row['fileDetails']={'videoStreams':[{'widthPixels':1080,'heightPixels':1920}]}
        r=self.verdict(media_items=[item],youtube_rows={item['youtube_id']:row})
        self.assertFalse(r['public_completion_inferred'])
        self.assertFalse(r['short_state']['producer_lineage_proven'])
        item['source']=item['source']|{'title':'כותרת מקור מזויפת','short_title':'כותרת מקור מזויפת'}
        item['youtube_metadata']=publication_metadata(item['source'],'short')
        row['snippet'].update(item['youtube_metadata'])
        r=self.verdict(media_items=[item],youtube_rows={item['youtube_id']:row})
        self.assertEqual(r['short_state']['status'],'metadata_mismatch')
