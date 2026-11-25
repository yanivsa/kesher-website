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
        daily = dict(run(), event='workflow_dispatch', display_title='Kesher Publish (daily) - '+SLOT, conclusion='cancelled')
        data = r.unstarted_receipt(daily, {'total_count':0, 'jobs':[]}, lambda _:None)
        self.assertEqual(r.retry_identity(data,daily,lambda _:daily)['action'],'daily')
        jobs={'total_count':1,'jobs':[{'steps':[{'name':'Execute Kesher Cloud Publisher','conclusion':'cancelled'}]}]}
        self.assertIsNone(r.unstarted_receipt(daily,jobs,lambda _:None))

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

if __name__=='__main__':
    unittest.main()
