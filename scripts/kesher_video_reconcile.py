#!/usr/bin/env python3
"""Reconcile Kesher video state without abandoning a prior-day daily video.

The worker always finishes the single unresolved video item before starting a
new one. This lets a delayed Saturday/previous-day job recover after midnight
instead of being silently replaced by today's article.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

try:
    import kesher_daily_pipeline as pipeline
except ImportError:
    from scripts import kesher_daily_pipeline as pipeline

UNRESOLVED_STATUSES = {
    "source_selected", "source_added", "generating", "downloaded",
    "pending_review", "approved", "rejected", "uploading",
}
MAX_TECHNICAL_RETRIES = 3


def source_slug(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def posts() -> list[dict[str, Any]]:
    value = json.loads(pipeline.POSTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise pipeline.PipelineError("posts.json must contain a list")
    return [row for row in value if isinstance(row, dict)]


def authoritative_article() -> dict[str, Any]:
    today = pipeline.israel_now().date().isoformat()
    matches = [
        pipeline.source_metadata(post)
        for post in posts()
        if str(post.get("date") or "") == today
    ]
    if len(matches) != 1:
        raise pipeline.PipelineError(
            f"Expected exactly one authoritative article for {today}, found {len(matches)}"
        )
    return matches[0]


def current_source_snapshot(slug: str) -> dict[str, Any]:
    matches = [
        pipeline.source_metadata(post)
        for post in posts()
        if str(post.get("slug") or post.get("id") or "").strip() == slug
    ]
    if len(matches) != 1:
        raise pipeline.PipelineError(
            f"Expected exactly one published source for unresolved video {slug}, found {len(matches)}"
        )
    return matches[0]


def unresolved_items(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in state.get("items") or []
        if isinstance(item, dict)
        and item.get("uploaded") is not True
        and item.get("status") in UNRESOLVED_STATUSES
    ]


def retry_technical_rejection(state: dict[str, Any]) -> dict[str, Any] | None:
    rejected = [
        item for item in unresolved_items(state)
        if item.get("status") == "rejected" and item.get("technical_verified") is not True
    ]
    if not rejected:
        return None
    if len(rejected) != 1:
        raise pipeline.PipelineError(
            f"More than one unresolved technical rejection exists: {len(rejected)}"
        )
    old = rejected[0]
    slug = source_slug(old)
    if not slug:
        raise pipeline.PipelineError("Technical rejection has no source slug")
    source = current_source_snapshot(slug)
    if (old.get("source") or {}).get("content_sha256") != source["content_sha256"]:
        raise pipeline.PipelineError(
            f"Published source changed after video selection for {slug}"
        )
    retries = int(old.get("technical_retry_count") or 0)
    if retries >= MAX_TECHNICAL_RETRIES:
        raise pipeline.PipelineError(
            f"Technical retry limit reached for authoritative article {slug}"
        )

    old["status"] = "superseded"
    old["superseded_reason"] = "technical_retry_same_source"
    old["superseded_at"] = pipeline.utc_now()
    old["updated_at"] = pipeline.utc_now()

    replacement = pipeline.new_item(source)
    replacement["technical_retry_count"] = retries + 1
    replacement["retry_of"] = old.get("id")
    state.setdefault("items", []).append(replacement)
    return replacement


def prepare_generation() -> int:
    state = pipeline.load_state()
    existing = unresolved_items(state)
    if len(existing) > 1:
        raise pipeline.PipelineError(
            f"More than one unresolved video item exists: {len(existing)}"
        )
    replacement = retry_technical_rejection(state)
    if replacement:
        pipeline.save_state(state)
        print(
            "VIDEO_RECONCILED_GENERATION "
            f"slug={source_slug(replacement)} technical_retry=yes"
        )
        return 0

    remaining = unresolved_items(state)
    if remaining:
        item = remaining[0]
        print(
            "VIDEO_RECONCILED_GENERATION "
            f"slug={source_slug(item)} backlog_resume=yes status={item.get('status')}"
        )
        return 0

    source = authoritative_article()
    print(
        "VIDEO_RECONCILED_GENERATION "
        f"slug={source['slug']} backlog_resume=no technical_retry=no"
    )
    return 0


def advisory_outcome(item: dict[str, Any]) -> str:
    statuses = [item.get(f"{gate}_review_status") for gate in ("visual", "semantic", "metadata")]
    if statuses == ["approved", "approved", "approved"]:
        return "approved"
    if any(value == "rejected" for value in statuses):
        return "rejected"
    return "unavailable"


def recover_persisted_youtube_id(state: dict[str, Any], item: dict[str, Any]) -> bool:
    """Finish public verification after an earlier upload already returned its ID."""
    if not item.get("youtube_id") or item.get("uploaded") is True:
        return False
    token = pipeline.youtube_access_token()
    pipeline.verify_authenticated_channel(token)
    verification = pipeline.verify_public_upload(item, token)
    item["youtube_verification"] = verification
    item["youtube_url"] = f"https://www.youtube.com/watch?v={item['youtube_id']}"
    item["uploaded"] = True
    item["status"] = "uploaded"
    item["uploaded_at"] = pipeline.utc_now()
    item["updated_at"] = pipeline.utc_now()
    pipeline.save_state(state)
    print(
        "VIDEO_YOUTUBE_ID_RECOVERED "
        f"item={item.get('id')} youtube_id={item.get('youtube_id')}"
    )
    return True


def prepare_upload() -> int:
    state = pipeline.load_state()
    candidates = [
        item for item in unresolved_items(state)
        if item.get("technical_verified") is True
        and item.get("status") in {"pending_review", "approved", "rejected", "uploading"}
    ]
    if not candidates:
        print("VIDEO_RECONCILED_UPLOAD candidate=none")
        return 0
    if len(candidates) != 1:
        raise pipeline.PipelineError(
            f"More than one technically verified upload candidate exists: {len(candidates)}"
        )
    item = candidates[0]
    slug = source_slug(item)
    source = current_source_snapshot(slug)
    if (item.get("source") or {}).get("content_sha256") != source["content_sha256"]:
        raise pipeline.PipelineError(
            f"Published source changed before upload for {slug}"
        )
    if recover_persisted_youtube_id(state, item):
        return 0
    item["advisory_review_decision"] = advisory_outcome(item)
    item["review_is_advisory"] = True
    if item.get("status") != "uploading":
        item["status"] = "approved"
    item["updated_at"] = pipeline.utc_now()
    pipeline.save_state(state)
    print(
        "VIDEO_RECONCILED_UPLOAD "
        f"slug={slug} item={item.get('id')} advisory={item['advisory_review_decision']}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare-generation", action="store_true")
    mode.add_argument("--prepare-upload", action="store_true")
    args = parser.parse_args()
    if args.prepare_generation:
        return prepare_generation()
    return prepare_upload()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (pipeline.PipelineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"VIDEO_RECONCILE_BLOCKED {exc}")
        raise SystemExit(1)
