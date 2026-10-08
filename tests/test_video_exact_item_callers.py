"""Exercise workflow boundaries locally with no external dispatch or provider."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from scripts import jules_video_reviewer as reviewer
from scripts import kesher_daily_pipeline as pipeline
from scripts import kesher_video_reconcile as reconcile

ROOT = Path(__file__).resolve().parents[1]


class ExactItemCallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = {'date': '2026-10-05', 'slug': 'generic-source', 'content_sha256': 'a' * 64}
        self.new = {'id': 'new-item', 'type': 'video_overview', 'source': self.source,
                    'status': 'pending_review', 'technical_verified': True, 'fresh_generation_attempt': 2}
        self.old = {**copy.deepcopy(self.new), 'id': 'old-item'}
        self.state = {'version': 1, 'items': [self.old, self.new]}
        (self.root / 'state.json').write_text(json.dumps(self.state))
        (self.root / 'bin').mkdir()
        (self.root / 'bin/python').symlink_to(sys.executable)
        (self.root / 'bin/python3').symlink_to(sys.executable)
        self.env = {'TARGET_ITEM_ID': 'new-item', 'TARGET_SLUG': 'generic-source',
                    'TARGET_CONTENT_SHA256': 'a' * 64, 'TARGET_GENERATION_ATTEMPT': '2',
                    'KESHER_MEDIA_MODE': 'video_overview'}
        p = patch.dict(os.environ, self.env, clear=True)
        p.start(); self.addCleanup(p.stop)

    def pending_script(self):
        doc = yaml.safe_load((ROOT / '.github/workflows/kesher-daily-video.yml').read_text())
        return next(s['run'] for s in doc['jobs']['pipeline']['steps'] if s.get('id') == 'pending')

    def run_pending(self, env):
        output = self.root / 'output'
        result = subprocess.run(['bash', '-c', self.pending_script()], cwd=ROOT,
                                env={**os.environ, 'PATH': str(self.root / 'bin') + os.pathsep + os.defpath, 'PYTHONPATH': str(ROOT),
                                     'KESHER_STATE_DIR': str(self.root), 'GITHUB_OUTPUT': str(output), **env},
                                text=True, capture_output=True)
        return result, output.read_text() if output.exists() else ''

    def test_workflow_review_detection_retains_exact_requested_item(self):
        result, output = self.run_pending({})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('found=true', output)
        self.assertIn('item_id=new-item', output)

    def test_workflow_single_global_pending_without_binding_is_refused(self):
        (self.root / 'state.json').write_text(json.dumps({'items': [self.old]}))
        result, output = self.run_pending({'TARGET_ITEM_ID': ''})
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('found=true', output)

    def test_reconciliation_overview_without_any_binding_refuses_global_fifo(self):
        with patch.dict(os.environ, {'TARGET_ITEM_ID': '', 'TARGET_CONTENT_SHA256': '',
                                    'TARGET_SLUG': '', 'TARGET_GENERATION_ATTEMPT': ''}), \
                patch.object(pipeline, 'load_state', return_value=self.state), \
                patch.object(reconcile, 'published_slugs', return_value={'generic-source'}):
            with self.assertRaisesRegex(pipeline.PipelineError, "EXACT|Exact identity"):
                reconcile.prepare_upload()

    def test_generation_resume_exports_same_item_and_attempt_for_later_steps(self):
        output = self.root / 'environment'
        with patch.dict(os.environ, {'GITHUB_ENV': str(output)}), \
                patch.object(pipeline, 'load_state', return_value=self.state), \
                patch.object(pipeline, 'auth_preflight'):
            pipeline.run_generation(1, None, item_id='new-item')
        env = dict(line.split('=', 1) for line in output.read_text().splitlines())
        self.assertEqual(env.get('TARGET_ITEM_ID'), 'new-item')
        self.assertEqual(env.get('TARGET_CONTENT_SHA256'), 'a' * 64)
        self.assertEqual(env.get('TARGET_GENERATION_ATTEMPT'), '2')

    def test_wrong_requested_generation_attempt_refuses(self):
        with patch.dict(os.environ, {'TARGET_GENERATION_ATTEMPT': '3'}):
            with self.assertRaises(pipeline.PipelineError):
                pipeline.active_item(self.state, item_id='new-item')

    def test_record_decision_does_not_apply_old_evidence_after_item_changed(self):
        import hashlib
        frame = self.root / 'frame.png'
        frame.write_bytes(b'frame-fixture')
        sha = hashlib.sha256(frame.read_bytes()).hexdigest()
        self.new.update(manifest_sha256='a' * 64, final_sha256='b' * 64,
                        transcript_sha256='c' * 64, source_file_sha256='d' * 64,
                        visual_review_sha256='e' * 64, frame_paths=[], frame_sha256={})
        for n in range(pipeline.REVIEW_FRAME_COUNT):
            name = f'frame-{n}.png'
            (self.root / name).write_bytes(frame.read_bytes())
            self.new['frame_paths'].append(name)
            self.new['frame_sha256'][name] = sha
        decision = {'item_id': 'new-item', **reviewer.expected_hashes(self.root, self.new),
                    'frame_observations': ['כל הפריימים נבדקו בעברית בצורה מלאה'] * pipeline.REVIEW_FRAME_COUNT,
                    'visual_status': 'approved', 'semantic_status': 'approved', 'metadata_status': 'approved',
                    'visual_note': 'נבדקו כל הפריימים', 'semantic_note': 'תואם למקור', 'metadata_note': 'תקין בעברית'}
        self.new['final_sha256'] = 'f' * 64
        (self.root / 'state.json').write_text(json.dumps(self.state))
        with patch.object(reviewer.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
            with self.assertRaisesRegex(reviewer.ReviewError, 'evidence mismatch'):
                reviewer.record_decision(self.root, decision, 'sessions/offline-fixture')

    def test_targeted_recovery_dispatches_existing_item_without_generation(self):
        from tests.test_video_reconcile import post
        article = post('generic-source', '2026-10-05')
        sha = pipeline.source_metadata(article)['content_sha256']
        (self.root / '.github').mkdir()
        (self.root / 'src/data').mkdir(parents=True)
        (self.root / 'src/data/posts.json').write_text(json.dumps([article]))
        request = {'enabled': True, 'target_slug': 'generic-source', 'target_date': '2026-10-05',
                   'target_content_sha256': sha, 'target_item_id': 'new-item',
                   'deliverables': {'short_youtube_url': 'https://youtu.be/existing-short'}}
        request_path = self.root / '.github/kesher-media-recovery-request.json'
        request_path.write_text(json.dumps(request))
        doc = yaml.safe_load((ROOT / '.github/workflows/kesher-targeted-media-recovery-dispatch.yml').read_text())
        steps = doc['jobs']['dispatch']['steps']
        select = next(s['run'] for s in steps if s.get('id') == 'target')
        output = self.root / 'output'
        env = {**os.environ, 'PATH': str(self.root / 'bin') + os.pathsep + os.defpath,
               'PYTHONPATH': str(ROOT), 'GITHUB_OUTPUT': str(output)}
        selected = subprocess.run(['bash', '-c', select], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertEqual(selected.returncode, 0, selected.stderr)
        values = dict(line.split('=', 1) for line in output.read_text().splitlines())
        self.assertEqual(values.get('target_item_id'), 'new-item')
        self.assertEqual(values['need_short'], 'false')
        fake = self.root / 'bin/gh'
        fake.write_text('#!' + sys.executable + '\nimport json, sys\nfrom pathlib import Path\nPath("dispatch.json").write_text(json.dumps(sys.argv[1:]))\n')
        fake.chmod(0o755)
        dispatch = next(s['run'] for s in steps if s['name'] == 'Dispatch exact Video Overview worker')
        env.update(TARGET_SLUG=values['slug'], TARGET_CONTENT_SHA256=values['content_sha256'],
                   TARGET_ITEM_ID=values['target_item_id'])
        dispatched = subprocess.run(['bash', '-c', dispatch], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertEqual(dispatched.returncode, 0, dispatched.stderr)
        self.assertEqual(json.loads((self.root / 'dispatch.json').read_text()),
                         ['workflow', 'run', 'kesher-daily-video.yml', '--ref', 'main',
                          '-f', 'operation=upload', '-f', 'target_slug=generic-source',
                          '-f', 'target_content_sha256=' + sha, '-f', 'target_item_id=new-item'])
        request.pop('target_item_id')
        request_path.write_text(json.dumps(request))
        selected = subprocess.run(['bash', '-c', select], cwd=self.root, env=env, text=True, capture_output=True)
        self.assertNotEqual(selected.returncode, 0)

    def test_controller_resume_propagates_known_item_and_rejects_same_source_duplicates(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from scripts import kesher_content_controller_stabilized as stabilized
        from scripts import kesher_content_controller_v5 as v5
        from tests.test_v5_shared_video_controller import FakeGitHub, article
        gh = FakeGitHub()
        source = v5.article_source_identity(article())
        current = {**copy.deepcopy(self.new), 'source': source}
        gh.long_state['items'] = [current]
        controller = stabilized.StabilizedRuntimeV5Controller(gh, None, now=datetime(2026,8,19,19,tzinfo=ZoneInfo('Asia/Jerusalem')))
        state = controller.state()
        state['video'] = state['long_video']
        with patch.object(controller, '_article_source', return_value=source):
            controller._dispatch_budgeted(state, 'video', v5.LONG_VIDEO_WORKFLOW, {'operation': 'full'})
        self.assertEqual(gh.dispatches[-1][1].get('target_item_id'), 'new-item')
        self.assertEqual(gh.dispatches[-1][1].get('target_content_sha256'), source['content_sha256'])
        gh.long_state['items'].append({**copy.deepcopy(current), 'id': 'old-item'})
        with patch.object(controller, '_article_source', return_value=source):
            with self.assertRaises(v5.core.ControllerError):
                controller._dispatch_budgeted(state, 'video', v5.LONG_VIDEO_WORKFLOW, {'operation': 'full'})

    def test_overview_reconciliation_without_mode_still_requires_exact_item(self):
        with patch.dict(os.environ, {'KESHER_MEDIA_MODE': '', 'TARGET_ITEM_ID': '',
                                    'TARGET_CONTENT_SHA256': '', 'TARGET_SLUG': '',
                                    'TARGET_GENERATION_ATTEMPT': ''}), \
                patch.object(pipeline, 'load_state', return_value=self.state), \
                patch.object(reconcile, 'published_slugs', return_value={'generic-source'}):
            with self.assertRaisesRegex(pipeline.PipelineError, 'EXACT|Exact identity'):
                reconcile.prepare_upload()

    def test_new_generation_checks_requested_content_before_provider_work(self):
        source = {**self.source, 'title': 'כותרת בעברית', 'youtube_metadata': {}}
        with patch.dict(os.environ, {'TARGET_ITEM_ID': '', 'TARGET_CONTENT_SHA256': 'c' * 64}), \
                patch.object(pipeline, 'load_state', return_value={'version': 1, 'items': []}), \
                patch.object(pipeline, 'article_by_slug', return_value=source), \
                patch.object(pipeline, 'auth_preflight'), patch.object(pipeline, 'save_state'), \
                patch.object(pipeline, 'add_source') as provider:
            with self.assertRaises(pipeline.PipelineError):
                pipeline.run_generation(1, None)
            provider.assert_not_called()

    def test_unclassified_active_artifact_cannot_be_ignored_for_fresh_generation(self):
        unknown = {**copy.deepcopy(self.new), 'type': None}
        with patch.dict(os.environ, {'TARGET_ITEM_ID': '', 'TARGET_GENERATION_ATTEMPT': ''}):
            with self.assertRaises(pipeline.PipelineError):
                pipeline.active_item({'items': [unknown]}, slug='generic-source')


if __name__ == '__main__':
    unittest.main()
