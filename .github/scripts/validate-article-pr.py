#!/usr/bin/env python3
"""Independent trusted quality gate for Kesher article publication PRs."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import struct
import sys
import urllib.parse
import urllib.request

ALLOWED_FILES = {
    "src/data/posts.json",
    "src/data/postSummaries.json",
    "public/sitemap.xml",
    "public/llms.txt",
    "public/llms-full.txt",
}
IMAGE_PREFIX = "public/images/generated/blog/"
IMAGE_PROVIDERS = {"Gemini", "Unsplash", "Pexels", "Local"}
IMAGE_RESULTS = {"generated", "stock", "local_fallback"}


def word_count(content: str) -> int:
    visible = html.unescape(re.sub(r"<[^>]+>", " ", content or ""))
    return len([word for word in re.split(r"\s+", visible.strip()) if word])


def image_dimensions(data: bytes) -> tuple[int, int]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
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
            segment_length = struct.unpack(">H", data[index:index + 2])[0]
            if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
                if index + 7 > len(data):
                    break
                height, width = struct.unpack(">HH", data[index + 3:index + 7])
                return width, height
            if segment_length < 2:
                break
            index += segment_length
    raise ValueError("unsupported or malformed image")


def exact_field(body: str, label: str) -> str | None:
    match = re.search(rf"(?im)^{re.escape(label)}:\s*([^\r\n]+?)\s*$", body or "")
    return match.group(1).strip() if match else None


def evaluate(pr, files_data, checks, base_posts, head_posts, image_loader):
    errors: list[str] = []
    files = [entry["filename"] for entry in files_data]
    body = pr.get("body") or ""
    title = pr.get("title") or ""

    if pr.get("state") != "open" or pr.get("draft"):
        errors.append("PR must be open and non-draft")
    if pr.get("base", {}).get("ref") != "main":
        errors.append("PR base must be main")
    if pr.get("head", {}).get("repo", {}).get("full_name") != pr.get("base", {}).get("repo", {}).get("full_name"):
        errors.append("PR head must belong to the same repository")
    if not title.startswith("Publish Kesher article:"):
        errors.append("PR title must start with 'Publish Kesher article:'")
    if "src/data/posts.json" not in files:
        errors.append("Article PR must modify src/data/posts.json")
    if not all(path in ALLOWED_FILES or path.startswith(IMAGE_PREFIX) for path in files):
        errors.append("Article PR contains a forbidden file")
    if any(path.startswith("public/videos/") for path in files):
        errors.append("Article PRs may not contain video files")
    if not any(check.get("name") == "verify" and check.get("conclusion") == "success" for check in checks):
        errors.append("Fresh successful verify check is required on the current head")

    base_ids = {post.get("id") for post in base_posts}
    base_by_id = {post.get("id"): post for post in base_posts}
    head_by_id = {post.get("id"): post for post in head_posts}
    if any(head_by_id.get(post_id) != base_post for post_id, base_post in base_by_id.items()):
        errors.append("Article publication PR may not modify or remove existing posts")
    new_posts = [post for post in head_posts if post.get("id") not in base_ids]
    if len(new_posts) != 1:
        errors.append(f"Expected exactly one new article, found {len(new_posts)}")
        return errors

    post = new_posts[0]
    count = word_count(post.get("content", ""))
    if not 700 <= count <= 1100:
        errors.append(f"New article word count must be 700-1100, found {count}")
    if len(re.findall(r"<h3(?:\s|>)", post.get("content", ""), re.I)) < 5:
        errors.append("New article must contain at least five H3 sections")
    if post.get("video"):
        errors.append("New article may not contain a video field")

    # Pipeline v2 invariant: publication without an independently verified local
    # image is impossible. Provider outages must have been absorbed by the
    # trusted repository-curated fallback before this gate runs.
    image_path = post.get("image")
    if not image_path:
        errors.append("New article requires a trusted local image; no-image publication is forbidden")
        return errors
    if not post.get("imageAlt") or len(str(post.get("imageAlt"))) < 20:
        errors.append("Image-bearing article requires concrete imageAlt text")

    expected_path = "public/" + image_path.lstrip("/")
    image_files = [entry for entry in files_data if entry["filename"].startswith(IMAGE_PREFIX)]
    matching = [entry for entry in image_files if entry["filename"] == expected_path]
    if len(matching) != 1:
        errors.append("Image-bearing article must add exactly its referenced local image")
        return errors

    pipeline_version = exact_field(body, "Image Pipeline Version")
    provider = exact_field(body, "Image Provider")
    attempt_chain = exact_field(body, "Image Attempt Chain")
    generation_result = exact_field(body, "Image Generation Result")
    source_url = exact_field(body, "Image Source URL")
    expected_sha = exact_field(body, "Image SHA-256")
    declared_dimensions = exact_field(body, "Image Dimensions")
    visual_match = exact_field(body, "Image Visual Match")

    if pipeline_version != "2":
        errors.append("Committed image requires Image Pipeline Version: 2")
    if provider not in IMAGE_PROVIDERS:
        errors.append("Committed image requires a trusted Image Provider")
    if not attempt_chain or attempt_chain.split("/")[0] != "gemini" or attempt_chain.split("/")[-1] not in {"gemini", "unsplash", "pexels", "local-curated"}:
        errors.append("Image Attempt Chain must truthfully begin with gemini and record provider fallthrough")
    if generation_result not in IMAGE_RESULTS:
        errors.append("Committed image requires Image Generation Result generated|stock|local_fallback")
    if provider == "Gemini" and generation_result != "generated":
        errors.append("Gemini image must record generated result")
    if provider in {"Unsplash", "Pexels"} and generation_result != "stock":
        errors.append("Stock provider image must record stock result")
    if provider == "Local" and generation_result != "local_fallback":
        errors.append("Local provider image must record local_fallback result")
    if provider == "Local":
        if not source_url or not source_url.startswith("local://public/images/generated/blog/"):
            errors.append("Local fallback requires exact local:// repository source")
    elif not source_url or not re.fullmatch(r"https://\S+", source_url):
        errors.append("External provider image requires an exact HTTPS source URL")
    if not expected_sha or not re.fullmatch(r"[a-f0-9]{64}", expected_sha):
        errors.append("Committed image requires a lowercase SHA-256")
    if not visual_match or len(visual_match) < 24:
        errors.append("Committed image requires a concrete Image Visual Match sentence")

    try:
        image_data = image_loader(matching[0])
        actual_sha = hashlib.sha256(image_data).hexdigest()
        if expected_sha and actual_sha != expected_sha:
            errors.append(f"Image SHA-256 mismatch: expected {expected_sha}, got {actual_sha}")
        width, height = image_dimensions(image_data)
        if width < 640 or height < 360:
            errors.append(f"Image dimensions too small: {width}x{height}")
        if declared_dimensions != f"{width}x{height}":
            errors.append(f"Image dimensions mismatch: expected {width}x{height}")
    except Exception as exc:
        errors.append(f"Image validation failed: {exc}")

    return errors


def api_json(url: str, token: str):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "kesher-article-gate",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_posts(repo: str, ref: str, token: str):
    quoted_ref = urllib.parse.quote(ref, safe="")
    payload = api_json(f"https://api.github.com/repos/{repo}/contents/src/data/posts.json?ref={quoted_ref}", token)
    return json.loads(base64.b64decode(payload["content"]).decode("utf-8"))


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: validate-article-pr.py pr.json files.json checks.json", file=sys.stderr)
        return 2
    pr = json.load(open(sys.argv[1], encoding="utf-8"))
    files_data = json.load(open(sys.argv[2], encoding="utf-8"))
    checks = json.load(open(sys.argv[3], encoding="utf-8")).get("check_runs", [])
    repo = os.environ["REPO"]
    token = os.environ["GITHUB_TOKEN"]
    base_posts = fetch_posts(repo, pr["base"]["sha"], token)
    head_posts = fetch_posts(repo, pr["head"]["sha"], token)

    def load_image(entry):
        request = urllib.request.Request(
            entry["raw_url"],
            headers={"Authorization": f"Bearer {token}", "User-Agent": "kesher-article-gate"},
        )
        with urllib.request.urlopen(request) as response:
            return response.read()

    errors = evaluate(pr, files_data, checks, base_posts, head_posts, load_image)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
