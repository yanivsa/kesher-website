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


if __name__ == '__main__':
    unittest.main()
