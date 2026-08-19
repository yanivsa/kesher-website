#!/usr/bin/env python3
"""Launch exactly one autonomous Jules article session for a publication slot.

This runner deliberately keeps the GitHub Actions YAML thin. The durable article
policy lives in `.github/prompts/jules-weekday-article-update.md`; the runtime
prompt only supplies the slot, task identity and terminal-output contract.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://jules.googleapis.com/v1alpha"
REPO = "yanivsa/kesher-website"
SOURCE = "sources/github/yanivsa/kesher-website"
POLICY_PATH = Path(__file__).resolve().parents[1] / ".github" / "prompts" / "jules-weekday-article-update.md"
MAX_ATTEMPTS = 4
SESSION_SECONDS = 36 * 60
WAITING_STATES = {"AWAITING_USER_FEEDBACK", "WAITING_FOR_USER", "PAUSED"}
TERMINAL_FAILURES = {"FAILED", "CANCELLED", "CANCELED"}


class ArticleRunnerError(RuntimeError):
    pass


def request_json(method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    last: Exception | None = None
    for attempt in range(4):
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            if exc.code not in {429, 500, 502, 503, 504}:
                raise ArticleRunnerError(f"HTTP {exc.code}: {detail}") from exc
            last = exc
        except urllib.error.URLError as exc:
            last = exc
        time.sleep(2 ** attempt)
    raise ArticleRunnerError(f"request failed after retries: {last}")


def load_policy(path: Path = POLICY_PATH) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ArticleRunnerError(f"article policy is unreadable: {path}") from exc
    if not value:
        raise ArticleRunnerError("article policy is empty")
    return value


def article_exists_for_slot(posts: list[dict[str, Any]], slot: str) -> bool:
    return any(isinstance(post, dict) and str(post.get("date") or "") == slot for post in posts)


def build_prompt(slot: str, policy: str) -> str:
    return f"""Run one Kesher article publication task fully autonomously.

Publication slot: `{slot}` (Israel date). Create at most ONE article for this slot. If current `main` already contains an article with `date == {slot}`, or a currently open `Publish Kesher article:` PR already modifies `src/data/posts.json`, stop cleanly without editing anything and without creating another PR.

Repository: {REPO}. Start from current `main`.

Execution contract:
1. Read the durable policy below first and follow it exactly.
2. Read current `src/data/posts.json`, especially the recent articles, before selecting the topic.
3. Produce exactly one new Hebrew article for the publication slot and only the minimal generated indexes/image evidence allowed by policy.
4. Article publication runs MUST NOT create a video. The NotebookLM/Remotion video is a later controller stage after the article is public.
5. Run the required generation and full checks from the durable policy.
6. Use Jules built-in PR submission. The non-draft PR title MUST start exactly with `Publish Kesher article:`.
7. Never ask the user for approval, confirmation, topic choice, image choice, Start clicks or plan approval. Choose the smallest high-quality repo-consistent option and continue.
8. Do not edit workflows, tests, scripts, package files or existing articles. Do not create scratch/helper/cache files in the final diff.
9. A session is successful only when it produces a real pull request output. A completed session with no pull request is a failed attempt and will be replaced.

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
        if not isinstance(pr, dict) or not str(pr.get("title") or "").startswith("Publish Kesher article:"):
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
        raise ArticleRunnerError("src/data/posts.json is missing")
    posts = json.loads(posts_path.read_text(encoding="utf-8"))
    if not isinstance(posts, list):
        raise ArticleRunnerError("src/data/posts.json is not a list")
    if article_exists_for_slot(posts, slot):
        return "ARTICLE_ALREADY_PUBLISHED"
    prs = open_article_prs(token)
    if len(prs) > 1:
        raise ArticleRunnerError(f"duplicate open article PRs detected: {len(prs)}")
    if len(prs) == 1:
        return f"ARTICLE_ALREADY_IN_PROGRESS pr={prs[0].get('number')}"
    return "READY"


def create_session(api_key: str, prompt: str, attempt: int) -> tuple[str, str]:
    payload = {
        "title": f"Kesher article slot {attempt}",
        "prompt": prompt,
        "sourceContext": {
            "source": SOURCE,
            "githubRepoContext": {"startingBranch": "main"},
        },
        "requirePlanApproval": False,
    }
    created = request_json("POST", f"{API_BASE}/sessions", jules_headers(api_key), payload)
    name = str((created or {}).get("name") or (created or {}).get("id") or "")
    url = str((created or {}).get("url") or (created or {}).get("agentUrl") or (created or {}).get("sessionUrl") or "")
    if not name or not url:
        raise ArticleRunnerError(f"Jules create response missing identity: {created}")
    if not name.startswith("sessions/"):
        name = f"sessions/{name}"
    print(f"JULES_ARTICLE_STARTED attempt={attempt} session={name} url={url}", flush=True)
    return name, url


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
    )


def poll(api_key: str, session: str, timeout_seconds: int = SESSION_SECONDS) -> str | None:
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
            return urls[0]
        if state == "COMPLETED":
            print("JULES_ARTICLE_COMPLETED_WITHOUT_PR", file=sys.stderr, flush=True)
            return None
        if state in TERMINAL_FAILURES:
            print(f"JULES_ARTICLE_TERMINAL_FAILURE state={state}", file=sys.stderr, flush=True)
            return None
        if state in {"AWAITING_USER_FEEDBACK", "WAITING_FOR_USER"} and not continued:
            send_message(
                api_key,
                sid,
                "Continue autonomously. Do not ask a question. Finish the one article, validate it, and create the required PR.",
            )
            continued = True
            print("JULES_ARTICLE_CONTINUED", flush=True)
        elif state == "AWAITING_PLAN_APPROVAL" and not approved:
            request_json("POST", f"{API_BASE}/sessions/{sid}:approvePlan", jules_headers(api_key), {})
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
        request_json("DELETE", f"{API_BASE}/sessions/{sid}", jules_headers(api_key))
    except Exception as exc:
        print(f"JULES_ARTICLE_DELETE_WARNING {exc}", file=sys.stderr)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.slot):
        raise ArticleRunnerError("--slot must be YYYY-MM-DD")
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    api_key = os.environ.get("JULES_API_KEY", "").strip()
    if not github_token:
        raise ArticleRunnerError("GITHUB_TOKEN is missing")
    if not api_key:
        raise ArticleRunnerError("JULES_API_KEY is missing")

    gate = preflight(args.slot, github_token)
    if gate != "READY":
        print(gate)
        return 0

    prompt = build_prompt(args.slot, load_policy())
    for attempt in range(1, MAX_ATTEMPTS + 1):
        session, _ = create_session(api_key, prompt, attempt)
        if poll(api_key, session):
            return 0
        if attempt < MAX_ATTEMPTS:
            # Recheck reality before replacing a failed session. A slow prior attempt
            # may have produced a PR after the terminal signal was observed.
            gate = preflight(args.slot, github_token)
            if gate != "READY":
                print(gate)
                return 0
            print(f"JULES_ARTICLE_REPLACEMENT next_attempt={attempt + 1}", flush=True)
    raise ArticleRunnerError(f"all {MAX_ATTEMPTS} Jules article attempts failed to create a PR")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ArticleRunnerError, json.JSONDecodeError, ValueError, KeyError) as exc:
        print(f"JULES_ARTICLE_BLOCKED {exc}", file=sys.stderr)
        raise SystemExit(1)
