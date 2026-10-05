#!/usr/bin/env python3
"""Build a small verified batch for the managed article fallback image bank.

This is intentionally cost-bounded: one dispatch creates at most eight assets
total, even when all categories are requested. Assets are generated with Gemini,
pixel-verified by the same trusted verifier as article heroes, and committed via
a reviewable pull request by the workflow.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "article-image-library.json"
WORKER_PATH = ROOT / ".github" / "scripts" / "article-image-worker-v4.py"
BANK_ROOT = ROOT / "public" / "images" / "fallback"
MANIFEST_PATH = BANK_ROOT / "manifest.json"


def load_worker():
    spec = importlib.util.spec_from_file_location("kesher_article_image_worker_v4_library", WORKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load trusted image worker from {WORKER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def all_existing_hashes() -> set[str]:
    hashes: set[str] = set()
    image_root = ROOT / "public" / "images"
    if not image_root.is_dir():
        return hashes
    for path in image_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        try:
            hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
        except OSError:
            pass
    return hashes


def category_count(category: str) -> int:
    root = BANK_ROOT / category
    if not root.is_dir():
        return 0
    return sum(1 for path in root.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png"})


def build_post(category: str, cfg: dict[str, Any], scene: str, ordinal: int) -> dict[str, str]:
    return {
        "id": f"fallback-library-{category}-{ordinal:03d}",
        "title": str(cfg["title_he"]),
        "category": str(cfg["category_he"]),
        "subcategory": str(cfg.get("subcategory_he") or ""),
        "excerpt": (
            f"{cfg['brief']} {scene} "
            "זו תמונת מאגר לשימוש עתידי, לכן יש להימנע מפרטים ייחודיים מדי ולשמור על סצנה אנושית שימושית ורב-תכליתית."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="all")
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, {})
    categories = config.get("categories") or {}
    if not isinstance(categories, dict) or not categories:
        raise RuntimeError("article-image-library config has no categories")

    max_batch = int(config.get("max_batch_size") or 8)
    batch_size = max(1, min(int(args.batch_size), max_batch))
    target = int(config.get("target_per_category") or 40)
    scenes = list(config.get("scene_variants") or [])
    if not scenes:
        raise RuntimeError("article-image-library config has no scene variants")

    if args.category == "all":
        selected = list(categories)
    elif args.category in categories:
        selected = [args.category]
    else:
        raise RuntimeError(f"Unknown category: {args.category}")

    if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is required for owned fallback-library generation")

    worker = load_worker()
    existing_hashes = all_existing_hashes()
    manifest = load_json(MANIFEST_PATH, {"version": 1, "assets": []})
    assets = manifest.setdefault("assets", [])
    produced = 0
    stalled_rounds = 0

    while produced < batch_size:
        progress = False
        for category in selected:
            if produced >= batch_size:
                break
            current = category_count(category)
            if current >= target:
                continue

            cfg = categories[category]
            ordinal = current + 1
            scene = scenes[(ordinal - 1) % len(scenes)]
            post = build_post(category, cfg, scene, ordinal)
            attempts: list[str] = []
            candidate = worker.try_gemini_variants(post, attempts, existing_hashes=existing_hashes)
            if candidate is None:
                print(f"LIBRARY_GENERATION_MISS category={category} ordinal={ordinal} attempts={attempts}", file=sys.stderr)
                continue

            width, height, ext = worker.core.validate_candidate(candidate.data)
            digest = hashlib.sha256(candidate.data).hexdigest()
            if digest in existing_hashes:
                print(f"LIBRARY_DUPLICATE_REJECTED category={category} sha256={digest}", file=sys.stderr)
                continue

            destination = BANK_ROOT / category / f"{category}-{ordinal:03d}-{digest[:10]}.{ext}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(candidate.data)
            relative = destination.relative_to(ROOT).as_posix()

            assets.append({
                "path": relative,
                "category": category,
                "provider": candidate.provider,
                "source_url": candidate.source_url,
                "visual_match": candidate.visual_match,
                "sha256": digest,
                "width": width,
                "height": height,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            })
            existing_hashes.add(digest)
            produced += 1
            progress = True
            print(f"LIBRARY_ASSET_READY category={category} path={relative} dimensions={width}x{height}")

        if progress:
            stalled_rounds = 0
        else:
            stalled_rounds += 1
            if stalled_rounds >= 2:
                break

    BANK_ROOT.mkdir(parents=True, exist_ok=True)
    manifest["target_per_category"] = target
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = {category: category_count(category) for category in categories}
    print("LIBRARY_COUNTS " + " ".join(f"{key}={value}" for key, value in counts.items()))
    print(f"LIBRARY_BATCH_COMPLETE produced={produced} requested={batch_size}")
    return 0 if produced > 0 or all(counts[c] >= target for c in selected) else 2


if __name__ == "__main__":
    raise SystemExit(main())
