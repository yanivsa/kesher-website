"""Execute one admitted media command through provider, render and publication.

The worker receives only a command ID. It resumes that exact canonical item and
returns bounded pending observations to the controller. It never selects FIFO,
the newest artifact, or another provider task, and never installs module globals.
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from .identity import MediaIdentity, SourceIdentity, digest
from .media_state import CanonicalMediaState, snapshots
from .output_artifacts import require_bundle
from .provider import observe_provider, reconcile_provider
from .state import StateInvalid
from .worker import WorkerContext
from .worker_entry import actions_admission
from .youtube import repair_metadata


@dataclass(frozen=True)
class MediaRunResult:
    status: str
    reason: str


def require_owner_media_quality(item: dict, kind: str, *, approval_root: Path | None = None) -> None:
    """Fail closed before FIRST upload unless OWNER reviewed these exact media bytes.

    GitHub-reviewed approval JSON is an immutable media/source-bound receipt, not
    an automatic inference from ffprobe success or a generated ASR transcript.
    No external reviewer, paid service, new workflow or upload is invoked.
    Existing YouTube videos are reconciled by the caller before reaching here.
    """
    import json
    import re

    def reject(code: str) -> None:
        raise StateInvalid(code)

    if kind not in {"overview", "short"} or item.get("technical_verified") is not True:
        reject("EDITORIAL_QA_MEDIA_NOT_VALIDATED")
    source = item.get("source") or {}
    slug = str(source.get("slug") or "")
    source_sha = str(source.get("content_sha256") or "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or not re.fullmatch(r"[a-f0-9]{64}", source_sha):
        reject("EDITORIAL_QA_SOURCE_IDENTITY_INVALID")
    if item.get("type") != ("video_overview" if kind == "overview" else "article_short"):
        reject("EDITORIAL_QA_MEDIA_KIND_MISMATCH")
    root = approval_root if approval_root is not None else Path(__file__).resolve().parents[2] / "research" / "owner-media-quality"
    approval_path = root / f"{slug}--{kind}.json"
    if approval_path.is_symlink() or not approval_path.is_file():
        reject("EDITORIAL_QA_PENDING: no reviewed OWNER approval for exact media")
    if approval_path.stat().st_size > 16_384:
        reject("EDITORIAL_QA_INVALID_APPROVAL_SIZE")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        reject("EDITORIAL_QA_INVALID_APPROVAL")
    if not isinstance(approval, dict) or approval.get("schema_version") != 1:
        reject("EDITORIAL_QA_INVALID_APPROVAL")
    exact = {
        "source_slug": slug,
        "content_sha256": source_sha,
        "media_kind": kind,
        "media_item_id": item.get("id"),
    }
    exact.update({key: item.get(key) for key in (
        "final_sha256", "manifest_sha256", "transcript_sha256",
        "visual_review_sha256", "source_file_sha256",
    )})
    for key, expected in exact.items():
        if approval.get(key) != expected or not isinstance(expected, str) or not expected:
            reject("EDITORIAL_QA_EXACT_IDENTITY_MISMATCH")
    for key in ("final_sha256", "manifest_sha256", "transcript_sha256",
                "visual_review_sha256", "source_file_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", str(exact[key])):
            reject("EDITORIAL_QA_INVALID_EVIDENCE_HASH")
    frames = item.get("frame_sha256")
    if (not isinstance(frames, dict) or len(frames) != 8
            or any(not re.fullmatch(r"[a-f0-9]{64}", str(v)) for v in frames.values())
            or approval.get("frame_sha256") != frames):
        reject("EDITORIAL_QA_FRAME_HASH_MISMATCH")
    if approval.get("reviewed_by") != "OWNER" or not str(approval.get("reviewed_at") or ""):
        reject("EDITORIAL_QA_OWNER_ATTESTATION_MISSING")
    checks = approval.get("checks") or {}
    if any(checks.get(key) != "approved" for key in ("visual", "semantic", "audio", "metadata", "licensing")):
        reject("EDITORIAL_QA_HOLD: required review did not pass")
    methods = approval.get("methods") or {}
    if (methods.get("visual") != "full_motion_and_frames"
            or methods.get("semantic") != "research_vs_exact_transcript"
            or methods.get("audio") not in {"direct_playback", "authorized_audio_tool_with_script_comparison"}):
        reject("EDITORIAL_QA_METHOD_NOT_VERIFIED")
    notes = approval.get("review_notes") or {}
    if any(len(re.findall(r"[\u0590-\u05ff]", str(notes.get(key) or ""))) < 12
           for key in ("visual", "semantic", "audio", "licensing")):
        reject("EDITORIAL_QA_NOTES_MISSING")
    rights = approval.get("rights") or {}
    if rights.get("commercial_use_permitted") is not True:
        reject("EDITORIAL_QA_LICENSE_HOLD")
    if any(not isinstance(rights.get(key), str)
           or not rights[key].startswith("https://")
           or len(rights[key]) > 2048
           for key in ("voice_license_url", "visual_license_url")):
        reject("EDITORIAL_QA_LICENSE_EVIDENCE_MISSING")




def _file(root: Path, name: str | None) -> Path | None:
    if not name:
        return None
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        raise StateInvalid('Output reference escapes the exact worker directory')
    return root / path


def run_media(context: WorkerContext, *, encryption_key: str = '', phase: str = 'prepare') -> MediaRunResult:
    from scripts import kesher_daily_pipeline as core
    from scripts import kesher_short_pipeline_v4 as short
    from scripts import kesher_e2e_delivery_guard as guard

    target = context.target
    if phase not in {'prepare', 'publish'}:
        raise StateInvalid('Media execution requires an explicit prepare or publish boundary')
    if not isinstance(target, MediaIdentity):
        raise StateInvalid('Media worker requires an exact media identity')
    command = context.store.load().state['commands'][context.command_id]
    if command['operation'] not in {'publish', 'reconcile', 'rebuild', 'repair_metadata'}:
        raise StateInvalid('Unsupported canonical media operation')
    source = core.article_by_slug(target.source.slug)
    if SourceIdentity(source['date'], source['slug'], source['content_sha256']) != target.source:
        raise StateInvalid('AUTHORITATIVE_SOURCE_CHANGED: do not select another article')
    engine = short if target.kind == 'short' else core
    initial = engine.new_item(source)
    # Canonical byte/publication audits compare the complete independently
    # observed source, including the provider body and publication metadata.
    initial['source'] = copy.deepcopy(source)
    initial['id'] = f'media-{digest(target.to_dict())[:24]}'
    raw_attempt = command['inputs'].get('generation_attempt', '1')
    if raw_attempt not in {'1', '2', '3'}:
        raise StateInvalid('Generation attempt must be controller-authorized and bounded')
    attempt = int(raw_attempt)
    initial['fresh_generation_attempt'] = attempt
    if attempt > 1:
        initial['id'] += f'-a{attempt}'
    state = CanonicalMediaState(context, initial, encryption_key=encryption_key)
    item = state.item
    if item.get('fresh_generation_attempt', 1) != attempt:
        raise StateInvalid('Generation attempt changed without explicit canonical attempt transition')
    state.persist()

    # Existing publication is reconciled before reading local media or touching
    # provider generation/auth. Missing MP4s are irrelevant to metadata repair.
    if item.get('youtube_id'):
        token = core.youtube_access_token()
        core.verify_authenticated_channel(token)
        repair_metadata(state, core, token)
        return MediaRunResult('observed_public', 'Existing video read back; independent controller verification remains required')
    if command['operation'] == 'repair_metadata':
        raise StateInvalid('Metadata-only command has no existing video ID')
    if not isinstance(encryption_key, str) or len(encryption_key) < 24:
        raise StateInvalid('CAPABILITY_KEY_UNAVAILABLE: validate upload storage before generation')
    if phase == 'publish':
        # This process must not fall back into provider/render work. Exact bytes
        # and the immutable archive receipt must exist before any upload effect.
        require_bundle(context, item, core.STATE_DIR)
        return _publish(state, core, guard)
    # Auth readiness is checked before consuming any provider generation intent.
    token = core.youtube_access_token()
    core.verify_authenticated_channel(token)
    core.auth_preflight()
    core.STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not reconcile_provider(state, lambda name, request: observe_provider(core, name, request)):
        return MediaRunResult('waiting', 'Prior provider creation is uncertain; reconcile exact intent without another creation')

    if item.get('status') == 'rejected' and command['operation'] != 'rebuild':
        raise StateInvalid('TECHNICAL_REJECTION: controller must classify before another attempt')
    if not item.get('source_id'):
        core.add_source(state, item)
    if not item.get('task_id'):
        engine.start_generation(state, item)
    if item.get('status') == 'generating':
        if not core.wait_for_generation(state, item, max_wait_seconds=0):
            return MediaRunResult('waiting', 'Exact provider task is pending; no new generation or upload')

    if target.kind == 'short':
        overview = MediaIdentity(target.source, 'overview')
        history = snapshots(context.store.load().state, overview)
        if not history or any(not history[-1]['item'].get(field) for field in
                              ('notebook_id', 'source_id', 'task_id', 'artifact_id', 'raw_sha256')):
            return MediaRunResult('waiting', 'Exact Short provider output retained; await Overview provenance before rendering')
        item['overview_provider_identity'] = {field: history[-1]['item'][field] for field in
                                              ('notebook_id', 'source_id', 'task_id', 'artifact_id', 'raw_sha256')}
        state.persist()

    final = _file(core.STATE_DIR, item.get('final_mp4'))
    manifest = _file(core.STATE_DIR, item.get('manifest_path'))
    local_output = bool(final and final.is_file() and manifest and manifest.is_file()
                        and item.get('technical_verified') is True)
    if not local_output or command['operation'] == 'rebuild':
        if item.get('upload_session_uri'):
            raise StateInvalid('UPLOAD_BYTES_UNAVAILABLE: restore exact immutable output before resuming existing session')
        raw = _file(core.STATE_DIR, item.get('raw_mp4'))
        if not raw or not raw.is_file() or core.sha256_file(raw) != item.get('raw_sha256'):
            expected = core.STATE_DIR / f"{item['id']}-notebooklm.mp4"
            if expected.exists() and core.sha256_file(expected) != item.get('raw_sha256'):
                expected.unlink()
            raw = core.download_artifact(state, item)
        if target.kind == 'short':
            native_failures = short.native_provider_short_failures(core.ffprobe(raw), item)
            if native_failures:
                item.update(status='rejected', technical_verified=False,
                    generation_rejection={'reason': 'native_short', 'attempt': attempt,
                                          'raw_sha256': item['raw_sha256'], 'artifact_id': item['artifact_id']})
                state.persist()
                raise StateInvalid('PROVIDER_MEDIA_REJECTED: exact completed native Short output failed its contract')
        engine.validate_and_manifest(state, item, raw)
    if item.get('technical_verified') is not True or item.get('status') == 'rejected':
        final = _file(core.STATE_DIR, item.get('final_mp4'))
        if final and final.is_file() and not core.validate_female_voice(final, item)[0]:
            item['generation_rejection'] = {'reason': 'voice', 'attempt': attempt,
                                           'raw_sha256': item['raw_sha256'], 'artifact_id': item['artifact_id']}
            state.persist()
        raise StateInvalid('TECHNICAL_REJECTION: output did not satisfy the publication gate')

    if target.kind == 'short':
        if not guard._short_origin_verified(item) or not guard._signature_verified(item):
            raise StateInvalid('SHORT_PROVENANCE_INVALID: independent origin and current signature evidence required')
    return MediaRunResult('output_ready', 'Exact output validated; archive and read back its bytes before publication')


def _publish(state, core, guard) -> MediaRunResult:
    item, target = state.item, state.context.target
    if item.get('technical_verified') is not True or item.get('status') == 'rejected':
        raise StateInvalid('TECHNICAL_REJECTION: output did not satisfy the publication gate')
    media = core.ffprobe(_file(core.STATE_DIR, item.get('final_mp4')))
    if not guard._signature_verified(dict(item, media=media)):
        raise StateInvalid('SIGNATURE_PROVENANCE_INVALID: current bytes must preserve source duration and audio')
    if target.kind == 'short' and not guard._short_origin_verified(item):
        raise StateInvalid('SHORT_PROVENANCE_INVALID: restored output requires independent origin and signature proof')
    # Editorial quality and licensing are independent of the technical/byte gates.
    # Never upgrade pending/rejected review evidence to APPROVED on a green render.
    require_owner_media_quality(item, target.kind)
    item['status'] = 'uploading' if item.get('upload_session_uri') else 'approved'
    state.persist()
    core.upload_only(slug=target.source.slug, item_id=item['id'], state=state)
    if not item.get('youtube_id'):
        raise StateInvalid('UPLOAD_RECEIPT_MISSING: worker success cannot replace a video ID')
    return MediaRunResult('uploaded', 'Exact upload receipt saved; independent controller verification remains required')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command_id')
    parser.add_argument('--phase', choices=('prepare', 'publish'), default='prepare')
    args = parser.parse_args(argv)
    try:
        admission = actions_admission(args.command_id, attach=True)
        result = run_media(admission.context, encryption_key=os.environ.get('NOTEBOOKLM_STATE_KEY', ''), phase=args.phase)
        receipt = 'preparation_result' if result.status == 'output_ready' else 'execution_result'
        admission.context.checkpoint(receipt, {'status': result.status, 'reason': result.reason}, phase='STARTED')
        if os.environ.get('GITHUB_OUTPUT'):
            with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as stream:
                stream.write('status=' + result.status + '\n')
        print(f'MEDIA_WORKER_{result.status.upper()}')
        # The workflow records immutable output-artifact references and calls
        # worker_entry finish afterward. A green process is not public completion.
        return 0
    except Exception as exc:
        print(f'MEDIA_WORKER_FAILED:{type(exc).__name__}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
