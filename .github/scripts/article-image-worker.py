#!/usr/bin/env python3
"""Trusted, idempotent article image worker for Kesher Pipeline v3.

Runs only from trusted main code. Provider fallthrough is deterministic:
Gemini -> Unsplash -> Pexels -> repository-curated local fallback. Provider
fallthrough is one worker attempt; scheduling/retry ownership remains with the
content controller.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

GEMINI_MODEL = "gemini-3.1-flash-image"
IMAGE_PREFIX = "public/images/generated/blog/"
PUBLIC_PREFIX = "/images/generated/blog/"
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024

# Existing repository images are the guaranteed final fallback. Each source is
# already versioned with the site and is copied to a unique article path.
LOCAL_FALLBACKS = {
    "dating": ("public/images/generated/blog/dating-communication-early-stages.jpg", "שני אנשים בשיחה רגועה בשלב היכרות זוגית"),
    "singles": ("public/images/generated/blog/late-singleness-friends-moving-forward.jpg", "אדם בסיטואציה חברתית המתאימה לנושא רווקות וקשרים"),
    "relocation": ("public/images/generated/blog/relocation-career-loss-and-dependence.jpg", "זוג בסיטואציה ביתית הקשורה לשינויי חיים ורילוקיישן"),
    "premarital": ("public/images/generated/blog/premarital-questions-before-wedding.jpg", "זוג בשיחה פתוחה סביב ציפיות ותכנון קשר"),
    "parenting": ("public/images/generated/blog/asking-for-help-without-yelling.jpg", "הורה וילד באינטראקציה ביתית תומכת"),
    "gifted": ("public/images/generated/blog/child-perfectionism-fear-of-failure.jpg", "ילד בסביבה לימודית עם נוכחות תומכת של מבוגר"),
    "adhd": ("public/images/generated/blog/adhd-first-grade-preparation.jpg", "הורה וילד מתארגנים יחד לקראת מסגרת לימודית"),
    "couples": ("public/images/generated/blog/defensiveness-in-relationships.jpg", "זוג בשיח כנה בסלון הבית סביב תקשורת זוגית"),
}


@dataclass
class ImageCandidate:
    provider: str
    data: bytes
    extension: str
    source_url: str
    visual_match: str
    attempts: list[str]


def request_json(method: str, url: str, token: str | None = None, body: Any = None, headers: dict[str, str] | None = None) -> Any:
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    merged = {"Accept": "application/vnd.github+json", "User-Agent": "kesher-image-worker"}
    if token:
        merged["Authorization"] = f"Bearer {token}"
    if body is not None:
        merged["Content-Type"] = "application/json"
    if headers:
        merged.update(headers)
    request = urllib.request.Request(url, data=payload, method=method, headers=merged)
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("response exceeded size limit")
    return json.loads(raw.decode("utf-8")) if raw else {}


def download(url: str, headers: dict[str, str] | None = None) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "kesher-image-worker", **(headers or {})})
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if not data or len(data) > MAX_DOWNLOAD_BYTES:
        raise RuntimeError("image download empty or too large")
    return data


def decode_content(payload: dict[str, Any]) -> bytes:
    return base64.b64decode(payload["content"].replace("\n", ""))


def github_content(repo: str, path: str, ref: str, token: str) -> dict[str, Any]:
    quoted = urllib.parse.quote(path, safe="/")
    encoded_ref = urllib.parse.quote(ref, safe="")
    result = request_json("GET", f"https://api.github.com/repos/{repo}/contents/{quoted}?ref={encoded_ref}", token)
    if not isinstance(result, dict):
        raise RuntimeError(f"Unexpected GitHub content response for {path}")
    return result


def posts_at(repo: str, ref: str, token: str) -> list[dict[str, Any]]:
    return json.loads(decode_content(github_content(repo, "src/data/posts.json", ref, token)).decode("utf-8"))


def image_dimensions(data: bytes) -> tuple[int, int, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return width, height, "png"
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(data):
                break
            length = struct.unpack(">H", data[index:index + 2])[0]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                height, width = struct.unpack(">HH", data[index + 3:index + 7])
                return width, height, "jpg"
            if length < 2:
                break
            index += length
    raise RuntimeError("Only valid PNG/JPEG images are accepted")


def validate_candidate(data: bytes) -> tuple[int, int, str]:
    width, height, ext = image_dimensions(data)
    if width < 640 or height < 360:
        raise RuntimeError(f"image too small: {width}x{height}")
    ratio = width / height
    if ratio < 1.2 or ratio > 2.2:
        raise RuntimeError(f"image aspect ratio unsuitable for article hero: {ratio:.2f}")
    return width, height, ext


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


def extract_image_block(value: Any) -> tuple[bytes, str] | None:
    if isinstance(value, dict):
        if value.get("type") == "image" and isinstance(value.get("data"), str):
            mime = str(value.get("mime_type") or value.get("mimeType") or "image/png")
            return base64.b64decode(value["data"]), mime
        for key in ("output_image", "outputImage"):
            block = value.get(key)
            if isinstance(block, dict) and isinstance(block.get("data"), str):
                mime = str(block.get("mime_type") or block.get("mimeType") or "image/png")
                return base64.b64decode(block["data"]), mime
        for child in value.values():
            found = extract_image_block(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in reversed(value):
            found = extract_image_block(child)
            if found:
                return found
    return None


def try_gemini(post: dict[str, Any], attempts: list[str], existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts.append("gemini")
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        payload = request_json(
            "POST",
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            body={
                "model": GEMINI_MODEL,
                "input": image_prompt(post),
                "response_format": {"type": "image", "mime_type": "image/jpeg", "aspect_ratio": "16:9"},
            },
            headers={"x-goog-api-key": key},
        )
        found = extract_image_block(payload)
        if not found:
            return None
        data, _mime = found
        _w, _h, ext = validate_candidate(data)
        digest = hashlib.sha256(data).hexdigest()
        if existing_hashes and digest in existing_hashes:
            print("IMAGE_PROVIDER_REJECTED provider=gemini reason=sha256_collision", file=sys.stderr)
            return None
        return ImageCandidate("Gemini", data, ext, f"https://ai.google.dev/gemini-api/docs/image-generation#{GEMINI_MODEL}", "תמונה פוטוריאליסטית שנוצרה ישירות מהכותרת והתקציר של המאמר", attempts.copy())
    except Exception as exc:
        print(f"IMAGE_PROVIDER_FAILED provider=gemini error={type(exc).__name__}", file=sys.stderr)
        return None


def try_unsplash(post: dict[str, Any], attempts: list[str], existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts.append("unsplash")
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        return None
    try:
        for query_text in stock_queries(post):
            q = urllib.parse.quote(query_text)
            result = request_json("GET", f"https://api.unsplash.com/search/photos?query={q}&orientation=landscape&per_page=5", headers={"Authorization": f"Client-ID {key}"})
            for photo in result.get("results", []):
                url = (photo.get("urls") or {}).get("regular")
                source = (photo.get("links") or {}).get("html")
                if not url or not source:
                    continue
                data = download(url)
                _w, _h, ext = validate_candidate(data)
                digest = hashlib.sha256(data).hexdigest()
                if existing_hashes and digest in existing_hashes:
                    print("IMAGE_PROVIDER_REJECTED provider=unsplash reason=sha256_collision", file=sys.stderr)
                    continue
                return ImageCandidate("Unsplash", data, ext, source, f"צילום נוף אופקי שנבחר בחיפוש ממוקד: {query_text}", attempts.copy())
    except Exception as exc:
        print(f"IMAGE_PROVIDER_FAILED provider=unsplash error={type(exc).__name__}", file=sys.stderr)
    return None


def try_pexels(post: dict[str, Any], attempts: list[str], existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts.append("pexels")
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        for query_text in stock_queries(post):
            q = urllib.parse.quote(query_text)
            result = request_json("GET", f"https://api.pexels.com/v1/search?query={q}&orientation=landscape&per_page=5", headers={"Authorization": key})
            for photo in result.get("photos", []):
                src = photo.get("src") or {}
                url = src.get("large") or src.get("large2x")
                source = photo.get("url")
                if not url or not source:
                    continue
                data = download(url)
                _w, _h, ext = validate_candidate(data)
                digest = hashlib.sha256(data).hexdigest()
                if existing_hashes and digest in existing_hashes:
                    print("IMAGE_PROVIDER_REJECTED provider=pexels reason=sha256_collision", file=sys.stderr)
                    continue
                return ImageCandidate("Pexels", data, ext, source, f"צילום נוף אופקי שנבחר בחיפוש ממוקד: {query_text}", attempts.copy())
    except Exception as exc:
        print(f"IMAGE_PROVIDER_FAILED provider=pexels error={type(exc).__name__}", file=sys.stderr)
    return None


def local_fallback(repo: str, post: dict[str, Any], head_ref: str, token: str, attempts: list[str], existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts.append("local-curated")
    source_path, description = LOCAL_FALLBACKS[article_key(post)]
    payload = github_content(repo, source_path, head_ref, token)
    data = decode_content(payload)
    _w, _h, ext = validate_candidate(data)
    digest = hashlib.sha256(data).hexdigest()
    if existing_hashes and digest in existing_hashes:
        print("IMAGE_LOCAL_FALLBACK_REJECTED reason=sha256_collision", file=sys.stderr)
        return None
    return ImageCandidate("Local", data, ext, f"local://{source_path}", description, attempts.copy())


def choose_candidate(repo: str, post: dict[str, Any], head_ref: str, token: str, existing_hashes: set[str] | None = None) -> ImageCandidate | None:
    attempts: list[str] = []
    for provider in (
        lambda p, att: try_gemini(p, att, existing_hashes),
        lambda p, att: try_unsplash(p, att, existing_hashes),
        lambda p, att: try_pexels(p, att, existing_hashes),
    ):
        candidate = provider(post, attempts)
        if candidate:
            return candidate
    return local_fallback(repo, post, head_ref, token, attempts, existing_hashes)


def summaries(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for post in posts:
        if not post.get("published", True):
            continue
        row = {k: post.get(k) for k in ("id", "title", "date", "category")}
        if post.get("subcategory"):
            row["subcategory"] = post["subcategory"]
        row["excerpt"] = post.get("excerpt")
        row["image"] = post.get("image")
        result.append(row)
    return result


def create_blob(repo: str, token: str, data: bytes, binary: bool = False) -> str:
    if binary:
        body = {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"}
    else:
        body = {"content": data.decode("utf-8"), "encoding": "utf-8"}
    return request_json("POST", f"https://api.github.com/repos/{repo}/git/blobs", token, body)["sha"]


def commit_files(repo: str, pr: dict[str, Any], token: str, files: dict[str, tuple[bytes, bool]]) -> str:
    head = pr["head"]["sha"]
    head_ref = pr["head"]["ref"]
    commit = request_json("GET", f"https://api.github.com/repos/{repo}/git/commits/{head}", token)
    entries = []
    for path, (data, binary) in files.items():
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": create_blob(repo, token, data, binary)})
    tree = request_json("POST", f"https://api.github.com/repos/{repo}/git/trees", token, {"base_tree": commit["tree"]["sha"], "tree": entries})
    new_commit = request_json("POST", f"https://api.github.com/repos/{repo}/git/commits", token, {"message": "Attach trusted article image", "tree": tree["sha"], "parents": [head]})
    encoded_ref = urllib.parse.quote(head_ref, safe="")
    request_json("PATCH", f"https://api.github.com/repos/{repo}/git/refs/heads/{encoded_ref}", token, {"sha": new_commit["sha"], "force": False})
    return new_commit["sha"]


def replace_image_evidence(body: str, evidence: dict[str, str]) -> str:
    labels = [
        "Image Pipeline Version", "Image Provider", "Image Attempt Chain", "Image Generation Result",
        "Image Source URL", "Image SHA-256", "Image Dimensions", "Image Visual Match",
        "Image Generation Attempt", "Image Fallback Attempt", "Image Fallback Result",
    ]
    kept = []
    for line in (body or "").splitlines():
        if not any(re.match(rf"^\s*(?:[-*]\s*)?{re.escape(label)}\s*:", line) for label in labels):
            kept.append(line)
    while kept and not kept[-1].strip():
        kept.pop()
    kept += ["", "### Image evidence (trusted automation)"]
    kept += [f"{key}: {value}" for key, value in evidence.items()]
    return "\n".join(kept).rstrip() + "\n"


def patch_pr_body(repo: str, number: int, body: str, token: str) -> None:
    request_json("PATCH", f"https://api.github.com/repos/{repo}/pulls/{number}", token, {"body": body})


def ensure_image(repo: str, pr: dict[str, Any], token: str) -> bool:
    if pr.get("state") != "open" or pr.get("draft"):
        return False
    if pr.get("base", {}).get("ref") != "main":
        return False
    if (pr.get("head", {}).get("repo") or {}).get("full_name") != repo:
        raise RuntimeError("Refusing image mutation for cross-repository PR")

    base_posts = posts_at(repo, pr["base"]["sha"], token)
    head_posts = posts_at(repo, pr["head"]["sha"], token)
    base_ids = {post.get("id") for post in base_posts}
    new_posts = [post for post in head_posts if post.get("id") not in base_ids]
    if len(new_posts) != 1:
        return False
    post = new_posts[0]
    if post.get("image"):
        print(f"ARTICLE_IMAGE_PRESENT id={post.get('id')}")
        return False

    candidate = choose_candidate(repo, post, pr["head"]["sha"], token)
    if candidate is None:
        print(f"ARTICLE_IMAGE_SKIPPED id={post.get('id')} reason=no_unique_image_available")
        return False
    width, height, ext = validate_candidate(candidate.data)
    image_path = f"{IMAGE_PREFIX}{post['id']}.{ext}"
    public_path = f"{PUBLIC_PREFIX}{post['id']}.{ext}"
    post["image"] = public_path
    post["imageAlt"] = candidate.visual_match

    posts_bytes = (json.dumps(head_posts, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    summaries_bytes = (json.dumps(summaries(head_posts), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    new_sha = commit_files(repo, pr, token, {
        image_path: (candidate.data, True),
        "src/data/posts.json": (posts_bytes, False),
        "src/data/postSummaries.json": (summaries_bytes, False),
    })

    digest = hashlib.sha256(candidate.data).hexdigest()
    evidence = {
        "Image Pipeline Version": "2",
        "Image Provider": candidate.provider,
        "Image Attempt Chain": "/".join(candidate.attempts),
        "Image Generation Result": "local_fallback" if candidate.provider == "Local" else ("generated" if candidate.provider == "Gemini" else "stock"),
        "Image Source URL": candidate.source_url,
        "Image SHA-256": digest,
        "Image Dimensions": f"{width}x{height}",
        "Image Visual Match": candidate.visual_match,
    }
    patch_pr_body(repo, int(pr["number"]), replace_image_evidence(pr.get("body") or "", evidence), token)
    print(f"ARTICLE_IMAGE_COMMITTED id={post['id']} provider={candidate.provider} sha={new_sha}")
    return True


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: article-image-worker.py OWNER/REPO PR_NUMBER", file=sys.stderr)
        return 2
    repo, number = sys.argv[1], int(sys.argv[2])
    token = os.environ["GITHUB_TOKEN"]
    pr = request_json("GET", f"https://api.github.com/repos/{repo}/pulls/{number}", token)
    ensure_image(repo, pr, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
