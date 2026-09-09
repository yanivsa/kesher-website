#!/usr/bin/env python3
"""Resolve safe, optional visual assets for Kesher Remotion enhancement.

The resolver is intentionally conservative. It can always return no assets.
Today it automatically reuses the exact article's repository-owned hero image
when available, and it can consume a pre-staged Jules/controller asset catalog.
It never makes publication depend on asset availability.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
POSTS_FILE = PROJECT_DIR / "src" / "data" / "posts.json"
CATALOG_NAME = "enhancement-assets.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_state_item(video_path: Path) -> dict[str, Any] | None:
    state_path = video_path.parent / "state.json"
    if not state_path.is_file():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    items = state.get("items") if isinstance(state, dict) else None
    if not isinstance(items, list):
        return None
    for item in reversed(items):
        if not isinstance(item, dict):
            continue
        if item.get("raw_mp4") == video_path.name:
            return item
        item_id = str(item.get("id") or "")
        if item_id and item_id in video_path.name:
            return item
    return None


def _source_record(item: dict[str, Any] | None) -> dict[str, Any]:
    if not item or not isinstance(item.get("source"), dict):
        return {}
    source = dict(item["source"])
    if source.get("image"):
        return source
    slug = str(source.get("slug") or source.get("id") or "").strip()
    if not slug or not POSTS_FILE.is_file():
        return source
    try:
        posts = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return source
    for post in posts if isinstance(posts, list) else []:
        if not isinstance(post, dict):
            continue
        if str(post.get("slug") or post.get("id") or "") == slug:
            merged = dict(post)
            merged.update(source)
            return merged
    return source


def source_identity(video_path: Path) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    item = _load_state_item(video_path)
    source = _source_record(item)
    slug = str(source.get("slug") or source.get("id") or "unknown")
    content_sha = str(source.get("content_sha256") or "")
    if not content_sha and video_path.is_file():
        content_sha = _sha256(video_path)
    item_id = str((item or {}).get("id") or video_path.stem)
    task_id = str((item or {}).get("task_id") or (item or {}).get("artifact_id") or "no-task")
    product = str((item or {}).get("type") or "video_overview")
    return f"{item_id}:{slug}:{content_sha}:{product}:{task_id}", item, source


def _repo_image_path(image_value: str) -> Path | None:
    value = image_value.strip()
    if not value or value.startswith("http://") or value.startswith("https://"):
        return None
    if value.startswith("/public/"):
        candidate = PROJECT_DIR / value.lstrip("/")
    elif value.startswith("public/"):
        candidate = PROJECT_DIR / value
    elif value.startswith("/"):
        candidate = PROJECT_DIR / "public" / value.lstrip("/")
    else:
        candidate = PROJECT_DIR / "public" / value
    try:
        candidate = candidate.resolve()
        public_root = (PROJECT_DIR / "public").resolve()
        candidate.relative_to(public_root)
    except (OSError, ValueError):
        return None
    return candidate if candidate.is_file() and candidate.stat().st_size > 0 else None


def _stage_repo_asset(source_path: Path, state_dir: Path) -> tuple[str, str]:
    digest = _sha256(source_path)
    suffix = source_path.suffix.lower() or ".asset"
    runtime_name = f"enhancement-{digest[:16]}{suffix}"
    target = state_dir / runtime_name
    if not target.is_file() or target.stat().st_size != source_path.stat().st_size:
        shutil.copyfile(source_path, target)
    return runtime_name, digest


def _timing(duration_seconds: float, profile: str) -> tuple[float, float]:
    duration = max(0.0, float(duration_seconds))
    if duration <= 1.0:
        return 0.0, duration
    if profile == "short_9_16":
        start = min(max(0.6, duration * 0.14), max(0.0, duration - 1.0))
        length = min(2.8, max(1.0, duration * 0.16))
    else:
        start = min(max(2.0, duration * 0.18), max(0.0, duration - 2.0))
        length = min(5.0, max(2.5, duration * 0.06))
    return round(start, 3), round(min(duration, start + length), 3)


def _catalog_candidates(
    state_dir: Path,
    *,
    identity: str,
    slug: str,
    profile: str,
) -> list[dict[str, Any]]:
    catalog_path = state_dir / CATALOG_NAME
    if not catalog_path.is_file():
        return []
    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = payload if isinstance(payload, list) else payload.get("assets", []) if isinstance(payload, dict) else []
    result: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("source_identity") not in {None, "", identity}:
            continue
        if entry.get("slug") not in {None, "", slug}:
            continue
        if entry.get("profile") not in {None, "", profile}:
            continue
        # Catalog entries must already have explicit approval/provenance. The
        # shared enhancement contract performs the final fail-closed filtering.
        result.append(dict(entry))
    return result


def resolve_asset_candidates(
    video_path: Path,
    *,
    duration_seconds: float,
    profile: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Return exact source identity plus zero-or-more safe candidate assets."""
    identity, _item, source = source_identity(video_path)
    state_dir = video_path.parent
    state_dir.mkdir(parents=True, exist_ok=True)
    slug = str(source.get("slug") or source.get("id") or "")
    candidates = _catalog_candidates(state_dir, identity=identity, slug=slug, profile=profile)

    image_value = str(source.get("image") or "").strip()
    hero = _repo_image_path(image_value) if image_value else None
    if hero:
        runtime_name, digest = _stage_repo_asset(hero, state_dir)
        start, end = _timing(duration_seconds, profile)
        candidates.append(
            {
                "asset_ref": runtime_name,
                "type": "image",
                "source": f"repo:{hero.relative_to(PROJECT_DIR).as_posix()}",
                "provenance": "repo-owned exact article hero image",
                "usage_status": "approved",
                "semantic_fit": 1.0,
                "sha256": digest,
                "start": start,
                "end": end,
                "intent": "reinforce the exact article topic with its approved hero visual",
            }
        )
    return identity, candidates
