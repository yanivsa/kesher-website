#!/usr/bin/env python3
"""Seed one exact Kesher article identity into durable long-video state.

This helper is used only by backlog recovery. It never guesses "latest": the
caller must supply the published article slug and its authoritative content
SHA-256. Existing exact work is resumed; unrelated unresolved work fails closed
instead of creating duplicate provider generations.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

if __package__:
    from . import kesher_daily_pipeline as pipeline
else:
    import kesher_daily_pipeline as pipeline

ACTIVE = {
    "source_selected",
    "source_added",
    "generating",
    "downloaded",
    "pending_review",
    "approved",
    "rejected",
    "uploading",
}


def exact_source(slug: str, content_sha256: str) -> dict[str, Any]:
    slug = str(slug or "").strip()
    content_sha256 = str(content_sha256 or "").strip().lower()
    if not slug or not content_sha256:
        raise pipeline.PipelineError("Exact target requires slug and content hash")
    if len(content_sha256) != 64 or any(ch not in "0123456789abcdef" for ch in content_sha256):
        raise pipeline.PipelineError("Exact target content hash is invalid")
    if not pipeline.POSTS_FILE.is_file():
        raise pipeline.PipelineError(f"Article source does not exist: {pipeline.POSTS_FILE}")
    raw = json.loads(pipeline.POSTS_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise pipeline.PipelineError("posts.json must contain a list")
    matches = [
        pipeline.source_metadata(post)
        for post in raw
        if isinstance(post, dict)
        and str(post.get("slug") or post.get("id") or "").strip() == slug
    ]
    if len(matches) != 1:
        raise pipeline.PipelineError(f"Exact target slug must resolve uniquely: {slug}")
    source = matches[0]
    if str(source.get("content_sha256") or "").lower() != content_sha256:
        raise pipeline.PipelineError(f"Exact target content hash mismatch for {slug}")
    return source


def seed_exact_target(slug: str, content_sha256: str) -> dict[str, Any]:
    source = exact_source(slug, content_sha256)
    state = pipeline.load_state()
    items = state.setdefault("items", [])
    exact = [
        item for item in items
        if isinstance(item, dict)
        and str((item.get("source") or {}).get("slug") or "") == source["slug"]
        and str((item.get("source") or {}).get("content_sha256") or "") == source["content_sha256"]
    ]
    if exact:
        chosen = exact[-1]
        print(
            "EXACT_VIDEO_TARGET_REUSED "
            f"slug={source['slug']} item={chosen.get('id')} status={chosen.get('status')}"
        )
        return chosen

    unrelated_unresolved = [
        item for item in items
        if isinstance(item, dict)
        and item.get("uploaded") is not True
        and str(item.get("status") or "") in ACTIVE
    ]
    if unrelated_unresolved:
        first = unrelated_unresolved[0]
        other = (first.get("source") or {}).get("slug") or first.get("id") or "unknown"
        raise pipeline.PipelineError(
            f"Cannot seed exact target while unrelated unresolved video exists: {other}"
        )

    item = pipeline.new_item(source)
    items.append(item)
    pipeline.save_state(state)
    print(f"EXACT_VIDEO_TARGET_SEEDED slug={source['slug']} item={item['id']}")
    return item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--content-sha256", required=True)
    args = parser.parse_args()
    seed_exact_target(args.slug, args.content_sha256)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (pipeline.PipelineError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"EXACT_VIDEO_TARGET_BLOCKED {exc}")
        raise SystemExit(1)
