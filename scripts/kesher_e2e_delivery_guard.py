from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


SIGNATURE_DURATION_SECONDS = 3.0


def _source_identity(item: dict[str, Any]) -> tuple[str, str]:
    source = item.get("source") or {}
    return (
        str(source.get("slug") or source.get("id") or "").strip(),
        str(source.get("content_sha256") or "").strip(),
    )


def _signature_verified(item: dict[str, Any]) -> bool:
    """Require evidence for the approved full-screen three-second signature ending."""
    try:
        duration = float(item.get("signature_duration_seconds") or 0)
    except (TypeError, ValueError):
        return False
    return bool(
        item.get("signature_verified") is True
        and item.get("signature_fullscreen") is True
        and abs(duration - SIGNATURE_DURATION_SECONDS) < 0.001
        and str(item.get("signature_video_sha256") or "").strip()
    )


def short_public_portrait_verified(
    item: dict[str, Any],
    source: dict[str, str],
    *,
    youtube_verified: Callable[[dict[str, Any], str], bool],
) -> bool:
    """Require exact identity, public YouTube evidence, true 9:16 and signature proof."""
    if _source_identity(item) != (source["slug"], source["content_sha256"]):
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
    deliverables = {
        "article_url": str(article.get("url") or "").strip() or None,
        "overview_youtube_url": str(overview.get("youtube_url") or "").strip() or None,
        "short_youtube_url": str(short.get("youtube_url") or "").strip() or None,
        "short_portrait_verified": short.get("portrait_verified") is True,
        "short_signature_verified": short.get("signature_verified") is True,
    }
    ready = bool(
        article.get("live") is True
        and deliverables["article_url"]
        and overview.get("verified") is True
        and deliverables["overview_youtube_url"]
        and short.get("verified") is True
        and deliverables["short_youtube_url"]
        and deliverables["short_portrait_verified"]
        and deliverables["short_signature_verified"]
    )
    return ready, deliverables


def media_fingerprint(item: dict[str, Any]) -> str:
    """Stable fingerprint of real provider/publication progress, not poll timestamps."""
    payload = {
        "id": item.get("id"),
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
        "signature_verified": item.get("signature_verified"),
        "signature_duration_seconds": item.get("signature_duration_seconds"),
        "signature_fullscreen": item.get("signature_fullscreen"),
        "signature_video_sha256": item.get("signature_video_sha256"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
