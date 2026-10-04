"""Current media evidence must describe this render, not a previous item-ID file."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import kesher_e2e_delivery_guard as guard
from scripts import kesher_short_pipeline_v4 as short
from scripts import kesher_daily_pipeline as overview



def audio_fixture(raw_sha256: str, final_sha256: str, duration: float) -> dict:
    timing = {'codec': 'aac', 'sample_rate': 48000, 'channels': 1, 'start_seconds': 0.0, 'duration_seconds': duration}
    return {'schema_version': 1, 'mode': 'stream_copy', 'raw_sha256': raw_sha256, 'final_sha256': final_sha256,
            'raw_audio_sha256': '9' * 64, 'final_audio_sha256': '9' * 64,
            'raw_timing': dict(timing), 'final_timing': dict(timing)}

def bound_short(duration: float = 132.0) -> dict:
    return {
        'id': 'short-1', 'type': 'article_short', 'source_mode': 'direct-short',
        'visual_pipeline': short.VISUAL_PIPELINE,
        'source': {'slug': 'article', 'content_sha256': 'a' * 64},
        'notebook_id': 'notebook', 'source_id': 'short-source',
        'task_id': 'short-task', 'artifact_id': 'short-artifact',
        'provider_video_format': 'short', 'provider_native_short': True,
        'provider_native_short_verified': True, 'provider_short_fallback_used': False,
        'fresh_generation_attempt': 1,
        'overview_provider_identity': {'notebook_id': 'notebook', 'source_id': 'overview-source',
                                      'task_id': 'overview-task', 'artifact_id': 'overview-artifact',
                                      'raw_sha256': 'e' * 64},
        'raw_sha256': 'b' * 64, 'final_sha256': 'c' * 64,
        'audio_provenance': audio_fixture('b' * 64, 'c' * 64, duration),
        'provider_raw_media': {'width': 1080, 'height': 1920, 'duration': duration, 'audio_codec': 'aac'},
        'media': {'width': 1080, 'height': 1920, 'duration': duration, 'codec': 'h264', 'audio_codec': 'aac'},
        'short_start_seconds': 0.0, 'short_duration_seconds': duration,
        'signature_overlay': True, 'signature_fullscreen': True, 'signature_verified': True,
        'signature_duration_seconds': min(3.0, duration), 'signature_sha256': 'd' * 64,
        'signature_video_sha256': 'f' * 64,
        'signature_provenance': {
            'schema_version': 1, 'final_sha256': 'c' * 64, 'raw_sha256': 'b' * 64,
            'asset_sha256': 'd' * 64, 'segment_sha256': 'f' * 64,
            'source_duration_seconds': duration, 'final_duration_seconds': duration,
            'start_seconds': max(0.0, duration - 3.0), 'end_seconds': duration, 'audio_source_sha256': 'b' * 64,
        },
    }


class SignatureProvenanceTests(unittest.TestCase):
    def test_signature_does_not_certify_missing_changed_or_shifted_audio(self):
        for field, value in [('final_audio_sha256', '0' * 64), ('raw_sha256', '1' * 64),
                             ('final_sha256', '2' * 64), ('mode', 'unverified')]:
            with self.subTest(field=field):
                item = bound_short()
                item['audio_provenance'][field] = value
                self.assertFalse(guard._signature_verified(item))
        item = bound_short()
        item['audio_provenance']['final_timing']['start_seconds'] = .043
        self.assertFalse(guard._signature_verified(item))
        item.pop('audio_provenance')
        self.assertFalse(guard._signature_verified(item))

    def test_shorter_natural_source_keeps_signature_inside_its_entire_timeline(self):
        item = bound_short(2.0)
        self.assertEqual(short.short_technical_failures(item['media'], item=item), [])

    def test_full_background_is_allowed_with_exact_in_content_timing(self):
        self.assertTrue(guard._signature_verified(bound_short()))

    def test_old_fullscreen_appended_outro_cannot_masquerade_as_overlay(self):
        item = bound_short()
        item.pop('signature_provenance')
        item.pop('signature_overlay')
        item['media']['duration'] = 135.0
        self.assertFalse(guard._signature_verified(item))

    def test_changed_current_file_or_timeline_invalidates_old_signature(self):
        for field, value in [('final_sha256', '1' * 64), ('raw_sha256', '2' * 64),
                             ('signature_sha256', '3' * 64), ('signature_video_sha256', '4' * 64),
                             ('short_duration_seconds', 55.0)]:
            with self.subTest(field=field):
                item = bound_short()
                item[field] = value
                self.assertFalse(guard._signature_verified(item))
        for field, value in [('final_duration_seconds', 135.0), ('start_seconds', 132.0),
                             ('end_seconds', 135.0), ('audio_source_sha256', '0' * 64)]:
            with self.subTest(field=field):
                item = bound_short()
                item['signature_provenance'][field] = value
                self.assertFalse(guard._signature_verified(item))

    def test_item_id_segment_cannot_be_reused_when_current_final_is_missing(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(short.core, 'STATE_DIR', Path(temp)):
            (Path(temp) / 'id-signature-segment.mp4').write_bytes(b'old evidence')
            with self.assertRaises(short.core.PipelineError):
                short.extract_signature_video_segment(Path(temp) / 'missing.mp4', 'id')

    def test_extraction_receipt_reuses_only_same_final_and_segment_bytes(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(short.core, 'STATE_DIR', Path(temp)):
            final = Path(temp) / 'final.mp4'
            final.write_bytes(b'final one')
            rendered = []
            def ffmpeg(command, **kwargs):
                rendered.append(command)
                Path(command[-1]).write_bytes(b'segment:' + final.read_bytes())
                return SimpleNamespace(returncode=0, stderr='', stdout='')
            with patch.object(short.shutil, 'which', return_value='ffmpeg'), patch.object(short.subprocess, 'run', side_effect=ffmpeg):
                first, first_hash = short.extract_signature_video_segment(final, 'id')
                short.extract_signature_video_segment(final, 'id')
                self.assertEqual(len(rendered), 1)
                final.write_bytes(b'final two')
                _, second_hash = short.extract_signature_video_segment(final, 'id')
                self.assertNotEqual(first_hash, second_hash)
                first.write_bytes(b'tampered segment')
                short.extract_signature_video_segment(final, 'id')
                self.assertEqual(len(rendered), 3)


class ShortOriginProvenanceTests(unittest.TestCase):
    def test_independent_native_short_preserves_natural_duration(self):
        self.assertTrue(guard._short_origin_verified(bound_short()))

    def test_labels_do_not_override_shared_provider_source_or_raw_identity(self):
        changes = [('shared_provider_identity', True), ('adopted_from_long_item_id', 'long'),
                   ('source_id', 'overview-source'), ('task_id', 'overview-artifact'),
                   ('artifact_id', 'overview-task'), ('raw_sha256', 'e' * 64),
                   ('overview_provider_identity', {}), ('provider_native_short_verified', False)]
        for field, value in changes:
            with self.subTest(field=field):
                item = bound_short()
                item[field] = value
                self.assertFalse(guard._short_origin_verified(item))

    def test_independent_landscape_fallback_only_on_third_attempt(self):
        for attempt, wanted in [(1, False), (2, False), (3, True), (4, False)]:
            with self.subTest(attempt=attempt):
                item = bound_short()
                item.update(fresh_generation_attempt=attempt, provider_video_format='explainer',
                            provider_native_short=False, provider_native_short_verified=False,
                            provider_short_fallback_used=True)
                item['provider_raw_media'].update(width=1920, height=1080)
                self.assertEqual(guard._short_origin_verified(item), wanted)

    def test_provider_gate_rejects_fourth_attempt_landscape(self):
        failures = short.native_provider_short_failures(
            {'width': 1920, 'height': 1080},
            {'fresh_generation_attempt': 4, 'provider_video_format': 'explainer'})
        self.assertTrue(failures)


class ShortRenderCacheTests(unittest.TestCase):
    def test_short_invokes_the_existing_full_timeline_signature_composition(self):
        class CapturedRender(BaseException):
            pass
        captured = {}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / 'native.mp4'; raw.write_bytes(b'native portrait fixture')
            (root / 'signature.svg').write_bytes(b'<svg/>')
            item = {'id': 'exact-short', 'source': {'title': 'כותרת', 'category': 'זוגיות'},
                    'fresh_generation_attempt': 1, 'provider_video_format': 'short'}
            def execute(*, renderer, edit_plan, output_path, **kwargs):
                renderer(edit_plan, output_path)
            def capture(command, **kwargs):
                captured.update(command=command, cwd=kwargs['cwd'],
                    props=json.loads((root / 'exact-short-short-remotion-props.json').read_text()))
                raise CapturedRender()
            with patch.object(short.core, 'STATE_DIR', root), \
                    patch.object(short, 'prepare_signature_asset', return_value='signature.svg'), \
                    patch.object(short.core, 'ffprobe', return_value={'width': 360, 'height': 640, 'duration': 2}), \
                    patch.object(short, 'build_motion_plan', return_value={'targets': []}), \
                    patch.object(short, 'execute_enhancement', side_effect=execute), \
                    patch.object(short.subprocess, 'run', side_effect=capture):
                with self.assertRaises(CapturedRender):
                    short.render_remotion_video(raw, item)
        self.assertEqual(captured['command'][2:4], ['src/remotion/index.ts', 'ArticleShort'])
        self.assertEqual(captured['cwd'], short.core.PROJECT_DIR)
        self.assertEqual(captured['props']['durationInFrames'], 60)
        self.assertEqual(captured['props']['sourceStartFrame'], 0)
        self.assertEqual(captured['props']['signatureImageSrc'], 'signature.svg')

    def test_existing_render_with_stale_evidence_cannot_skip_rebuild(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name, data in [('raw.mp4', b'raw'), ('sig.svg', b'<svg/>'),
                               ('id-short-final.mp4', b'stale final'),
                               ('id-short-motion-plan.json', b'{}'), ('id-short-remotion-props.json', b'{}')]:
                (root / name).write_bytes(data)
            item = {'id': 'id', 'provider_video_format': 'short', 'fresh_generation_attempt': 1,
                    'enhancement_status': 'enhancement_complete',
                    'motion_plan_path': 'id-short-motion-plan.json', 'motion_plan_sha256': 'wrong',
                    'remotion_props_path': 'id-short-remotion-props.json', 'remotion_props_sha256': 'wrong'}
            with patch.object(short.core, 'STATE_DIR', root), patch.object(short, 'prepare_signature_asset', return_value='sig.svg'), patch.object(short.core, 'ffprobe', return_value={'width': 1080, 'height': 1920, 'duration': 132.0}), patch.object(short, 'build_motion_plan', side_effect=short.core.PipelineError('rebuild required')):
                with self.assertRaises(short.core.PipelineError):
                    short.render_remotion_video(root / 'raw.mp4', item)


class OverviewRenderCacheTests(unittest.TestCase):
    def test_complete_cache_binds_actual_bytes_source_and_current_renderer(self):
        from scripts.kesher_runtime.render_provenance import record_signature, render_input_digest
        with tempfile.TemporaryDirectory() as temp, patch.object(overview, 'STATE_DIR', Path(temp)):
            root = Path(temp)
            raw, final, asset, segment = [root / name for name in ('raw.mp4', 'final.mp4', 'signature-mask.svg', 'segment.mp4')]
            raw.write_bytes(b'raw overview'); final.write_bytes(b'final overview'); segment.write_bytes(b'extracted segment')
            asset.write_bytes((overview.PROJECT_DIR / overview.SIGNATURE_SOURCE).read_bytes())
            media = {'duration': 104.0, 'codec': 'h264', 'audio_codec': 'aac', 'width': 1280, 'height': 720}
            item = {'id': 'overview-1', 'type': 'video_overview', 'source': {'slug': 'article', 'content_sha256': 'a' * 64},
                    'raw_mp4': raw.name, 'content_duration_seconds': 104.0, 'enhancement_status': 'enhancement_complete'}
            with patch('scripts.kesher_runtime.render_provenance.extract_signature_segment',
                       return_value=(segment, overview.sha256_file(segment))), patch(
                       'scripts.kesher_runtime.render_provenance.preserve_source_audio',
                       return_value=audio_fixture(overview.sha256_file(raw), overview.sha256_file(final), 104.0)):
                record_signature(overview, raw, final, item, asset, media, media)
            plan = {'segments': [], 'render_mode': 'basic'}
            props = {'videoSrc': raw.name, 'audioSrc': raw.name, 'signatureImageSrc': asset.name,
                     'durationInFrames': 3120, 'motionPlan': plan}
            for field, value, name in [('motion_plan', plan, 'plan.json'), ('remotion_props', props, 'props.json')]:
                (root / name).write_text(json.dumps(value))
                item[field + '_path'], item[field + '_sha256'] = name, overview.sha256_file(root / name)
            item['render_input_sha256'] = render_input_digest(overview, raw, item, overview.sha256_file(asset), 'overview')
            with patch.object(overview, 'ffprobe', return_value=media):
                self.assertTrue(guard._signature_verified(item))
                self.assertTrue(overview.remotion_cache_is_reusable(item, final))
                changed = copy.deepcopy(item); changed['source']['content_sha256'] = 'b' * 64
                self.assertFalse(overview.remotion_cache_is_reusable(changed, final))
                final.write_bytes(b'replaced final')
                self.assertFalse(overview.remotion_cache_is_reusable(item, final))

    def test_plan_and_props_hashes_cannot_certify_an_unbound_final_or_source(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(overview, 'STATE_DIR', Path(temp)):
            root = Path(temp)
            final = root / 'final.mp4'
            final.write_bytes(b'old final from another source')
            for name in ('plan.json', 'props.json'):
                (root / name).write_text('{}')
            item = {'enhancement_status': 'enhancement_complete',
                    'motion_plan_path': 'plan.json', 'motion_plan_sha256': overview.sha256_file(root / 'plan.json'),
                    'remotion_props_path': 'props.json', 'remotion_props_sha256': overview.sha256_file(root / 'props.json')}
            self.assertFalse(overview.remotion_cache_is_reusable(item, final))


if __name__ == '__main__':
    unittest.main()
