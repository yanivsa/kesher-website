#!/usr/bin/env python3
"""Reconcile Kesher video state around the authoritative article of the Israel day.

This layer keeps the legacy video worker narrow while enforcing two production
rules owned by the controller architecture:
1. stale unfinished items from older articles may not block today's article;
2. Jules review is advisory, so a technically verified MP4 stays uploadable.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from typing import Any

try:
    import kesher_daily_pipeline as pipeline
except ImportError:
    from scripts import kesher_daily_pipeline as pipeline

ACTIVE_OR_REVIEW_STATUSES = {
    "source_selected", "source_added", "generating", "downloaded",
    "pending_review", "approved", "rejected", "uploading",
}
MAX_TECHNICAL_RETRIES = 3


def source_slug(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def authoritative_article() -> dict[str, Any]:
    posts = json.loads(pipeline.POSTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        raise pipeline.PipelineError("posts.json must contain a list")
    today = pipeline.israel_now().date().isoformat()
    matches: list[dict[str, Any]] = []
    for post in posts:
        if not isinstance(post, dict) or str(post.get("date") or "") != today:
            continue
        matches.append(pipeline.source_metadata(post))
    if len(matches) != 1:
        raise pipeline.PipelineError(
            f"Expected exactly one authoritative article for {today}, found {len(matches)}"
        )
    return matches[0]


def supersede_stale_items(state: dict[str, Any], expected_slug: str) -> int:
    changed = 0
    for item in state.get("items") or []:
        if not isinstance(item, dict) or item.get("uploaded") is True:
            continue
        if item.get("status") not in ACTIVE_OR_REVIEW_STATUSES:
            continue
        if source_slug(item) == expected_slug:
            continue
        item["status"] = "superseded"
        item["superseded_reason"] = "newer_authoritative_article"
        item["superseded_at"] = pipeline.utc_now()
        item["updated_at"] = pipeline.utc_now()
        changed += 1
    return changed


def retry_same_source_after_technical_rejection(
    state: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any] | None:
    rejected = [
        item for item in state.get("items") or []
        if isinstance(item, dict)
        and source_slug(item) == source["slug"]
        and item.get("uploaded") is not True
        and item.get("status") == "rejected"
        and item.get("technical_verified") is not True
    ]
    if not rejected:
        return None
    if len(rejected) != 1:
        raise pipeline.PipelineError(
            f"More than one technical rejection exists for {source['slug']}"
        )
    old = rejected[0]
    retries = int(old.get("technical_retry_count") or 0)
    if retries >= MAX_TECHNICAL_RETRIES:
        raise pipeline.PipelineError(
            f"Technical retry limit reached for authoritative article {source['slug']}"
        )
    if (old.get("source") or {}).get("content_sha256") != source["content_sha256"]:
        raise pipeline.PipelineError("Authoritative article changed after video selection")

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
    source = authoritative_article()
    stale = supersede_stale_items(state, source["slug"])
    replacement = retry_same_source_after_technical_rejection(state, source)
    if stale or replacement:
        pipeline.save_state(state)
    print(
        "VIDEO_RECONCILED_GENERATION "
        f"slug={source['slug']} stale_superseded={stale} "
        f"technical_retry={'yes' if replacement else 'no'}"
    )
    return 0


def advisory_outcome(item: dict[str, Any]) -> str:
    statuses = [item.get(f"{gate}_review_status") for gate in ("visual", "semantic", "metadata")]
    if statuses == ["approved", "approved", "approved"]:
        return "approved"
    if any(value == "rejected" for value in statuses):
        return "rejected"
    return "unavailable"


def prepare_upload() -> int:
    state = pipeline.load_state()
    source = authoritative_article()
    candidates = [
        item for item in state.get("items") or []
        if isinstance(item, dict)
        and source_slug(item) == source["slug"]
        and item.get("technical_verified") is True
        and item.get("uploaded") is not True
        and item.get("status") in {"pending_review", "approved", "rejected", "uploading"}
    ]
    if not candidates:
        print(f"VIDEO_RECONCILED_UPLOAD slug={source['slug']} candidate=none")
        return 0
    if len(candidates) != 1:
        raise pipeline.PipelineError(
            f"More than one technically verified upload candidate exists for {source['slug']}"
        )
    item = candidates[0]
    item["advisory_review_decision"] = advisory_outcome(item)
    item["review_is_advisory"] = True
    if item.get("status") != "uploading":
        item["status"] = "approved"
    item["updated_at"] = pipeline.utc_now()
    pipeline.save_state(state)
    print(
        "VIDEO_RECONCILED_UPLOAD "
        f"slug={source['slug']} item={item.get('id')} "
        f"advisory={item['advisory_review_decision']}"
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
