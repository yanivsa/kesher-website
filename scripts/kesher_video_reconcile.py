#!/usr/bin/env python3
"""Reconcile Kesher video state without abandoning older daily work.

Unresolved videos are processed oldest-first. Multiple items form a durable
FIFO backlog instead of a fatal conflict. Jules review is advisory: a new
YouTube upload is permitted after machine technical verification of the exact
source/video identity.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

if __package__:
    from . import kesher_daily_pipeline as pipeline
    from .kesher_automation_policy import load_policy
    from .kesher_video_upload_guard import validate_candidate as validate_upload_candidate
else:
    import kesher_daily_pipeline as pipeline
    from kesher_automation_policy import load_policy
    from kesher_video_upload_guard import validate_candidate as validate_upload_candidate

UNRESOLVED_STATUSES = {
    "source_selected", "source_added", "generating", "downloaded",
    "pending_review", "approved", "rejected", "uploading",
}
MAX_TECHNICAL_RETRIES = 3


def source_slug(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def source_date(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(
        source.get("date")
        or item.get("israel_date")
        or item.get("created_at")
        or item.get("updated_at")
        or "9999-12-31"
    )


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
    rows = [
        item for item in state.get("items") or []
        if isinstance(item, dict)
        and item.get("uploaded") is not True
        and item.get("status") in UNRESOLVED_STATUSES
    ]
    return sorted(
        rows,
        key=lambda item: (
            source_date(item),
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        ),
    )


def retry_technical_rejection(state: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    if not (old.get("status") == "rejected" and old.get("technical_verified") is not True):
        raise pipeline.PipelineError("Technical retry requested for a non-technical rejection")
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
    if existing:
        item = existing[0]
        if item.get("status") == "rejected" and item.get("technical_verified") is not True:
            replacement = retry_technical_rejection(state, item)
            pipeline.save_state(state)
            print(
                "VIDEO_RECONCILED_GENERATION "
                f"slug={source_slug(replacement)} technical_retry=yes backlog_size={len(existing)}"
            )
            return 0
        print(
            "VIDEO_RECONCILED_GENERATION "
            f"slug={source_slug(item)} backlog_resume=yes status={item.get('status')} backlog_size={len(existing)}"
        )
        return 0

    source = authoritative_article()
    print(
        "VIDEO_RECONCILED_GENERATION "
        f"slug={source['slug']} backlog_resume=no technical_retry=no"
    )
    return 0


def technical_publication_ready(item: dict[str, Any]) -> bool:
    policy = load_policy()
    video_policy = policy["video"]
    if video_policy.get("publication_gate") != "technical" or video_policy.get("jules_is_advisory") is not True:
        raise pipeline.PipelineError("Video policy no longer declares technical publication with advisory Jules review")
    return bool(
        item.get("technical_verified") is True
        and item.get("status") in {"pending_review", "approved", "rejected", "uploading"}
        and item.get("final_sha256")
    )


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
    unresolved = unresolved_items(state)
    if not unresolved:
        print("VIDEO_RECONCILED_UPLOAD candidate=none")
        return 0

    item = unresolved[0]
    if item.get("youtube_id") and item.get("uploaded") is not True:
        if recover_persisted_youtube_id(state, item):
            return 0

    if not technical_publication_ready(item):
        raise pipeline.PipelineError(
            "Oldest unresolved video is not technically verified for publication"
        )

    slug = source_slug(item)
    source = current_source_snapshot(slug)
    if (item.get("source") or {}).get("content_sha256") != source["content_sha256"]:
        raise pipeline.PipelineError(
            f"Published source changed before upload for {slug}"
        )

    prior_status = item.get("status")
    item["review_gate"] = "advisory-jules"
    item["advisory_review_status_before_upload"] = prior_status
    # The canonical uploader historically accepts approved/uploading only.
    # Bridge that legacy state machine without treating Jules approval as a gate.
    if prior_status not in {"approved", "uploading"}:
        item["status"] = "approved"
    item["updated_at"] = pipeline.utc_now()
    try:
        validate_upload_candidate(item)
    except Exception as exc:
        raise pipeline.PipelineError(f"Exact-evidence upload guard rejected candidate: {exc}") from exc
    pipeline.save_state(state)
    print(
        "VIDEO_RECONCILED_UPLOAD "
        f"slug={slug} item={item.get('id')} gate=technical jules=advisory exact_evidence=yes"
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
