"""Minimal NotebookLM source-video finish: keep every provider visual and audio packet's meaning.

The only visual change is the existing KESHER signature during the final three
seconds. No new scene, TTS voice, Adobe/Descript or Remotion is used.
Publishing remains in the existing canonical worker with exact artifact and
editorial approval gates. This renderer never uploads.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

OVERVIEW_PIPELINE = "notebooklm-native-signature-v1"
SHORT_PIPELINE = "notebooklm-native-short-signature-v1"


def native_render_requested() -> bool:
    """Native is default; old Remotion rendering is an explicit opt-in only."""
    import os

    mode = os.environ.get("KESHER_MEDIA_RENDERER", "notebooklm-native").strip()
    if mode not in {"notebooklm-native", "remotion"}:
        raise ValueError("KESHER_MEDIA_RENDERER_INVALID")
    return mode == "notebooklm-native"


def _identity_digest(core, raw_path: Path, item: dict, signature_path: Path, kind: str) -> str:
    payload = {
        "schema_version": 1,
        "renderer": OVERVIEW_PIPELINE if kind == "overview" else SHORT_PIPELINE,
        "raw_sha256": core.sha256_file(raw_path),
        "signature_sha256": core.sha256_file(signature_path),
        "source": {
            "slug": (item.get("source") or {}).get("slug"),
            "content_sha256": (item.get("source") or {}).get("content_sha256"),
        },
        "provider": {key: item.get(key) for key in
                     ("notebook_id", "source_id", "task_id", "artifact_id",
                      "fresh_generation_attempt", "provider_video_format",
                      "overview_provider_identity")},
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                      separators=(",", ":")).encode("utf-8")).hexdigest()


def render_native_provider(core, raw_path: Path, item: dict, *, kind: str,
                           signature_path: Path) -> Path:
    """Use the exact NotebookLM source, adding only an auditable end signature.

    Refuse previously conflicting output, unverified origin, wrong geometry or
    unexpected source bytes. Never fall back to Remotion or a second generation.
    """
    if kind not in {"overview", "short"}:
        raise core.PipelineError("NATIVE_MEDIA_KIND_INVALID")
    if not raw_path.is_file() or not raw_path.stat().st_size:
        raise core.PipelineError("NATIVE_MEDIA_SOURCE_MISSING")
    expected_source_sha = item.get("raw_sha256")
    source_sha = core.sha256_file(raw_path)
    if not isinstance(expected_source_sha, str) or source_sha != expected_source_sha:
        raise core.PipelineError("NATIVE_MEDIA_SOURCE_HASH_MISMATCH")
    if not signature_path.is_file() or not signature_path.stat().st_size:
        raise core.PipelineError("NATIVE_MEDIA_SIGNATURE_ASSET_MISSING")

    raw = core.ffprobe(raw_path)
    width, height = int(raw.get("width") or 0), int(raw.get("height") or 0)
    duration = float(raw.get("duration") or 0)
    if (not math.isfinite(duration) or duration <= 0 or raw.get("codec") != "h264"
            or not raw.get("audio_codec")):
        raise core.PipelineError("NATIVE_MEDIA_UNSUPPORTED_OR_SILENT")
    if kind == "overview":
        if width <= height or not 1.70 <= width / height <= 1.82:
            raise core.PipelineError("NATIVE_OVERVIEW_NOT_LANDSCAPE")
        item["content_duration_seconds"] = round(duration, 3)
    else:
        if (width != 1080 or height != 1920 or item.get("source_mode") != "direct-short"
                or item.get("provider_video_format") != "short"
                or item.get("provider_short_fallback_used") is not False):
            raise core.PipelineError("NATIVE_SHORT_NOT_PROVIDER_PORTRAIT")
        item["provider_native_short_verified"] = True
        item["short_start_seconds"] = 0.0
        item["short_duration_seconds"] = round(duration, 3)
    item["visual_pipeline"] = OVERVIEW_PIPELINE if kind == "overview" else SHORT_PIPELINE

    core.STATE_DIR.mkdir(parents=True, exist_ok=True)
    final_path = core.STATE_DIR / f"{item['id']}-native-final.mp4"
    render_identity = _identity_digest(core, raw_path, item, signature_path, kind)
    if final_path.exists():
        from scripts.kesher_e2e_delivery_guard import _signature_verified
        if (final_path.is_file()
                and item.get("render_input_sha256") == render_identity
                and item.get("final_sha256") == core.sha256_file(final_path)
                and _signature_verified(dict(item, media=core.ffprobe(final_path)))):
            return final_path
        raise core.PipelineError("NATIVE_OUTPUT_CONFLICT: existing bytes cannot be replaced")

    try:
        import cairosvg
    except ImportError as exc:
        raise core.PipelineError("NATIVE_SIGNATURE_RASTERIZER_MISSING") from exc

    logo = core.STATE_DIR / f"{item['id']}-native-signature.png"
    logo_width = max(240, round(width * (0.48 if kind == "overview" else 0.82)))
    cairosvg.svg2png(url=str(signature_path), write_to=str(logo),
                     output_width=logo_width)
    if not logo.is_file() or logo.stat().st_size == 0:
        raise core.PipelineError("NATIVE_SIGNATURE_RASTERIZATION_FAILED")

    start = max(0.0, duration - 3.0)
    # Source audio packets are stream-copied; the proof function independently
    # checks identical packet hashes and timestamps after remuxing.
    filter_graph = (
        f"[0:v]format=yuv420p,drawbox=x=0:y=0:w=iw:h=ih:"
        f"color=white@0.88:t=fill:enable='gte(t,{start:.6f})'[base];"
        f"[base][1:v]overlay=x=(main_w-overlay_w)/2:"
        f"y=(main_h-overlay_h)/2:enable='gte(t,{start:.6f})':"
        f"format=auto,format=yuv420p[v]"
    )
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-i", str(raw_path), "-loop", "1", "-framerate", "30", "-i", str(logo),
        "-filter_complex", filter_graph, "-map", "[v]", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
        "-t", f"{duration:.6f}", str(final_path),
    ]
    try:
        run = subprocess.run(command, capture_output=True, text=True,
                             timeout=1800, check=False)
        if run.returncode or not final_path.is_file() or final_path.stat().st_size < 1024:
            raise core.PipelineError(
                "NATIVE_SIGNATURE_OVERLAY_FAILED: " + (run.stderr or run.stdout)[-500:])
        from scripts.kesher_runtime.render_provenance import record_signature
        final_media = core.ffprobe(final_path)
        record_signature(core, raw_path, final_path, item, signature_path, raw, final_media)
        if core.sha256_file(raw_path) != source_sha:
            raise core.PipelineError("NATIVE_SOURCE_CHANGED_DURING_RENDER")
        item["render_input_sha256"] = render_identity
        item["enhancement_status"] = "enhancement_skipped"
        item["enhancement_render_mode"] = "native_source_signature_only"
        item["enhancement_assets_used"] = []
        item["enhancement_assets_dropped"] = []
        item["enhancement_fallback_reason"] = None
        return final_path
    except Exception:
        final_path.unlink(missing_ok=True)
        raise
    finally:
        logo.unlink(missing_ok=True)
