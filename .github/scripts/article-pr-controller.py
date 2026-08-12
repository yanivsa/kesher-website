#!/usr/bin/env python3
"""Self-healing controller for Kesher article publication PRs.

The controller keeps technical cleanup deterministic and gives Jules at most two
content-repair turns on the same PR/head sequence. It never creates a second
article PR.
"""

from __future__ import annotations

import argparse
import base64
import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ALLOWED_FILES = {
    "src/data/posts.json",
    "src/data/postSummaries.json",
    "public/sitemap.xml",
    "public/llms.txt",
    "public/llms-full.txt",
}
IMAGE_PREFIX = "public/images/generated/blog/"
IMAGE_FIELDS = (
    "Image Generation Attempt",
    "Image Generation Result",
    "Image Fallback Attempt",
    "Image Fallback Result",
    "Image Source URL",
    "Image SHA-256",
    "Image Dimensions",
    "Image Visual Match",
)
REPAIR_MARKER = re.compile(
    r"<!--\s*kesher-article-repair\s+attempt=(\d+)\s+head=([0-9a-f]{40})\s*-->",
    re.I,
)
MAX_REPAIRS = 2


def request_json(method: str, url: str, token: str, body: dict | None = None) -> dict | list:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "kesher-article-controller",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read()
            return json.loads(payload.decode("utf-8")) if payload else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(f"GitHub API {method} {url} failed with HTTP {error.code}: {detail}") from error


def request_optional_json(url: str, token: str) -> dict | None:
    try:
        result = request_json("GET", url, token)
        return result if isinstance(result, dict) else None
    except RuntimeError as error:
        if "HTTP 404" in str(error):
            return None
        raise


def load_validator():
    path = Path(__file__).with_name("validate-article-pr.py")
    spec = importlib.util.spec_from_file_location("kesher_article_validator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load validator from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_article_scope(pr: dict, files: list[dict]) -> bool:
    title = pr.get("title") or ""
    paths = [item.get("filename") or "" for item in files]
    return title.startswith("Publish Kesher article:") or any(
        path == "src/data/posts.json" or path.startswith(IMAGE_PREFIX) for path in paths
    )


def normalize_field_line(line: str) -> tuple[str, str] | None:
    candidate = line.strip()
    candidate = re.sub(r"^[-*]\s+", "", candidate).strip()
    if candidate.startswith("`") and candidate.endswith("`") and len(candidate) >= 2:
        candidate = candidate[1:-1].strip()
    if candidate.startswith("**") and candidate.endswith("**") and len(candidate) >= 4:
        candidate = candidate[2:-2].strip()
    for label in IMAGE_FIELDS:
        prefix = f"{label}:"
        if candidate.startswith(prefix):
            return label, candidate[len(prefix):].strip()
    return None


def normalize_pr_body(repo: str, pr: dict, token: str) -> bool:
    body = pr.get("body") or ""
    found: dict[str, str] = {}
    kept: list[str] = []
    changed = False
    for line in body.splitlines():
        parsed = normalize_field_line(line)
        if parsed:
            label, value = parsed
            found[label] = value
            canonical = f"{label}: {value}"
            if line.strip() != canonical:
                changed = True
            continue
        kept.append(line)

    if not found or not changed:
        return False

    while kept and not kept[-1].strip():
        kept.pop()
    kept.extend(["", "### Image evidence (normalized by automation)"])
    for label in IMAGE_FIELDS:
        if label in found:
            kept.append(f"{label}: {found[label]}")
    new_body = "\n".join(kept).rstrip() + "\n"
    request_json(
        "PATCH",
        f"https://api.github.com/repos/{repo}/pulls/{pr['number']}",
        token,
        {"body": new_body},
    )
    pr["body"] = new_body
    print(f"Normalized structured image evidence in PR #{pr['number']} body.")
    return True


def forbidden_paths(files: list[dict]) -> list[str]:
    return [
        item.get("filename") or ""
        for item in files
        if not (
            (item.get("filename") or "") in ALLOWED_FILES
            or (item.get("filename") or "").startswith(IMAGE_PREFIX)
        )
    ]


def clean_forbidden_files(repo: str, pr: dict, paths: list[str], token: str) -> bool:
    if not paths:
        return False
    head_repo = ((pr.get("head") or {}).get("repo") or {}).get("full_name")
    base_repo = ((pr.get("base") or {}).get("repo") or {}).get("full_name")
    if head_repo != base_repo or head_repo != repo:
        raise RuntimeError("Refusing technical cleanup for a cross-repository article PR")

    head_ref = (pr.get("head") or {}).get("ref") or ""
    head_sha = (pr.get("head") or {}).get("sha") or ""
    base_sha = (pr.get("base") or {}).get("sha") or ""
    if not head_ref or not head_sha or not base_sha:
        raise RuntimeError("PR is missing head/base ref evidence required for cleanup")

    tree_entries: list[dict] = []
    for path in paths:
        quoted_path = urllib.parse.quote(path, safe="/")
        base_item = request_optional_json(
            f"https://api.github.com/repos/{repo}/contents/{quoted_path}?ref={urllib.parse.quote(base_sha, safe='')}",
            token,
        )
        if base_item:
            tree_entries.append(
                {"path": path, "mode": "100644", "type": "blob", "sha": base_item["sha"]}
            )
        else:
            tree_entries.append({"path": path, "mode": "100644", "type": "blob", "sha": None})

    current_commit = request_json(
        "GET", f"https://api.github.com/repos/{repo}/git/commits/{head_sha}", token
    )
    base_tree = current_commit["tree"]["sha"]
    new_tree = request_json(
        "POST",
        f"https://api.github.com/repos/{repo}/git/trees",
        token,
        {"base_tree": base_tree, "tree": tree_entries},
    )
    new_commit = request_json(
        "POST",
        f"https://api.github.com/repos/{repo}/git/commits",
        token,
        {
            "message": "Auto-clean article PR scope",
            "tree": new_tree["sha"],
            "parents": [head_sha],
        },
    )
    encoded_ref = urllib.parse.quote(head_ref, safe="")
    request_json(
        "PATCH",
        f"https://api.github.com/repos/{repo}/git/refs/heads/{encoded_ref}",
        token,
        {"sha": new_commit["sha"], "force": False},
    )
    print(
        f"Auto-cleaned forbidden article paths from PR #{pr['number']}: "
        + ", ".join(paths)
    )
    return True


def fetch_checks(repo: str, sha: str, token: str) -> dict:
    result = request_json(
        "GET",
        f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs?per_page=100",
        token,
    )
    if not isinstance(result, dict):
        raise RuntimeError("Unexpected check-runs response")
    return result


def verify_check(checks: dict) -> dict | None:
    candidates = [item for item in checks.get("check_runs", []) if item.get("name") == "verify"]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.get("completed_at") or item.get("started_at") or "")[-1]


def image_loader(entry: dict, token: str) -> bytes:
    request = urllib.request.Request(
        entry["raw_url"],
        headers={"Authorization": f"Bearer {token}", "User-Agent": "kesher-article-controller"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def existing_repair_attempts(repo: str, number: int, token: str) -> tuple[int, set[str]]:
    comments = request_json(
        "GET",
        f"https://api.github.com/repos/{repo}/issues/{number}/comments?per_page=100",
        token,
    )
    total = 0
    heads: set[str] = set()
    if isinstance(comments, list):
        for comment in comments:
            for match in REPAIR_MARKER.finditer(comment.get("body") or ""):
                total = max(total, int(match.group(1)))
                heads.add(match.group(2).lower())
    return total, heads


def send_jules_repair(
    repo: str,
    pr: dict,
    errors: list[str],
    verify: dict | None,
    github_token: str,
    jules_key: str,
) -> bool:
    number = int(pr["number"])
    head_sha = ((pr.get("head") or {}).get("sha") or "").lower()
    attempt, repaired_heads = existing_repair_attempts(repo, number, github_token)
    if head_sha in repaired_heads:
        print(f"Repair already requested for current head {head_sha}; waiting for Jules.")
        return False
    if attempt >= MAX_REPAIRS:
        print(f"PR #{number} exhausted the bounded {MAX_REPAIRS} Jules repair attempts.")
        return False

    body = pr.get("body") or ""
    match = re.search(r"https://jules\.google\.com/task/(\d+)", body)
    if not match:
        print(f"PR #{number} has no parseable Jules task URL; cannot request autonomous repair.")
        return False
    session_id = match.group(1)
    next_attempt = attempt + 1
    verify_status = "missing"
    if verify:
        verify_status = f"status={verify.get('status')} conclusion={verify.get('conclusion')}"
    error_text = "\n".join(f"- {error}" for error in errors) or "- verify check did not pass"
    head_ref = (pr.get("head") or {}).get("ref") or ""
    prompt = f"""Autonomous article repair attempt {next_attempt}/{MAX_REPAIRS}.

Your existing PR #{number} in {repo} failed the independent publication gate. Repair THE SAME PR AND THE SAME BRANCH `{head_ref}` only. Do not create a new article, new branch, or new PR. Do not ask for user approval.

Current head: {head_sha}
CI verify: {verify_status}
Gate errors:
{error_text}

If CI verify failed, inspect the current PR checks/logs and fix the actual content/test failure. If the article is too short, structurally invalid, repetitive, too similar to recent posts, or otherwise fails content policy, rewrite only the new article as needed and rerun all required generation/check commands. If the topic itself is too similar, replace the new article within this same PR with one fresh topic while still publishing exactly one new article.

Final diff must contain only the allowed article publication files: src/data/posts.json, src/data/postSummaries.json, public/sitemap.xml, public/llms.txt, public/llms-full.txt, and at most one independently verified image under public/images/generated/blog/. Do not modify tests, workflows, prompts, scripts, packages, or public/videos/.

Update the existing PR body with exact plain structured image evidence lines (no bullets/backticks around the field names), run npm run generate after the final article edit, run npm run check, push the repaired commits to the existing branch, and leave PR #{number} open for the independent gate to re-check automatically."""

    request = urllib.request.Request(
        f"https://jules.googleapis.com/v1alpha/sessions/{session_id}:sendMessage",
        data=json.dumps({"prompt": prompt}, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"x-goog-api-key": jules_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:2000]
        raise RuntimeError(
            f"Jules repair message failed with HTTP {error.code}: {detail}"
        ) from error

    marker = f"<!-- kesher-article-repair attempt={next_attempt} head={head_sha} -->"
    comment = (
        f"{marker}\n"
        f"Automatic Jules repair requested ({next_attempt}/{MAX_REPAIRS}) for this exact PR head. "
        f"The same PR must be updated; no replacement PR is allowed."
    )
    request_json(
        "POST",
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        github_token,
        {"body": comment},
    )
    print(f"Requested Jules article repair {next_attempt}/{MAX_REPAIRS} for PR #{number}.")
    return True


def merge_and_deploy(repo: str, pr: dict, token: str) -> None:
    number = int(pr["number"])
    head_sha = (pr.get("head") or {}).get("sha") or ""
    merged = request_json(
        "PUT",
        f"https://api.github.com/repos/{repo}/pulls/{number}/merge",
        token,
        {
            "sha": head_sha,
            "commit_title": "Auto-merge validated Kesher article",
            "merge_method": "squash",
        },
    )
    if not isinstance(merged, dict) or merged.get("merged") is not True:
        raise RuntimeError(f"Article merge did not complete: {merged}")
    request_json(
        "POST",
        f"https://api.github.com/repos/{repo}/actions/workflows/deploy.yml/dispatches",
        token,
        {"ref": "main"},
    )
    print(f"Merged validated article PR #{number} and dispatched deploy.")


def process(repo: str, number: int, github_token: str, jules_key: str) -> int:
    pr = request_json("GET", f"https://api.github.com/repos/{repo}/pulls/{number}", github_token)
    if not isinstance(pr, dict) or pr.get("state") != "open" or pr.get("draft"):
        return 0
    files = request_json(
        "GET",
        f"https://api.github.com/repos/{repo}/pulls/{number}/files?per_page=100",
        github_token,
    )
    if not isinstance(files, list) or not is_article_scope(pr, files):
        return 0

    normalize_pr_body(repo, pr, github_token)
    forbidden = forbidden_paths(files)
    if clean_forbidden_files(repo, pr, forbidden, github_token):
        # The cleanup commit changes the head. A fresh CI run will trigger this
        # controller again through workflow_run; never repair against stale checks.
        return 0

    sha = (pr.get("head") or {}).get("sha") or ""
    checks = fetch_checks(repo, sha, github_token)
    validator = load_validator()
    base_posts = validator.fetch_posts(repo, (pr.get("base") or {}).get("sha") or "", github_token)
    head_posts = validator.fetch_posts(repo, sha, github_token)
    errors = validator.evaluate(
        pr,
        files,
        checks.get("check_runs", []),
        base_posts,
        head_posts,
        lambda entry: image_loader(entry, github_token),
    )
    if not errors:
        merge_and_deploy(repo, pr, github_token)
        return 0

    print(f"PR #{number} failed article gate: " + " | ".join(errors))
    verify = verify_check(checks)
    if not verify or verify.get("status") != "completed":
        print("Fresh verify is not terminal yet; waiting for CI instead of spending a repair attempt.")
        return 0

    send_jules_repair(repo, pr, errors, verify, github_token, jules_key)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    args = parser.parse_args()
    github_token = os.environ.get("GITHUB_TOKEN", "")
    jules_key = os.environ.get("JULES_API_KEY", "")
    if not github_token:
        raise RuntimeError("GITHUB_TOKEN is required")
    if not jules_key:
        raise RuntimeError("JULES_API_KEY is required")
    return process(args.repo, args.pr, github_token, jules_key)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Article PR controller failed: {error}", file=sys.stderr)
        raise SystemExit(1)
