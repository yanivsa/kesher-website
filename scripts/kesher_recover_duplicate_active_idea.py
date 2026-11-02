#!/usr/bin/env python3
"""Fail-closed preflight for one proven duplicate KESHER active idea deadlock.

The pure recovery is deliberately strict and tested. The CLI is idempotent: outside
its exact target cycle/idea/terminal state it is a no-op so it can live temporarily
inside the canonical controller workflow without creating a second authority path.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

STATE_REF = "automation-state"
STATE_PATH = ".kesher-controller/state.json"
ARTICLE_WORKFLOW = "kesher-article-generation.yml"
MAX_HISTORY = 50


class RecoveryError(RuntimeError):
    pass


def _stage() -> dict[str, Any]:
    return {
        "attempt_count": 0,
        "status": "pending",
        "last_error": None,
        "next_retry_at": None,
        "run_id": None,
        "processed_run_id": None,
        "provider_id": None,
        "failure_fingerprint": None,
        "same_failure_streak": 0,
        "failure_count_by_type": {},
    }


def _verified_completed_idea(state: dict[str, Any], idea_id: str) -> dict[str, Any] | None:
    for row in reversed(state.get("idea_history") or []):
        if not isinstance(row, dict) or str(row.get("idea_id") or "") != idea_id:
            continue
        outputs = row.get("outputs") if isinstance(row.get("outputs"), dict) else {}
        if str(row.get("status") or "") != "complete":
            return None
        if not all(str(outputs.get(key) or "").strip() for key in ("article_url", "long_url", "short_url")):
            return None
        return row
    return None


def recover_duplicate_active_idea(
    state: dict[str, Any],
    *,
    target_cycle: str,
    target_idea_id: str,
    completed_idea_id: str,
    now_iso: str,
    pr_is_closed_unmerged: Callable[[int], bool],
    article_workflow_active: Callable[[], bool],
) -> bool:
    """Apply one exact state transition, mutating only after every gate passes."""
    if not isinstance(state, dict):
        raise RecoveryError("STATE_INVALID")
    if str(state.get("cycle") or "") != target_cycle:
        raise RecoveryError("CYCLE_MISMATCH")

    active = state.get("active_idea")
    if not isinstance(active, dict) or str(active.get("idea_id") or "") != target_idea_id:
        raise RecoveryError("ACTIVE_IDEA_MISMATCH")
    if str(active.get("status") or "") != "claimed":
        raise RecoveryError("ACTIVE_IDEA_NOT_CLAIMED")

    last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
    article = state.get("article") if isinstance(state.get("article"), dict) else {}
    attempts = int(article.get("attempts") or article.get("attempt_count") or 0)
    if (
        str(state.get("status") or "") != "blocked"
        or str(last_error.get("stage") or "") != "article"
        or str(last_error.get("code") or "") != "ARTICLE_ATTEMPTS_EXHAUSTED"
        or attempts < 3
    ):
        raise RecoveryError("NOT_TERMINAL_ARTICLE_EXHAUSTION")

    completed = _verified_completed_idea(state, completed_idea_id)
    if completed is None:
        raise RecoveryError("COMPLETED_SOURCE_NOT_VERIFIED")
    if article_workflow_active():
        raise RecoveryError("ARTICLE_WORKFLOW_ACTIVE")

    pr_number = article.get("pr_number")
    if pr_number is not None:
        try:
            pr_number = int(pr_number)
        except (TypeError, ValueError) as exc:
            raise RecoveryError("ARTICLE_PR_INVALID") from exc
        if not pr_is_closed_unmerged(pr_number):
            raise RecoveryError("DUPLICATE_PR_NOT_CLOSED_UNMERGED")

    queue = state.get("idea_queue") if isinstance(state.get("idea_queue"), list) else []
    if not queue:
        raise RecoveryError("NO_REPLACEMENT_IDEA")
    replacement = copy.deepcopy(queue[0])
    if not isinstance(replacement, dict) or str(replacement.get("status") or "") != "queued":
        raise RecoveryError("REPLACEMENT_IDEA_INVALID")
    replacement_id = str(replacement.get("idea_id") or "").strip()
    if not replacement_id or replacement_id == target_idea_id:
        raise RecoveryError("REPLACEMENT_IDEA_INVALID")

    prior_status = str(state.get("status") or "")
    rejected = copy.deepcopy(active)
    rejected.update({
        "status": "rejected",
        "rejected_at": now_iso,
        "rejection_code": "DUPLICATE_COMPLETED_SOURCE",
        "rejection_message": f"Owner recovery: duplicate source already completed as {completed_idea_id}",
        "duplicate_of_idea_id": completed_idea_id,
        "duplicate_outputs": copy.deepcopy(completed.get("outputs") or {}),
        "prior_article_attempts": attempts,
        "stale_pr_number": pr_number,
    })
    idea_history = state.get("idea_history") if isinstance(state.get("idea_history"), list) else []
    idea_history.append(rejected)
    state["idea_history"] = idea_history[-MAX_HISTORY:]

    state["idea_queue"] = copy.deepcopy(queue[1:])
    replacement.update({"status": "claimed", "publication_slot": target_cycle, "claimed_at": now_iso})
    state["active_idea"] = replacement

    article_stage = _stage()
    article_stage.update({"attempts": 0, "deploy_attempts": 0})
    state["article"] = article_stage
    state["image"] = _stage()
    state["long_video"] = _stage()
    state["short"] = _stage()
    state.pop("video", None)
    state["deliverables"] = {
        "article_url": None,
        "overview_youtube_url": None,
        "short_youtube_url": None,
        "overview_edit_verified": False,
        "short_portrait_verified": False,
        "short_signature_verified": False,
        "short_origin_verified": False,
    }
    state["pending_dispatches"] = {}
    state["status"] = "article_needed"
    state["last_error"] = None
    history = state.get("history") if isinstance(state.get("history"), list) else []
    history.append({
        "at": now_iso,
        "from": prior_status,
        "to": "article_needed",
        "reason": "owner_duplicate_active_idea_recovery",
        "details": {
            "rejected_idea_id": target_idea_id,
            "duplicate_of_idea_id": completed_idea_id,
            "stale_pr_number": pr_number,
            "replacement_idea_id": replacement_id,
            "publication_slot": target_cycle,
        },
    })
    state["history"] = history[-100:]
    state["updated_at"] = now_iso
    return True


class GitHubAPI:
    def __init__(self, token: str, repo: str, api_root: str = "https://api.github.com") -> None:
        if not token:
            raise RecoveryError("GITHUB_TOKEN_MISSING")
        self.token = token
        self.repo = repo
        self.api_root = api_root.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8") if body is not None else None
        request = urllib.request.Request(
            self.api_root + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "kesher-owner-duplicate-recovery",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RecoveryError(f"GITHUB_{exc.code}: {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise RecoveryError("GITHUB_NETWORK_UNCERTAIN") from exc

    def load_state(self) -> tuple[dict[str, Any], str]:
        quoted = urllib.parse.quote(STATE_PATH, safe="/")
        payload = self.request("GET", f"/repos/{self.repo}/contents/{quoted}?ref={STATE_REF}")
        if payload.get("encoding") != "base64":
            raise RecoveryError("STATE_ENCODING_INVALID")
        raw = base64.b64decode("".join(str(payload.get("content") or "").split()), validate=True)
        return json.loads(raw), str(payload.get("sha") or "")

    def pr_is_closed_unmerged(self, number: int) -> bool:
        pr = self.request("GET", f"/repos/{self.repo}/pulls/{number}")
        return str(pr.get("state") or "") == "closed" and pr.get("merged_at") in (None, "")

    def article_workflow_active(self) -> bool:
        for status in ("in_progress", "queued", "waiting", "pending", "requested"):
            payload = self.request(
                "GET", f"/repos/{self.repo}/actions/workflows/{ARTICLE_WORKFLOW}/runs?status={status}&per_page=10"
            )
            if int(payload.get("total_count") or 0) > 0:
                return True
        return False

    def save_state(self, state: dict[str, Any], sha: str) -> None:
        if not sha:
            raise RecoveryError("STATE_SHA_MISSING")
        written = copy.deepcopy(state)
        written["revision"] = int(written.get("revision") or 0) + 1
        encoded = base64.b64encode((json.dumps(written, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")
        quoted = urllib.parse.quote(STATE_PATH, safe="/")
        self.request("PUT", f"/repos/{self.repo}/contents/{quoted}", {
            "message": f"state: owner duplicate recovery revision {written['revision']}",
            "branch": STATE_REF,
            "content": encoded,
            "sha": sha,
        })


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cli_target_is_applicable(state: dict[str, Any], cycle: str, idea_id: str) -> bool:
    active = state.get("active_idea") if isinstance(state.get("active_idea"), dict) else {}
    last_error = state.get("last_error") if isinstance(state.get("last_error"), dict) else {}
    article = state.get("article") if isinstance(state.get("article"), dict) else {}
    attempts = int(article.get("attempts") or article.get("attempt_count") or 0)
    return (
        str(state.get("cycle") or "") == cycle
        and str(active.get("idea_id") or "") == idea_id
        and str(active.get("status") or "") == "claimed"
        and str(state.get("status") or "") == "blocked"
        and str(last_error.get("stage") or "") == "article"
        and str(last_error.get("code") or "") == "ARTICLE_ATTEMPTS_EXHAUSTED"
        and attempts >= 3
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover one proven duplicate active KESHER idea")
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--idea-id", required=True)
    parser.add_argument("--completed-idea-id", required=True)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "yanivsa/kesher-website"))
    args = parser.parse_args()

    api = GitHubAPI(os.environ.get("GITHUB_TOKEN", ""), args.repo)
    state, sha = api.load_state()
    if not _cli_target_is_applicable(state, args.cycle, args.idea_id):
        print("Duplicate-active-idea recovery not applicable; canonical controller continues")
        return 0
    if api.article_workflow_active():
        print("Duplicate-active-idea recovery deferred: article workflow is active")
        return 0

    recover_duplicate_active_idea(
        state,
        target_cycle=args.cycle,
        target_idea_id=args.idea_id,
        completed_idea_id=args.completed_idea_id,
        now_iso=_utc_now(),
        pr_is_closed_unmerged=api.pr_is_closed_unmerged,
        article_workflow_active=lambda: False,
    )
    api.save_state(state, sha)
    replacement = (state.get("active_idea") or {}).get("idea_id")
    print(f"Recovered duplicate active idea {args.idea_id}; claimed replacement {replacement}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RecoveryError as exc:
        print(f"RECOVERY_BLOCKED: {exc}", file=sys.stderr)
        sys.exit(2)
