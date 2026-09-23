"""Approved image providers and deterministic local fallback, without PR mutators.

Consolidated from the proven V3 pixel-verification and V4 local-render paths.
The canonical worker owns durable attempt fences and all Git/PR effects.
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import json
import os
import re
import struct
import sys
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from scripts.kesher_article_contract import image_dimensions as decoded_image_dimensions, image_pixel_sha256

MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
GEMINI_MODEL = 'gemini-3.1-flash-image'
VERIFY_MODEL = 'gemini-3.5-flash'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _read(request, *, timeout=20):
    # Provider keys must never follow a redirect to another origin. Downloads
    # also stay on the provider's known public image host and carry no keys.
    with urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if not data or len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError('Image response empty or exceeded size limit')
    return data


def request_json(method, url, *, headers=None):
    if method != 'GET' or urllib.parse.urlsplit(url).hostname not in {'api.unsplash.com', 'api.pexels.com'} or not url.startswith('https://'):
        raise ValueError('Unexpected stock provider endpoint')
    request = urllib.request.Request(url, method=method, headers={'User-Agent': 'kesher-canonical-image', **(headers or {})})
    return json.loads(_read(request))


def download(url):
    if not url.startswith('https://') or urllib.parse.urlsplit(url).hostname not in {'images.unsplash.com', 'images.pexels.com'}:
        raise ValueError('Unexpected stock image origin')
    return _read(urllib.request.Request(url, headers={'User-Agent': 'kesher-canonical-image'}))


@dataclass
class ImageCandidate:
    provider: str
    data: bytes
    extension: str
    source_url: str
    visual_match: str
    attempts: list[str]


def image_dimensions(data: bytes) -> tuple[int, int, str]:
    try:
        width, height = decoded_image_dimensions(data)
    except ValueError as exc:
        raise RuntimeError(f"Only valid PNG/JPEG images are accepted: {exc}") from exc
    # The shared decoder has already rejected every format except PNG/JPEG.
    return width, height, "png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "jpg"


def validate_candidate(data: bytes) -> tuple[int, int, str]:
    width, height, ext = image_dimensions(data)
    if width < 640 or height < 360:
        raise RuntimeError(f"image too small: {width}x{height}")
    ratio = width / height
    if ratio < 1.2 or ratio > 2.2:
        raise RuntimeError(f"image aspect ratio unsuitable for article hero: {ratio:.2f}")
    return width, height, ext


def candidate_is_duplicate(data: bytes, existing_hashes: set[str] | None) -> bool:
    return bool(existing_hashes and (hashlib.sha256(data).hexdigest() in existing_hashes
                or 'pixels:' + image_pixel_sha256(data) in existing_hashes))


def article_key(post: dict[str, Any]) -> str:
    text = " ".join(str(post.get(k) or "") for k in ("id", "title", "category", "subcategory", "excerpt")).lower()
    if any(x in text for x in ("דייט", "מציאת זוגיות", "dating", "היכרות")):
        return "dating"
    if any(x in text for x in ("רווק", "singleness", "single")):
        return "singles"
    if any(x in text for x in ("רילוקיישן", "עלייה", "relocation", "aliyah")):
        return "relocation"
    if any(x in text for x in ("נישוא", "premarital", "newlywed")):
        return "premarital"
    if any(x in text for x in ("קשב", "adhd")):
        return "adhd"
    if any(x in text for x in ("מחונ", "gifted")):
        return "gifted"
    if any(x in text for x in ("הור", "ילד", "parent", "child")):
        return "parenting"
    return "couples"


KEYWORD_QUERY_RULES: list[tuple[str, str]] = [
    (r"כסף|חשבון|כלכלי|הוצאות|פזרנ|חסכנ", "couple money finances budget conversation table"),
    (r"טלפון|מסך|הסחות דעת|אל הקיר|סמארטפון", "couple smartphone distraction living room disconnect"),
    (r"בגיד|אמון|שקר|לסדוק|לב שבור", "couple emotional reconciliation serious discussion daylight"),
    (r"התגוננ|האשמות|להתווכח|מריב", "couple honest talk conflict resolution calm"),
    (r"רווקות|שישי|ארוחת שישי|רווק|לחץ משפחתי", "thoughtful person reflection dining table warm light"),
    (r"שחיקה|דייטים|היכרויות|אפליקציות|כוונות", "young adult thoughtful coffee shop candid portrait"),
    (r"רילוקיישן|שפה|הגירה|עולים|זרות", "couple living room relocation moving boxes conversation"),
    (r"מחוננ|פרפקציוניזם|דף נקרע|תסכול", "parent comforting young child desk studying"),
    (r"הפרעת קשב|adhd|קשב|ילקוט|בוקר|פיג'מה", "parent helping young child morning routine school bag"),
    (r"כיתה א|מסגרת חדשה|מעבר לבית ספר", "parent child walking together school morning"),
    (r"עבודה|חמש אחר הצהריים|עייפות", "couple greeting home entrance evening reunion"),
    (r"דייט|היכרות|התקרבות|סמס", "two people coffee date outdoor seating authentic conversation"),
    (r"נישוא|חתונה|הכנה לנישואים", "engaged couple planning table smiling natural light"),
]


def stock_queries(post: dict[str, Any]) -> list[str]:
    text = " ".join([str(post.get(k) or "") for k in ("id", "title", "excerpt", "category", "subcategory")]).lower()
    queries: list[str] = []
    for pattern, query in KEYWORD_QUERY_RULES:
        if re.search(pattern, text, re.I):
            if query not in queries:
                queries.append(query)
    key = article_key(post)
    default_query = {
        "dating": "couple talking coffee date relationship",
        "singles": "adult friends conversation social",
        "relocation": "couple moving home boxes conversation",
        "premarital": "engaged couple planning together home",
        "parenting": "parent child supportive conversation home",
        "gifted": "parent child studying supportive",
        "adhd": "parent child school routine supportive",
        "couples": "couple talking listening relationship home",
    }.get(key, "couple talking listening relationship home")
    if default_query not in queries:
        queries.append(default_query)
    return queries


def stock_query(post: dict[str, Any]) -> str:
    return stock_queries(post)[0]


def image_prompt(post: dict[str, Any]) -> str:
    title = str(post.get("title") or "").strip()
    category = str(post.get("category") or "").strip()
    subcategory = str(post.get("subcategory") or "").strip()
    excerpt = str(post.get("excerpt") or "").strip()
    return (
        "Create one photorealistic editorial hero photograph for a Hebrew professional counseling article. "
        "Style: Authentic documentary editorial photography, 35mm lens, natural warm daylight, 16:9 landscape aspect ratio. "
        "Setting: Realistic everyday Israeli apartment, home kitchen, balcony, or neighborhood cafe. "
        "Subjects: Real Israeli people with natural, candid expressions and genuine emotional interaction. "
        "Strict rules: Absolutely no text, no captions, no logos, no watermarks, no illustrations, no 3D renders, "
        "no infographic diagrams, no surreal symbolism, no floating objects, no empty clinic rooms. "
        f"Article title: {title}. "
        f"Category: {category}{(' - ' + subcategory) if subcategory else ''}. "
        f"Context: {excerpt[:500]}"
    )


def google_key() -> str:
    return (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()


def google_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    key = google_key()
    if not key:
        raise RuntimeError("Gemini API key is unavailable")
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "User-Agent": "kesher-image-worker-v3",
        },
    )
    raw = _read(request, timeout=30)
    if not raw or len(raw) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("Gemini response empty or exceeded size limit")
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("Gemini response was not an object")
    return payload


def _parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    for candidate in payload.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content") or {}
        if isinstance(content, dict):
            parts.extend(part for part in (content.get("parts") or []) if isinstance(part, dict))
    return parts


def extract_generated_image(payload: dict[str, Any]) -> bytes | None:
    for part in reversed(_parts(payload)):
        block = part.get("inlineData") or part.get("inline_data")
        if isinstance(block, dict) and isinstance(block.get("data"), str):
            return base64.b64decode(block["data"])
    return None


def extract_text(payload: dict[str, Any]) -> str:
    return "\n".join(
        str(part.get("text") or "").strip()
        for part in _parts(payload)
        if str(part.get("text") or "").strip()
    ).strip()


def mime_for(ext: str) -> str:
    return "image/png" if ext == "png" else "image/jpeg"


def verify_pixels(post: dict[str, Any], data: bytes, ext: str) -> tuple[bool, str]:
    """Verify actual pixels. Never infer visual match from search metadata."""
    if not google_key():
        return False, "pixel verifier unavailable"
    prompt = (
        "Inspect the ACTUAL pixels of this candidate article hero image. "
        "Return exactly one line beginning MATCH| or REJECT|. "
        "MATCH only if it is a photorealistic landscape image with real people in a concrete, natural interaction "
        "that is visibly relevant to the article topic, without visible text/logo/infographic, abstract symbolism, "
        "or an empty-room-only composition. After MATCH| write a concrete Hebrew description of what is visibly in "
        "the image, at least 30 characters. Do not claim anything not visible. "
        f"Article title: {post.get('title','')}. Category: {post.get('category','')}. "
        f"Context: {str(post.get('excerpt') or '')[:500]}"
    )
    try:
        payload = google_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{VERIFY_MODEL}:generateContent",
            {
                "contents": [{
                    "parts": [
                        {"inline_data": {"mime_type": mime_for(ext), "data": base64.b64encode(data).decode("ascii")}},
                        {"text": prompt},
                    ]
                }]
            },
        )
        text = extract_text(payload)
    except Exception as exc:
        print(f"IMAGE_PIXEL_VERIFY_FAILED error={type(exc).__name__}", file=sys.stderr)
        return False, "pixel verification failed"
    if not text.startswith("MATCH|"):
        return False, text[:300] or "pixel verifier rejected candidate"
    description = text.split("|", 1)[1].strip()
    if len(description) < 30:
        return False, "pixel verifier returned an underspecified match"
    return True, description


def try_gemini(post: dict[str, Any], attempts: list[str], existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts.append("gemini")
    if not google_key():
        return None
    try:
        payload = google_json(
            f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent",
            {
                "contents": [{"parts": [{"text": image_prompt(post)}]}],
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                    "responseFormat": {"image": {"aspectRatio": "16:9"}},
                },
            },
        )
        data = extract_generated_image(payload)
        if not data:
            raise RuntimeError("Gemini returned no inline image")
        _w, _h, ext = validate_candidate(data)
        digest = hashlib.sha256(data).hexdigest()
        if candidate_is_duplicate(data, existing_hashes):
            print("IMAGE_PROVIDER_REJECTED provider=gemini reason=sha256_collision", file=sys.stderr)
            return None
        matched, description = verify_pixels(post, data, ext)
        if not matched:
            print("IMAGE_PROVIDER_REJECTED provider=gemini reason=pixel_mismatch", file=sys.stderr)
            return None
        return ImageCandidate(
            "Gemini", data, ext,
            f"https://ai.google.dev/gemini-api/docs/models/{GEMINI_MODEL}",
            description, attempts.copy(),
        )
    except Exception as exc:
        print(f"IMAGE_PROVIDER_FAILED provider=gemini error={type(exc).__name__}", file=sys.stderr)
        return None


def _stock_candidate(post: dict[str, Any], attempts: list[str], provider: str, existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    # Stock search metadata is not visual evidence. Without a pixel verifier we
    # skip stock entirely and use the repository-curated fallback.
    if not google_key():
        return None
    for query_text in stock_queries(post)[:2]:
        query = urllib.parse.quote(query_text)
        try:
            if provider == "unsplash":
                key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
                if not key:
                    return None
                result = request_json(
                    "GET",
                    f"https://api.unsplash.com/search/photos?query={query}&orientation=landscape&per_page=5",
                    headers={"Authorization": f"Client-ID {key}"},
                )
                rows = [
                    ((photo.get("urls") or {}).get("regular"), (photo.get("links") or {}).get("html"))
                    for photo in (result.get("results") or []) if isinstance(photo, dict)
                ]
                label = "Unsplash"
            else:
                key = os.environ.get("PEXELS_API_KEY", "").strip()
                if not key:
                    return None
                result = request_json(
                    "GET",
                    f"https://api.pexels.com/v1/search?query={query}&orientation=landscape&per_page=5",
                    headers={"Authorization": key},
                )
                rows = [
                    (((photo.get("src") or {}).get("large") or (photo.get("src") or {}).get("large2x")), photo.get("url"))
                    for photo in (result.get("photos") or []) if isinstance(photo, dict)
                ]
                label = "Pexels"
            for url, source in rows[:2]:
                if not url or not source:
                    continue
                data = download(str(url))
                _w, _h, ext = validate_candidate(data)
                digest = hashlib.sha256(data).hexdigest()
                if candidate_is_duplicate(data, existing_hashes):
                    print(f"IMAGE_STOCK_REJECTED provider={provider} reason=sha256_collision", file=sys.stderr)
                    continue
                matched, description = verify_pixels(post, data, ext)
                if matched:
                    return ImageCandidate(label, data, ext, str(source), description, attempts.copy())
        except Exception as exc:
            print(f"IMAGE_PROVIDER_FAILED provider={provider} error={type(exc).__name__}", file=sys.stderr)
    return None


def try_unsplash(post: dict[str, Any], attempts: list[str], existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts.append("unsplash")
    return _stock_candidate(post, attempts, "unsplash", existing_hashes)


def try_pexels(post: dict[str, Any], attempts: list[str], existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts.append("pexels")
    return _stock_candidate(post, attempts, "pexels", existing_hashes)


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
) -> ImageCandidate:
    """Create a unique deterministic local image when curated bytes are exhausted."""
    attempts.append("local-editorial")
    slug = str(post.get("slug") or post.get("id") or "article").strip()
    title = str(post.get("title") or slug).strip()
    identity = f"{slug}|{title}"
    used = existing_hashes or set()

    for variant in range(8):
        data = _render_editorial_png(identity, variant=variant)
        width, height, ext = validate_candidate(data)
        digest = hashlib.sha256(data).hexdigest()
        if candidate_is_duplicate(data, used):
            continue
        print(
            f"IMAGE_LOCAL_EDITORIAL_READY slug={slug} variant={variant} dimensions={width}x{height}",
            file=sys.stderr,
            flush=True,
        )
        return ImageCandidate(
            "LocalEditorial",
            data,
            ext,
            f"local-editorial://{slug}/{variant}",
            f"איור עריכתי מופשט בגוונים חמים עבור {title}",
            attempts.copy(),
        )
    raise RuntimeError("Unable to create a unique deterministic editorial fallback after 8 variants")


def curated_candidate(post, existing_hashes, root):
    root = Path(root).resolve()
    candidates = LOCAL_FALLBACK_CANDIDATES.get(article_key(post), LOCAL_FALLBACK_CANDIDATES['couples'])
    for source, description in candidates:
        path = (root / source).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        try:
            data = path.read_bytes()
            _, _, ext = validate_candidate(data)
            if candidate_is_duplicate(data, existing_hashes):
                continue
            return ImageCandidate('Local', data, ext, 'local://' + source, description, [])
        except (OSError, ValueError, RuntimeError):
            continue
    return None


def provider_functions(root):
    def adapt(function):
        def run(post, used):
            candidate = function(post, used)
            return asdict(candidate) if candidate else None
        return run
    return {
        'gemini': adapt(lambda post, used: try_gemini(post, [], used)),
        'unsplash': adapt(lambda post, used: try_unsplash(post, [], used)),
        'pexels': adapt(lambda post, used: try_pexels(post, [], used)),
        'local-curated': adapt(lambda post, used: curated_candidate(post, used, root)),
        'local-editorial': adapt(lambda post, used: generate_editorial_fallback(post, [], existing_hashes=used)),
    }
