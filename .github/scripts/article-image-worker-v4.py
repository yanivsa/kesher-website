#!/usr/bin/env python3
"""Trusted article image worker for Kesher Pipeline V4.

Runtime strategy:
1. Try several owned Gemini image-generation variants.
2. Try verified Pexels photography.
3. Try verified Pixabay photography when configured.
4. Fall back to a broad repository-curated pool of real photographs.

The worker never fabricates an abstract gradient/placeholder for production.
If no concrete image is available, it fails closed and lets the controller retry
or escalate instead of publishing a weak hero image.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import urllib.parse
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
try_pexels = v3.try_pexels
verify_pixels = v3.verify_pixels
summaries = v3.summaries
trusted_image_present = v3.trusted_image_present
commit_files = v3.commit_files

# Hand-curated anchors are preferred, while the runtime also discovers a much
# larger pool of existing real JPG assets by semantic filename hints.
LOCAL_FALLBACK_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "dating": [
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "שני אנשים בשיחה רגועה בשלב היכרות זוגית"),
        ("public/images/generated/blog/dating-second-chance-criteria.jpg", "מפגש היכרות נינוח בסביבה ביתית חמה"),
        ("public/images/generated/blog/dating-emotional-needs-vs-checklists.jpg", "שיחה אישית על צרכים וציפיות בתחילת קשר"),
        ("public/images/generated/blog/dating-fatigue-resilience.jpg", "אדם ברגע של מחשבה והתבוננות סביב מסע ההיכרויות"),
    ],
    "singles": [
        ("public/images/generated/blog/late-singleness-friends-moving-forward.jpg", "אדם בסיטואציה חברתית המתאימה לנושא רווקות וקשרים"),
        ("public/images/generated/blog/single-hood-family-dinners-pressure.jpg", "שיחה משפחתית רגועה המציגה התמודדות עם רווקות"),
        ("public/images/generated/blog/unspoken-expectations-in-relationships.jpg", "תמונה אווירתית על ציפיות, בחירות והרהור אישי סביב קשרים והחמצה"),
        ("public/images/generated/blog/dating-fatigue-resilience.jpg", "אדם המתמודד עם שחיקה רגשית במסע למציאת זוגיות"),
    ],
    "relocation": [
        ("public/images/generated/blog/relocation-career-loss-and-dependence.jpg", "זוג בסיטואציה ביתית הקשורה לשינויי חיים ורילוקיישן"),
        ("public/images/generated/blog/relocation-language-barrier-isolation.jpg", "זוג בסלון הבית בדיון על הסתגלות ומעבר"),
        ("public/images/generated/blog/aliyah-couples-cultural-gaps.jpg", "זוג בשיחה על פערים תרבותיים, הסתגלות וגעגוע לאחר מעבר"),
        ("public/images/generated/blog/relocation-couple-conversations-before-moving.jpg", "זוג משוחח בבית לקראת מעבר ושינוי משמעותי"),
    ],
    "premarital": [
        ("public/images/generated/blog/premarital-questions-before-wedding.jpg", "זוג בשיחה פתוחה סביב ציפיות ותכנון קשר"),
        ("public/images/generated/blog/marriage-preparation-money-fights.jpg", "זוג בדיון רגוע סביב תכנון תקציבי ונושאי חיים"),
        ("public/images/generated/blog/newlyweds-domestic-duties-sharing.jpg", "זוג בשיחה פתוחה בסלון הבית על חלוקת תפקידים בשנה הראשונה לנישואים"),
        ("public/images/generated/blog/newlywed-first-year-conflicts.jpg", "זוג צעיר בשיחה ביתית על הסתגלות לחיים משותפים"),
    ],
    "parenting": [
        ("public/images/generated/blog/asking-for-help-without-yelling.jpg", "הורה וילד באינטראקציה ביתית תומכת"),
        ("public/images/generated/blog/breaking-the-yelling-cycle.jpg", "הורה וילד בסביבה ביתית רגועה ותומכת"),
        ("public/images/generated/blog/first-grade-preparation-morning-routine.jpg", "הורה וילד מתארגנים יחד לקראת בית הספר"),
        ("public/images/generated/blog/separation-anxiety-morning-dropoff.jpg", "ילד והורה בסביבת מסגרת לימודית ברגע של תמיכה"),
    ],
    "gifted": [
        ("public/images/generated/blog/child-perfectionism-fear-of-failure.jpg", "ילד בסביבה לימודית עם נוכחות תומכת של מבוגר"),
        ("public/images/generated/blog/gifted-children-perfectionism-tears.jpg", "ילד ברגע לימודי רגשי הזקוק להכלה והדרכה"),
        ("public/images/generated/blog/gifted-children-first-days-adjustment.jpg", "ילד בסביבת לימודים חדשה עם תמיכה רגועה"),
    ],
    "adhd": [
        ("public/images/generated/blog/adhd-first-grade-preparation.jpg", "הורה וילד מתארגנים יחד לקראת מסגרת לימודית"),
        ("public/images/generated/blog/adhd-and-screen-addiction-strategies.jpg", "ילד בסביבה ביתית המתאימה להדרכת הורים סביב קשב וויסות"),
        ("public/images/generated/blog/separation-anxiety-morning-dropoff.jpg", "ילד והורה בסביבת מסגרת לימודית, מתאים לנושא קשב, הסתגלות והתארגנות"),
        ("public/images/generated/blog/adhd-morning-routine.jpg", "הורה וילד במהלך שגרת בוקר ביתית לקראת יום לימודים"),
    ],
    "couples": [
        ("public/images/generated/blog/defensiveness-in-relationships.jpg", "זוג בשיח כנה בסלון הבית סביב תקשורת זוגית"),
        ("public/images/generated/blog/couples-communication-distance.jpg", "זוג בסלון הבית בדיון רגוע על הקשבה וקרבה"),
        ("public/images/generated/blog/listening-in-relationships.jpg", "זוג בשיחה פנים אל פנים המדגישה הקשבה"),
        ("public/images/generated/blog/repairing-relationship-after-resentment.jpg", "זוג בשיחה רגועה על תיקון וקרבה בקשר"),
    ],
}

CATEGORY_FILENAME_HINTS: dict[str, tuple[str, ...]] = {
    "dating": ("dating-", "new-relationship", "navigating-new-relationships"),
    "singles": ("single-", "singleness", "late-singleness", "older-singles", "dating-fatigue"),
    "relocation": ("relocation-", "aliyah-", "returning-to-israel"),
    "premarital": ("premarital-", "before-wedding", "newlywed", "marriage-prep", "marriage-preparation"),
    "parenting": ("parenting-", "child-", "children-", "toddler-", "sibling-", "first-grade-", "school-", "separation-anxiety", "morning-routine"),
    "gifted": ("gifted-", "child-perfectionism"),
    "adhd": ("adhd-", "attention-", "executive-function"),
    "couples": ("couples-", "relationship-", "marriage-", "communication-", "intimacy-", "trust-", "mental-load", "money-fights", "silent-treatment", "defensiveness"),
}

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


def provider_preflight() -> dict[str, bool]:
    availability = {
        "gemini": bool((os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()),
        "pexels": bool((os.environ.get("PEXELS_API_KEY") or "").strip()),
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


def collect_existing_image_usage(repo_root: Path) -> tuple[set[str], dict[str, int], set[str]]:
    """Return assigned hero hashes, usage counts, and paths known to be abstract placeholders."""
    hashes: set[str] = set()
    usage: dict[str, int] = {}
    banned_paths: set[str] = set()
    posts_path = repo_root / "src" / "data" / "posts.json"
    try:
        posts = json.loads(posts_path.read_text(encoding="utf-8"))
    except Exception:
        return hashes, usage, banned_paths

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
    return hashes, usage, banned_paths


def collect_existing_hashes(repo_root: Path) -> set[str]:
    return collect_existing_image_usage(repo_root)[0]


def _trusted_candidate_path(source_path: str) -> Path:
    candidate_path = (REPO_ROOT / source_path).resolve()
    trusted_root = REPO_ROOT.resolve()
    if trusted_root != candidate_path and trusted_root not in candidate_path.parents:
        raise RuntimeError("Refusing local fallback path outside trusted checkout")
    return candidate_path


def _candidate_score(post: dict[str, Any], source_path: str) -> str:
    identity = str(post.get("slug") or post.get("id") or post.get("title") or "article")
    return hashlib.sha256(f"{identity}|{source_path}".encode("utf-8")).hexdigest()


def _dynamic_candidates(category: str, banned_paths: set[str]) -> list[tuple[str, str]]:
    hints = CATEGORY_FILENAME_HINTS.get(category, CATEGORY_FILENAME_HINTS["couples"])
    description = CATEGORY_DESCRIPTIONS.get(category, CATEGORY_DESCRIPTIONS["couples"])
    candidates: list[tuple[str, str]] = []

    generated_root = REPO_ROOT / "public" / "images" / "generated" / "blog"
    if generated_root.is_dir():
        # Historical generated/blog PNGs include the abstract placeholders that
        # caused the regression. Restrict automatic discovery here to JPGs.
        for path in sorted(generated_root.glob("*.jpg")):
            relative = path.relative_to(REPO_ROOT).as_posix()
            stem = path.stem.lower()
            if relative in banned_paths:
                continue
            if any(hint in stem for hint in hints):
                candidates.append((relative, description))

    bank_root = REPO_ROOT / "public" / "images" / "fallback" / category
    if bank_root.is_dir():
        # Assets in the managed fallback bank are generated and pixel-verified
        # by the trusted library builder, so JPEG and PNG are both eligible.
        for pattern in ("*.jpg", "*.jpeg", "*.png"):
            for path in sorted(bank_root.glob(pattern)):
                relative = path.relative_to(REPO_ROOT).as_posix()
                if relative not in banned_paths:
                    candidates.append((relative, description))

    return candidates


def _candidate_pool(post: dict[str, Any], banned_paths: set[str]) -> list[tuple[str, str]]:
    category = core.article_key(post)
    raw = list(LOCAL_FALLBACK_CANDIDATES.get(category) or LOCAL_FALLBACK_CANDIDATES["couples"])
    raw.extend(_dynamic_candidates(category, banned_paths))
    seen: set[str] = set()
    deduped: list[tuple[str, str]] = []
    for source_path, description in raw:
        if source_path in seen or source_path in banned_paths:
            continue
        seen.add(source_path)
        deduped.append((source_path, description))
    return sorted(deduped, key=lambda item: _candidate_score(post, item[0]))


def try_gemini_variants(
    post: dict[str, Any],
    attempts: list[str],
    existing_hashes: set[str] | None = None,
) -> core.ImageCandidate | None:
    """Try three materially different editorial framings before leaving owned generation."""
    variants = (
        "Visual direction: candid medium shot, natural eye-level interaction, warm daylight.",
        "Visual direction: wider environmental documentary frame with relevant home or cafe context.",
        "Visual direction: intimate but natural emotional moment, restrained expressions, realistic composition.",
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
    banned_paths: set[str] | None = None,
    **kwargs: Any,
) -> core.ImageCandidate | None:
    """Prefer unused real photos; when the pool is exhausted, reuse the least-used real photo."""
    attempts.append("local-curated")
    if existing_hashes is None or existing_usage is None or banned_paths is None:
        discovered_hashes, discovered_usage, discovered_banned = collect_existing_image_usage(REPO_ROOT)
        existing_hashes = discovered_hashes if existing_hashes is None else existing_hashes
        existing_usage = discovered_usage if existing_usage is None else existing_usage
        banned_paths = discovered_banned if banned_paths is None else banned_paths

    category = core.article_key(post)
    candidates = _candidate_pool(post, banned_paths)
    reusable: list[tuple[int, str, str, bytes, str]] = []
    failures: list[str] = []

    for source_path, description in candidates:
        try:
            candidate_path = _trusted_candidate_path(source_path)
            if not candidate_path.is_file():
                raise RuntimeError("missing")
            data = candidate_path.read_bytes()
            width, height, ext = core.validate_candidate(data)
            digest = hashlib.sha256(data).hexdigest()
            reuse_count = existing_usage.get(digest, 0)
            if digest not in existing_hashes:
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
            reusable.append((reuse_count, source_path, description, data, ext))
        except Exception as exc:
            failures.append(f"{source_path}:{type(exc).__name__}")
            print(
                f"IMAGE_LOCAL_FALLBACK_REJECTED category={category} path={source_path} error={type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )

    if reusable:
        reusable.sort(key=lambda row: (row[0], _candidate_score(post, row[1])))
        reuse_count, source_path, description, data, ext = reusable[0]
        print(
            f"IMAGE_LOCAL_FALLBACK_REUSE category={category} path={source_path} previous_uses={reuse_count}",
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
    discovered_hashes, existing_usage, banned_paths = collect_existing_image_usage(REPO_ROOT)
    if existing_hashes is None:
        existing_hashes = discovered_hashes
    attempts: list[str] = []

    for provider in (try_gemini_variants, try_pexels, try_pixabay):
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
        banned_paths=banned_paths,
    )


v3.local_fallback = local_fallback
v3.choose_candidate = choose_candidate
ensure_image = v3.ensure_image


def main() -> int:
    provider_preflight()
    return v3.main()


if __name__ == "__main__":
    raise SystemExit(main())
