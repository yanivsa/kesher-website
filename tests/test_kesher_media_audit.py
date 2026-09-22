import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image

from scripts.kesher_runtime.media_audit import audit_files, verify_lineage
from scripts.kesher_runtime.media_publication import MediaVerificationError
from scripts.kesher_runtime.output_artifacts import FILE_FIELDS, descriptor, sha256_file
from scripts.kesher_runtime.identity import digest
from scripts.kesher_runtime.provider import text_hash
from tests.test_kesher_media_publication import fixture


class IndependentMediaAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.args = fixture(); self.item = self.args['item']
        item = self.item
        signature = Path(__file__).resolve().parents[1] / 'public/images/signature/signature-mask.svg'
        item.update(signature_asset='signature.svg', signature_video_path='segment.mp4', motion_plan_path='plan.json',
            remotion_props_path='props.json', transcript_path='transcript.txt', source_path='source.txt',
            visual_review_path='sheet.png', frame_paths=[f'frame{i}.png' for i in range(8)])
        png = io.BytesIO(); Image.new('RGB', (16, 9), '#446688').save(png, format='PNG')
        data = {'raw.mp4': b'raw', 'final.mp4': b'final', 'signature.svg': signature.read_bytes(),
            'segment.mp4': b'segment', 'plan.json': b'{"targets":[]}',
            'props.json': json.dumps({'videoSrc': 'raw.mp4', 'sourceStartFrame': 0, 'durationInFrames': 3960,
                'title': item['source']['title'], 'category': item['source']['category'],
                'signatureImageSrc': 'signature.svg', 'motionPlan': []}).encode(),
            'transcript.txt': ('תמליל בעברית לצורך בדיקת ראיות מקור ' * 3).encode(),
            'source.txt': (item['source']['body'] + '\n').encode(), 'sheet.png': png.getvalue()}
        data.update({name: png.getvalue() for name in item['frame_paths']})
        for name, body in data.items(): (self.root / name).write_bytes(body)
        for path_key, hash_key in FILE_FIELDS:
            if path_key != 'manifest_path': item[hash_key] = sha256_file(self.root / item[path_key])
        item['frame_sha256'] = {name: sha256_file(self.root / name) for name in item['frame_paths']}
        item['signature_provenance'].update(raw_sha256=item['raw_sha256'], final_sha256=item['final_sha256'],
            asset_sha256=item['signature_sha256'], segment_sha256=item['signature_video_sha256'], audio_source_sha256=item['raw_sha256'])
        item['audio_provenance'].update(raw_sha256=item['raw_sha256'], final_sha256=item['final_sha256'])
        self.write_manifest()

    def write_manifest(self):
        manifest = {**self.item, 'item_id': self.item['id']}
        (self.root / 'manifest.json').write_text(json.dumps(manifest))
        self.item['manifest_sha256'] = sha256_file(self.root / 'manifest.json')

    def audit(self):
        from scripts import kesher_daily_pipeline as core
        def probe(path):
            return self.item['provider_raw_media'] if path.name == 'raw.mp4' else self.item['media']
        with patch.object(core, 'ffprobe', side_effect=probe), patch.object(core, 'validate_female_voice', return_value=(True, 220., 'female')), \
             patch('scripts.kesher_runtime.media_audit._stream_hash', return_value='9'*64), \
             patch('scripts.kesher_runtime.media_audit._audio_timing', return_value=self.item['audio_provenance']['raw_timing']):
            return audit_files(self.args['identity'], self.args['source'], self.item, self.root)

    def test_byte_audit_records_actual_size_and_full_descriptor(self):
        proof = self.audit()
        self.assertEqual(proof['final_size_bytes'], 5)
        self.assertEqual(proof['identity'], self.args['identity'].to_dict())

    def test_changed_archived_bytes_cannot_be_certified_by_worker_booleans(self):
        (self.root / 'final.mp4').write_bytes(b'other')
        with self.assertRaises(MediaVerificationError): self.audit()

    def test_wrong_source_file_is_rejected_even_with_updated_checksums(self):
        (self.root / 'source.txt').write_text('תוכן אחר')
        self.item['source_file_sha256'] = sha256_file(self.root / 'source.txt'); self.write_manifest()
        with self.assertRaises(MediaVerificationError): self.audit()

    def test_wrong_audio_packet_proof_is_rejected_after_actual_stream_read(self):
        self.item['audio_provenance']['raw_audio_sha256'] = '1'*64
        self.item['audio_provenance']['final_audio_sha256'] = '1'*64; self.write_manifest()
        with self.assertRaises(MediaVerificationError): self.audit()

    def test_old_props_trimming_native_short_fail_even_with_current_manifest(self):
        path = self.root / 'props.json'; props = json.loads(path.read_text()); props['durationInFrames'] = 1650
        path.write_text(json.dumps(props)); self.item['remotion_props_sha256'] = sha256_file(path); self.write_manifest()
        with self.assertRaises(MediaVerificationError): self.audit()

    def test_claimed_youtube_id_without_exact_single_upload_effect_is_not_lineage(self):
        with self.assertRaises(MediaVerificationError):
            verify_lineage({'commands': {}}, self.args['identity'], self.item)

    def test_source_generation_archive_and_upload_are_one_exact_lineage(self):
        target, item = self.args['identity'], self.item
        prompt = 'הוראות בעברית'
        item['generation_prompt_sha256'] = text_hash(prompt)
        def effect(request, receipt):
            return {'request': request, 'receipt': receipt, 'request_sha256': digest(request)}
        effects = {
            'provider_source': effect({'notebook_id': item['notebook_id'], 'body_sha256': text_hash(item['source']['body']),
                'title': f'kesher:{target.key}:1'}, {'source_id': item['source_id']}),
            'provider_generation': effect({'notebook_id': item['notebook_id'], 'source_id': item['source_id'],
                'prompt': prompt, 'prompt_sha256': text_hash(prompt), 'format': 'short', 'language': 'he'},
                {'task_id': item['task_id'], 'artifact_id': item['artifact_id']}),
            'youtube_session': effect({'final_sha256': item['final_sha256'], 'size_bytes': 5}, {'capability_sha256': '7'*64}),
            'output_artifact': effect({'command_id': 'producer', 'run_id': '123/1', 'code_sha': 'a'*40,
                'output': descriptor(target, item), 'sizes': {'final.mp4': 5}}, {'artifact_id': 1})}
        state = {'commands': {'producer': {'target': target.to_dict(), 'effects': effects,
            'code_sha': 'a'*40, 'owner': {'run_id': '123/1'}}}}
        self.assertEqual(verify_lineage(state, target, item), effects['output_artifact'])
        effects['youtube_session']['request']['final_sha256'] = '0'*64
        with self.assertRaises(MediaVerificationError): verify_lineage(state, target, item)

    def test_corrupt_review_frame_is_not_evidence_even_with_matching_hashes(self):
        path = self.root / self.item['frame_paths'][0]; path.write_bytes(b'not an image')
        self.item['frame_sha256'][path.name] = sha256_file(path); self.write_manifest()
        with self.assertRaises(MediaVerificationError): self.audit()


if __name__ == '__main__': unittest.main()
