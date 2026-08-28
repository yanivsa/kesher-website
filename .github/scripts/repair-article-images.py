#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
POSTS = ROOT / "src/data/posts.json"
SUMMARIES = ROOT / "src/data/postSummaries.json"
V4_PATH = Path(__file__).with_name("article-image-worker-v4.py")
BANNED_SHA256 = {"12371ac5046f21d7874161fafe2d751ecbb3738c43b775062c23d1035a80dc67"}

spec = importlib.util.spec_from_file_location("kesher_article_image_worker_v4_repair", V4_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {V4_PATH}")
v4 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v4
spec.loader.exec_module(v4)
core = v4.core

def image_path(post: dict[str, Any]) -> Path | None:
    ref = str(post.get("image") or "").strip()
    if not ref.startswith("/images/"):
        return None
    return ROOT / "public" / ref.lstrip("/")

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def image_problem(post: dict[str, Any], strict_dimensions: bool) -> str | None:
    path = image_path(post)
    if path is None:
        return "missing_image_field"
    if not path.is_file():
        return "missing_file"
    try:
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in BANNED_SHA256:
            return "banned_placeholder"
        if strict_dimensions:
            core.validate_candidate(data)
        else:
            core.image_dimensions(data)
    except Exception as exc:
        return f"invalid_image:{type(exc).__name__}"
    return None

def find_targets(posts: list[dict[str, Any]], scope: str) -> tuple[set[str], dict[str, str]]:
    strict_dimensions = scope == "all"
    targets: set[str] = set()
    reasons: dict[str, str] = {}
    seen: dict[str, str] = {}
    for post in posts:
        pid = str(post.get("id") or "")
        problem = image_problem(post, strict_dimensions)
        if problem:
            targets.add(pid); reasons[pid] = problem
            continue
        path = image_path(post)
        if not path:
            continue
        digest = sha(path)
        if digest in seen:
            targets.add(pid); reasons[pid] = f"duplicate_sha_of:{seen[digest]}"
        else:
            seen[digest] = pid
    return targets, reasons

def used_hashes(posts: list[dict[str, Any]], targets: set[str]) -> set[str]:
    hashes = set(BANNED_SHA256)
    for post in posts:
        if str(post.get("id") or "") in targets:
            continue
        path = image_path(post)
        if path and path.is_file():
            try:
                hashes.add(sha(path))
            except Exception:
                pass
    return hashes

def strong_alt(value: Any) -> bool:
    text = str(value or "").strip()
    return len(text) >= 20 and bool(re.search(r"[\u0590-\u05FF]", text))

def final_audit(posts: list[dict[str, Any]], strict_dimensions: bool) -> None:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for post in posts:
        pid = str(post.get("id") or "<unknown>")
        path = image_path(post)
        if path is None:
            errors.append(f"{pid}: image field missing/non-local"); continue
        if not path.is_file():
            errors.append(f"{pid}: file missing {path.relative_to(ROOT)}"); continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in BANNED_SHA256:
            errors.append(f"{pid}: banned placeholder sha256")
        if digest in seen:
            errors.append(f"{pid}: duplicate sha256 with {seen[digest]}")
        else:
            seen[digest] = pid
        try:
            if strict_dimensions:
                core.validate_candidate(data)
            else:
                core.image_dimensions(data)
        except Exception as exc:
            errors.append(f"{pid}: invalid hero {exc}")
        if not strong_alt(post.get("imageAlt")):
            errors.append(f"{pid}: weak/missing Hebrew imageAlt")
    if errors:
        print("ARTICLE_IMAGE_AUDIT_FAILED", file=sys.stderr)
        for err in errors:
            print(" - " + err, file=sys.stderr)
        raise SystemExit(1)
    print(f"ARTICLE_IMAGE_AUDIT_OK posts={len(posts)} unique_sha={len(seen)} strict_dimensions={strict_dimensions}")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope", choices=("critical", "all"), default="all")
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY", "yanivsa/kesher-website")
    token = os.environ.get("GITHUB_TOKEN", "")
    posts = json.loads(POSTS.read_text(encoding="utf-8"))
    targets, reasons = find_targets(posts, args.scope)
    if not targets:
        final_audit(posts, strict_dimensions=args.scope == "all")
        print("ARTICLE_IMAGE_REPAIR_NOOP")
        return 0

    print("ARTICLE_IMAGE_REPAIR_TARGETS " + json.dumps(reasons, ensure_ascii=False, sort_keys=True))
    used = used_hashes(posts, targets)
    failures: list[str] = []

    for post in posts:
        pid = str(post.get("id") or "")
        if pid not in targets:
            continue
        candidate = v4.choose_candidate(repo, post, "main", token, existing_hashes=used)
        if candidate is None:
            failures.append(f"{pid}: no unique candidate")
            continue
        width, height, ext = core.validate_candidate(candidate.data)
        digest = hashlib.sha256(candidate.data).hexdigest()
        if digest in used or digest in BANNED_SHA256:
            failures.append(f"{pid}: candidate sha collision")
            continue
        old_path = image_path(post)
        new_rel = Path("public/images/generated/blog") / f"{pid}.{ext}"
        new_path = ROOT / new_rel
        new_path.parent.mkdir(parents=True, exist_ok=True)
        new_path.write_bytes(candidate.data)
        if old_path and old_path != new_path and old_path.is_file():
            try:
                old_path.unlink()
            except OSError:
                pass
        post["image"] = "/" + str(new_rel.relative_to("public")).replace(os.sep, "/")
        post["imageAlt"] = candidate.visual_match
        used.add(digest)
        print(f"ARTICLE_IMAGE_REPAIRED id={pid} provider={candidate.provider} dimensions={width}x{height} sha256={digest}")

    if failures:
        print("ARTICLE_IMAGE_REPAIR_FAILED", file=sys.stderr)
        for failure in failures:
            print(" - " + failure, file=sys.stderr)
        return 1

    POSTS.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMMARIES.write_text(json.dumps(v4.summaries(posts), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    final_audit(posts, strict_dimensions=args.scope == "all")
    print(f"ARTICLE_IMAGE_REPAIR_COMPLETE repaired={len(targets)} scope={args.scope}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
