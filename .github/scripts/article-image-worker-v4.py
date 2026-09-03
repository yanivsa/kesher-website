#!/usr/bin/env python3
"""Best-effort trusted article image worker with a deterministic local terminal fallback.

External providers are optional enhancements. The terminal local provider reads
only versioned assets from the trusted ``main`` checkout and validates the real
bytes before use. Each semantic category has at least one repository-curated
landscape candidate, and runtime falls through candidates if one is missing or
invalid. Image failure never blocks publication of an otherwise valid article.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

V3_PATH = Path(__file__).with_name("article-image-worker-v3.py")
spec = importlib.util.spec_from_file_location("kesher_article_image_worker_v3", V3_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load image worker v3 from {V3_PATH}")
v3 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = v3
spec.loader.exec_module(v3)

core = v3.core
REPO_ROOT = Path(__file__).resolve().parents[2]

try_gemini = v3.try_gemini
try_unsplash = v3.try_unsplash
try_pexels = v3.try_pexels
summaries = v3.summaries
trusted_image_present = v3.trusted_image_present
commit_files = v3.commit_files

# All candidates are repository-versioned assets. Runtime still validates every
# byte and can fall through to a second candidate where one exists.
# Each category has distinct, non-overlapping curated fallback candidates.
LOCAL_FALLBACK_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "dating": [
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "שני אנשים בשיחה רגועה בשלב היכרות זוגית"),
        ("public/images/generated/blog/dating-second-chance-criteria.jpg", "מפגש היכרות נינוח בסביבה ביתית חמה"),
    ],
    "singles": [
        ("public/images/generated/blog/late-singleness-friends-moving-forward.jpg", "אדם בסיטואציה חברתית המתאימה לנושא רווקות וקשרים"),
        ("public/images/generated/blog/single-hood-family-dinners-pressure.jpg", "שיחה משפחתית רגועה המציגה התמודדות עם רווקות"),
    ],
    "relocation": [
        ("public/images/generated/blog/relocation-career-loss-and-dependence.jpg", "זוג בסיטואציה ביתית הקשורה לשינויי חיים ורילוקיישן"),
        ("public/images/generated/blog/relocation-language-barrier-isolation.jpg", "זוג בסלון הבית בדיון על הסתגלות ומעבר"),
        ("public/images/generated/blog/aliyah-couples-cultural-gaps.jpg", "זוג בשיחה על פערים תרבותיים, הסתגלות וגעגוע לאחר מעבר"),
    ],
    "premarital": [
        ("public/images/generated/blog/premarital-questions-before-wedding.jpg", "זוג בשיחה פתוחה סביב ציפיות ותכנון קשר"),
        ("public/images/generated/blog/marriage-preparation-money-fights.jpg", "זוג בדיון רגוע סביב תכנון תקציבי ונושאי חיים"),
    ],
    "parenting": [
        ("public/images/generated/blog/asking-for-help-without-yelling.jpg", "הורה וילד באינטראקציה ביתית תומכת"),
        ("public/images/generated/blog/breaking-the-yelling-cycle.jpg", "הורה וילד בסביבה ביתית רגועה ותומכת"),
    ],
    "gifted": [
        ("public/images/generated/blog/child-perfectionism-fear-of-failure.jpg", "ילד בסביבה לימודית עם נוכחות תומכת של מבוגר"),
        ("public/images/generated/blog/gifted-children-perfectionism-tears.jpg", "ילד ברגע לימודי רגשי הזקוק להכלה והדרכה"),
    ],
    "adhd": [
        ("public/images/generated/blog/adhd-first-grade-preparation.jpg", "הורה וילד מתארגנים יחד לקראת מסגרת לימודית"),
        ("public/images/generated/blog/adhd-and-screen-addiction-strategies.jpg", "ילד בסביבה ביתית המתאימה להדרכת הורים סביב קשב וויסות"),
        ("public/images/generated/blog/adhd-morning-routine.jpg", "ילד מתארגן בסביבה ביתית סביב שגרה, קשב ומשימות"),
    ],
    "couples": [
        ("public/images/generated/blog/defensiveness-in-relationships.jpg", "זוג בשיח כנה בסלון הבית סביב תקשורת זוגית"),
        ("public/images/generated/blog/couples-communication-distance.jpg", "זוג בסלון הבית בדיון רגוע על הקשבה וקרבה"),
    ],
}


def provider_preflight() -> dict[str, bool]:
    availability = {
        "gemini": bool((os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()),
        "unsplash": bool((os.environ.get("UNSPLASH_ACCESS_KEY") or "").strip()),
        "pexels": bool((os.environ.get("PEXELS_API_KEY") or "").strip()),
        "local": True,
    }
    print(
        "IMAGE_PROVIDER_PREFLIGHT "
        + " ".join(f"{name}={'configured' if ready else 'missing'}" for name, ready in availability.items()),
        file=sys.stderr,
        flush=True,
    )
    return availability


import hashlib


def collect_existing_hashes(repo_root: Path) -> set[str]:
    """Hash only hero bytes that are already assigned to published articles.

    Curated-but-unused local fallback files must remain eligible. Hashing every
    file in the blog directory makes each fallback collide with itself before
    it can ever be selected.
    """
    hashes: set[str] = set()
    posts_path = repo_root / "src" / "data" / "posts.json"
    try:
        posts = json.loads(posts_path.read_text(encoding="utf-8"))
    except Exception:
        return hashes
    for post in posts if isinstance(posts, list) else []:
        if not isinstance(post, dict):
            continue
        image = str(post.get("image") or "").strip()
        if not image.startswith("/images/"):
            continue
        path = repo_root / "public" / image.lstrip("/")
        if not path.is_file():
            continue
        try:
            hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
        except Exception:
            pass
    return hashes


def _trusted_candidate_path(source_path: str) -> Path:
    candidate_path = (REPO_ROOT / source_path).resolve()
    trusted_root = REPO_ROOT.resolve()
    if trusted_root != candidate_path and trusted_root not in candidate_path.parents:
        raise RuntimeError("Refusing local fallback path outside trusted checkout")
    return candidate_path


def local_fallback(
    repo: str,
    post: dict[str, Any],
    _head_ref: str,
    _token: str,
    attempts: list[str],
    *args: Any,
    existing_hashes: set[str] | None = None,
    **kwargs: Any,
) -> core.ImageCandidate | None:
    """Return the first valid curated landscape image from trusted main bytes."""
    attempts.append("local-curated")
    category = core.article_key(post)
    candidates = LOCAL_FALLBACK_CANDIDATES.get(category) or LOCAL_FALLBACK_CANDIDATES["couples"]
    failures: list[str] = []
    for source_path, description in candidates:
        try:
            candidate_path = _trusted_candidate_path(source_path)
            if not candidate_path.is_file():
                raise RuntimeError("missing")
            data = candidate_path.read_bytes()
            width, height, ext = core.validate_candidate(data)
            digest = hashlib.sha256(data).hexdigest()
            if existing_hashes and digest in existing_hashes:
                print(
                    f"IMAGE_LOCAL_FALLBACK_REJECTED category={category} path={source_path} reason=sha256_collision",
                    file=sys.stderr,
                    flush=True,
                )
                failures.append(f"{source_path}:sha256_collision")
                continue
            print(
                f"IMAGE_LOCAL_FALLBACK_READY category={category} path={source_path} dimensions={width}x{height}",
                file=sys.stderr,
                flush=True,
            )
            return core.ImageCandidate(
                "Local",
                data,
                ext,
                f"local://{source_path}",
                description,
                attempts.copy(),
            )
        except Exception as exc:
            failures.append(f"{source_path}:{type(exc).__name__}")
            print(
                f"IMAGE_LOCAL_FALLBACK_REJECTED category={category} path={source_path} error={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
    print(
        "IMAGE_LOCAL_FALLBACK_EXHAUSTED category=" + category + " errors=" + ", ".join(failures),
        file=sys.stderr,
        flush=True,
    )
    return None


def choose_candidate(
    repo: str,
    post: dict[str, Any],
    head_ref: str,
    token: str,
    *args: Any,
    existing_hashes: set[str] | None = None,
    **kwargs: Any,
) -> core.ImageCandidate | None:
    if existing_hashes is None:
        existing_hashes = collect_existing_hashes(REPO_ROOT)
    attempts: list[str] = []
    for provider in (try_gemini, try_unsplash, try_pexels):
        try:
            candidate = provider(post, attempts, existing_hashes=existing_hashes)
        except TypeError:
            candidate = provider(post, attempts)
        if candidate:
            return candidate
    try:
        return local_fallback(repo, post, head_ref, token, attempts, existing_hashes=existing_hashes)
    except TypeError:
        return local_fallback(repo, post, head_ref, token, attempts)


v3.local_fallback = local_fallback
v3.choose_candidate = choose_candidate
ensure_image = v3.ensure_image


def main() -> int:
    provider_preflight()
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
