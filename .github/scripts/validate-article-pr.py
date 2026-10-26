#!/usr/bin/env python3
"""Independent trusted quality gate for Kesher article publication PRs."""

from __future__ import annotations

from typing import Any
import base64
import hashlib
import html
from html.parser import HTMLParser
import io
from datetime import datetime, timezone
import json
import os
import re
import sys
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.kesher_article_contract import (
    ARTICLE_PUBLICATION_PATHS, ARTICLE_IMAGE_PREFIX, forbidden_article_paths,
    exact_field, image_dimensions, image_proof_errors, image_pixel_sha256,
)
from scripts.kesher_primary_keyword_contract import validate_primary_keyword_contract

ALLOWED_FILES = ARTICLE_PUBLICATION_PATHS
IMAGE_PREFIX = ARTICLE_IMAGE_PREFIX


def word_count(content: str) -> int:
    visible = html.unescape(re.sub(r"<[^>]+>", " ", content or ""))
    return len([word for word in re.split(r"\s+", visible.strip()) if word])


def internal_blog_link_errors(content: str, catalog: list[dict]) -> list[str]:
    """Resolve internal blog destinations against real current and archived posts."""
    known = {str(row.get(key) or "").strip() for row in catalog if isinstance(row, dict)
             for key in ("id", "slug") if row.get(key)}
    hrefs: list[str] = []

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag.lower() == "a":
                hrefs.extend(value for key, value in attrs if key.lower() == "href" and value)

    Links().feed(str(content or ""))
    errors = []
    for href in hrefs:
        parts = urllib.parse.urlsplit(href)
        if parts.netloc and parts.netloc.lower() != "kesher.saharoni.com":
            continue
        path = urllib.parse.unquote(parts.path)
        if path.startswith("/blog/") and path.removeprefix("/blog/").strip("/") not in known:
            errors.append(f"internal_blog_link_missing: {path}")
    return sorted(set(errors))


def raw_github_content_url(repo: str, ref: str, repo_path: str) -> str:
    """Build a raw.githubusercontent URL that is safe for non-ASCII repository paths."""
    quoted_ref = urllib.parse.quote(str(ref or ""), safe="")
    quoted_path = urllib.parse.quote("/" + str(repo_path or "").lstrip("/"), safe="/")
    return f"https://raw.githubusercontent.com/{repo}/{quoted_ref}{quoted_path}"


def _parse_iso(val: Any) -> datetime | None:
    if not isinstance(val, str) or not val.strip():
        return None
    s = val.strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _check_time_tuple(check: dict) -> tuple[datetime | str, datetime | str] | None:
    started_raw = check.get("started_at")
    completed_raw = check.get("completed_at")
    created_raw = check.get("created_at")

    dt_start = _parse_iso(started_raw) or _parse_iso(created_raw) or _parse_iso(completed_raw)
    dt_comp = _parse_iso(completed_raw) or _parse_iso(started_raw) or _parse_iso(created_raw)

    if dt_start is not None and dt_comp is not None:
        return (dt_start, dt_comp)

    s_start = str(started_raw or created_raw or completed_raw or "").strip()
    s_comp = str(completed_raw or started_raw or created_raw or "").strip()
    if s_start or s_comp:
        return (s_start or s_comp, s_comp or s_start)
    return None


def _check_id(check: dict) -> int | None:
    val = check.get("id")
    if val is None and isinstance(check.get("check_suite"), dict):
        val = check["check_suite"].get("id")
    if val is None:
        val = check.get("run_id")
    if val is not None:
        try:
            return int(val)
        except (ValueError, TypeError):
            pass
    return None


def compare_check_runs(a: dict, b: dict) -> int | None:
    """Compare two check-runs for chronological precedence.
    Returns:
       1 if a is strictly newer than b
      -1 if b is strictly newer than a
      None if ambiguous, conflicting, or indistinguishable
    """
    time_a = _check_time_tuple(a)
    time_b = _check_time_tuple(b)
    id_a = _check_id(a)
    id_b = _check_id(b)

    time_cmp = 0
    if time_a is not None and time_b is not None:
        try:
            if time_a > time_b:
                time_cmp = 1
            elif time_a < time_b:
                time_cmp = -1
        except TypeError:
            s_time_a = (str(time_a[0]), str(time_a[1]))
            s_time_b = (str(time_b[0]), str(time_b[1]))
            if s_time_a > s_time_b:
                time_cmp = 1
            elif s_time_a < s_time_b:
                time_cmp = -1

    id_cmp = 0
    if id_a is not None and id_b is not None:
        if id_a > id_b:
            id_cmp = 1
        elif id_a < id_b:
            id_cmp = -1

    # Contradiction: one signal says A > B, the other says B > A
    if time_cmp != 0 and id_cmp != 0 and time_cmp != id_cmp:
        return None

    # Concordant or one signal present while other is equal/missing
    if time_cmp > 0 or id_cmp > 0:
        return 1
    if time_cmp < 0 or id_cmp < 0:
        return -1

    return None


def resolve_latest_verify_check(candidates: list[dict]) -> tuple[dict | None, str | None]:
    if not candidates:
        return None, "No candidate verify checks found"
    if len(candidates) == 1:
        return candidates[0], None

    for i, cand in enumerate(candidates):
        is_strictly_latest = True
        for j, other in enumerate(candidates):
            if i == j:
                continue
            cmp_val = compare_check_runs(cand, other)
            if cmp_val != 1:
                is_strictly_latest = False
                break
        if is_strictly_latest:
            return cand, None

    return None, "Multiple indistinguishable or conflicting latest verify checks"


def evaluate(pr, files_data, checks, base_posts, head_posts, image_loader, extra_base_posts=None, owner_topic_brief="", published_catalog=None):
    errors = evaluate_content(
        pr, files_data, base_posts, head_posts, image_loader,
        extra_base_posts=extra_base_posts, owner_topic_brief=owner_topic_brief, published_catalog=published_catalog,
    )
    head_sha = str((pr.get("head") or {}).get("sha") or "").strip()
    if not head_sha:
        errors.append("Fresh successful verify check is required on the current head")
        return errors

    candidates = [
        check for check in checks
        if isinstance(check, dict)
        and check.get("name") == "verify"
        and str(check.get("head_sha") or "").strip() == head_sha
    ]
    if not candidates:
        errors.append("Fresh successful verify check is required on the current head")
        return errors

    latest_check, ambiguity = resolve_latest_verify_check(candidates)
    if ambiguity or latest_check is None:
        errors.append("Ambiguous verify check runs on the current head; failing closed")
        errors.append("Fresh successful verify check is required on the current head")
        return errors

    status = str(latest_check.get("status") or "completed").strip().lower()
    conclusion = str(latest_check.get("conclusion") or "").strip().lower()

    if status != "completed" or conclusion != "success":
        errors.append("Fresh successful verify check is required on the current head")
    return errors


def evaluate_content(pr, files_data, base_posts, head_posts, image_loader, extra_base_posts=None, owner_topic_brief="", published_catalog=None):
    """Pure content policy, also run inside canonical CI before CI can finish."""
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
    content_errors: list[str] = []
    content_errors.extend(internal_blog_link_errors(
        post.get("content", ""),
        list(published_catalog) + [post] if published_catalog is not None else list(head_posts) + list(extra_base_posts or []),
    ))
    count = word_count(post.get("content", ""))
    if not 700 <= count <= 1100:
        content_errors.append(f"New article word count must be 700-1100, found {count}")
    if len(re.findall(r"<h3(?:\s|>)", post.get("content", ""), re.I)) < 5:
        content_errors.append("New article must contain at least five H3 sections")
    if post.get("video"):
        content_errors.append("New article may not contain a video field")

    # Primary Keyword Contract verification
    # Required for every article PR containing new or changed article content.
    # Detect deterministically from content fields diff vs base_posts — NEVER from attacker-controlled PR body text.
    base_match = next(
        (p for p in base_posts if isinstance(p, dict) and (p.get("id") == post.get("id") or (p.get("slug") and p.get("slug") == post.get("slug")))),
        None
    )
    content_fields = ("title", "content", "excerpt", "slug")
    is_true_image_only = (
        base_match is not None
        and all(str(post.get(f) or "").strip() == str(base_match.get(f) or "").strip() for f in content_fields)
    )

    if not is_true_image_only:
        content_errors.extend(
            validate_primary_keyword_contract(post, body, owner_topic_brief=owner_topic_brief)
        )

    # Pipeline v2 invariant: publication without an independently verified local
    # image is impossible. Provider outages must have been absorbed by the
    # trusted repository-curated fallback before this gate runs.
    image_path = post.get("image")
    if not image_path:
        errors.append("New article requires a trusted local image; no-image publication is forbidden")

    if content_errors or not image_path:
        errors.extend(content_errors)
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
        head_sha = str((pr.get("head") or {}).get("sha") or "").strip().lower()
        evidence_head = str(exact_field(body, "Image Evidence Head") or "").strip().lower()
        effective_head = head_sha
        if evidence_head and head_sha != evidence_head:
            repo_full_name = pr.get("base", {}).get("repo", {}).get("full_name") or os.environ.get("REPO") or ""
            github_token = os.environ.get("GITHUB_TOKEN") or ""
            if repo_full_name and github_token:
                curr = head_sha
                for _ in range(6):
                    try:
                        req = urllib.request.Request(
                            f"https://api.github.com/repos/{repo_full_name}/commits/{curr}",
                            headers={
                                "Authorization": f"Bearer {github_token}",
                                "Accept": "application/vnd.github+json",
                            },
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            commit_data = json.loads(resp.read().decode("utf-8"))
                            parents = [
                                str(p.get("sha") or "").strip().lower()
                                for p in (commit_data.get("parents") or [])
                                if isinstance(p, dict)
                            ]
                            if len(parents) < 2:
                                break
                            curr = parents[0]
                            if curr == evidence_head:
                                effective_head = evidence_head
                                break
                    except Exception:
                        break
        errors.extend(image_proof_errors(post, body, effective_head, image_data))
        actual_sha = hashlib.sha256(image_data).hexdigest()
        actual_pixels = image_pixel_sha256(image_data)

        # Enforce SHA-256 uniqueness against all existing base posts
        comparison_posts = list(base_posts) + list(extra_base_posts or [])
        for base_post in comparison_posts:
            if not isinstance(base_post, dict):
                continue
            base_img = str(base_post.get("image") or "").strip()
            if not base_img.startswith("/images/"):
                continue
            try:
                base_entry = {
                    "raw_url": raw_github_content_url(
                        pr.get("base", {}).get("repo", {}).get("full_name"),
                        pr["base"]["sha"],
                        f"public{base_img}",
                    )
                }
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


class StripAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            new_req.headers = {k: v for k, v in new_req.headers.items() if k.lower() != "authorization"}
            new_req.unredirected_hdrs = {k: v for k, v in new_req.unredirected_hdrs.items() if k.lower() != "authorization"}
        return new_req


def api_bytes(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "kesher-article-gate",
        },
    )
    opener = urllib.request.build_opener(StripAuthRedirectHandler)
    with opener.open(request) as response:
        return response.read()


def fetch_repo_json(repo: str, ref: str, token: str, filename: str):
    quoted_ref = urllib.parse.quote(ref, safe="")
    quoted_path = urllib.parse.quote(filename, safe="/")
    payload = api_json(f"https://api.github.com/repos/{repo}/contents/{quoted_path}?ref={quoted_ref}", token)
    blob_sha = payload.get("sha")
    if not isinstance(blob_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
        raise ValueError(f"Trusted JSON blob identity unavailable for {filename}")
    if payload.get("encoding") == "none":
        payload = api_json(f"https://api.github.com/repos/{repo}/git/blobs/{blob_sha}", token)
    if payload.get("sha") != blob_sha or payload.get("encoding") != "base64":
        raise ValueError(f"Trusted JSON blob unavailable for {filename}")
    raw = base64.b64decode("".join(str(payload.get("content") or "").split()), validate=True)
    actual_sha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if actual_sha != blob_sha:
        raise ValueError(f"Trusted JSON blob identity changed for {filename}")
    return json.loads(raw.decode("utf-8"))


def trusted_owner_topic_brief(repo: str, pr: dict, token: str) -> str:
    """Load owner keyword only from the exact controller-bound workflow artifact.

    Neither PR body nor article fields are trusted for owner intent. The controller
    state lives on the separate automation-state branch and binds the PR to the
    Article Generation run whose result artifact was produced by trusted main code.
    """
    state = fetch_repo_json(repo, "automation-state", token, ".kesher-controller/state.json")
    article = state.get("article") if isinstance(state, dict) else None
    if not isinstance(article, dict):
        return ""
    pr_number = int(pr.get("number") or 0)
    if int(article.get("pr_number") or 0) != pr_number:
        return ""
    run_id = int(article.get("run_id") or 0)
    if run_id <= 0:
        return ""
    artifacts = api_json(
        f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100", token
    )
    exact_name = f"kesher-article-result-{run_id}"
    matches = [
        a for a in (artifacts.get("artifacts") or [])
        if isinstance(a, dict) and a.get("name") == exact_name and a.get("expired") is not True
    ]
    if len(matches) != 1:
        raise ValueError(f"Trusted article result artifact {exact_name} is not unique/available")
    artifact_id = int(matches[0].get("id") or 0)
    if artifact_id <= 0:
        raise ValueError("Trusted article result artifact id is invalid")
    archive = api_bytes(f"https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}/zip", token)
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        result_names = [name for name in zf.namelist() if name.endswith("result.json")]
        if len(result_names) != 1:
            raise ValueError("Trusted article result artifact does not contain exactly one result.json")
        result = json.loads(zf.read(result_names[0]).decode("utf-8"))
    expected_pr_url = str(pr.get("html_url") or pr.get("url") or "").rstrip("/")
    artifact_pr_url = str(result.get("pr_url") or "").rstrip("/")
    if expected_pr_url and artifact_pr_url != expected_pr_url:
        raise ValueError("Trusted article result artifact PR identity mismatch")
    expected_slot = str(state.get("cycle") or "").strip()
    artifact_slot = str(result.get("slot") or "").strip()
    if expected_slot and artifact_slot and expected_slot != artifact_slot:
        raise ValueError("Trusted article result artifact slot mismatch")
    keyword = str(result.get("owner_required_primary_keyword") or "").strip()
    return f"Required Primary Keyword: {keyword}" if keyword else ""


def fetch_posts(repo: str, ref: str, token: str, filename: str = "src/data/posts.json"):
    quoted_ref = urllib.parse.quote(ref, safe="")
    quoted_path = urllib.parse.quote(filename, safe="/")
    payload = api_json(f"https://api.github.com/repos/{repo}/contents/{quoted_path}?ref={quoted_ref}", token)
    blob_sha = payload.get("sha")
    if not isinstance(blob_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", blob_sha):
        raise ValueError("Article catalog blob identity is unavailable")
    # Contents omits inline data above 1 MiB. Fetch the exact returned blob,
    # never a mutable main ref or an API-supplied arbitrary download URL.
    if payload.get("encoding") == "none":
        payload = api_json(f"https://api.github.com/repos/{repo}/git/blobs/{blob_sha}", token)
    if (payload.get("sha") != blob_sha or payload.get("encoding") != "base64"
            or not isinstance(payload.get("content"), str) or not payload["content"].strip()):
        raise ValueError("Article catalog blob is unavailable")
    data = base64.b64decode("".join(payload["content"].split()), validate=True)
    actual_sha = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    if actual_sha != blob_sha:
        raise ValueError("Article catalog blob identity changed")
    posts = json.loads(data.decode("utf-8"))
    if not isinstance(posts, list):
        raise ValueError("Article catalog must be a list")
    return posts


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: validate-article-pr.py pr.json files.json checks.json", file=sys.stderr)
        return 2
    pr = json.load(open(sys.argv[1], encoding="utf-8"))
    files_data = json.load(open(sys.argv[2], encoding="utf-8"))
    checks = json.load(open(sys.argv[3], encoding="utf-8")).get("check_runs", [])
    repo = os.environ["REPO"]
    token = os.environ["GITHUB_TOKEN"]
    base_posts = fetch_posts(repo, pr["base"]["sha"], token, "src/data/posts.json")
    head_posts = fetch_posts(repo, pr["head"]["sha"], token, "src/data/posts.json")
    extra_base_posts = fetch_posts(repo, pr["base"]["sha"], token, "src/data/postsRecent.json")
    published_catalog = fetch_repo_json(repo, pr["base"]["sha"], token, "src/data/postSummaries.json")

    def load_image(entry):
        request = urllib.request.Request(
            entry["raw_url"],
            headers={"Authorization": f"Bearer {token}", "User-Agent": "kesher-article-gate"},
        )
        with urllib.request.urlopen(request) as response:
            return response.read()

    try:
        owner_topic_brief = trusted_owner_topic_brief(repo, pr, token)
    except Exception as exc:
        print(f"Trusted owner keyword provenance could not be verified: {exc}", file=sys.stderr)
        return 1
    errors = evaluate(
        pr, files_data, checks, base_posts, head_posts, load_image,
        extra_base_posts=extra_base_posts, owner_topic_brief=owner_topic_brief, published_catalog=published_catalog,
    )
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
