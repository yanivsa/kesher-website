"""Shared byte/provenance contract for the two deterministic media renderers."""
from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from .identity import digest


def render_input_digest(core, raw_path: Path, item: dict, signature_sha256: str, kind: str) -> str:
    paths = sorted((core.PROJECT_DIR / 'src' / 'remotion').rglob('*.tsx'))
    paths += sorted((core.PROJECT_DIR / 'src' / 'remotion').rglob('*.ts'))
    paths += [core.PROJECT_DIR / relative for relative in (
        'package-lock.json', 'scripts/kesher_daily_pipeline.py', 'scripts/kesher_short_pipeline_v4.py',
        'scripts/motion_plan_generator.py', 'scripts/kesher_video_enhancement.py',
        'scripts/kesher_runtime/render_provenance.py')]
    renderer = {str(path.relative_to(core.PROJECT_DIR)): core.sha256_file(path) for path in paths if path.is_file()}
    return digest({'schema_version': 1, 'kind': kind, 'raw_sha256': core.sha256_file(raw_path),
        'source': item.get('source'), 'signature_sha256': signature_sha256,
        'provider': {key: item.get(key) for key in ('notebook_id', 'source_id', 'task_id', 'artifact_id',
                     'provider_video_format', 'fresh_generation_attempt', 'overview_provider_identity')},
        'renderer': renderer, 'fps': 30})


def extract_signature_segment(core, output_path: Path, item_id: str, *, duration_seconds: float = 3.0) -> tuple[Path, str]:
    if not math.isfinite(duration_seconds) or not 0 < duration_seconds <= 3.0:
        raise core.PipelineError('Signature segment must remain within the source timeline')
    core.STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not output_path.is_file() or output_path.stat().st_size <= 0:
        raise core.PipelineError('Current final MP4 is missing; signature evidence cannot be reused')
    final_sha256 = core.sha256_file(output_path)
    path = core.STATE_DIR / f'{item_id}-signature-segment.mp4'
    receipt_path = path.with_suffix('.json')
    if path.is_file() and path.stat().st_size > 0:
        try:
            receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
            checksum = core.sha256_file(path)
            if receipt == {'schema_version': 1, 'final_sha256': final_sha256,
                           'segment_sha256': checksum, 'duration_seconds': duration_seconds}:
                return path, checksum
        except (OSError, ValueError, TypeError):
            pass
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise core.PipelineError('ffmpeg is required to extract the signature video segment')
    command = [ffmpeg, '-y', '-sseof', f'-{duration_seconds}', '-i', str(output_path),
               '-t', str(duration_seconds), '-c:v', 'libx264', '-c:a', 'aac', str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
    if result.returncode or not path.is_file() or path.stat().st_size <= 0:
        raise core.PipelineError('Failed to extract signature video segment')
    if core.sha256_file(output_path) != final_sha256:
        raise core.PipelineError('Final MP4 changed during signature extraction')
    checksum = core.sha256_file(path)
    core.atomic_json_write(receipt_path, {'schema_version': 1, 'final_sha256': final_sha256,
        'segment_sha256': checksum, 'duration_seconds': duration_seconds})
    return path, checksum



def _stream_hash(core, path: Path, selector: str) -> str:
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-map', selector,
        '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-'], capture_output=True, text=True, check=False, timeout=120)
    match = re.fullmatch(r'SHA256=([a-f0-9]{64})\s*', result.stdout)
    if result.returncode or not match:
        raise core.PipelineError('Unable to verify original media packets')
    return match[1]


def _audio_timing(core, path: Path) -> dict:
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
        'stream=codec_name,sample_rate,channels,start_time,duration', '-of', 'json', str(path)],
        capture_output=True, text=True, check=False, timeout=120)
    try:
        streams = json.loads(result.stdout)['streams']
        if result.returncode or len(streams) != 1:
            raise ValueError('Missing exact audio stream')
        row = streams[0]
        return {'codec': row['codec_name'], 'sample_rate': int(row['sample_rate']), 'channels': int(row['channels']),
                'start_seconds': float(row['start_time']), 'duration_seconds': float(row['duration'])}
    except (ValueError, TypeError, KeyError) as exc:
        raise core.PipelineError('Unable to verify exact audio timeline') from exc


def preserve_source_audio(core, raw_path: Path, final_path: Path) -> dict:
    """Mux the original compressed audio with rendered video, without re-encoding.

    Real Remotion probes exposed an extra 2 AAC-frame delay from re-encoding.
    Packet and timeline readback makes source preservation independently testable.
    """
    if raw_path.resolve() == final_path.resolve():
        raise core.PipelineError('Rendered output cannot overwrite the provider source')
    raw_sha = core.sha256_file(raw_path)
    audio_sha, video_sha = _stream_hash(core, raw_path, '0:a:0'), _stream_hash(core, final_path, '0:v:0')
    timing = _audio_timing(core, raw_path)
    temporary = final_path.with_name(final_path.stem + '.source-audio.mp4')
    try:
        result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-i', str(final_path), '-i', str(raw_path), '-map', '0:v:0', '-map', '1:a:0',
            '-c', 'copy', '-map_metadata', '-1', '-movflags', '+faststart', str(temporary)],
            capture_output=True, text=True, check=False, timeout=120)
        if result.returncode or not temporary.is_file():
            raise core.PipelineError('Unable to preserve original audio in rendered output')
        output_audio = _stream_hash(core, temporary, '0:a:0')
        output_timing = _audio_timing(core, temporary)
        if (output_audio != audio_sha or output_timing != timing
                or _stream_hash(core, temporary, '0:v:0') != video_sha or core.sha256_file(raw_path) != raw_sha):
            raise core.PipelineError('Mux changed the original audio, rendered video or source timeline')
        temporary.replace(final_path)
    finally:
        temporary.unlink(missing_ok=True)
    return {'schema_version': 1, 'mode': 'stream_copy', 'raw_sha256': raw_sha,
            'final_sha256': core.sha256_file(final_path), 'raw_audio_sha256': audio_sha,
            'final_audio_sha256': output_audio, 'raw_timing': timing, 'final_timing': output_timing}


def audio_evidence_valid(item: dict) -> bool:
    proof = item.get('audio_provenance') or {}
    if not isinstance(proof, dict) or proof.get('schema_version') != 1 or proof.get('mode') != 'stream_copy':
        return False
    for field in ('raw_sha256', 'final_sha256'):
        if (not isinstance(item.get(field), str) or not re.fullmatch(r'[a-f0-9]{64}', item[field])
                or proof.get(field) != item[field]):
            return False
    checksum = proof.get('raw_audio_sha256')
    if not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum) or proof.get('final_audio_sha256') != checksum:
        return False
    timing = proof.get('raw_timing')
    if not isinstance(timing, dict) or timing != proof.get('final_timing'):
        return False
    try:
        return bool(timing['codec'] and type(timing['sample_rate']) is int and timing['sample_rate'] > 0
                    and type(timing['channels']) is int and timing['channels'] > 0
                    and math.isfinite(float(timing['start_seconds']))
                    and math.isfinite(float(timing['duration_seconds'])) and float(timing['duration_seconds']) > 0
                    and abs(float(timing['duration_seconds']) - float(item['provider_raw_media']['duration'])) <= 0.15)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False

def record_signature(core, raw_path: Path, final_path: Path, item: dict, signature: Path,
                     raw_media: dict, final_media: dict) -> None:
    source_duration, final_duration = float(raw_media['duration']), float(final_media['duration'])
    if (not all(math.isfinite(value) and value > 0 for value in (source_duration, final_duration))
            or abs(source_duration - final_duration) > 0.15
            or not raw_media.get('audio_codec') or not final_media.get('audio_codec')):
        raise core.PipelineError('Render changed the source duration or lost its audio')
    audio = preserve_source_audio(core, raw_path, final_path)
    final_media = {**final_media, 'audio_codec': audio['final_timing']['codec']}
    duration = min(3.0, source_duration)
    segment, segment_sha = extract_signature_segment(core, final_path, item['id'], duration_seconds=duration)
    raw_sha, final_sha, asset_sha = (core.sha256_file(path) for path in (raw_path, final_path, signature))
    item.update(raw_sha256=raw_sha, final_sha256=final_sha, provider_raw_media=raw_media, media=final_media, audio_provenance=audio,
        signature_asset=signature.name, signature_sha256=asset_sha, signature_asset_sha256=asset_sha,
        signature_video_path=segment.name, signature_video_sha256=segment_sha,
        signature_duration_seconds=duration, signature_fullscreen=True, signature_overlay=True, signature_verified=True,
        signature_provenance={'schema_version': 1, 'final_sha256': final_sha, 'raw_sha256': raw_sha,
            'asset_sha256': asset_sha, 'segment_sha256': segment_sha,
            'source_duration_seconds': source_duration, 'final_duration_seconds': final_duration,
            'start_seconds': max(0.0, final_duration - duration), 'end_seconds': final_duration,
            'audio_source_sha256': raw_sha})
