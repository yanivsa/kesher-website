#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTS_PATH = ROOT / "src" / "data" / "posts.json"
CORE_PATH = Path(__file__).with_name("article-image-worker.py")
CONTRACT_PATH = ROOT / "config" / "kesher-production-contract.json"
BANNED_SHA256 = {"12371ac5046f21d7874161fafe2d751ecbb3738c43b775062c23d1035a80dc67"}

spec = importlib.util.spec_from_file_location("kesher_article_image_validator_core", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load image validation core from {CORE_PATH}")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def reuse_policy() -> tuple[int, int]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    image = contract.get("image") if isinstance(contract, dict) else {}
    if not isinstance(image, dict):
        raise RuntimeError("Missing image policy in production contract")
    policy = str(image.get("local_fallback_policy") or "")
    cooldown_days = int(image.get("local_fallback_reuse_cooldown_days") or 0)
    max_uses = int(image.get("local_fallback_max_lifetime_uses") or 0)
    if policy != "unique-only-never-reuse-published-hero" or cooldown_days != 0 or max_uses != 1:
        raise RuntimeError("Invalid unique-only hero policy")
    return cooldown_days, max_uses


def _parse_date(value: object) -> date | None:
    raw = str(value or "").strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def unique_enforcement_start_date() -> date:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    image = contract.get("image") if isinstance(contract, dict) else {}
    raw = str(image.get("hero_unique_enforcement_start_date") or "") if isinstance(image, dict) else ""
    parsed = _parse_date(raw)
    if parsed is None:
        raise RuntimeError("Invalid hero uniqueness enforcement start date")
    return parsed


def validate_hash_reuse(
    digest: str,
    uses: list[dict[str, object]],
    *,
    cooldown_days: int,
    max_uses: int,
) -> list[str]:
    del cooldown_days, max_uses
    if len(uses) <= 1:
        return []
    cutoff = unique_enforcement_start_date()
    dated: list[tuple[date, str]] = []
    for use in uses:
        pid = str(use.get("id") or "<unknown>")
        parsed = _parse_date(use.get("date"))
        if parsed is None:
            return [f"hero pixel reuse has missing publication date: {digest} includes {pid}"]
        dated.append((parsed, pid))
    if all(published < cutoff for published, _pid in dated):
        return []
    ids = ", ".join(pid for _published, pid in dated)
    return [
        f"hero pixels must be unique for articles on/after {cutoff.isoformat()}: "
        f"{digest} used by {ids}"
    ]


def main() -> int:
    posts = json.loads(POSTS_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []
    hash_uses: dict[str, list[dict[str, object]]] = {}
    seen_paths: dict[str, str] = {}
    cooldown_days, max_uses = reuse_policy()

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
        try:
            pixels = core.image_pixel_sha256(data)
        except Exception as exc:
            errors.append(f"{pid}: invalid hero pixels: {exc}")
            continue
        if digest in BANNED_SHA256:
            errors.append(f"{pid}: banned blue placeholder SHA-256")
        hash_uses.setdefault(pixels, []).append(
            {
                "id": pid,
                "date": post.get("date"),
                "imageProvider": post.get("imageProvider"),
                "imageSourceUrl": post.get("imageSourceUrl"),
                "imageIsFallback": post.get("imageIsFallback"),
            }
        )
        try:
            core.validate_candidate(data)
        except Exception as exc:
            errors.append(f"{pid}: invalid hero image: {exc}")
        if len(alt) < 20 or not re.search(r"[\u0590-\u05FF]", alt):
            errors.append(f"{pid}: imageAlt must be descriptive Hebrew text (20+ chars)")

    for digest, uses in hash_uses.items():
        errors.extend(
            validate_hash_reuse(
                digest,
                uses,
                cooldown_days=cooldown_days,
                max_uses=max_uses,
            )
        )

    if errors:
        print("ARTICLE_IMAGE_GUARD_FAILED", file=sys.stderr)
        for error in errors:
            print(" - " + error, file=sys.stderr)
        return 1
    print(f"ARTICLE_IMAGE_GUARD_OK posts={len(posts)} unique_sha={len(hash_uses)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
