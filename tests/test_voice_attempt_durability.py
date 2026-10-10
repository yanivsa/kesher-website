import copy,json,os,tempfile,unittest
from pathlib import Path
from unittest import mock
from scripts import kesher_daily_pipeline as p, kesher_video_reconcile as r

class VoiceAttemptDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'state.json'
        patch=mock.patch.object(p,'STATE_FILE',self.path);patch.start();self.addCleanup(patch.stop)
        self.env_file=Path(self.tmp.name)/'env.tmp'
        env_patch=mock.patch.dict(os.environ,{'GITHUB_ENV':str(self.env_file)})
        env_patch.start();self.addCleanup(env_patch.stop)
        self.source={'id':'one','slug':'one','content_sha256':'a'*64,'youtube_metadata':{}}
    def item(self,attempt=1):
        item=p.new_item(self.source);item.update(id=f'item-{attempt}',fresh_generation_attempt=attempt,status='rejected',technical_verified=False)
        return item
    def test_new_item_persists_one_and_ignores_global_attempt_override(self):
        with mock.patch.dict(os.environ,{'KESHER_FRESH_GENERATION_ATTEMPT':'3'}):item=p.new_item(self.source)
        self.assertEqual(item.get('fresh_generation_attempt'),1)
    def test_pitch_rejects_first_two_and_accepts_final_only(self):
        with mock.patch.object(p,'estimate_voice_pitch',return_value=125.0):
            for attempt,want in [(1,False),(2,False),(3,True)]:
                with self.subTest(attempt=attempt):self.assertEqual(p.validate_female_voice(Path('fake.mp4'),self.item(attempt))[0],want)
    def test_retry_continues_recorded_attempt_even_if_retry_counter_is_stale(self):
        old=self.item(2);old['technical_retry_count']=0;state={'version':1,'items':[old]}
        with mock.patch.object(r,'current_source_snapshot',return_value=self.source):new=r.retry_technical_rejection(state,old)
        self.assertEqual(new['fresh_generation_attempt'],3)
        p.save_state(state);reloaded=p.load_state()
        self.assertEqual(reloaded['items'][-1]['fresh_generation_attempt'],3)
        self.assertEqual(reloaded['items'][-1]['retry_of'],'item-2')
    def test_targeted_long_voice_rejection_creates_exact_second_attempt(self):
        old=self.item(1);old.update(type='video_overview',failure_signature='wrong_narrator_gender')
        state={'version':1,'items':[old]};p.save_state(state)
        with mock.patch.dict(os.environ,{
                'KESHER_MEDIA_MODE':'video_overview','TARGET_SLUG':'one',
                'TARGET_CONTENT_SHA256':'a'*64,'TARGET_ITEM_ID':'item-1'}), \
                mock.patch.object(r,'current_source_snapshot',return_value=self.source):
            self.assertEqual(r.prepare_generation('one'),0)
        rows=p.load_state()['items']
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['status'],'superseded')
        self.assertEqual(rows[1]['fresh_generation_attempt'],2)
        self.assertEqual(rows[1]['retry_of'],'item-1')
        self.assertEqual(rows[1]['source']['content_sha256'],'a'*64)
    def test_stale_write_cannot_reset_attempt_or_drop_retry_receipt(self):
        old=self.item(3);p.save_state({'version':1,'items':[old]})
        stale=copy.deepcopy(old);stale['fresh_generation_attempt']=1
        with self.assertRaisesRegex(p.PipelineError,'ATTEMPT_REGRESSION'):p.save_state({'version':1,'items':[stale]})
        with self.assertRaisesRegex(p.PipelineError,'ATTEMPT_REGRESSION'):p.save_state({'version':1,'items':[]})
        self.assertEqual(p.load_state()['items'][0]['fresh_generation_attempt'],3)
    def test_final_voice_rejection_never_creates_fourth_generation(self):
        old=self.item(3);old.update(failure_signature='wrong_narrator_gender',raw_mp4='original.mp4',task_id='task3')
        state={'version':1,'items':[old]}
        with mock.patch.object(r,'current_source_snapshot',return_value=self.source):new=r.retry_technical_rejection(state,old)
        self.assertIs(new,old);self.assertEqual(len(state['items']),1)
        self.assertEqual(old.get('status'),'downloaded');self.assertEqual(old['task_id'],'task3')
    def test_unrelated_source_starts_one_without_counter_leakage(self):
        p.save_state({'version':1,'items':[self.item(3)]})
        other=p.new_item({**self.source,'slug':'two','id':'two','content_sha256':'b'*64})
        self.assertEqual(other.get('fresh_generation_attempt'),1)
