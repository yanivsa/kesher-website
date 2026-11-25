import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch, Mock
import tempfile, json, os
from pathlib import Path
from scripts import kesher_publish_recovery as r
from scripts import kesher_cloud_publisher as p

NOW = datetime(2026, 11, 25, 20, tzinfo=timezone.utc)
SLOT = '2026-11-25'
SHA = 'a'*64
SLUG = 'existing-article'

def run(id=10, **kw):
    return dict(id=id, path=r.WORKFLOW_PATH, head_branch='main', status='completed',
                event='issues', display_title='Kesher Publish from Issue #42: [Publish] Topic',
                conclusion='failure', updated_at='2026-11-25T19:00:00Z', **kw)

def receipt(**kw):
    return dict(dict(action='run_now', slot=SLOT, request_issue='42', request_root='10',
                     recovery_attempt=0, slug=SLUG, source_sha256=SHA, dry_run=False,
                     stage_only=False, status='error', contract_complete=False), **kw)

def complete(**kw):
    return receipt(**dict(dict(status='success', contract_complete=True,
                     article_url='https://kesher.saharoni.com/blog/'+SLUG,
                     long_video_url='https://www.youtube.com/watch?v=abcdefghijk',
                     short_video_url='https://www.youtube.com/shorts/lmnopqrstuv'), **kw))

class RecoveryTest(unittest.TestCase):
    def test_contract_requires_three_distinct_exact_links_and_identity(self):
        self.assertTrue(r.complete_receipt(complete(), issue='42'))
        for bad in ({'contract_complete':False}, {'short_video_url':None}, {'long_video_url':None},
                    {'article_url':'https://example.com/blog/'+SLUG}, {'dry_run':True},
                    {'stage_only':True}, {'request_issue':'43'}, {'source_sha256':''},
                    {'short_video_url':'https://www.youtube.com/shorts/abcdefghijk'}):
            self.assertFalse(r.complete_receipt(complete(**bad), issue='42'), bad)

    def test_failed_issue_recovery_exact_identity_and_bound(self):
        result = r.retry_identity(receipt(), run(), lambda _:run())
        self.assertEqual(result['target_slug'], SLUG)
        self.assertEqual(result['expected_source_sha'], SHA)
        self.assertEqual(result['issue_number'], '42')
        self.assertEqual(result['action'], 'resume')
        self.assertEqual(result['recovery_attempt'], '1')
        self.assertIsNone(r.retry_identity(receipt(recovery_attempt=3), run(), lambda _:run()))
        self.assertIsNone(r.retry_identity(receipt(request_issue='43'), run(), lambda _:run()))

    def test_planning_issue_preserves_original_topic(self):
        data = receipt(slug='', source_sha256='', request_payload={'topic_brief':'topic'})
        self.assertEqual(r.retry_identity(data, run(), lambda _:run())['topic_brief'], 'topic')
        self.assertIsNone(r.retry_identity(receipt(slug='', source_sha256=''), run(), lambda _:run()))

    def test_no_duplicate_retry_when_pending_or_issue_closed(self):
        pick = lambda runs, opened=True: r.choose_recovery(runs, lambda _:receipt(), lambda _:run(), lambda _:opened, today=date.fromisoformat(SLOT), now=NOW)
        self.assertEqual(pick([run()])[0],10)
        self.assertIsNone(pick([run(), {'status':'queued'}]))
        self.assertIsNone(pick([run()], False))

    def test_newest_receipt_prevents_old_failure_replay(self):
        newer = dict(run(), id=11, event='workflow_dispatch', display_title='Kesher Publish recovery #10', conclusion='success')
        data = complete(request_issue='', request_root='10', recovery_attempt=1)
        self.assertIsNone(r.choose_recovery([newer,run()], lambda v: data if v['id']==11 else receipt(), lambda _:run(), lambda _:True, today=date.fromisoformat(SLOT), now=NOW))

    def test_recover_cancelled_daily_before_any_mutation(self):
        daily = dict(run(), event='workflow_dispatch', display_title='Kesher Publish (daily) - '+SLOT, conclusion='cancelled', actor={'login':'github-actions[bot]'})
        data = r.unstarted_receipt(daily, {'total_count':0, 'jobs':[]}, lambda _:None)
        self.assertEqual(r.retry_identity(data,daily,lambda _:daily)['action'],'daily')
        jobs={'total_count':1,'jobs':[{'steps':[{'name':'Execute Kesher Cloud Publisher','conclusion':'cancelled'}]}]}
        self.assertIsNone(r.unstarted_receipt(daily,jobs,lambda _:None))

    def test_cancelled_manual_daily_cannot_be_replayed_as_live(self):
        daily = dict(run(), event='workflow_dispatch', display_title='Kesher Publish (daily) - '+SLOT, conclusion='cancelled', actor={'login':'owner'})
        self.assertIsNone(r.unstarted_receipt(daily, {'total_count':0, 'jobs':[]}, lambda _:None))

    def test_missing_receipt_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'missing.json'
            with patch.dict(os.environ, {'PUBLISH_OUTCOME':'success','GITHUB_RUN_ID':'10'}), patch('sys.argv',['recovery','report','--issue','42','--receipt',str(path)]), patch.object(r.subprocess,'run') as call:
                self.assertEqual(r.main(),1)
                self.assertEqual(call.call_args.args[0][:3],['gh','issue','comment'])

    def test_wrong_branch_artifact_rejected_before_read(self):
        client=Mock()
        with self.assertRaisesRegex(ValueError,'NOT_TRUSTED'):
            r.read_receipt(client, dict(run(),head_branch='feature'))
        client.get_run_artifact_zip.assert_not_called()

    def test_failure_never_closes_issue(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'result.json'
            path.write_text(json.dumps(complete(short_video_url=None)))
            with patch.dict(os.environ, {'PUBLISH_OUTCOME':'success','GITHUB_RUN_ID':'10'}), patch('sys.argv',['recovery','report','--issue','42','--receipt',str(path)]), patch.object(r.subprocess,'run') as call:
                self.assertEqual(r.main(),1)
                self.assertEqual(call.call_args.args[0][:3],['gh','issue','comment'])

    def test_checkpoint_survives_failure_and_incomplete_exit(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'result.json'
            def fail(*args, **kw):
                kw['checkpoint'](slug=SLUG,source_sha256=SHA,phase='published_article')
                raise RuntimeError('provider timeout')
            with patch('sys.argv',['publisher','run_now','--slot',SLOT,'--output-json',str(path)]), patch.dict(os.environ,{'GITHUB_RUN_ID':'10','KESHER_REQUEST_ISSUE':'42'}), patch.object(p,'handle_run_now',side_effect=fail):
                self.assertEqual(p.main(),1)
            data=json.loads(path.read_text())
            self.assertEqual(data['slug'],SLUG)
            self.assertEqual(data['source_sha256'],SHA)
            self.assertFalse(data['contract_complete'])
            self.assertEqual(data['request_root'],'10')

    def test_three_integrated_failure_recovery_cycles(self):
        import sys, io, zipfile
        from contextlib import ExitStack
        from scripts.kesher_daily_pipeline import source_metadata
        slot=SLOT; slug='controlled-recovery-fixture'
        post={'id':slug,'slug':slug,'title':'תקשורת במשפחה','date':slot,'category':'הדרכת הורים',
              'excerpt':'הקשבה ושיתוף פעולה בבית','content':'<p>תוכן בדיקה בעברית.</p>'}
        sha=source_metadata(post)['content_sha256']; long='abcdefghijk'; short='lmnopqrstuv'
        def artifact(items):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as z:
                z.writestr('state.json',json.dumps({'items':items}))
            return out.getvalue()
        src={'slug':slug,'content_sha256':sha}
        longstate=artifact([{'source':src,'id':'existing-item','status':'uploaded','youtube_id':long}])
        shortstate=artifact([{'source':src,'uploaded':True,'youtube_id':short}])
        def audit(complete):
            return {'complete':complete,'triads':[{'complete':complete,'slug':slug,'date':slot,
                    'expected_source_sha256':sha,'article':{'url':f'https://kesher.saharoni.com/blog/{slug}'},
                    'long_video':{'youtube_url':f'https://www.youtube.com/watch?v={long}'},
                    'short':{'youtube_url':f'https://www.youtube.com/shorts/{short}'}}]}
        for fault in ('long_auth','short_failure','deploy_failure'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
                root=Path(tmp); posts=root/'posts.json'; videos=root/'videos.json'; out=root/'result.json'
                posts.write_text(json.dumps([post])); videos.write_text('{}')
                client=Mock(); state={'long':False,'short':False,'deployed':False,'faulted':False}; dispatches=[]
                def dispatch(workflow, *a, **k):
                    dispatches.append(workflow)
                    return True
                def poll(workflow,*a,**k):
                    if workflow=='kesher-daily-video.yml':
                        if fault=='long_auth' and not state['faulted']:
                            state['faulted']=True; return {'conclusion':'failure','id':1}
                        state['long']=True; return {'conclusion':'success','id':2}
                    if workflow=='kesher-short-v4.yml':
                        if fault=='short_failure' and not state['faulted']:
                            state['faulted']=True; return {'conclusion':'failure','id':3}
                        state['short']=True; return {'conclusion':'success','id':4}
                    raise AssertionError(workflow)
                def latest(name):
                    return (longstate if state['long'] else None) if name=='kesher-video-controller-state' else (shortstate if state['short'] else None)
                def bind(s,long_id,short_id):
                    assert s==slug and long_id==long and short_id==short
                    videos.write_text(json.dumps({slug:{'youtubeId':long,'youtubeShortId':short}}))
                    posts.write_text(json.dumps([{**post,'youtubeVideoId':long,'youtubeShortId':short}]))
                def deploy(*a,**k):
                    if fault=='deploy_failure' and not state['faulted']:
                        state['faulted']=True; raise RuntimeError('simulated deploy timeout')
                    state['deployed']=True
                client.dispatch.side_effect=dispatch; client.poll_workflow.side_effect=poll
                client.get_latest_artifact_zip.side_effect=latest
                client.get_run_artifact_zip.side_effect=lambda i,n: longstate if 'video-controller' in n else shortstate
                for name,value in [('POSTS_FILE',posts),('ARTICLE_VIDEOS_FILE',videos),('GitHubActionsClient',Mock(return_value=client)),('run_supervisor_audit',Mock(side_effect=lambda *a,**k:audit(state['deployed']))),('verify_live_article',Mock(return_value=True)),('deploy_to_cloudflare',Mock(side_effect=deploy)),('update_article_videos',Mock(side_effect=bind))]:
                    stack.enter_context(patch.object(p,name,value))
                stack.enter_context(patch.object(p.subprocess,'run',return_value=Mock(returncode=0)))
                stack.enter_context(patch.dict(os.environ,{'GITHUB_TOKEN':'fake-no-network','GITHUB_RUN_ID':'10','KESHER_REQUEST_ROOT':'10','KESHER_REQUEST_ISSUE':'42','KESHER_RECOVERY_ATTEMPT':'0'}))
                args=['publisher','resume','--slot',slot,'--target-slug',slug,'--expected-source-sha',sha,'--output-json',str(out)]
                with patch.object(sys,'argv',[a for a in args if a not in ('--expected-source-sha',sha)]): assert p.main()==1
                failed=json.loads(out.read_text()); assert failed['contract_complete'] is False and failed['source_sha256']==sha
                rootrun={'id':10,'path':r.WORKFLOW_PATH,'head_branch':'main','status':'completed','event':'issues','display_title':'Kesher Publish from Issue #42: [Publish] test','conclusion':'failure','updated_at':'2026-11-25T19:00:00Z'}
                identity=r.retry_identity(failed,rootrun,lambda _:rootrun)
                assert identity and identity['target_slug']==slug and identity['expected_source_sha']==sha
                with patch.dict(os.environ,{'KESHER_RECOVERY_ATTEMPT':'1','GITHUB_RUN_ID':'11'}),patch.object(sys,'argv',args): assert p.main()==0
                receipt=json.loads(out.read_text()); assert r.complete_receipt(receipt,issue='42')
                before=dispatches[:]
                with patch.object(sys,'argv',args): assert p.main()==0
                assert dispatches==before
                assert dispatches.count('kesher-daily-video.yml')==(2 if fault=='long_auth' else 1)
                assert dispatches.count('kesher-short-v4.yml')==(2 if fault=='short_failure' else 1)
                self.assertTrue(state['deployed'])

if __name__=='__main__':
    unittest.main()
