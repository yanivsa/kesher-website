#!/usr/bin/env python3
"""Independent quality gate for Jules article publication PRs."""

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
FAILURE_IMAGE_RESULTS = {"unavailable", "blocked", "api_error", "rejected_visual_quality"}
FALLBACK_FAILURE_RESULTS = {"no_pixel_verified_match", "unavailable", "blocked"}


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

    image_files = [entry for entry in files_data if entry["filename"].startswith(IMAGE_PREFIX)]
    image_path = post.get("image")
    if image_path:
        expected_path = "public/" + image_path.lstrip("/")
        matching = [entry for entry in image_files if entry["filename"] == expected_path]
        if len(matching) != 1:
            errors.append("Image-bearing article must add exactly its referenced local image")
            return errors

        generation_result = exact_field(body, "Image Generation Result")
        source_url = exact_field(body, "Image Source URL")
        expected_sha = exact_field(body, "Image SHA-256")
        declared_dimensions = exact_field(body, "Image Dimensions")
        visual_match = exact_field(body, "Image Visual Match")
        if exact_field(body, "Image Generation Attempt") != "DeepAI":
            errors.append("Image Generation Attempt must be DeepAI")
        if generation_result not in {"success", "generated"}:
            errors.append("Committed image requires Image Generation Result success|generated")
        if not source_url or not re.fullmatch(r"https://\S+", source_url) or source_url == "https://none":
            errors.append("Committed image requires an exact HTTPS source URL")
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
            if declared_dimensions != f"{width}x{height}":
                errors.append(f"Image dimensions mismatch: expected {width}x{height}")
        except Exception as exc:
            errors.append(f"Image validation failed: {exc}")
    else:
        if post.get("imageAlt"):
            errors.append("No-image article may not retain imageAlt")
        if image_files:
            errors.append("No-image article may not add an image file")
        generation_result = exact_field(body, "Image Generation Result")
        fallback_result = exact_field(body, "Image Fallback Result")
        if exact_field(body, "Image Generation Attempt") != "DeepAI":
            errors.append("No-image fallback must record the DeepAI attempt")
        if generation_result not in FAILURE_IMAGE_RESULTS:
            errors.append("No-image fallback must record an allowed generation failure")
        if exact_field(body, "Image Fallback Attempt") != "Unsplash/Pexels":
            errors.append("No-image fallback must record Unsplash/Pexels attempt")
        if fallback_result not in FALLBACK_FAILURE_RESULTS:
            errors.append("No-image fallback must record an allowed stock fallback failure")
        if exact_field(body, "Image Source URL") != "none":
            errors.append("No-image fallback must use Image Source URL: none")

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
