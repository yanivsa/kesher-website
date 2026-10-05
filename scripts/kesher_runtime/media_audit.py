"""Read-only audit of exact immutable output archives, independent of the worker."""
from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path

from scripts.kesher_article_contract import image_dimensions

from .identity import MediaIdentity, digest, require_sha
from .media_publication import MediaVerificationError, reject
from .output_artifacts import (FILE_FIELDS, _check_archive, _validate_metadata, _verify_local,
                               _producer_run, artifact_effects, descriptor, local_file, sha256_file)
from .provider import text_hash
from .media_state import provider_effect_name
from .render_provenance import _audio_timing, _stream_hash


def verifier_fingerprint() -> str:
    root = Path(__file__).resolve().parents[2]
    paths = ['scripts/kesher_runtime/media_audit.py', 'scripts/kesher_runtime/media_publication.py',
             'scripts/kesher_runtime/render_provenance.py', 'scripts/kesher_runtime/output_artifacts.py',
             'scripts/kesher_e2e_delivery_guard.py', 'scripts/kesher_daily_pipeline.py',
             'scripts/kesher_short_pipeline_v4.py', 'config/kesher-production-contract.json',
             'public/images/signature/signature-mask.svg']
    return digest({name: sha256_file(root / name) for name in paths})


def _unique_effect(state: dict, target: MediaIdentity, name: str) -> dict:
    effects = artifact_effects(state, target) if name == 'output_artifact' else [command['effects'][name] for command in state['commands'].values()
               if command['target'] == target.to_dict() and name in command['effects']]
    requests = {digest(effect['request']) for effect in effects}
    receipts = {digest(effect['receipt']) for effect in effects if effect.get('receipt') is not None}
    if len(requests) != 1 or len(receipts) != 1:
        reject('MEDIA_LINEAGE_INVALID')
    return next(effect for effect in effects if effect.get('receipt') is not None)


def verify_lineage(state: dict, target: MediaIdentity, item: dict) -> dict:
    """Bind source -> generation -> immutable output -> one upload intent."""
    try:
        attempt = item.get('fresh_generation_attempt', 1)
        source = _unique_effect(state, target, provider_effect_name('provider_source', attempt))
        generation = _unique_effect(state, target, provider_effect_name('provider_generation', attempt))
        upload = _unique_effect(state, target, 'youtube_session')
        archive = _unique_effect(state, target, 'output_artifact')
        if (source['receipt']['source_id'] != item['source_id']
                or source['request']['notebook_id'] != item['notebook_id']
                or source['request']['body_sha256'] != text_hash(item['source']['body'])
                or generation['request']['notebook_id'] != item['notebook_id']
                or generation['request']['source_id'] != item['source_id']
                or generation['request']['prompt_sha256'] != item['generation_prompt_sha256']
                or generation['request']['prompt_sha256'] != text_hash(generation['request']['prompt'])
                or generation['receipt']['task_id'] != item['task_id']
                or generation['receipt']['artifact_id'] != item['artifact_id']
                or upload['request']['final_sha256'] != item['final_sha256']
                or archive['request']['output'] != descriptor(target, item)
                or upload['request']['size_bytes'] != archive['request']['sizes'][item['final_mp4']]):
            reject('MEDIA_LINEAGE_INVALID')
        producer = state['commands'][archive['request']['command_id']]
        if (producer['target'] != target.to_dict() or producer['code_sha'] != archive['request']['code_sha']
                or producer['owner']['run_id'] != archive['request']['run_id']):
            reject('MEDIA_LINEAGE_INVALID')
        return archive
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, MediaVerificationError):
            raise
        reject('MEDIA_LINEAGE_INVALID')


def audit_files(target: MediaIdentity, source: dict, item: dict, root: Path) -> dict:
    """Rehash every file, re-probe streams/audio, and inspect render/source inputs."""
    from scripts import kesher_daily_pipeline as core, kesher_short_pipeline_v4 as short
    from scripts.kesher_e2e_delivery_guard import _signature_verified, _short_origin_verified
    try:
        output = descriptor(target, item)
        sizes = _verify_local(root, output)
        required = [key for key, _ in FILE_FIELDS]
        if any(not item.get(key) for key in required) or source != item['source']:
            reject('MEDIA_EVIDENCE_INVALID')
        raw, final = local_file(root, item['raw_mp4']), local_file(root, item['final_mp4'])
        raw_media, media = core.ffprobe(raw), core.ffprobe(final)
        if (media != item['media'] or raw_media != item['provider_raw_media']
                or media['codec'] != 'h264' or not _signature_verified(item)):
            reject('MEDIA_EVIDENCE_INVALID')
        if target.kind == 'short':
            if (not _short_origin_verified(item) or media['width'] != 1080 or media['height'] != 1920
                    or short.short_technical_failures(media, item=item)):
                reject('MEDIA_EVIDENCE_INVALID')
        elif (item.get('visual_pipeline') != 'remotion-v1-notebooklm-audio'
              or media['width'] != 1280 or media['height'] != 720 or not 90 <= media['duration'] <= 180):
            reject('MEDIA_EVIDENCE_INVALID')
        audio = item['audio_provenance']
        if any(_stream_hash(core, path, '0:a:0') != audio[key] for path, key in
               [(raw, 'raw_audio_sha256'), (final, 'final_audio_sha256')]):
            reject('MEDIA_EVIDENCE_INVALID')
        if _audio_timing(core, raw) != audio['raw_timing'] or _audio_timing(core, final) != audio['final_timing']:
            reject('MEDIA_EVIDENCE_INVALID')
        if not core.validate_female_voice(final, item)[0]:
            reject('MEDIA_EVIDENCE_INVALID')
        asset = core.PROJECT_DIR / 'public/images/signature/signature-mask.svg'
        if item['signature_sha256'] != sha256_file(asset):
            reject('MEDIA_EVIDENCE_INVALID')
        plan = json.loads(local_file(root, item['motion_plan_path']).read_text(encoding='utf-8'))
        props = json.loads(local_file(root, item['remotion_props_path']).read_text(encoding='utf-8'))
        expected_plan = short._short_targets_for_plan(plan) if target.kind == 'short' else plan
        expected_props = {'videoSrc': raw.name, 'durationInFrames': max(1, round(raw_media['duration'] * 30)),
                          'title': source['title'], 'category': source['category'],
                          'signatureImageSrc': item['signature_asset'], 'motionPlan': expected_plan}
        expected_props.update({'sourceStartFrame': 0} if target.kind == 'short' else {'audioSrc': raw.name})
        if any(props.get(key) != value for key, value in expected_props.items()):
            reject('MEDIA_EVIDENCE_INVALID')
        manifest = json.loads(local_file(root, item['manifest_path']).read_text(encoding='utf-8'))
        fields = ['source', 'notebook_id', 'source_id', 'task_id', 'artifact_id', 'signature_provenance',
                  'audio_provenance', 'render_input_sha256', 'media', 'frame_paths', 'frame_sha256']
        fields += [key for pair in FILE_FIELDS if pair[0] != 'manifest_path' for key in pair]
        if manifest.get('item_id') != item['id'] or any(manifest.get(key) != item.get(key) for key in fields):
            reject('MEDIA_EVIDENCE_INVALID')
        require_sha(item['render_input_sha256'])
        if len(item['frame_paths']) != 8 or len(set(item['frame_paths'])) != 8:
            reject('MEDIA_EVIDENCE_INVALID')
        for name in [*item['frame_paths'], item['visual_review_path']]:
            image_dimensions(local_file(root, name).read_bytes())
        if local_file(root, item['source_path']).read_text(encoding='utf-8').strip() != source['body'].strip():
            reject('MEDIA_EVIDENCE_INVALID')
        transcript = local_file(root, item['transcript_path']).read_text(encoding='utf-8')
        core.require_hebrew(transcript, 'transcript', allow_url=True)
        if len(re.findall(r'[\u0590-\u05ff]', transcript)) < 40:
            reject('MEDIA_EVIDENCE_INVALID')
        # Detect changes during the audit before issuing any reusable receipt.
        _verify_local(root, output)
        return {'schema_version': 1, 'identity': target.to_dict(), 'output_sha256': digest(output),
                'verifier_sha256': verifier_fingerprint(), 'media': media, 'final_size_bytes': sizes[item['final_mp4']],
                'raw_sha256': item['raw_sha256'], 'final_sha256': item['final_sha256'],
                'audio_sha256': audio['raw_audio_sha256']}
    except (OSError, ValueError, KeyError, TypeError, core.PipelineError) as exc:
        if isinstance(exc, MediaVerificationError):
            raise
        reject('MEDIA_EVIDENCE_INVALID')


class ArchivedMediaAuditor:
    def __init__(self, github, repo: str, download):
        self.github, self.repo, self.download = github, repo, download

    def __call__(self, state: dict, target: MediaIdentity, source: dict, item: dict) -> dict:
        effect = verify_lineage(state, target, item)
        output_hash = digest(descriptor(target, item))
        fingerprint = verifier_fingerprint()
        # These receipts are written only by the controller's independent audit,
        # outside worker checkpoints. Immutable byte proof survives archive expiry;
        # live YouTube metadata/processing/inventory are always fetched again.
        for key, proof in state['items'][target.key]['receipts'].items():
            if (key == 'technical:' + digest(proof) and proof.get('identity') == target.to_dict()
                    and proof.get('output_sha256') == output_hash and proof.get('verifier_sha256') == fingerprint):
                return proof
        request, receipt = effect['request'], effect['receipt']
        api = f'/repos/{self.repo}/actions'
        metadata = self.github.request('GET', f"{api}/artifacts/{receipt['artifact_id']}")
        run = _producer_run(self.github, self.repo, request)
        if _validate_metadata(request, metadata, run, receipt['artifact_id']) != receipt:
            reject('MEDIA_EVIDENCE_INVALID')
        with tempfile.TemporaryDirectory(prefix='kesher-independent-media-') as folder:
            root = Path(folder); archive = root / 'archive.zip'; stage = root / 'files'; stage.mkdir()
            self.download(receipt['artifact_id'], archive)
            _check_archive(archive, request, receipt, stage)
            return audit_files(target, source, item, stage)
