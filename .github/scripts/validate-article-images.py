#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTS_PATH = ROOT / "src" / "data" / "posts.json"
CORE_PATH = Path(__file__).with_name("article-image-worker.py")
BANNED_SHA256 = {"12371ac5046f21d7874161fafe2d751ecbb3738c43b775062c23d1035a80dc67"}

spec = importlib.util.spec_from_file_location("kesher_article_image_validator_core", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load image validation core from {CORE_PATH}")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

def main() -> int:
    posts = json.loads(POSTS_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    seen_hashes: dict[str, str] = {}
    seen_paths: dict[str, str] = {}

    for post in posts if isinstance(posts, list) else []:
        if not isinstance(post, dict):
            continue
        pid = str(post.get("id") or "<unknown>")
        image = str(post.get("image") or "").strip()
        alt = str(post.get("imageAlt") or "").strip()
        if not image.startswith("/images/"):
            errors.append(f"{pid}: missing or non-local image reference")
            continue
        if image in seen_paths:
            errors.append(f"{pid}: duplicate image path with {seen_paths[image]}: {image}")
        else:
            seen_paths[image] = pid
        path = ROOT / "public" / image.lstrip("/")
        if not path.is_file():
            errors.append(f"{pid}: image file does not exist: {path.relative_to(ROOT)}")
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in BANNED_SHA256:
            errors.append(f"{pid}: banned blue placeholder SHA-256")
        if digest in seen_hashes:
            errors.append(f"{pid}: duplicate hero SHA-256 with {seen_hashes[digest]}")
        else:
            seen_hashes[digest] = pid
        try:
            core.validate_candidate(data)
        except Exception as exc:
            errors.append(f"{pid}: invalid hero image: {exc}")
        if len(alt) < 20 or not re.search(r"[\u0590-\u05FF]", alt):
            errors.append(f"{pid}: imageAlt must be descriptive Hebrew text (20+ chars)")

    if errors:
        print("ARTICLE_IMAGE_GUARD_FAILED", file=sys.stderr)
        for error in errors:
            print(" - " + error, file=sys.stderr)
        return 1
    print(f"ARTICLE_IMAGE_GUARD_OK posts={len(posts)} unique_sha={len(seen_hashes)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
