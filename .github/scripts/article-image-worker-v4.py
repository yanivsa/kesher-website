#!/usr/bin/env python3
"""Trusted article image worker with an inexhaustible local terminal fallback.

External providers are optional enhancements. Repository-curated images are
preferred when they are still unique. If that finite pool is exhausted, the
worker deterministically renders a clean 1200x675 editorial PNG from the article
identity using only the Python standard library. Image failure remains
publication-blocking under the production contract.
"""

from __future__ import annotations

import binascii
import hashlib
import importlib.util
import json
import os
import struct
import sys
import zlib
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
# byte and can fall through to another candidate before using the deterministic
# local editorial renderer.
LOCAL_FALLBACK_CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "dating": [
        ("public/images/generated/blog/dating-communication-early-stages.jpg", "שני אנשים בשיחה רגועה בשלב היכרות זוגית"),
        ("public/images/generated/blog/dating-second-chance-criteria.jpg", "מפגש היכרות נינוח בסביבה ביתית חמה"),
    ],
    "singles": [
        ("public/images/generated/blog/late-singleness-friends-moving-forward.jpg", "אדם בסיטואציה חברתית המתאימה לנושא רווקות וקשרים"),
        ("public/images/generated/blog/single-hood-family-dinners-pressure.jpg", "שיחה משפחתית רגועה המציגה התמודדות עם רווקות"),
        ("public/images/generated/blog/unspoken-expectations-in-relationships.jpg", "תמונה אווירתית על ציפיות, בחירות והרהור אישי סביב קשרים והחמצה"),
        ("public/images/generated/blog/dating-fatigue-resilience.jpg", "אדם המתמודד עם שחיקה רגשית במסע למציאת זוגיות"),
        ("public/images/generated/blog/dating-emotional-needs-vs-checklists.jpg", "סצנה זוגית שקטה על בחירות, צרכים וציפיות בקשר"),
    ],
    "relocation": [
        ("public/images/generated/blog/relocation-career-loss-and-dependence.jpg", "זוג בסיטואציה ביתית הקשורה לשינויי חיים ורילוקיישן"),
        ("public/images/generated/blog/relocation-language-barrier-isolation.jpg", "זוג בסלון הבית בדיון על הסתגלות ומעבר"),
        ("public/images/generated/blog/aliyah-couples-cultural-gaps.jpg", "זוג בשיחה על פערים תרבותיים, הסתגלות וגעגוע לאחר מעבר"),
    ],
    "premarital": [
        ("public/images/generated/blog/premarital-questions-before-wedding.jpg", "זוג בשיחה פתוחה סביב ציפיות ותכנון קשר"),
        ("public/images/generated/blog/marriage-preparation-money-fights.jpg", "זוג בדיון רגוע סביב תכנון תקציבי ונושאי חיים"),
        ("public/images/generated/blog/newlyweds-domestic-duties-sharing.jpg", "זוג בשיחה פתוחה בסלון הבית על חלוקת תפקידים בשנה הראשונה לנישואים"),
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
        ("public/images/generated/blog/separation-anxiety-morning-dropoff.jpg", "ילד והורה בסביבת מסגרת לימודית, מתאים לנושא קשב, הסתגלות והתארגנות"),
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


def collect_existing_hashes(repo_root: Path) -> set[str]:
    """Hash only hero bytes that are already assigned to published articles."""
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


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    checksum = binascii.crc32(kind + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", checksum)


def _render_editorial_png(identity: str, *, variant: int = 0) -> bytes:
    """Render a deterministic premium-style abstract 16:9 hero with stdlib only."""
    width, height = 1200, 675
    seed = hashlib.sha256(f"{identity}|{variant}".encode("utf-8")).digest()

    top = (238 + seed[0] % 12, 225 + seed[1] % 14, 214 + seed[2] % 18)
    bottom = (224 + seed[3] % 18, 207 + seed[4] % 20, 198 + seed[5] % 18)
    accent_a = (128 + seed[6] % 70, 82 + seed[7] % 70, 98 + seed[8] % 65)
    accent_b = (78 + seed[9] % 75, 112 + seed[10] % 70, 118 + seed[11] % 65)
    accent_c = (174 + seed[12] % 55, 126 + seed[13] % 55, 92 + seed[14] % 50)

    blobs = (
        (210 + seed[15] * 2, 150 + seed[16], 230 + seed[17], accent_a, 86),
        (760 + seed[18], 370 + seed[19] // 2, 250 + seed[20], accent_b, 72),
        (1020 - seed[21], 110 + seed[22] // 2, 170 + seed[23] // 2, accent_c, 58),
    )

    raw = bytearray()
    for y in range(height):
        raw.append(0)
        t = y * 255 // (height - 1)
        base = [
            (top[channel] * (255 - t) + bottom[channel] * t) // 255
            for channel in range(3)
        ]
        for x in range(width):
            horizontal = (x * 18 // (width - 1)) - 9
            pixel = [max(0, min(255, channel + horizontal)) for channel in base]
            for cx, cy, radius, color, strength in blobs:
                dx = x - cx
                dy = y - cy
                radius_sq = radius * radius
                distance_sq = dx * dx + dy * dy
                if distance_sq >= radius_sq:
                    continue
                weight = ((radius_sq - distance_sq) * strength) // radius_sq
                pixel = [
                    (pixel[channel] * (255 - weight) + color[channel] * weight) // 255
                    for channel in range(3)
                ]
            grain = ((x * 17 + y * 29 + seed[(x + y) % len(seed)]) % 7) - 3
            raw.extend(max(0, min(255, channel + grain)) for channel in pixel)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )


def generate_editorial_fallback(
    post: dict[str, Any],
    attempts: list[str],
    *,
    existing_hashes: set[str] | None = None,
) -> core.ImageCandidate:
    """Create a unique deterministic local image when curated bytes are exhausted."""
    attempts.append("local-editorial")
    slug = str(post.get("slug") or post.get("id") or "article").strip()
    title = str(post.get("title") or slug).strip()
    identity = f"{slug}|{title}"
    used = existing_hashes or set()

    for variant in range(8):
        data = _render_editorial_png(identity, variant=variant)
        width, height, ext = core.validate_candidate(data)
        digest = hashlib.sha256(data).hexdigest()
        if digest in used:
            continue
        print(
            f"IMAGE_LOCAL_EDITORIAL_READY slug={slug} variant={variant} dimensions={width}x{height}",
            file=sys.stderr,
            flush=True,
        )
        return core.ImageCandidate(
            "LocalEditorial",
            data,
            ext,
            f"local-editorial://{slug}/{variant}",
            f"איור עריכתי מופשט בגוונים חמים עבור {title}",
            attempts.copy(),
        )
    raise RuntimeError("Unable to create a unique deterministic editorial fallback after 8 variants")


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
    """Use curated trusted bytes first, then an inexhaustible local renderer."""
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
    return generate_editorial_fallback(post, attempts, existing_hashes=existing_hashes)


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
