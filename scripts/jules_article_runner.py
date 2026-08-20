#!/usr/bin/env python3
"""Run one bounded Jules article worker for one publication slot.

The daily controller owns business retries and backoff. This worker creates or
resumes at most one authoritative Jules session for the slot, records a
machine-readable result artifact, and exits. Unsafe Jules mutations are never
blindly retried: if a create response is uncertain, a later lookup/retry adopts
the existing slot session instead of starting a duplicate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_BASE = "https://jules.googleapis.com/v1alpha"
REPO = "yanivsa/kesher-website"
SOURCE = "sources/github/yanivsa/kesher-website"
PROMPTS_DIR = Path(__file__).resolve().parents[1] / ".github" / "prompts"
POLICY_PATH = PROMPTS_DIR / "jules-weekday-article-update.md"
POLICY_META_PATH = PROMPTS_DIR / "jules-weekday-article-update.meta.json"
ARTICLE_POLICY_VERSION = 1
SESSION_SECONDS = 36 * 60
TERMINAL_FAILURES = {"FAILED", "CANCELLED", "CANCELED"}
RESULT_SCHEMA_VERSION = 1
DEFAULT_RESULT_PATH = Path("/tmp/kesher-article-result.json")
SESSION_LOOKUP_ATTEMPTS_AFTER_UNCERTAIN_CREATE = 4
SESSION_LOOKUP_DELAY_SECONDS = 5


class ArticleRunnerError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def result_path() -> Path:
    configured = os.environ.get("KESHER_ARTICLE_RESULT_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_RESULT_PATH


def emit_result(
    slot: str,
    outcome: str,
    *,
    retryable: bool,
    message: str = "",
    session_id: str = "",
    pr_url: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "slot": slot,
        "outcome": outcome,
        "retryable": bool(retryable),
        "message": str(message),
        "session_id": str(session_id),
        "pr_url": str(pr_url),
        "github_run_id": str(os.environ.get("GITHUB_RUN_ID") or ""),
        "completed_at": utc_now(),
    }
    path = result_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    print("KESHER_ARTICLE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
    return payload


def request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    *,
    max_attempts: int = 4,
) -> Any:
    """HTTP helper.

    Safe reads retain bounded transport retries. Callers performing a mutation
    whose duplicate side effect would be harmful must pass ``max_attempts=1``
    and reconcile uncertainty explicitly.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    last: Exception | None = None
    for attempt in range(max_attempts):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            if exc.code in {401, 403}:
                raise ArticleRunnerError("JULES_AUTH_ERROR", f"HTTP {exc.code}: {detail}") from exc
            if exc.code == 429 or exc.code in {500, 502, 503, 504}:
                last = exc
            else:
                raise ArticleRunnerError("JULES_API_ERROR", f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            last = exc
        if attempt + 1 < max_attempts:
            time.sleep(2 ** attempt)
    if isinstance(last, urllib.error.HTTPError) and last.code == 429:
        raise ArticleRunnerError("JULES_RATE_LIMIT", f"request failed after {max_attempts} attempt(s): {last}")
    if isinstance(last, urllib.error.HTTPError):
        raise ArticleRunnerError("JULES_SERVER_ERROR", f"request failed after {max_attempts} attempt(s): {last}")
    raise ArticleRunnerError("JULES_NETWORK_ERROR", f"request failed after {max_attempts} attempt(s): {last}")


def git_blob_sha1(payload: bytes) -> str:
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def load_policy(path: Path = POLICY_PATH, meta_path: Path = POLICY_META_PATH) -> str:
    try:
        raw = path.read_bytes()
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArticleRunnerError("ARTICLE_POLICY_ERROR", "article policy or version manifest is unreadable") from exc
    if not raw.strip():
        raise ArticleRunnerError("ARTICLE_POLICY_ERROR", "article policy is empty")
    if not isinstance(meta, dict) or meta.get("policy_version") != ARTICLE_POLICY_VERSION:
        raise ArticleRunnerError(
            "ARTICLE_POLICY_ERROR",
            f"article policy version mismatch: expected {ARTICLE_POLICY_VERSION}",
        )
    expected_blob = str(meta.get("git_blob_sha1") or "").strip().lower()
    actual_blob = git_blob_sha1(raw)
    if not re.fullmatch(r"[0-9a-f]{40}", expected_blob) or expected_blob != actual_blob:
        raise ArticleRunnerError(
            "ARTICLE_POLICY_ERROR",
            f"article policy content drift: expected blob {expected_blob or 'missing'}, actual {actual_blob}",
        )
    return raw.decode("utf-8").strip()


def article_exists_for_slot(posts: list[dict[str, Any]], slot: str) -> bool:
    return any(isinstance(post, dict) and str(post.get("date") or "") == slot for post in posts)


def build_prompt(slot: str, policy: str) -> str:
    return f"""Run one Kesher article publication task fully autonomously.

Publication slot: `{slot}` (Israel date). Create at most ONE article for this slot. If current `main` already contains an article with `date == {slot}`, or a currently open `Publish Kesher article:` PR already modifies `src/data/posts.json`, stop cleanly without editing anything and without creating another PR.

Repository: {REPO}. Start from current `main`.
Article policy version: `{ARTICLE_POLICY_VERSION}`.

Execution contract:
1. Read the durable policy below first and follow it exactly.
2. Read current `src/data/posts.json`, especially the recent articles, before selecting the topic.
3. Produce exactly one new Hebrew article for the publication slot and only the minimal generated indexes/image evidence allowed by policy.
4. Article publication runs MUST NOT create a video. The NotebookLM/Remotion video is a later controller stage after the article is public.
5. Run the required generation and full checks from the durable policy.
6. Use Jules built-in PR submission. The non-draft PR title MUST start exactly with `Publish Kesher article:`.
7. Never ask the user for approval, confirmation, topic choice, image choice, Start clicks or plan approval. Choose the smallest high-quality repo-consistent option and continue.
8. Do not edit workflows, tests, scripts, package files or existing articles. Do not create scratch/helper/cache files in the final diff.
9. A session is successful only when it produces a real pull request output. A completed session with no pull request is a failed attempt. The controller, not this worker, decides whether and when to retry.

--- BEGIN AUTHORITATIVE ARTICLE POLICY ---
{policy}
--- END AUTHORITATIVE ARTICLE POLICY ---
"""


def github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "kesher-jules-article-runner",
    }


def jules_headers(key: str) -> dict[str, str]:
    return {"x-goog-api-key": key, "Content-Type": "application/json"}


def open_article_prs(token: str) -> list[dict[str, Any]]:
    headers = github_headers(token)
    prs = request_json("GET", f"https://api.github.com/repos/{REPO}/pulls?state=open&per_page=100", headers)
    matches: list[dict[str, Any]] = []
    for pr in prs if isinstance(prs, list) else []:
        if not isinstance(pr, dict):
            continue
        number = pr.get("number")
        if not number:
            continue
        files = request_json("GET", f"https://api.github.com/repos/{REPO}/pulls/{number}/files?per_page=100", headers)
        if isinstance(files, list) and any(
            isinstance(row, dict) and row.get("filename") == "src/data/posts.json" for row in files
        ):
            matches.append(pr)
    return matches


def preflight(slot: str, token: str) -> str:
    posts_path = Path("src/data/posts.json")
    if not posts_path.is_file():
        raise ArticleRunnerError("ARTICLE_SOURCE_ERROR", "src/data/posts.json is missing")
    try:
        posts = json.loads(posts_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArticleRunnerError("ARTICLE_SOURCE_ERROR", "src/data/posts.json is invalid JSON") from exc
    if not isinstance(posts, list):
        raise ArticleRunnerError("ARTICLE_SOURCE_ERROR", "src/data/posts.json is not a list")
    if article_exists_for_slot(posts, slot):
        return "ARTICLE_ALREADY_PUBLISHED"
    prs = open_article_prs(token)
    if len(prs) > 1:
        raise ArticleRunnerError("DUPLICATE_ARTICLE_PRS", f"duplicate open article PRs detected: {len(prs)}")
    if len(prs) == 1:
        return f"ARTICLE_ALREADY_IN_PROGRESS pr={prs[0].get('number')}"
    return "READY"


def slot_session_title(slot: str) -> str:
    return f"Kesher article {slot}"


def normalize_session_name(payload: dict[str, Any]) -> str:
    name = str(payload.get("name") or payload.get("id") or "").strip()
    if name and not name.startswith("sessions/"):
        name = f"sessions/{name}"
    return name


def list_active_slot_sessions(api_key: str, slot: str) -> list[dict[str, Any]]:
    payload = request_json(
        "GET",
        f"{API_BASE}/sessions?pageSize=100",
        jules_headers(api_key),
    )
    sessions = payload.get("sessions") if isinstance(payload, dict) else None
    if not isinstance(sessions, list):
        raise ArticleRunnerError("JULES_SESSION_LIST_ERROR", "Jules session list response is invalid")
    title = slot_session_title(slot)
    active: list[dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict) or str(session.get("title") or "") != title:
            continue
        state = str(session.get("state") or "UNKNOWN").upper()
        if state == "COMPLETED" or state in TERMINAL_FAILURES:
            continue
        if not normalize_session_name(session):
            continue
        active.append(session)
    active.sort(key=lambda row: (str(row.get("createTime") or ""), normalize_session_name(row)))
    return active


def recover_active_slot_session(api_key: str, slot: str) -> tuple[str, str] | None:
    """Reuse one live session for the slot and clean up accidental extras."""

    active = list_active_slot_sessions(api_key, slot)
    if not active:
        return None
    authoritative = active[0]
    for extra in active[1:]:
        extra_name = normalize_session_name(extra)
        try:
            request_json(
                "DELETE",
                f"{API_BASE}/{extra_name}",
                jules_headers(api_key),
                max_attempts=1,
            )
        except ArticleRunnerError as exc:
            raise ArticleRunnerError(
                "JULES_DUPLICATE_SESSION_CLEANUP",
                f"multiple active Jules sessions exist for {slot}; cleanup of {extra_name} was not confirmed: {exc}",
            ) from exc
        print(f"JULES_ARTICLE_DUPLICATE_CANCELLED session={extra_name}", flush=True)

    name = normalize_session_name(authoritative)
    url = str(
        authoritative.get("url")
        or authoritative.get("agentUrl")
        or authoritative.get("sessionUrl")
        or ""
    )
    print(f"JULES_ARTICLE_REUSED session={name}", flush=True)
    return name, url


def create_session(api_key: str, prompt: str, slot: str) -> tuple[str, str]:
    payload = {
        "title": slot_session_title(slot),
        "prompt": prompt,
        "sourceContext": {
            "source": SOURCE,
            "githubRepoContext": {"startingBranch": "main"},
        },
        "requirePlanApproval": False,
        "automationMode": "AUTO_CREATE_PR",
    }
    # Session creation is not documented as idempotent. Never retry the POST
    # blindly; reconcile an uncertain response through list/get instead.
    created = request_json(
        "POST",
        f"{API_BASE}/sessions",
        jules_headers(api_key),
        payload,
        max_attempts=1,
    )
    if not isinstance(created, dict):
        raise ArticleRunnerError("JULES_CREATE_ERROR", f"Jules create response is invalid: {created}")
    name = normalize_session_name(created)
    url = str(created.get("url") or created.get("agentUrl") or created.get("sessionUrl") or "")
    if not name:
        raise ArticleRunnerError("JULES_CREATE_ERROR", f"Jules create response missing identity: {created}")
    print(f"JULES_ARTICLE_STARTED session={name} url={url or 'n/a'}", flush=True)
    return name, url


def acquire_session(api_key: str, prompt: str, slot: str) -> tuple[str, str]:
    existing = recover_active_slot_session(api_key, slot)
    if existing:
        return existing
    try:
        return create_session(api_key, prompt, slot)
    except ArticleRunnerError as exc:
        if exc.code not in {"JULES_CREATE_ERROR", "JULES_SERVER_ERROR", "JULES_NETWORK_ERROR"}:
            raise
        original = exc

    # The create request may have reached Jules even when its response was lost.
    # Reconcile by title before allowing the controller to retry this worker.
    last_lookup_error: ArticleRunnerError | None = None
    for attempt in range(SESSION_LOOKUP_ATTEMPTS_AFTER_UNCERTAIN_CREATE):
        if attempt:
            time.sleep(SESSION_LOOKUP_DELAY_SECONDS)
        try:
            recovered = recover_active_slot_session(api_key, slot)
        except ArticleRunnerError as exc:
            last_lookup_error = exc
            continue
        if recovered:
            print("JULES_ARTICLE_CREATE_RESPONSE_RECOVERED", flush=True)
            return recovered
    detail = f"create response was uncertain: {original}"
    if last_lookup_error is not None:
        detail += f"; final reconciliation error: {last_lookup_error}"
    raise ArticleRunnerError("JULES_CREATE_UNCERTAIN", detail) from original


def pr_urls(session_payload: dict[str, Any]) -> list[str]:
    urls: list[str] = []
    for output in session_payload.get("outputs") or []:
        pr = (output or {}).get("pullRequest") or {}
        if pr.get("url"):
            urls.append(str(pr["url"]))
    return urls


def send_message(api_key: str, sid: str, prompt: str) -> None:
    request_json(
        "POST",
        f"{API_BASE}/sessions/{sid}:sendMessage",
        jules_headers(api_key),
        {"prompt": prompt},
        max_attempts=1,
    )


def poll(api_key: str, session: str, timeout_seconds: int = SESSION_SECONDS) -> tuple[str, str, str]:
    sid = session.removeprefix("sessions/")
    deadline = time.monotonic() + timeout_seconds
    continued = False
    approved = False
    paused_nudged = False
    while time.monotonic() < deadline:
        current = request_json("GET", f"{API_BASE}/sessions/{sid}", jules_headers(api_key))
        state = str((current or {}).get("state") or "UNKNOWN").upper()
        urls = pr_urls(current if isinstance(current, dict) else {})
        if urls:
            print(f"JULES_ARTICLE_PR {urls[0]}", flush=True)
            return "PR_CREATED", urls[0], ""
        if state == "COMPLETED":
            return "COMPLETED_WITHOUT_PR", "", "Jules completed without creating a pull request"
        if state in TERMINAL_FAILURES:
            return "JULES_TERMINAL_FAILURE", "", f"Jules ended with terminal state {state}"
        if state in {"AWAITING_USER_FEEDBACK", "WAITING_FOR_USER"} and not continued:
            send_message(
                api_key,
                sid,
                "Continue autonomously. Do not ask a question. Finish the one article, validate it, and create the required PR.",
            )
            continued = True
            print("JULES_ARTICLE_CONTINUED", flush=True)
        elif state == "AWAITING_PLAN_APPROVAL" and not approved:
            request_json(
                "POST",
                f"{API_BASE}/sessions/{sid}:approvePlan",
                jules_headers(api_key),
                {},
                max_attempts=1,
            )
            approved = True
            print("JULES_ARTICLE_PLAN_AUTO_APPROVED", flush=True)
        elif state == "PAUSED" and not paused_nudged:
            send_message(
                api_key,
                sid,
                "Resume autonomously and finish the existing article task, including the PR. Do not ask for approval.",
            )
            paused_nudged = True
            print("JULES_ARTICLE_RESUMED", flush=True)
        time.sleep(15)

    print(f"JULES_ARTICLE_TIMEOUT session={session}", file=sys.stderr, flush=True)
    try:
        request_json(
            "DELETE",
            f"{API_BASE}/sessions/{sid}",
            jules_headers(api_key),
            max_attempts=1,
        )
        return "JULES_TIMEOUT", "", "Jules session timed out and was cancelled"
    except ArticleRunnerError as exc:
        return (
            "JULES_TIMEOUT_CANCELLATION_UNCONFIRMED",
            "",
            f"Jules session timed out; cancellation could not be confirmed: {exc}",
        )


def retryable_code(code: str) -> bool:
    return code in {
        "COMPLETED_WITHOUT_PR",
        "JULES_TERMINAL_FAILURE",
        "JULES_TIMEOUT",
        "JULES_TIMEOUT_CANCELLATION_UNCONFIRMED",
        "JULES_RATE_LIMIT",
        "JULES_SERVER_ERROR",
        "JULES_NETWORK_ERROR",
        "JULES_CREATE_ERROR",
        "JULES_CREATE_UNCERTAIN",
        "JULES_DUPLICATE_SESSION_CLEANUP",
        "JULES_SESSION_LIST_ERROR",
    }


def run_slot(slot: str, github_token: str, api_key: str) -> int:
    gate = preflight(slot, github_token)
    if gate == "ARTICLE_ALREADY_PUBLISHED":
        emit_result(slot, gate, retryable=False, message="Article already exists in main")
        return 0
    if gate.startswith("ARTICLE_ALREADY_IN_PROGRESS"):
        emit_result(slot, "ARTICLE_ALREADY_IN_PROGRESS", retryable=False, message=gate)
        return 0

    prompt = build_prompt(slot, load_policy())
    session, _ = acquire_session(api_key, prompt, slot)
    outcome, pr_url, message = poll(api_key, session)
    emit_result(
        slot,
        outcome,
        retryable=retryable_code(outcome),
        message=message,
        session_id=session,
        pr_url=pr_url,
    )
    return 0 if outcome == "PR_CREATED" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.slot):
        raise ArticleRunnerError("ARTICLE_SLOT_ERROR", "--slot must be YYYY-MM-DD")
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    api_key = os.environ.get("JULES_API_KEY", "").strip()
    if not github_token:
        raise ArticleRunnerError("GITHUB_TOKEN_MISSING", "GITHUB_TOKEN is missing")
    if not api_key:
        raise ArticleRunnerError("JULES_API_KEY_MISSING", "JULES_API_KEY is missing")
    try:
        return run_slot(args.slot, github_token, api_key)
    except ArticleRunnerError as exc:
        emit_result(
            args.slot,
            exc.code,
            retryable=retryable_code(exc.code),
            message=str(exc),
        )
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ArticleRunnerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"JULES_ARTICLE_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
