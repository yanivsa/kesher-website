#!/usr/bin/env python3
"""Reconcile Kesher Short/video state without duplicate generation.

Unresolved work is processed oldest-first. Multiple items form a durable FIFO
backlog instead of a fatal conflict. Jules review is advisory: a new YouTube
upload is permitted after machine technical verification of the exact
source/video identity. Provider polling resumes persisted IDs instead of
creating duplicate videos.

V4 adds a durable ``released_without_short`` tombstone. Four fresh generation
rounds are the maximum (initial + three technical retries). Once that budget is
exhausted, or the V4 controller explicitly releases the article, the slug is
persisted as released and is never selected for generation again.
"""

from __future__ import annotations

import argparse
import json
import os
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
PROVIDER_PROGRESS_STATUSES = {"source_selected", "source_added", "generating", "downloaded"}
RELEASED_STATUS = "released_without_short"
# Initial generation + three replacement generations = four fresh videos max.
MAX_TECHNICAL_RETRIES = 3


def workflow_output(name: str, value: str) -> None:
    """Expose a workflow decision without making pending provider work fail."""
    path = (os.environ.get("GITHUB_OUTPUT") or "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as output:
        output.write(f"{name}={value}\n")


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


def _mark_released(item: dict[str, Any], reason: str) -> None:
    item["status"] = RELEASED_STATUS
    item["uploaded"] = False
    item["release_reason"] = reason
    item["released_without_short_at"] = pipeline.utc_now()
    item["updated_at"] = pipeline.utc_now()


def release_without_short(slug: str, reason: str = "controller_bounded_release") -> int:
    """Persist a terminal no-Short result for one exact published article.

    If an item already exists, preserve its provider/upload identity as history
    but remove it from the unresolved FIFO. If no item exists, write a minimal
    tombstone containing the article source identity so future selection still
    treats this article as consumed.
    """
    slug = str(slug or "").strip()
    if not slug:
        raise pipeline.PipelineError("Release requires an exact article slug")
    source = current_source_snapshot(slug)
    state = pipeline.load_state()
    matches = [
        item
        for item in state.get("items") or []
        if isinstance(item, dict) and source_slug(item) == slug
    ]
    if matches:
        for item in matches:
            if item.get("uploaded") is True:
                # A public result already wins over a later release request.
                continue
            _mark_released(item, reason)
    else:
        state.setdefault("items", []).append({
            "id": f"short-release-{slug}-{source['content_sha256'][:10]}",
            "type": "short_release",
            "israel_date": pipeline.israel_now().date().isoformat(),
            "status": RELEASED_STATUS,
            "source": {
                key: value
                for key, value in source.items()
                if key not in {"body", "youtube_metadata"}
            },
            "uploaded": False,
            "release_reason": reason,
            "released_without_short_at": pipeline.utc_now(),
            "created_at": pipeline.utc_now(),
            "updated_at": pipeline.utc_now(),
        })
    pipeline.save_state(state)
    print(f"SHORT_RELEASED_WITHOUT_VIDEO slug={slug} reason={reason}")
    return 0


def retry_technical_rejection(state: dict[str, Any], old: dict[str, Any]) -> dict[str, Any] | None:
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
        _mark_released(old, "fresh_generation_budget_exhausted")
        return None

    old["status"] = "superseded"
    old["superseded_reason"] = "technical_retry_same_source"
    old["superseded_at"] = pipeline.utc_now()
    old["updated_at"] = pipeline.utc_now()

    replacement = pipeline.new_item(source)
    replacement["technical_retry_count"] = retries + 1
    replacement["fresh_generation_attempt"] = retries + 2
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
            if replacement is None:
                print(
                    "VIDEO_RECONCILED_GENERATION "
                    f"slug={source_slug(item)} released_without_short=yes fresh_attempts=4"
                )
                return 0
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
        workflow_output("ready", "false")
        print("VIDEO_RECONCILED_UPLOAD candidate=none")
        return 0

    item = unresolved[0]
    if item.get("youtube_id") and item.get("uploaded") is not True:
        if recover_persisted_youtube_id(state, item):
            workflow_output("ready", "false")
            return 0

    if not technical_publication_ready(item):
        # Provider progress is not a failed publication attempt. Preserve the
        # exact provider IDs and let the next poll resume the same task.
        if item.get("status") in PROVIDER_PROGRESS_STATUSES and item.get("technical_verified") is not True:
            workflow_output("ready", "false")
            print(
                "VIDEO_RECONCILED_UPLOAD candidate=pending "
                f"slug={source_slug(item)} status={item.get('status')} "
                f"task_id={item.get('task_id') or 'none'}"
            )
            return 0
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
    if prior_status not in {"approved", "uploading"}:
        item["status"] = "approved"
    item["updated_at"] = pipeline.utc_now()
    try:
        validate_upload_candidate(item)
    except Exception as exc:
        raise pipeline.PipelineError(f"Exact-evidence upload guard rejected candidate: {exc}") from exc
    pipeline.save_state(state)
    workflow_output("ready", "true")
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
    mode.add_argument("--release-without-short", metavar="SLUG")
    args = parser.parse_args()
    if args.prepare_generation:
        return prepare_generation()
    if args.prepare_upload:
        return prepare_upload()
    return release_without_short(str(args.release_without_short))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (pipeline.PipelineError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"VIDEO_RECONCILE_BLOCKED {exc}")
        raise SystemExit(1)
