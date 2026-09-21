#!/usr/bin/env python3
"""Independent trusted quality gate for Kesher article publication PRs."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path
import urllib.parse
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.kesher_article_contract import (
    ARTICLE_PUBLICATION_PATHS, ARTICLE_IMAGE_PREFIX, forbidden_article_paths,
    exact_field, image_dimensions, image_proof_errors, image_pixel_sha256,
)

ALLOWED_FILES = ARTICLE_PUBLICATION_PATHS
IMAGE_PREFIX = ARTICLE_IMAGE_PREFIX


def word_count(content: str) -> int:
    visible = html.unescape(re.sub(r"<[^>]+>", " ", content or ""))
    return len([word for word in re.split(r"\s+", visible.strip()) if word])


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
    if forbidden_article_paths(files):
        errors.append("Article PR contains a forbidden file")
    if any(path.startswith("public/videos/") for path in files):
        errors.append("Article PRs may not contain video files")
    if not any(check.get("name") == "verify" and check.get("conclusion") == "success"
               and check.get("head_sha") == (pr.get("head") or {}).get("sha")
               and bool((pr.get("head") or {}).get("sha")) for check in checks):
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
    if len(matching) != 1 or len(image_files) != 1:
        errors.append("Image-bearing article must add exactly its referenced local image")
        return errors

    try:
        image_data = image_loader(matching[0])
        errors.extend(image_proof_errors(post, body, str((pr.get("head") or {}).get("sha") or ""), image_data))
        actual_sha = hashlib.sha256(image_data).hexdigest()
        actual_pixels = image_pixel_sha256(image_data)

        # Enforce SHA-256 uniqueness against all existing base posts
        for base_post in base_posts:
            if not isinstance(base_post, dict):
                continue
            base_img = str(base_post.get("image") or "").strip()
            if not base_img.startswith("/images/"):
                continue
            try:
                base_entry = {"raw_url": f"https://raw.githubusercontent.com/{pr.get('base',{}).get('repo',{}).get('full_name')}/{pr['base']['sha']}/public{base_img}"}
                base_data = image_loader(base_entry)
                if hashlib.sha256(base_data).hexdigest() == actual_sha:
                    errors.append(f"Hero image SHA-256 collides with existing article {base_post.get('id')}")
                    break
                if image_pixel_sha256(base_data) == actual_pixels:
                    errors.append(f"Hero image pixels collide with existing article {base_post.get('id')}")
                    break
            except Exception as exc:
                errors.append(f"Image uniqueness could not be verified against article {base_post.get('id')}: {exc}")
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
