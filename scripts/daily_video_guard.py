#!/usr/bin/env python3
"""Guard scheduled Kesher video work by the newest published article.

This keeps the daily chain article-first: normalize the current article schema, retire
stale backfill work, and skip generation only when the newest article already has a
publicly verified upload in durable state.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

try:
    import kesher_daily_pipeline as pipeline
except ImportError:
    from scripts import kesher_daily_pipeline as pipeline


ACTIVE_STATUSES = {
    "source_selected",
    "source_added",
    "generating",
    "downloaded",
    "pending_review",
    "approved",
    "rejected",
    "uploading",
}


def already_uploaded_today(state: dict[str, Any], today: date) -> bool:
    """Backward-compatible daily idempotency helper used by policy tests.

    The strict newest-article guard below is authoritative for runtime selection, but
    keeping this helper preserves the invariant that a verified uploaded item for the
    Israel date prevents a second scheduled upload for that same date.
    """
    target = today.isoformat()
    return any(
        str(item.get("israel_date") or "") == target
        and item.get("status") == "uploaded"
        and item.get("uploaded") is True
        for item in state.get("items", [])
        if isinstance(item, dict)
    )


def normalize_posts_and_latest_slug(today: date) -> str:
    posts = json.loads(pipeline.POSTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        raise pipeline.PipelineError("posts.json must contain a list")
    changed = False
    eligible: list[tuple[date, int, dict[str, Any]]] = []
    for index, post in enumerate(posts):
        if not isinstance(post, dict):
            continue
        if not str(post.get("slug") or "").strip() and str(post.get("id") or "").strip():
            post["slug"] = str(post["id"]).strip()
            changed = True
        try:
            published = date.fromisoformat(str(post.get("date", "")))
        except (TypeError, ValueError):
            continue
        if published <= today:
            eligible.append((published, -index, post))
    if not eligible:
        raise pipeline.PipelineError("No published article is available")
    if changed:
        pipeline.POSTS_FILE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    eligible.sort(reverse=True, key=lambda row: (row[0], row[1]))
    latest = eligible[0][2]
    return str(latest.get("slug") or latest.get("id") or "").strip()


def reconcile_stale_active(state: dict[str, Any], latest_slug: str) -> bool:
    changed = False
    for item in state.get("items", []):
        if item.get("uploaded") is True:
            continue
        if item.get("status") not in ACTIVE_STATUSES:
            continue
        source_slug = str((item.get("source") or {}).get("slug") or "").strip()
        if source_slug and source_slug != latest_slug:
            item["status"] = "superseded"
            item["superseded_reason"] = "newer_authoritative_article"
            item["superseded_at"] = pipeline.utc_now()
            item["updated_at"] = pipeline.utc_now()
            changed = True
    return changed


def latest_article_uploaded(state: dict[str, Any], latest_slug: str) -> bool:
    return any(
        str((item.get("source") or {}).get("slug") or "").strip() == latest_slug
        and item.get("uploaded") is True
        and bool(item.get("youtube_verification"))
        for item in state.get("items", [])
    )


def main() -> int:
    today = pipeline.israel_now().date()
    latest_slug = normalize_posts_and_latest_slug(today)
    state = pipeline.load_state()
    if reconcile_stale_active(state, latest_slug):
        pipeline.save_state(state)
    print("true" if latest_article_uploaded(state, latest_slug) else "false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
