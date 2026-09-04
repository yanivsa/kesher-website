from __future__ import annotations

import hashlib
import json
from typing import Any, Callable


def _source_identity(item: dict[str, Any]) -> tuple[str, str]:
    source = item.get("source") or {}
    return (
        str(source.get("slug") or source.get("id") or "").strip(),
        str(source.get("content_sha256") or "").strip(),
    )


def short_public_portrait_verified(
    item: dict[str, Any],
    source: dict[str, str],
    *,
    youtube_verified: Callable[[dict[str, Any], str], bool],
) -> bool:
    """Require exact article identity, public/succeeded YouTube evidence and a 9:16 file."""
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
    return width == 1080 and height == 1920 and height > width


def delivery_contract(state: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """The cycle is done only when the three requested public deliverables exist."""
    article = state.get("article") or {}
    overview = state.get("long_video") or {}
    short = state.get("short") or {}
    deliverables = {
        "article_url": str(article.get("url") or "").strip() or None,
        "overview_youtube_url": str(overview.get("youtube_url") or "").strip() or None,
        "short_youtube_url": str(short.get("youtube_url") or "").strip() or None,
        "short_portrait_verified": short.get("portrait_verified") is True,
    }
    ready = bool(
        article.get("live") is True
        and deliverables["article_url"]
        and overview.get("verified") is True
        and deliverables["overview_youtube_url"]
        and short.get("verified") is True
        and deliverables["short_youtube_url"]
        and deliverables["short_portrait_verified"]
    )
    return ready, deliverables


def media_fingerprint(item: dict[str, Any]) -> str:
    """Stable progress fingerprint; changes only when provider/publication evidence changes."""
    payload = {
        "id": item.get("id"),
        "status": item.get("status"),
        "updated_at": item.get("updated_at"),
        "task_id": item.get("task_id"),
        "artifact_id": item.get("artifact_id"),
        "technical_verified": item.get("technical_verified"),
        "uploaded": item.get("uploaded"),
        "youtube_id": item.get("youtube_id"),
        "youtube_verification": item.get("youtube_verification"),
        "final_sha256": item.get("final_sha256"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()
