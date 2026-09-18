#!/usr/bin/env python3
"""Trusted article image worker for Kesher Pipeline V4.

Production strategy:
1. Try three materially different Gemini hero generations.
2. Try verified Pexels, Unsplash, and Pixabay photography.
3. Use a repository-curated reservoir with 40 real JPG candidates per category.
4. Respect a 90-day reuse cooldown for local fallback assets.
5. Never publish a generated abstract/gradient placeholder.

When no acceptable concrete image is available, the worker fails closed so the
controller can retry or escalate rather than weakening the public article.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.parse
from datetime import date
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
MANIFEST_PATH = REPO_ROOT / "config" / "article-image-fallback-manifest.json"

try_gemini = v3.try_gemini
try_unsplash = v3.try_unsplash
try_pexels = v3.try_pexels
verify_pixels = v3.verify_pixels
summaries = v3.summaries
trusted_image_present = v3.trusted_image_present
commit_files = v3.commit_files

CATEGORY_DESCRIPTIONS = {
    "dating": "צילום מציאותי של שיחה או מפגש אנושי המתאים להיכרות ולבניית קשר",
    "singles": "צילום מציאותי של אדם או אינטראקציה חברתית המתאימים לנושא רווקות וקשרים",
    "relocation": "צילום מציאותי של זוג או משפחה בתקופת מעבר, הסתגלות או רילוקיישן",
    "premarital": "צילום מציאותי של זוג צעיר בשיחה ותכנון לקראת חיים משותפים",
    "parenting": "צילום מציאותי של הורה וילד באינטראקציה ביתית או לימודית תומכת",
    "gifted": "צילום מציאותי של ילד בסביבה לימודית עם תמיכה רגישה של מבוגר",
    "adhd": "צילום מציאותי של הורה וילד סביב שגרה, לימודים, קשב והתארגנות",
    "couples": "צילום מציאותי של זוג בשיחה טבעית המדגישה תקשורת, קרבה והקשבה",
}

TOPIC_FILENAME_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"כיתה|בית ספר|ילקוט|בוקר|התארגנות", ("first-grade", "school", "morning", "adhd")),
    (r"מחונ|פרפקציונ", ("gifted", "perfectionism")),
    (r"קשב|adhd", ("adhd", "executive", "attention")),
    (r"רילוקיישן|עלייה|חזרה לארץ|הגירה", ("relocation", "aliyah", "returning-to-israel")),
    (r"דייט|היכרות|אפליקציות", ("dating", "new-relationship")),
    (r"רווק", ("single", "singleness", "dating-fatigue")),
    (r"חתונה|נישוא|מאורס", ("premarital", "wedding", "newlywed", "marriage-prep", "marriage-preparation")),
    (r"תקשורת|הקשבה|מריב|קונפליקט", ("communication", "listening", "relationship", "couples")),
)


def provider_preflight() -> dict[str, bool]:
    availability = {
        "gemini": bool((os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()),
        "pexels": bool((os.environ.get("PEXELS_API_KEY") or "").strip()),
        "unsplash": bool((os.environ.get("UNSPLASH_ACCESS_KEY") or "").strip()),
        "pixabay": bool((os.environ.get("PIXABAY_API_KEY") or "").strip()),
        "local": True,
    }
    print(
        "IMAGE_PROVIDER_PREFLIGHT "
        + " ".join(f"{name}={'configured' if ready else 'missing'}" for name, ready in availability.items()),
        file=sys.stderr,
        flush=True,
    )
    return availability


def load_manifest() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("target_per_category") != 40:
        raise RuntimeError("Article fallback manifest must target exactly 40 candidates per category")
    categories = manifest.get("categories") or {}
    required = {"dating", "singles", "relocation", "premarital", "parenting", "gifted", "adhd", "couples"}
    if set(categories) != required:
        raise RuntimeError("Article fallback manifest category set is incomplete")
    for category, block in categories.items():
        paths = list(block.get("primary") or []) + list(block.get("reserve") or [])
        if len(paths) < 40 or len(set(paths)) < 40:
            raise RuntimeError(f"Article fallback manifest category {category} has fewer than 40 unique candidates")
        if any(not str(path).lower().endswith(".jpg") for path in paths):
            raise RuntimeError(f"Article fallback manifest category {category} contains a non-JPG asset")
    return manifest


def collect_existing_image_usage(repo_root: Path) -> tuple[set[str], dict[str, int], dict[str, date], set[str]]:
    """Collect assigned hero hashes, use counts, last-use dates and banned placeholder paths."""
    hashes: set[str] = set()
    usage: dict[str, int] = {}
    last_used: dict[str, date] = {}
    banned_paths: set[str] = set()
    posts_path = repo_root / "src" / "data" / "posts.json"
    try:
        posts = json.loads(posts_path.read_text(encoding="utf-8"))
    except Exception:
        return hashes, usage, last_used, banned_paths

    for post in posts if isinstance(posts, list) else []:
        if not isinstance(post, dict):
            continue
        image = str(post.get("image") or "").strip()
        alt = str(post.get("imageAlt") or "").strip()
        if not image.startswith("/images/"):
            continue
        source_path = "public/" + image.lstrip("/")
        if "איור עריכתי מופשט" in alt or "תמונה זמנית" in alt:
            banned_paths.add(source_path)
        path = repo_root / source_path
        if not path.is_file():
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            continue
        hashes.add(digest)
        usage[digest] = usage.get(digest, 0) + 1
        try:
            used_on = date.fromisoformat(str(post.get("date") or "")[:10])
        except Exception:
            continue
        previous = last_used.get(digest)
        if previous is None or used_on > previous:
            last_used[digest] = used_on
    return hashes, usage, last_used, banned_paths


def collect_existing_hashes(repo_root: Path) -> set[str]:
    return collect_existing_image_usage(repo_root)[0]


def _trusted_candidate_path(source_path: str) -> Path:
    candidate_path = (REPO_ROOT / source_path).resolve()
    trusted_root = REPO_ROOT.resolve()
    if trusted_root != candidate_path and trusted_root not in candidate_path.parents:
        raise RuntimeError("Refusing local fallback path outside trusted checkout")
    return candidate_path


def _topic_score(post: dict[str, Any], source_path: str) -> int:
    text = " ".join(str(post.get(k) or "") for k in ("id", "title", "category", "subcategory", "excerpt")).lower()
    filename = Path(source_path).stem.lower()
    score = 0
    for pattern, hints in TOPIC_FILENAME_RULES:
        if re.search(pattern, text, re.I):
            score += sum(20 for hint in hints if hint in filename)
    return score


def _stable_tiebreak(post: dict[str, Any], source_path: str) -> str:
    identity = str(post.get("slug") or post.get("id") or post.get("title") or "article")
    return hashlib.sha256(f"{identity}|{source_path}".encode("utf-8")).hexdigest()


def _candidate_pool(post: dict[str, Any], banned_paths: set[str]) -> list[tuple[int, str]]:
    manifest = load_manifest()
    category = core.article_key(post)
    block = manifest["categories"][category]
    rows: list[tuple[int, str]] = []
    seen: set[str] = set()
    for tier, field in ((0, "primary"), (1, "reserve")):
        for source_path in block.get(field) or []:
            source_path = str(source_path)
            if source_path in seen or source_path in banned_paths:
                continue
            seen.add(source_path)
            rows.append((tier, source_path))
    return rows


def try_gemini_variants(
    post: dict[str, Any],
    attempts: list[str],
    existing_hashes: set[str] | None = None,
) -> core.ImageCandidate | None:
    """Use distinct compositions instead of repeating the same image request."""
    variants = (
        "Visual direction: candid medium shot, natural eye-level interaction, warm daylight.",
        "Visual direction: wider environmental documentary frame with relevant home, school, street or cafe context.",
        "Visual direction: intimate but natural emotional moment, restrained expressions, realistic editorial composition.",
    )
    for index, direction in enumerate(variants, start=1):
        variant_post = dict(post)
        excerpt = str(post.get("excerpt") or "")
        variant_post["excerpt"] = f"{direction} {excerpt}"
        before = len(attempts)
        candidate = try_gemini(variant_post, attempts, existing_hashes=existing_hashes)
        if len(attempts) == before:
            attempts.append(f"gemini-{index}")
        elif attempts[-1] == "gemini":
            attempts[-1] = f"gemini-{index}"
        if candidate:
            candidate.attempts = attempts.copy()
            return candidate
    return None


def try_pixabay(
    post: dict[str, Any],
    attempts: list[str],
    existing_hashes: set[str] | None = None,
) -> core.ImageCandidate | None:
    attempts.append("pixabay")
    key = os.environ.get("PIXABAY_API_KEY", "").strip()
    if not key or not v3.google_key():
        return None

    for query_text in core.stock_queries(post):
        query = urllib.parse.quote(query_text)
        try:
            result = core.request_json(
                "GET",
                "https://pixabay.com/api/"
                f"?key={urllib.parse.quote(key)}&q={query}&image_type=photo&orientation=horizontal"
                "&safesearch=true&min_width=1200&min_height=675&per_page=8",
            )
            for photo in result.get("hits") or []:
                if not isinstance(photo, dict):
                    continue
                url = photo.get("largeImageURL") or photo.get("webformatURL")
                source = photo.get("pageURL")
                if not url or not source:
                    continue
                data = core.download(str(url))
                _w, _h, ext = core.validate_candidate(data)
                digest = hashlib.sha256(data).hexdigest()
                if existing_hashes and digest in existing_hashes:
                    print("IMAGE_STOCK_REJECTED provider=pixabay reason=sha256_collision", file=sys.stderr)
                    continue
                matched, description = verify_pixels(post, data, ext)
                if matched:
                    return core.ImageCandidate(
                        "Pixabay",
                        data,
                        ext,
                        str(source),
                        description,
                        attempts.copy(),
                    )
        except Exception as exc:
            print(f"IMAGE_PROVIDER_FAILED provider=pixabay error={type(exc).__name__}", file=sys.stderr)
    return None


def local_fallback(
    repo: str,
    post: dict[str, Any],
    _head_ref: str,
    _token: str,
    attempts: list[str],
    *args: Any,
    existing_hashes: set[str] | None = None,
    existing_usage: dict[str, int] | None = None,
    last_used: dict[str, date] | None = None,
    banned_paths: set[str] | None = None,
    **kwargs: Any,
) -> core.ImageCandidate | None:
    """Select a real local photo, preferring unused assets and enforcing cooldown on reuse."""
    attempts.append("local-curated")
    if existing_hashes is None or existing_usage is None or last_used is None or banned_paths is None:
        discovered_hashes, discovered_usage, discovered_last_used, discovered_banned = collect_existing_image_usage(REPO_ROOT)
        existing_hashes = discovered_hashes if existing_hashes is None else existing_hashes
        existing_usage = discovered_usage if existing_usage is None else existing_usage
        last_used = discovered_last_used if last_used is None else last_used
        banned_paths = discovered_banned if banned_paths is None else banned_paths

    category = core.article_key(post)
    cooldown_days = int(load_manifest().get("policy", {}).get("cooldown_days", 90))
    today = date.today()
    unused: list[tuple[int, int, str, str, bytes, str]] = []
    reusable: list[tuple[int, int, int, str, str, bytes, str]] = []

    for tier, source_path in _candidate_pool(post, banned_paths):
        try:
            candidate_path = _trusted_candidate_path(source_path)
            if not candidate_path.is_file():
                continue
            data = candidate_path.read_bytes()
            _width, _height, ext = core.validate_candidate(data)
            digest = hashlib.sha256(data).hexdigest()
            score = _topic_score(post, source_path)
            description = CATEGORY_DESCRIPTIONS.get(category, CATEGORY_DESCRIPTIONS["couples"])
            if digest not in existing_hashes:
                unused.append((-score, tier, _stable_tiebreak(post, source_path), source_path, data, ext))
                continue

            last = last_used.get(digest)
            days_since = (today - last).days if last else cooldown_days
            if days_since >= cooldown_days:
                reusable.append((
                    tier,
                    existing_usage.get(digest, 0),
                    -score,
                    _stable_tiebreak(post, source_path),
                    source_path,
                    data,
                    ext,
                ))
        except Exception as exc:
            print(
                f"IMAGE_LOCAL_FALLBACK_REJECTED category={category} path={source_path} error={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )

    if unused:
        unused.sort()
        _neg_score, tier, _stable, source_path, data, ext = unused[0]
        print(
            f"IMAGE_LOCAL_FALLBACK_READY category={category} tier={tier} path={source_path}",
            file=sys.stderr,
            flush=True,
        )
        return core.ImageCandidate(
            "Local",
            data,
            ext,
            f"local://{source_path}",
            CATEGORY_DESCRIPTIONS.get(category, CATEGORY_DESCRIPTIONS["couples"]),
            attempts.copy(),
        )

    if reusable:
        reusable.sort()
        tier, prior_uses, _neg_score, _stable, source_path, data, ext = reusable[0]
        print(
            f"IMAGE_LOCAL_FALLBACK_REUSE category={category} tier={tier} path={source_path} previous_uses={prior_uses}",
            file=sys.stderr,
            flush=True,
        )
        return core.ImageCandidate(
            "Local",
            data,
            ext,
            f"local://{source_path}",
            CATEGORY_DESCRIPTIONS.get(category, CATEGORY_DESCRIPTIONS["couples"]),
            attempts.copy(),
        )

    print(
        f"IMAGE_LOCAL_FALLBACK_EXHAUSTED category={category} cooldown_days={cooldown_days}",
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
    discovered_hashes, existing_usage, last_used, banned_paths = collect_existing_image_usage(REPO_ROOT)
    if existing_hashes is None:
        existing_hashes = discovered_hashes
    attempts: list[str] = []

    for provider in (try_gemini_variants, try_pexels, try_unsplash, try_pixabay):
        try:
            candidate = provider(post, attempts, existing_hashes=existing_hashes)
        except TypeError:
            candidate = provider(post, attempts)
        if candidate:
            return candidate

    return local_fallback(
        repo,
        post,
        head_ref,
        token,
        attempts,
        existing_hashes=existing_hashes,
        existing_usage=existing_usage,
        last_used=last_used,
        banned_paths=banned_paths,
    )


v3.local_fallback = local_fallback
v3.choose_candidate = choose_candidate
ensure_image = v3.ensure_image


def main() -> int:
    provider_preflight()
    load_manifest()
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
