#!/usr/bin/env python3
"""Pipeline-v3 adapter for the trusted article PR controller.

Image failures belong to the trusted image worker and never consume a Jules
content-repair attempt. Content repair stays on the same PR/branch and is capped
at two repairs after the initial generation attempt (three total opportunities).
A trusted hero image is publication-blocking. Auto-merge is allowed only after
the controller-owned image stage is complete and durable provider/source/hash
evidence exists for this exact article PR.
"""

from __future__ import annotations

import base64
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
NO_IMAGE_GATE_ERROR = "New article requires a trusted local image; no-image publication is forbidden"
CONTROLLER_STATE_REF = "automation-state"
CONTROLLER_STATE_PATH = ".kesher-controller/state.json"
_original_load_validator = core.load_validator


def image_only_errors(errors: list[str]) -> bool:
    return bool(errors) and all(any(marker in error for marker in IMAGE_ERROR_MARKERS) for error in errors)


def load_validator_best_effort():
    """Return canonical validator enforcing strict image requirements."""
    return _original_load_validator()


def controller_image_stage_terminal(
    repo: str,
    pr: dict,
    github_token: str,
    *,
    expected_slot: str = "",
) -> bool:
    """Require durable proof that the controller-owned image stage is terminal.

    A controller cycle rollover can reset attempt_count while preserving a
    validated completed image. In that case persisted provider/source/hash
    evidence is stronger proof than the historical counter. A deferred,
    exhausted, or no-image state is never publication-terminal.
    """
    number = int(pr["number"])
    if number <= 0:
        return False
    payload = core.request_json(
        "GET",
        f"https://api.github.com/repos/{repo}/contents/{CONTROLLER_STATE_PATH}?ref={CONTROLLER_STATE_REF}",
        github_token,
    )
    if not isinstance(payload, dict) or not payload.get("content"):
        raise RuntimeError("Kesher controller state is unavailable; refusing article merge")
    try:
        raw = base64.b64decode(str(payload["content"]).replace("\n", ""))
        state = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Kesher controller state is invalid; refusing article merge") from exc

    article = state.get("article") if isinstance(state, dict) else None
    image = state.get("image") if isinstance(state, dict) else None
    if not isinstance(article, dict) or not isinstance(image, dict):
        return False
    try:
        state_pr = int(article.get("pr_number") or 0)
        attempts = int(image.get("attempt_count") or 0)
    except (TypeError, ValueError):
        return False
    if state_pr != number:
        return False

    slot_clean = expected_slot.strip()
    if slot_clean:
        state_slot = str(article.get("normalization_slot") or state.get("cycle") or "").strip()
        if state_slot and state_slot != slot_clean:
            return False

    image_status = str(image.get("status") or "")
    if image_status == "complete":
        normalized_head_sha = str(article.get("normalized_head_sha") or "").strip().lower()
        current_head = str((pr.get("head") or {}).get("sha") or "").strip().lower()
        if normalized_head_sha and current_head and normalized_head_sha != current_head:
            return False
        return bool(
            image.get("provider_id")
            and image.get("source_id")
            and image.get("artifact_sha256")
        )
    return False


def verify_exact_target_pr_preflight(
    repo: str,
    pr: dict,
    github_token: str,
    *,
    expected_slot: str = "",
) -> None:
    """Validate exact target PR and durable state before any PR mutation, repair, or merge."""
    if not isinstance(pr, dict):
        raise RuntimeError("Target article PR payload is invalid")
    try:
        number = int(pr.get("number") or 0)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Target article PR number must be a positive integer") from exc
    if number <= 0:
        raise RuntimeError(f"Target article PR number must be positive: {number}")
    if pr.get("state") != "open" or pr.get("draft"):
        raise RuntimeError(f"PR #{number} is not an open non-draft PR")
    base_ref = str((pr.get("base") or {}).get("ref") or "").strip()
    if base_ref != "main":
        raise RuntimeError(f"PR #{number} does not target main (base.ref={base_ref!r})")
    head_repo = str(((pr.get("head") or {}).get("repo") or {}).get("full_name") or "").strip()
    if head_repo and head_repo != repo:
        raise RuntimeError(f"PR #{number} head repository mismatch: {head_repo!r} != {repo!r}")
    title = str(pr.get("title") or "").strip()
    if not title.startswith("Publish Kesher article:"):
        raise RuntimeError(f"PR #{number} does not have an article publication title: {title!r}")
    if not controller_image_stage_terminal(repo, pr, github_token, expected_slot=expected_slot):
        raise RuntimeError(
            f"PR #{number} is not the authoritative image-complete article PR in controller state; "
            "refusing branch update, cleanup, repair, or merge"
        )


def merge_and_deploy_after_image_stage(repo: str, pr: dict, token: str) -> None:
    """Merge the validated article; the canonical Schema-5 controller alone owns Deploy."""
    if not controller_image_stage_terminal(repo, pr, token):
        print(
            f"PR #{pr['number']} passed content gates but the controller-owned trusted image "
            "stage is not terminal yet; merge deferred without consuming a content attempt."
        )
        return
    number = int(pr["number"])
    head_sha = str((pr.get("head") or {}).get("sha") or "").strip()
    merged = core.request_json(
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
    print(f"Merged validated article PR #{number}; canonical controller owns deployment.")


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
            f"PR #{pr['number']} failed image gate; "
            "no Jules content-repair attempt is consumed.",
            file=sys.stderr,
        )
        print("ARTICLE_IMAGE_GATE_FAILED", file=sys.stderr)
        return False

    number = int(pr["number"])
    head_sha = ((pr.get("head") or {}).get("sha") or "").lower()
    attempt, repaired_heads = core.existing_repair_attempts(repo, number, github_token)
    if attempt >= MAX_REPAIRS:
        print(
            f"PR #{number} exhausted {MAX_TOTAL_CONTENT_ATTEMPTS} total article content attempts "
            f"(initial + {MAX_REPAIRS} same-PR repairs).",
            file=sys.stderr,
        )
        print("ARTICLE_ATTEMPTS_EXHAUSTED", file=sys.stderr)
        return False
    if head_sha in repaired_heads:
        print(f"Repair already requested for current head {head_sha}; waiting for Jules.", file=sys.stderr)
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

PIPELINE V3 IMAGE OWNERSHIP IS STRICT: do not generate, download, inspect, add, copy, modify or delete any image binary. Do not add/change/remove `image` or `imageAlt`. Do not write or modify Image Provider, Image Attempt Chain, Image Source URL, Image SHA-256, Image Dimensions or Image Visual Match evidence. The trusted GitHub Actions image worker owns all image mutations and provider credentials. A missing image is not a content failure and must never trigger a Jules repair.

Do not edit workflows, tests, prompts, scripts, packages or public/videos/. Run the required content generation/check commands after the final text edit, push to the existing branch, and leave PR #{number} open for the trusted gates to re-check automatically."""

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


_original_process = core.process


def process_v3(
    repo: str,
    number: int,
    github_token: str,
    jules_key: str,
    *,
    expected_slot: str = "",
) -> int:
    if int(number or 0) <= 0:
        raise RuntimeError(f"Target article PR number must be positive: {number}")
    pr = core.request_json("GET", f"https://api.github.com/repos/{repo}/pulls/{int(number)}", github_token)
    if not isinstance(pr, dict):
        raise RuntimeError(f"Unable to load PR #{number}")
    pr.setdefault("number", int(number))
    verify_exact_target_pr_preflight(repo, pr, github_token, expected_slot=expected_slot)
    return _original_process(repo, int(number), github_token, jules_key)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--slot", default="")
    args = parser.parse_args()
    github_token = os.environ.get("GITHUB_TOKEN", "")
    jules_key = os.environ.get("JULES_API_KEY", "")
    if not github_token:
        raise RuntimeError("GITHUB_TOKEN is required")
    if not jules_key:
        raise RuntimeError("JULES_API_KEY is required")

    core.MAX_REPAIRS = MAX_REPAIRS
    core.load_validator = load_validator_best_effort
    core.send_jules_repair = send_jules_repair_v3
    core.merge_and_deploy = merge_and_deploy_after_image_stage
    core.process = process_v3
    return process_v3(args.repo, args.pr, github_token, jules_key, expected_slot=args.slot)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Article PR controller v3 failed: {error}", file=sys.stderr)
        raise SystemExit(1)
