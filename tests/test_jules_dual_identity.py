import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest import mock
from scripts import jules_video_reviewer as reviewer

class JulesDualIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.target={'id':'exact','type':'video_overview','fresh_generation_attempt':1,'status':'pending_review','source':{'slug':'one','content_sha256':'a'*64}}
        stale={**self.target,'id':'stale','source':{'slug':'two','content_sha256':'b'*64}}
        (self.root/'state.json').write_text(json.dumps({'version':1,'items':[stale,self.target]}))
    def select(self,slug,sha):
        with mock.patch.dict(os.environ,{'TARGET_ITEM_ID':'exact','TARGET_SLUG':slug,'TARGET_CONTENT_SHA256':sha,'TARGET_GENERATION_ATTEMPT':'1'}):
            return reviewer.load_pending(self.root)[1]
    def test_same_slug_wrong_sha_refuses(self):
        with self.assertRaises(reviewer.ReviewError):self.select('one','b'*64)
    def test_wrong_slug_same_sha_refuses(self):
        with self.assertRaises(reviewer.ReviewError):self.select('two','a'*64)
    def test_only_dual_key_exact_item_survives_stale_state(self):
        self.assertEqual(self.select('one','a'*64)['id'],'exact')
    def test_missing_content_identity_in_item_refuses(self):
        self.target['source'].pop('content_sha256');(self.root/'state.json').write_text(json.dumps({'version':1,'items':[self.target]}))
        with mock.patch.dict(os.environ,{'TARGET_SLUG':'','TARGET_CONTENT_SHA256':'','TARGET_ITEM_ID':'exact','TARGET_GENERATION_ATTEMPT':''}):
            with self.assertRaisesRegex(reviewer.ReviewError,'IDENTITY_REQUIRED'):reviewer.load_pending(self.root)
    def test_review_cli_requires_both_target_keys_before_external_call(self):
        path=Path(reviewer.__file__)
        env={**os.environ,'JULES_API_KEY':''}
        result=subprocess.run([sys.executable,'-B',str(path),'--state-dir',str(self.root),'--item-id','exact','--review-branch','evidence','--evidence-root','evidence'],capture_output=True,text=True,env=env)
        self.assertEqual(result.returncode,2);self.assertIn('--target-slug',result.stderr);self.assertIn('--target-content-sha256',result.stderr)
