#!/usr/bin/env python3
"""Pipeline-v3 adapter for the trusted article PR controller.

Image failures belong to the trusted image worker and never consume a Jules
content-repair attempt. Content repair stays on the same PR/branch and is capped
at two repairs after the initial generation attempt (three total opportunities).
Article publication is allowed without an image; image validation remains strict
whenever an image is actually present. Auto-merge is deferred until the
controller-owned trusted image stage has made at least one attempt and reached a
terminal best-effort state (complete or deferred).
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
_original_merge_and_deploy = core.merge_and_deploy


def image_only_errors(errors: list[str]) -> bool:
    return bool(errors) and all(any(marker in error for marker in IMAGE_ERROR_MARKERS) for error in errors)


def load_validator_best_effort():
    """Keep strict validation for actual images but allow an article with none."""
    validator = _original_load_validator()
    original_evaluate = validator.evaluate

    def evaluate(*args, **kwargs):
        errors = list(original_evaluate(*args, **kwargs))
        return [error for error in errors if error != NO_IMAGE_GATE_ERROR]

    validator.evaluate = evaluate
    return validator


def controller_image_stage_terminal(repo: str, pr: dict, github_token: str) -> bool:
    """Require durable proof that the controller-owned image stage is terminal.

    A cycle rollover can legitimately reset the per-cycle attempt counter while
    retaining the still-authoritative open article PR and its already-persisted
    image result. In that case the terminal image record itself is the durable
    proof of the prior trusted attempt; refusing it would deadlock auto-merge.
    """
    number = int(pr["number"])
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

    status = str(image.get("status") or "")
    direct_attempt_proof = attempts >= 1
    persisted_complete_proof = bool(
        status == "complete"
        and image.get("provider_id")
        and image.get("source_id")
        and image.get("artifact_sha256")
    )
    persisted_deferred_proof = bool(
        status == "deferred"
        and (
            image.get("processed_run_id")
            or image.get("last_error")
            or image.get("failure_count_by_type")
        )
    )
    return bool(
        state_pr == number
        and status in {"complete", "deferred"}
        and (direct_attempt_proof or persisted_complete_proof or persisted_deferred_proof)
    )


def merge_and_deploy_after_image_stage(repo: str, pr: dict, token: str) -> None:
    """Prevent the auto-merge workflow from racing ahead of trusted image best effort."""
    if not controller_image_stage_terminal(repo, pr, token):
        print(
            f"PR #{pr['number']} passed content gates but the controller-owned trusted image "
            "stage is not terminal yet; merge deferred without consuming a content attempt."
        )
        return
    _original_merge_and_deploy(repo, pr, token)


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


def main() -> int:
    core.MAX_REPAIRS = MAX_REPAIRS
    core.load_validator = load_validator_best_effort
    core.send_jules_repair = send_jules_repair_v3
    core.merge_and_deploy = merge_and_deploy_after_image_stage
    return core.main()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Article PR controller v3 failed: {error}", file=sys.stderr)
        raise SystemExit(1)
