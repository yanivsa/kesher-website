from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Callable


SIGNATURE_DURATION_SECONDS = 3.0
CANONICAL_OVERVIEW_PIPELINE = "remotion-v1-notebooklm-audio"
CANONICAL_SHORT_TYPE = "article_short"
CANONICAL_SHORT_PIPELINE = "remotion-v4-notebooklm-short-motion-plan-v1"
CANONICAL_SHORT_SOURCE_MODE = "direct-short"
ENHANCEMENT_REQUIRED_FOR_PUBLICATION = False


def _source_identity(item: dict[str, Any]) -> tuple[str, str]:
    source = item.get("source") or {}
    return (
        str(source.get("slug") or source.get("id") or "").strip(),
        str(source.get("content_sha256") or "").strip(),
    )


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _signature_timing_evidence(item: dict[str, Any]) -> bool:
    """A full background describes pixels, never proof of an in-content overlay."""
    return item.get("signature_overlay") is True


def _signature_verified(item: dict[str, Any]) -> bool:
    """Bind the end overlay to the exact current source, final and extracted segment."""
    proof = item.get("signature_provenance")
    if not isinstance(proof, dict) or proof.get("schema_version") != 1:
        return False
    hashes = {
        "final_sha256": item.get("final_sha256"),
        "raw_sha256": item.get("raw_sha256"),
        "asset_sha256": item.get("signature_sha256") or item.get("signature_asset_sha256"),
        "segment_sha256": item.get("signature_video_sha256"),
        "audio_source_sha256": item.get("raw_sha256"),
    }
    if any(not _sha256(value) or proof.get(key) != value for key, value in hashes.items()):
        return False
    try:
        source_duration = float(proof["source_duration_seconds"])
        final_duration = float(proof["final_duration_seconds"])
        start = float(proof["start_seconds"])
        end = float(proof["end_seconds"])
        duration = float(item["signature_duration_seconds"])
        raw_duration = float((item.get("provider_raw_media") or {})["duration"])
        media_duration = float((item.get("media") or {})["duration"])
        content_duration = float(item["short_duration_seconds"])
        source_start = float(item["short_start_seconds"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    values = (source_duration, final_duration, start, end, duration, raw_duration,
              media_duration, content_duration, source_start)
    return bool(
        all(math.isfinite(value) for value in values)
        and item.get("signature_verified") is True
        and _signature_timing_evidence(item)
        and source_duration > 0
        and source_start == 0
        and abs(duration - min(SIGNATURE_DURATION_SECONDS, source_duration)) <= 0.001
        and abs(source_duration - raw_duration) <= 0.001
        and abs(source_duration - content_duration) <= 0.001
        and abs(final_duration - media_duration) <= 0.001
        and abs(final_duration - source_duration) <= 0.15
        and abs(end - final_duration) <= 0.001
        and abs(start - max(0.0, end - duration)) <= 0.001
        and (item.get("media") or {}).get("audio_codec")
        and (item.get("provider_raw_media") or {}).get("audio_codec")
    )


def _short_origin_verified(item: dict[str, Any]) -> bool:
    """Require source/provider/raw independence as well as the native-first policy.

    overview_provider_identity must be copied from the authoritative Overview
    artifact by the controller. Missing historical evidence is not independence.
    """
    if not (
        item
        and item.get("type") == CANONICAL_SHORT_TYPE
        and item.get("source_mode") == CANONICAL_SHORT_SOURCE_MODE
        and item.get("visual_pipeline") == CANONICAL_SHORT_PIPELINE
        and not item.get("shared_provider_identity")
        and not item.get("adopted_from_long_item_id")
    ):
        return False
    overview = item.get("overview_provider_identity")
    identity_fields = ("notebook_id", "source_id", "task_id", "artifact_id", "raw_sha256")
    if not isinstance(overview, dict) or any(
        not isinstance(record.get(field), str) or not record[field].strip()
        for record in (item, overview) for field in identity_fields
    ):
        return False
    if not _sha256(item["raw_sha256"]) or not _sha256(overview["raw_sha256"]):
        return False
    if item["raw_sha256"] == overview["raw_sha256"]:
        return False
    if item["notebook_id"] == overview["notebook_id"]:
        if item["source_id"] == overview["source_id"]:
            return False
        if {item["task_id"], item["artifact_id"]} & {overview["task_id"], overview["artifact_id"]}:
            return False
    try:
        attempt = int(item["fresh_generation_attempt"])
        raw = item["provider_raw_media"]
        width, height = int(raw["width"]), int(raw["height"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    if width <= 0 or height <= 0 or attempt < 1 or attempt > 3:
        return False
    native = height > width and 0.53 <= width / height <= 0.60
    if item.get("provider_video_format") == "short" and native:
        return bool(item.get("provider_native_short") is True
                    and item.get("provider_native_short_verified") is True
                    and item.get("provider_short_fallback_used") is False)
    return bool(attempt == 3
                and item.get("provider_video_format") in {"short", "explainer"}
                and item.get("provider_short_fallback_used") is True
                and item.get("provider_native_short_verified") is native)


def overview_edit_verified(stage: dict[str, Any]) -> bool:
    """Verify canonical Overview edit evidence, fail-closed in production.

    Direct unit/legacy Runtime fixtures predate the production evidence marker.
    The stabilized production controller always sets overview_evidence_required,
    so a URL-only Overview can never satisfy the real production DoD.
    """
    evidence_fields = ("technical_verified", "visual_pipeline", "codec", "width", "height")
    has_evidence = any(field in stage for field in evidence_fields)
    if not has_evidence:
        return bool(
            stage.get("overview_evidence_required") is not True
            and stage.get("verified") is True
            and str(stage.get("youtube_url") or "").strip()
        )
    if stage.get("technical_verified") is not True:
        return False
    if str(stage.get("visual_pipeline") or "").strip() != CANONICAL_OVERVIEW_PIPELINE:
        return False
    if str(stage.get("codec") or "").strip().lower() != "h264":
        return False
    try:
        width = int(stage.get("width") or 0)
        height = int(stage.get("height") or 0)
    except (TypeError, ValueError):
        return False
    ratio = (width / height) if height else 0.0
    dimensions_verified = width == 1280 and height == 720 and 1.70 <= ratio <= 1.82
    if not dimensions_verified:
        return False

    if stage.get("overview_evidence_required") is True:
        try:
            content_duration = float(stage.get("content_duration_seconds") or 0)
            final_duration = float(stage.get("duration") or 0)
            signature_duration = float(stage.get("signature_duration_seconds") or 0)
        except (TypeError, ValueError):
            return False
        return bool(
            90.0 <= content_duration <= 180.0
            and abs(signature_duration - SIGNATURE_DURATION_SECONDS) < 0.001
            and _signature_timing_evidence(stage)
            and str(stage.get("signature_asset_sha256") or "").strip()
            and abs(final_duration - content_duration) <= 0.15
        )

    return True


def short_public_portrait_verified(
    item: dict[str, Any],
    source: dict[str, str],
    *,
    youtube_verified: Callable[[dict[str, Any], str], bool],
) -> bool:
    """Require exact identity, canonical Short origin, public YouTube evidence, true 9:16 and signature proof."""
    if _source_identity(item) != (source["slug"], source["content_sha256"]):
        return False
    if not _short_origin_verified(item):
        return False
    if not youtube_verified(item, source["slug"]):
        return False
    media = item.get("media") or {}
    try:
        width = int(media.get("width") or 0)
        height = int(media.get("height") or 0)
    except (TypeError, ValueError):
        return False
    return (
        width == 1080
        and height == 1920
        and height > width
        and _signature_verified(item)
    )


def delivery_contract(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """The cycle is done only when all three requested public deliverables satisfy DoD."""
    article = state.get("article") or {}
    overview = state.get("long_video") or {}
    short = state.get("short") or {}
    sig_verified = _signature_verified(short)
    origin_verified = _short_origin_verified(short)
    overview_verified = overview_edit_verified(overview)
    deliverables = {
        "article_url": str(article.get("url") or "").strip() or None,
        "overview_youtube_url": str(overview.get("youtube_url") or "").strip() or None,
        "short_youtube_url": str(short.get("youtube_url") or "").strip() or None,
        "overview_edit_verified": overview_verified,
        "short_portrait_verified": short.get("portrait_verified") is True,
        "short_signature_verified": sig_verified,
        "short_origin_verified": origin_verified,
    }
    ready = bool(
        article.get("live") is True
        and deliverables["article_url"]
        and overview.get("verified") is True
        and deliverables["overview_youtube_url"]
        and deliverables["overview_edit_verified"]
        and short.get("verified") is True
        and deliverables["short_youtube_url"]
        and deliverables["short_portrait_verified"]
        and deliverables["short_signature_verified"]
        and deliverables["short_origin_verified"]
    )
    return ready, deliverables


def media_fingerprint(item: dict[str, Any]) -> str:
    """Stable fingerprint of real provider/publication progress, not poll timestamps."""
    payload = {
        "id": item.get("id"),
        "type": item.get("type"),
        "source_mode": item.get("source_mode"),
        "status": item.get("status"),
        "last_provider_status": item.get("last_provider_status"),
        "task_id": item.get("task_id"),
        "artifact_id": item.get("artifact_id"),
        "raw_sha256": item.get("raw_sha256"),
        "technical_verified": item.get("technical_verified"),
        "final_sha256": item.get("final_sha256"),
        "uploaded": item.get("uploaded"),
        "youtube_id": item.get("youtube_id"),
        "youtube_verification": item.get("youtube_verification"),
        "visual_pipeline": item.get("visual_pipeline"),
        "media": item.get("media"),
        "signature_asset": item.get("signature_asset"),
        "signature_verified": item.get("signature_verified"),
        "signature_duration_seconds": item.get("signature_duration_seconds"),
        "signature_fullscreen": item.get("signature_fullscreen"),
        "signature_overlay": item.get("signature_overlay"),
        "signature_sha256": item.get("signature_sha256"),
        "signature_asset_sha256": item.get("signature_asset_sha256"),
        "signature_video_sha256": item.get("signature_video_sha256"),
        "signature_provenance": item.get("signature_provenance"),
        "render_input_sha256": item.get("render_input_sha256"),
        "overview_provider_identity": item.get("overview_provider_identity"),
        "provider_raw_media": item.get("provider_raw_media"),
        "provider_video_format": item.get("provider_video_format"),
        "fresh_generation_attempt": item.get("fresh_generation_attempt"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
