#!/usr/bin/env python3
"""Pipeline-v3 adapter for the trusted article PR controller.

Image failures belong to the trusted image worker and never consume a Jules
content-repair attempt. Content repair stays on the same PR/branch and is capped
at two repairs after the initial generation attempt (three total opportunities).
The independent article gate remains authoritative, including its required-image
contract.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

LEGACY_PATH = Path(__file__).with_name("article-pr-controller.py")
spec = importlib.util.spec_from_file_location("kesher_article_pr_controller_core", LEGACY_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load controller core from {LEGACY_PATH}")
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

MAX_TOTAL_CONTENT_ATTEMPTS = 3
MAX_REPAIRS = MAX_TOTAL_CONTENT_ATTEMPTS - 1
IMAGE_ERROR_MARKERS = (
    "image", "Image", "no-image", "local fallback", "trusted local image",
)


def image_only_errors(errors: list[str]) -> bool:
    return bool(errors) and all(any(marker in error for marker in IMAGE_ERROR_MARKERS) for error in errors)


def send_jules_repair_v3(
    repo: str,
    pr: dict,
    errors: list[str],
    verify: dict | None,
    github_token: str,
    jules_key: str,
) -> bool:
    if image_only_errors(errors):
        print(
            f"PR #{pr['number']} is waiting only for the trusted image stage; "
            "no Jules content-repair attempt is consumed."
        )
        return False

    number = int(pr["number"])
    head_sha = ((pr.get("head") or {}).get("sha") or "").lower()
    attempt, repaired_heads = core.existing_repair_attempts(repo, number, github_token)
    if head_sha in repaired_heads:
        print(f"Repair already requested for current head {head_sha}; waiting for Jules.")
        return False
    if attempt >= MAX_REPAIRS:
        print(
            f"PR #{number} exhausted {MAX_TOTAL_CONTENT_ATTEMPTS} total article content attempts "
            f"(initial + {MAX_REPAIRS} same-PR repairs)."
        )
        return False

    body = pr.get("body") or ""
    match = re.search(r"https://jules\.google\.com/task/(\d+)", body)
    if not match:
        print(f"PR #{number} has no parseable Jules task URL; cannot request autonomous repair.")
        return False

    session_id = match.group(1)
    next_repair = attempt + 1
    total_attempt = next_repair + 1
    verify_status = "missing"
    if verify:
        verify_status = f"status={verify.get('status')} conclusion={verify.get('conclusion')}"
    error_text = "\n".join(f"- {error}" for error in errors) or "- verify check did not pass"
    head_ref = (pr.get("head") or {}).get("ref") or ""

    prompt = f"""Autonomous Kesher ARTICLE-TEXT repair attempt {total_attempt}/{MAX_TOTAL_CONTENT_ATTEMPTS}.

Repair THE SAME PR #{number} AND THE SAME BRANCH `{head_ref}` only. Do not create a new article PR or branch. Do not ask for user approval.

Current head: {head_sha}
CI verify: {verify_status}
Content/gate errors:
{error_text}

Fix only the new article text and generated text indexes required by the repository. If the article is too short, structurally invalid, repetitive, too similar to recent posts, or violates content policy, rewrite only the new article as necessary. If its topic is too similar, replace that one new article within this same PR while still publishing exactly one article.

PIPELINE V3 IMAGE OWNERSHIP IS STRICT: do not generate, download, inspect, add, copy, modify or delete any image binary. Do not add/change/remove `image` or `imageAlt`. Do not write or modify Image Provider, Image Attempt Chain, Image Source URL, Image SHA-256, Image Dimensions or Image Visual Match evidence. The trusted GitHub Actions image worker owns all image mutations and provider credentials. A missing image is not a content failure and must never trigger a Jules repair; the PR must remain open until the trusted image stage satisfies the independent publication gate.

Do not edit workflows, tests, prompts, scripts, packages or public/videos/. Run the required content generation/check commands after the final text edit, push to the existing branch, and leave PR #{number} open for the trusted gates to re-check."""

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
        raise RuntimeError(f"Jules repair message failed with HTTP {error.code}: {detail}") from error

    marker = f"<!-- kesher-article-repair attempt={next_repair} head={head_sha} -->"
    comment = (
        f"{marker}\nAutomatic Jules text repair requested as total attempt "
        f"{total_attempt}/{MAX_TOTAL_CONTENT_ATTEMPTS} for this exact PR head. "
        "Trusted image ownership remains outside Jules."
    )
    core.request_json(
        "POST",
        f"https://api.github.com/repos/{repo}/issues/{number}/comments",
        github_token,
        {"body": comment},
    )
    print(
        f"Requested Jules article text repair total_attempt={total_attempt}/"
        f"{MAX_TOTAL_CONTENT_ATTEMPTS} PR=#{number}."
    )
    return True


def main() -> int:
    core.MAX_REPAIRS = MAX_REPAIRS
    core.send_jules_repair = send_jules_repair_v3
    return core.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Article PR controller v3 failed: {error}", file=sys.stderr)
        raise SystemExit(1)
