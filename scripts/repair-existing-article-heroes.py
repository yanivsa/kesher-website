#!/usr/bin/env python3
"""Replace legacy abstract/placeholder article heroes with unique verified images.

This migration is intentionally separate from the runtime fallback worker:
- only articles that still carry a known placeholder imageAlt are targeted;
- each replacement is generated from that article's own title/category/excerpt;
- the same Gemini pixel verifier used in production must approve the pixels;
- every replacement SHA must be unique against all published heroes and against
  the other replacements in this run;
- no data or image file is written until every target has a verified candidate.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POSTS_PATH = ROOT / "src" / "data" / "posts.json"
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
IMAGE_DIR = ROOT / "public" / "images" / "generated" / "blog"
PLACEHOLDER_RE = re.compile(r"(איור עריכתי מופשט|תמונה זמנית|ממלאת מקום)")


def load_worker():
    spec = importlib.util.spec_from_file_location("kesher_article_image_worker_v4_migration", WORKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load trusted image worker from {WORKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def article_key(post: dict[str, Any]) -> str:
    raw = str(post.get("slug") or post.get("id") or "article").strip()
    cleaned = re.sub(r"[^\w\-\u0590-\u05FF]+", "-", raw, flags=re.UNICODE).strip("-")
    return cleaned or "article"


def main() -> int:
    posts = json.loads(POSTS_PATH.read_text(encoding="utf-8"))
    targets = [
        post for post in posts
        if isinstance(post, dict) and PLACEHOLDER_RE.search(str(post.get("imageAlt") or ""))
    ]
    if not targets:
        print("LEGACY_HERO_REPAIR_NOT_NEEDED")
        return 0

    worker = load_worker()
    existing_hashes = worker.collect_existing_hashes(ROOT)
    prepared: list[tuple[dict[str, Any], bytes, str, str, str]] = []

    for post in targets:
        attempts: list[str] = []
        candidate = worker.try_gemini_variants(post, attempts, existing_hashes=existing_hashes)
        if candidate is None:
            raise RuntimeError(
                f"No verified owned hero produced for {post.get('id')}; attempts={attempts}"
            )

        width, height, ext = worker.core.validate_candidate(candidate.data)
        digest = hashlib.sha256(candidate.data).hexdigest()
        if digest in existing_hashes:
            raise RuntimeError(f"Generated hero collision for {post.get('id')}: {digest}")
        existing_hashes.add(digest)

        key = article_key(post)
        filename = f"{key}-hero-v2-{digest[:10]}.{ext}"
        public_path = f"/images/generated/blog/{filename}"
        prepared.append((post, candidate.data, public_path, candidate.visual_match, digest))
        print(
            f"LEGACY_HERO_PREPARED id={post.get('id')} path={public_path} "
            f"dimensions={width}x{height} sha256={digest}"
        )

    # Commit to the working tree only after all target articles have a verified,
    # unique replacement. This keeps retries deterministic and avoids partial repair.
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for post, data, public_path, visual_match, digest in prepared:
        destination = ROOT / "public" / public_path.lstrip("/")
        if destination.exists() and hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"Refusing to overwrite different image bytes: {destination}")
        destination.write_bytes(data)
        post["image"] = public_path
        post["imageAlt"] = visual_match

    POSTS_PATH.write_text(
        json.dumps(posts, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )
    print(f"LEGACY_HERO_REPAIR_READY count={len(prepared)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
