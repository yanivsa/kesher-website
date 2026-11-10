import base64,hashlib,io,os,unittest
from datetime import date
from pathlib import Path
from unittest import mock
from PIL import Image
from tests.test_article_image_fallback_exhaustion import load_worker,ROOT

class ImageCatalogReplenishmentTests(unittest.TestCase):
    def run_case(self, *, duplicate=False, reject=False):
        worker=load_worker();post={'id':'generic-relationship','title':'תקשורת זוגית ושיחה רגועה','category':'זוגיות'}
        hashes=set();usage={};last={}
        for _,path in worker._candidate_pool(post,set()):
            p=ROOT/path
            if p.is_file():
                data=p.read_bytes();sha=hashlib.sha256(data).hexdigest();pixels='pixels:'+worker.core.image_pixel_sha256(data)
                hashes.update((sha,pixels));usage.update({sha:3,pixels:3});last.update({sha:date.today(),pixels:date.today()})
        buf=io.BytesIO()
        with Image.open(ROOT/'public/images/generated/services/premarital-first-year.webp') as img:img.convert('RGB').save(buf,format='PNG')
        fresh=buf.getvalue()
        if duplicate:hashes.add('pixels:'+worker.core.image_pixel_sha256(fresh))
        generation_calls=[]
        def response(url,body):
            if 'inline_data' in body['contents'][0]['parts'][0]:
                text='REJECT|תמונה אינה מתאימה' if reject else 'MATCH|זוג צעיר יושב יחד בשיחה רגועה בבית מואר באור טבעי'
                return {'candidates':[{'content':{'parts':[{'text':text}]}}]}
            generation_calls.append(body)
            parts=[] if 'IMAGE_CATALOG_EXHAUSTED' not in body['contents'][0]['parts'][0]['text'] else [{'inlineData':{'data':base64.b64encode(fresh).decode()}}]
            return {'candidates':[{'content':{'parts':parts}}]}
        with mock.patch.dict(os.environ,{'GOOGLE_API_KEY':'unit-test','GEMINI_API_KEY':'','PEXELS_API_KEY':'','PIXABAY_API_KEY':''}),mock.patch.object(worker.v3,'google_json',side_effect=response),mock.patch.object(worker,'collect_existing_image_usage',return_value=(hashes,usage,last)),mock.patch.object(worker,'collect_banned_paths',return_value=set()):
            candidate=worker.choose_candidate('o/r',post,'sha','unused')
        return worker,candidate,generation_calls,fresh
    def test_exhausted_catalog_automatically_obtains_validated_fresh_hero_within_three_generations(self):
        worker,candidate,calls,fresh=self.run_case()
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.provider,'Gemini');self.assertEqual(candidate.data,fresh)
        self.assertEqual(worker.core.validate_candidate(candidate.data)[:2],(1600,900))
        self.assertEqual(len(calls),3);self.assertIn('local-curated',candidate.attempts)
    def test_replenishment_duplicate_pixels_still_refuse(self):
        _,candidate,calls,_=self.run_case(duplicate=True)
        self.assertIsNone(candidate);self.assertLessEqual(len(calls),3)
    def test_replenishment_semantic_rejection_still_refuses(self):
        _,candidate,calls,_=self.run_case(reject=True)
        self.assertIsNone(candidate);self.assertLessEqual(len(calls),3)
