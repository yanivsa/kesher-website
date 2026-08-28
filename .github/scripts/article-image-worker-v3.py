#!/usr/bin/env python3
"""Hardened trusted image worker for Kesher Pipeline v3.

The worker is deliberately single-attempt. The content controller owns any
workflow retry. Inside one attempt providers fall through deterministically:
Gemini -> Unsplash -> Pexels -> repository-curated local fallback.

External images are accepted only after actual pixel-level Gemini verification.
The local fallback is read from trusted main, never from the article PR head.
PR evidence is written before the Git commit so a partial GitHub API failure is
recoverable and idempotent on the next controller-owned attempt.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

CORE_PATH = Path(__file__).with_name("article-image-worker.py")
spec = importlib.util.spec_from_file_location("kesher_article_image_worker_core", CORE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load image worker core from {CORE_PATH}")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

GEMINI_MODEL = "gemini-3.1-flash-image"
VERIFY_MODEL = "gemini-3.5-flash"
IMAGE_PREFIX = core.IMAGE_PREFIX
PUBLIC_PREFIX = core.PUBLIC_PREFIX
TRUSTED_PROVIDERS = {"Gemini", "Unsplash", "Pexels", "Local"}
TRUSTED_RESULTS = {"generated", "stock", "local_fallback"}


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
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read(core.MAX_DOWNLOAD_BYTES + 1)
    if not raw or len(raw) > core.MAX_DOWNLOAD_BYTES:
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


def try_gemini(post: dict[str, Any], attempts: list[str], used_shas: set[str] | None = None) -> core.ImageCandidate | None:
    attempts.append("gemini")
    if not google_key():
        return None
    if used_shas is None:
        used_shas = core.get_used_hero_shas(exclude_id=post.get("id"))
    try:
        payload = google_json(
            f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent",
            {
                "contents": [{"parts": [{"text": core.image_prompt(post)}]}],
                "generationConfig": {
                    "responseModalities": ["IMAGE"],
                    "responseFormat": {"image": {"aspectRatio": "16:9"}},
                },
            },
        )
        data = extract_generated_image(payload)
        if not data:
            raise RuntimeError("Gemini returned no inline image")
        _w, _h, ext = core.validate_candidate(data)
        digest = hashlib.sha256(data).hexdigest()
        if digest in used_shas:
            print(f"IMAGE_PROVIDER_REJECTED provider=gemini reason=duplicate_sha sha={digest[:8]}", file=sys.stderr)
            return None
        matched, description = verify_pixels(post, data, ext)
        if not matched:
            print("IMAGE_PROVIDER_REJECTED provider=gemini reason=pixel_mismatch", file=sys.stderr)
            return None
        return core.ImageCandidate(
            "Gemini", data, ext,
            f"https://ai.google.dev/gemini-api/docs/models/{GEMINI_MODEL}",
            description, attempts.copy(),
        )
    except Exception as exc:
        print(f"IMAGE_PROVIDER_FAILED provider=gemini error={type(exc).__name__}", file=sys.stderr)
        return None


def _stock_candidate(post: dict[str, Any], attempts: list[str], provider: str, used_shas: set[str] | None = None) -> core.ImageCandidate | None:
    # Stock search metadata is not visual evidence. Without a pixel verifier we
    # skip stock entirely and use the repository-curated fallback.
    if not google_key():
        return None
    if used_shas is None:
        used_shas = core.get_used_hero_shas(exclude_id=post.get("id"))
    query = urllib.parse.quote(core.stock_query(post))
    try:
        if provider == "unsplash":
            key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
            if not key:
                return None
            result = core.request_json(
                "GET",
                f"https://api.unsplash.com/search/photos?query={query}&orientation=landscape&per_page=10",
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
            result = core.request_json(
                "GET",
                f"https://api.pexels.com/v1/search?query={query}&orientation=landscape&per_page=10",
                headers={"Authorization": key},
            )
            rows = [
                (((photo.get("src") or {}).get("large") or (photo.get("src") or {}).get("large2x")), photo.get("url"))
                for photo in (result.get("photos") or []) if isinstance(photo, dict)
            ]
            label = "Pexels"
        for url, source in rows:
            if not url or not source:
                continue
            data = core.download(str(url))
            _w, _h, ext = core.validate_candidate(data)
            digest = hashlib.sha256(data).hexdigest()
            if digest in used_shas:
                print(f"IMAGE_PROVIDER_REJECTED provider={provider} reason=duplicate_sha sha={digest[:8]}", file=sys.stderr)
                continue
            matched, description = verify_pixels(post, data, ext)
            if matched:
                return core.ImageCandidate(label, data, ext, str(source), description, attempts.copy())
    except Exception as exc:
        print(f"IMAGE_PROVIDER_FAILED provider={provider} error={type(exc).__name__}", file=sys.stderr)
    return None


def try_unsplash(post: dict[str, Any], attempts: list[str], used_shas: set[str] | None = None) -> core.ImageCandidate | None:
    attempts.append("unsplash")
    return _stock_candidate(post, attempts, "unsplash", used_shas=used_shas)


def try_pexels(post: dict[str, Any], attempts: list[str], used_shas: set[str] | None = None) -> core.ImageCandidate | None:
    attempts.append("pexels")
    return _stock_candidate(post, attempts, "pexels", used_shas=used_shas)


def local_fallback(repo: str, post: dict[str, Any], _head_ref: str, token: str, attempts: list[str], used_shas: set[str] | None = None) -> core.ImageCandidate:
    attempts.append("local-curated")
    if used_shas is None:
        used_shas = core.get_used_hero_shas(exclude_id=post.get("id"))

    key = core.article_key(post)
    cat_fallback = core.LOCAL_FALLBACKS.get(key) or core.LOCAL_FALLBACKS["couples"]
    all_fallbacks = [cat_fallback] + [fb for k, fb in core.LOCAL_FALLBACKS.items() if fb != cat_fallback]

    failures = []
    for source_path, description in all_fallbacks:
        try:
            payload = core.github_content(repo, source_path, "main", token)
            data = core.decode_content(payload)
            _w, _h, ext = core.validate_candidate(data)
            digest = hashlib.sha256(data).hexdigest()
            if digest in used_shas:
                raise RuntimeError(f"duplicate_sha:{digest[:8]}")
            return core.ImageCandidate("Local", data, ext, f"local://{source_path}", description, attempts.copy())
        except Exception as exc:
            failures.append(f"{source_path}:{str(exc)}")

    raise RuntimeError("No valid non-duplicate trusted local fallback remained: " + ", ".join(failures))


def choose_candidate(repo: str, post: dict[str, Any], head_ref: str, token: str, used_shas: set[str] | None = None) -> core.ImageCandidate:
    if used_shas is None:
        used_shas = core.get_used_hero_shas(exclude_id=post.get("id"))
    attempts: list[str] = []
    for provider in (try_gemini, try_unsplash, try_pexels):
        candidate = provider(post, attempts, used_shas=used_shas)
        if candidate:
            return candidate
    return local_fallback(repo, post, head_ref, token, attempts, used_shas=used_shas)


def word_count(html: str) -> int:
    return len(re.sub(r"<[^>]+>", " ", str(html or "")).strip().split())


def heading_count(html: str) -> int:
    return len(re.findall(r"<h3", str(html or "")))


def publishable(post: dict[str, Any]) -> bool:
    return word_count(str(post.get("content") or "")) >= 500 and heading_count(str(post.get("content") or "")) >= 5


def summaries(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mirror scripts/generate-post-summaries.cjs/content-policy.cjs exactly."""
    result: list[dict[str, Any]] = []
    for post in posts:
        if not isinstance(post, dict) or not publishable(post):
            continue
        row: dict[str, Any] = {
            "id": post.get("id"),
            "title": post.get("title"),
            "date": post.get("date"),
            "category": post.get("category"),
        }
        if post.get("subcategory"):
            row["subcategory"] = post.get("subcategory")
        row["excerpt"] = post.get("excerpt")
        if "image" in post:
            row["image"] = post.get("image")
        result.append(row)
    return result


def exact_field(body: str, label: str) -> str | None:
    values: list[str] = []
    pattern = re.compile(rf"^\s*(?:[-*]\s*)?{re.escape(label)}\s*:\s*(.*?)\s*$")
    for line in (body or "").splitlines():
        match = pattern.match(line)
        if match:
            values.append(match.group(1).strip())
    return values[0] if len(values) == 1 else None


def trusted_image_present(repo: str, pr: dict[str, Any], post: dict[str, Any], token: str) -> bool:
    image = str(post.get("image") or "")
    if not image.startswith(PUBLIC_PREFIX) or len(str(post.get("imageAlt") or "")) < 20:
        return False
    body = str(pr.get("body") or "")
    provider = exact_field(body, "Image Provider")
    result = exact_field(body, "Image Generation Result")
    expected_sha = exact_field(body, "Image SHA-256")
    dimensions = exact_field(body, "Image Dimensions")
    visual = exact_field(body, "Image Visual Match")
    if exact_field(body, "Image Pipeline Version") != "2":
        return False
    if provider not in TRUSTED_PROVIDERS or result not in TRUSTED_RESULTS:
        return False
    if not expected_sha or not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        return False
    if not dimensions or not visual or len(visual) < 24:
        return False
    try:
        payload = core.github_content(repo, "public/" + image.lstrip("/"), pr["head"]["sha"], token)
        data = core.decode_content(payload)
        width, height, _ext = core.validate_candidate(data)
    except Exception:
        return False
    return hashlib.sha256(data).hexdigest() == expected_sha and dimensions == f"{width}x{height}"


def create_blob(repo: str, token: str, data: bytes, binary: bool) -> str:
    return core.create_blob(repo, token, data, binary)


def commit_files(
    repo: str,
    pr: dict[str, Any],
    token: str,
    files: dict[str, tuple[bytes, bool]],
    delete_paths: list[str],
) -> str:
    head = pr["head"]["sha"]
    head_ref = pr["head"]["ref"]
    commit = core.request_json("GET", f"https://api.github.com/repos/{repo}/git/commits/{head}", token)
    entries: list[dict[str, Any]] = []
    for path, (data, binary) in files.items():
        entries.append({"path": path, "mode": "100644", "type": "blob", "sha": create_blob(repo, token, data, binary)})
    for path in sorted(set(delete_paths)):
        if path not in files:
            entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
    tree = core.request_json(
        "POST", f"https://api.github.com/repos/{repo}/git/trees", token,
        {"base_tree": commit["tree"]["sha"], "tree": entries},
    )
    new_commit = core.request_json(
        "POST", f"https://api.github.com/repos/{repo}/git/commits", token,
        {"message": "Attach trusted article image", "tree": tree["sha"], "parents": [head]},
    )
    encoded_ref = urllib.parse.quote(head_ref, safe="")
    core.request_json(
        "PATCH", f"https://api.github.com/repos/{repo}/git/refs/heads/{encoded_ref}", token,
        {"sha": new_commit["sha"], "force": False},
    )
    return str(new_commit["sha"])


def ensure_image(repo: str, pr: dict[str, Any], token: str) -> bool:
    if pr.get("state") != "open" or pr.get("draft"):
        return False
    if pr.get("base", {}).get("ref") != "main":
        return False
    if (pr.get("head", {}).get("repo") or {}).get("full_name") != repo:
        raise RuntimeError("Refusing image mutation for cross-repository PR")

    base_posts = core.posts_at(repo, pr["base"]["sha"], token)
    head_posts = core.posts_at(repo, pr["head"]["sha"], token)
    base_ids = {post.get("id") for post in base_posts if isinstance(post, dict)}
    new_posts = [post for post in head_posts if isinstance(post, dict) and post.get("id") not in base_ids]
    if len(new_posts) != 1:
        return False
    post = new_posts[0]
    if trusted_image_present(repo, pr, post, token):
        print(f"ARTICLE_IMAGE_PRESENT id={post.get('id')} trusted=yes")
        return False

    candidate = choose_candidate(repo, post, pr["head"]["sha"], token)
    width, height, ext = core.validate_candidate(candidate.data)
    image_path = f"{IMAGE_PREFIX}{post['id']}.{ext}"
    public_path = f"{PUBLIC_PREFIX}{post['id']}.{ext}"
    post["image"] = public_path
    post["imageAlt"] = candidate.visual_match
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

    # Evidence first makes a commit/body split failure self-healing: a retry can
    # overwrite stale evidence and regenerate the exact trusted image.
    new_body = core.replace_image_evidence(str(pr.get("body") or ""), evidence)
    core.patch_pr_body(repo, int(pr["number"]), new_body, token)

    pr_files = core.request_json(
        "GET", f"https://api.github.com/repos/{repo}/pulls/{pr['number']}/files?per_page=100", token
    )
    delete_paths = [
        str(row.get("filename"))
        for row in (pr_files if isinstance(pr_files, list) else [])
        if isinstance(row, dict)
        and row.get("status") == "added"
        and str(row.get("filename") or "").startswith(IMAGE_PREFIX)
        and str(row.get("filename")) != image_path
    ]

    posts_bytes = (json.dumps(head_posts, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    summaries_bytes = (json.dumps(summaries(head_posts), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    new_sha = commit_files(
        repo,
        pr,
        token,
        {
            image_path: (candidate.data, True),
            "src/data/posts.json": (posts_bytes, False),
            "src/data/postSummaries.json": (summaries_bytes, False),
        },
        delete_paths,
    )
    print(f"ARTICLE_IMAGE_COMMITTED id={post['id']} provider={candidate.provider} sha={new_sha}")
    return True


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: article-image-worker-v3.py OWNER/REPO PR_NUMBER", file=sys.stderr)
        return 2
    repo, number = sys.argv[1], int(sys.argv[2])
    token = os.environ["GITHUB_TOKEN"]
    pr = core.request_json("GET", f"https://api.github.com/repos/{repo}/pulls/{number}", token)
    ensure_image(repo, pr, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
