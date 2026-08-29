#!/usr/bin/env python3
"""Jules-first supervisor for all open Kesher repository work.

The controller is intentionally separate from the daily content controller. It:
- rebuilds a fresh GitHub/Jules inventory every run;
- adopts existing Issue/PR/Jules work instead of duplicating it;
- advances stalled work by messaging the same Jules session where possible;
- uses deterministic GitHub/CI gates plus a structured Jules QA pass before merge;
- dispatches and verifies deploy/live after merge;
- never starts article/video generation or upload work itself.

State is persisted in issue comments and Jules activities, not committed to the repo.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

GITHUB_API = "https://api.github.com"
JULES_API = "https://jules.googleapis.com/v1alpha"
REPO = os.environ.get("GITHUB_REPOSITORY", "yanivsa/kesher-website")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
JULES_API_KEY = os.environ.get("JULES_API_KEY", "")
DRY_RUN = os.environ.get("SUPERVISOR_DRY_RUN", "false").lower() == "true"
MAX_NEW_SESSIONS = int(os.environ.get("SUPERVISOR_MAX_NEW_SESSIONS", "1"))
NEW_SESSION_INTERVAL_HOURS = int(os.environ.get("SUPERVISOR_NEW_SESSION_INTERVAL_HOURS", "2"))
FORCE_NEW_SESSIONS = os.environ.get("SUPERVISOR_FORCE_NEW_SESSIONS", "false").lower() == "true"
MAX_MESSAGES = int(os.environ.get("SUPERVISOR_MAX_MESSAGES_PER_RUN", "30"))
DEPLOY_WAIT_SECONDS = int(os.environ.get("SUPERVISOR_DEPLOY_WAIT_SECONDS", "900"))
DEPLOY_POLL_SECONDS = int(os.environ.get("SUPERVISOR_DEPLOY_POLL_SECONDS", "15"))

SESSION_MARKER = "<!-- kesher-supervisor-session"
HUMAN_MARKER = "<!-- kesher-supervisor-human-blocker"
WORKFLOW_MARKER = "<!-- kesher-supervisor-workflow-failure:"
QA_REQUEST = "KESHER_SUPERVISOR_QA_REQUEST"
QA_PASS = "KESHER_SUPERVISOR_QA_PASS"

ACTIVE_STATES = {
    "QUEUED",
    "PLANNING",
    "AWAITING_PLAN_APPROVAL",
    "AWAITING_USER_FEEDBACK",
    "IN_PROGRESS",
    "PAUSED",
}
FAILED_STATES = {"FAILED", "CANCELLED"}
GOOD_CONCLUSIONS = {"success", "neutral", "skipped"}
HUMAN_LABELS = {
    "human-blocked",
    "needs-human",
    "needs-user",
    "needs-user-action",
    "blocked-human",
}
CONTENT_GENERATION_WORDS = {
    "generate article",
    "article generation",
    "generate video",
    "video generation",
    "upload video",
    "youtube upload",
}
ALLOWED_MAIN_FAILURE_WORKFLOWS = {
    "CI",
    "Deploy to Cloudflare Pages",
    "Kesher Content Controller",
}

new_sessions = 0
messages_sent = 0
meaningful_changes: list[str] = []
warnings: list[str] = []


class ApiError(RuntimeError):
    pass


def _request_json(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, Any] | None = None,
    *,
    allow: set[int] | None = None,
    attempts: int = 3,
) -> tuple[int, Any]:
    allow = allow or set()
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, data=payload, method=method, headers=headers)
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                raw = response.read()
                parsed = json.loads(raw) if raw else {}
                return response.status, parsed
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code in allow:
                try:
                    return exc.code, json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return exc.code, {"raw": raw}
            retryable = exc.code == 429 or exc.code >= 500
            if retryable and attempt < attempts:
                time.sleep(attempt * 3)
                continue
            raise ApiError(f"{method} {url} -> HTTP {exc.code}: {raw[:1200]}") from exc
        except urllib.error.URLError as exc:
            if attempt < attempts:
                time.sleep(attempt * 3)
                continue
            raise ApiError(f"{method} {url} -> {exc.reason}") from exc
    raise ApiError(f"{method} {url} exhausted retries")


def gh(method: str, path: str, body: dict[str, Any] | None = None, *, allow: set[int] | None = None) -> tuple[int, Any]:
    if not GITHUB_TOKEN:
        raise ApiError("GITHUB_TOKEN is required")
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kesher-task-supervisor",
    }
    return _request_json(method, f"{GITHUB_API}{path}", headers, body, allow=allow)


def jules(method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    if not JULES_API_KEY:
        raise ApiError("JULES_API_KEY is required")
    headers = {
        "x-goog-api-key": JULES_API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "kesher-task-supervisor",
    }
    return _request_json(method, f"{JULES_API}{path}", headers, body)


def gh_pages(path: str, key: str | None = None, limit_pages: int = 10) -> list[Any]:
    items: list[Any] = []
    separator = "&" if "?" in path else "?"
    for page in range(1, limit_pages + 1):
        _, data = gh("GET", f"{path}{separator}per_page=100&page={page}")
        batch = data.get(key, []) if key else data
        if not isinstance(batch, list):
            break
        items.extend(batch)
        if len(batch) < 100:
            break
    return items


def jules_sessions(limit_pages: int = 5) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    token = ""
    for _ in range(limit_pages):
        query = "?pageSize=100"
        if token:
            query += "&pageToken=" + urllib.parse.quote(token, safe="")
        _, data = jules("GET", f"/sessions{query}")
        batch = data.get("sessions", [])
        sessions.extend(s for s in batch if isinstance(s, dict))
        token = str(data.get("nextPageToken") or "")
        if not token:
            break
    return sessions


def jules_activities(session_name: str) -> list[dict[str, Any]]:
    activities: list[dict[str, Any]] = []
    token = ""
    for _ in range(5):
        query = "?pageSize=100"
        if token:
            query += "&pageToken=" + urllib.parse.quote(token, safe="")
        _, data = jules("GET", f"/{session_name}/activities{query}")
        batch = data.get("activities", [])
        activities.extend(a for a in batch if isinstance(a, dict))
        token = str(data.get("nextPageToken") or "")
        if not token:
            break
    return activities


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def issue_ref_numbers(text: str) -> set[int]:
    refs: set[int] = set()
    for match in re.finditer(
        r"(?i)\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?|issue|refs?|references?)\s*:?\s*#(\d+)",
        text or "",
    ):
        refs.add(int(match.group(1)))
    return refs


def any_ref_numbers(text: str) -> set[int]:
    refs = issue_ref_numbers(text)
    for match in re.finditer(r"(?<![\w/])#(\d+)\b", text or ""):
        refs.add(int(match.group(1)))
    return refs


def labels_of(issue: dict[str, Any]) -> set[str]:
    labels: set[str] = set()
    for label in issue.get("labels") or []:
        if isinstance(label, str):
            labels.add(label.lower())
        elif isinstance(label, dict) and label.get("name"):
            labels.add(str(label["name"]).lower())
    return labels


def issue_is_human_blocked(issue: dict[str, Any]) -> bool:
    return bool(labels_of(issue) & HUMAN_LABELS)


def issue_is_content_generation(issue: dict[str, Any]) -> bool:
    text = f"{issue.get('title', '')}\n{issue.get('body', '')}".lower()
    return any(term in text for term in CONTENT_GENERATION_WORDS)


def repo_session(session: dict[str, Any]) -> bool:
    source = str((session.get("sourceContext") or {}).get("source") or "")
    return source.rstrip("/").endswith("github/yanivsa/kesher-website") or source.rstrip("/").endswith("github-yanivsa-kesher-website")


def session_mentions(session: dict[str, Any], issue_number: int, pr_numbers: set[int]) -> bool:
    haystack = f"{session.get('title', '')}\n{session.get('prompt', '')}"
    if issue_number in any_ref_numbers(haystack):
        return True
    for output in session.get("outputs") or []:
        pr = output.get("pullRequest") if isinstance(output, dict) else None
        url = ""
        if isinstance(pr, dict):
            url = str(pr.get("url") or pr.get("htmlUrl") or "")
        elif isinstance(pr, str):
            url = pr
        match = re.search(r"/pull/(\d+)", url)
        if match and int(match.group(1)) in pr_numbers:
            return True
    return False


def pick_session(sessions: list[dict[str, Any]], issue_number: int, pr_numbers: set[int]) -> dict[str, Any] | None:
    matches = [s for s in sessions if repo_session(s) and session_mentions(s, issue_number, pr_numbers)]
    if not matches:
        return None
    matches.sort(
        key=lambda s: (
            str(s.get("state", "")).upper() in ACTIVE_STATES,
            parse_time(str(s.get("updateTime") or s.get("createTime") or "")),
        ),
        reverse=True,
    )
    return matches[0]


def get_issue_comments(number: int) -> list[dict[str, Any]]:
    return gh_pages(f"/repos/{REPO}/issues/{number}/comments")


def comment_issue(number: int, body: str) -> None:
    if DRY_RUN:
        meaningful_changes.append(f"DRY-RUN issue #{number}: would comment")
        return
    gh("POST", f"/repos/{REPO}/issues/{number}/comments", {"body": body}, allow={201})


def marker_session_from_comments(comments: list[dict[str, Any]]) -> str | None:
    pattern = re.compile(r"<!-- kesher-supervisor-session issue=\d+ session=(sessions/[^ ]+) -->")
    for comment in reversed(comments):
        body = str(comment.get("body") or "")
        match = pattern.search(body)
        if match:
            return match.group(1)
    return None


def create_session(issue: dict[str, Any], starting_branch: str = "main", pr_number: int | None = None) -> dict[str, Any] | None:
    global new_sessions
    if new_sessions >= MAX_NEW_SESSIONS:
        warnings.append(f"Issue #{issue['number']}: new-session budget exhausted")
        return None

    # Scheduled runs deliberately pace brand-new Jules tasks to stay within the
    # free-plan rolling allowance (at most 12/day with the default 2h interval).
    # Existing sessions are still continued every hour and do not wait for this gate.
    if (
        not FORCE_NEW_SESSIONS
        and NEW_SESSION_INTERVAL_HOURS > 1
        and datetime.now(timezone.utc).hour % NEW_SESSION_INTERVAL_HOURS != 0
    ):
        warnings.append(
            f"Issue #{issue['number']}: no existing Jules session; new-session pacing gate deferred creation"
        )
        return None

    number = int(issue["number"])
    title = str(issue.get("title") or "")
    body = str(issue.get("body") or "")
    scope = f"Issue #{number}"
    if pr_number:
        scope += f" / PR #{pr_number}"

    prompt = f"""You are the implementation agent for Kesher {scope}.

Repository: {REPO}
Issue title: {title}

Issue body / acceptance evidence:
{body}

Execution contract:
1. Work autonomously. Do not ask the user for approval or choices.
2. Continue this exact underlying task only. Do not create a duplicate issue, session, branch, PR, article, video generation, or upload.
3. If PR #{pr_number or 'N/A'} already exists, update that same branch/PR. Never open a replacement PR for it.
4. Read current origin/main and the issue/PR discussion before editing. Preserve unrelated work.
5. Diagnose the exact root cause and implement the smallest safe fix that satisfies the issue's Definition of Done.
6. Run the relevant focused tests and npm run check when feasible. Never weaken validators, CI, security, CSP, or safeguards.
7. Do not trigger or create scheduled Kesher article/video generation or YouTube upload. The existing Kesher Content Controller remains the sole owner of scheduled content.
8. For live-facing work, include the exact production URL(s) that must be checked after merge.
9. If an unavoidable human-only blocker exists (new secret, 2FA, admin permission, product decision), finish with a message beginning exactly:
HUMAN_BLOCKER: <minimal exact action>
10. A code-changing completion must end in the existing PR or one focused non-draft PR through Jules built-in GitHub submission. A changeSet without a published PR is not completion.
"""
    payload = {
        "title": f"[Kesher Supervisor] Issue #{number}: {title[:90]}",
        "prompt": prompt,
        "sourceContext": {
            "source": "sources/github/yanivsa/kesher-website",
            "githubRepoContext": {"startingBranch": starting_branch},
        },
        "requirePlanApproval": False,
        "automationMode": "AUTO_CREATE_PR",
    }
    if DRY_RUN:
        meaningful_changes.append(f"DRY-RUN Issue #{number}: would create Jules session on {starting_branch}")
        return None

    _, created = jules("POST", "/sessions", payload)
    name = str(created.get("name") or "")
    if not name.startswith("sessions/"):
        raise ApiError(f"Issue #{number}: Jules create response missing session name: {created}")
    new_sessions += 1
    comment_issue(
        number,
        f"{SESSION_MARKER} issue={number} session={name} -->\n"
        f"Kesher Supervisor adopted this task in Jules session `{name}`"
        + (f" on existing PR #{pr_number}." if pr_number else "."),
    )
    meaningful_changes.append(f"Issue #{number}: created Jules session {name}")
    return created


def send_to_session(session: dict[str, Any], prompt: str, *, reason: str) -> bool:
    global messages_sent
    name = str(session.get("name") or "")
    if not name.startswith("sessions/"):
        return False
    if messages_sent >= MAX_MESSAGES:
        warnings.append(f"{name}: message budget exhausted ({reason})")
        return False
    if DRY_RUN:
        meaningful_changes.append(f"DRY-RUN {name}: would send {reason}")
        return True
    jules("POST", f"/{name}:sendMessage", {"prompt": prompt})
    messages_sent += 1
    meaningful_changes.append(f"{name}: sent {reason}")
    return True


def latest_checks(sha: str) -> dict[str, dict[str, Any]]:
    _, data = gh("GET", f"/repos/{REPO}/commits/{sha}/check-runs?per_page=100")
    latest: dict[str, dict[str, Any]] = {}
    for check in data.get("check_runs") or []:
        name = str(check.get("name") or "")
        current = latest.get(name)
        if not current or int(check.get("id") or 0) > int(current.get("id") or 0):
            latest[name] = check
    return latest


@dataclass
class GateState:
    state: str
    detail: str


def gate_state(checks: dict[str, dict[str, Any]]) -> GateState:
    if not checks:
        return GateState("missing", "no check-runs on current head")
    required_verify = checks.get("verify")
    if required_verify is None:
        return GateState("missing", "required `verify` check is missing")
    pending = [n for n, c in checks.items() if str(c.get("status")) != "completed"]
    if pending:
        return GateState("pending", "pending: " + ", ".join(sorted(pending)))
    failed = [
        n
        for n, c in checks.items()
        if str(c.get("conclusion") or "").lower() not in GOOD_CONCLUSIONS
    ]
    if failed:
        parts = [f"{n}={checks[n].get('conclusion')}" for n in sorted(failed)]
        return GateState("failed", "; ".join(parts))
    return GateState("green", "all current checks green; verify=success")


def linked_pr_map(prs: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    mapping: dict[int, list[dict[str, Any]]] = {}
    for pr in prs:
        refs = any_ref_numbers(f"{pr.get('title', '')}\n{pr.get('body', '')}")
        for ref in refs:
            mapping.setdefault(ref, []).append(pr)
    return mapping


def changed_files(pr_number: int) -> list[dict[str, Any]]:
    return gh_pages(f"/repos/{REPO}/pulls/{pr_number}/files")


def scope_gate(issue: dict[str, Any], files: list[dict[str, Any]]) -> GateState:
    paths = [str(f.get("filename") or "") for f in files]
    if not paths:
        return GateState("failed", "PR has zero changed files")
    if len(paths) > 60:
        return GateState("failed", f"PR is too broad ({len(paths)} changed files)")
    issue_text = f"{issue.get('title', '')}\n{issue.get('body', '')}".lower()
    allows_workflows = any(term in issue_text for term in (".github", "workflow", "github action", "controller"))
    workflow_paths = [p for p in paths if p.startswith(".github/workflows/")]
    if workflow_paths and not allows_workflows:
        return GateState("failed", "unrelated workflow changes: " + ", ".join(workflow_paths[:8]))
    return GateState("green", f"scope accepted ({len(paths)} files)")


def activity_messages(activities: list[dict[str, Any]], side: str) -> list[str]:
    key = "agentMessaged" if side == "agent" else "userMessaged"
    field = "agentMessage" if side == "agent" else "userMessage"
    messages: list[str] = []
    for activity in activities:
        event = activity.get(key)
        if isinstance(event, dict) and event.get(field):
            messages.append(str(event[field]))
    return messages


def qa_already_requested(activities: list[dict[str, Any]], pr_number: int, sha: str) -> bool:
    needle = f"{QA_REQUEST} PR #{pr_number} HEAD {sha}"
    return any(needle in message for message in activity_messages(activities, "user"))


def qa_passed(activities: list[dict[str, Any]], pr_number: int, sha: str) -> bool:
    needle = f"{QA_PASS} PR #{pr_number} HEAD {sha}"
    return any(needle in message for message in activity_messages(activities, "agent"))


def human_blocker(activities: list[dict[str, Any]]) -> str | None:
    for message in reversed(activity_messages(activities, "agent")):
        match = re.search(r"(?im)^HUMAN_BLOCKER:\s*(.+)$", message)
        if match:
            return match.group(1).strip()
    return None


def dispatch_ci(branch: str) -> None:
    if DRY_RUN:
        meaningful_changes.append(f"DRY-RUN: would dispatch CI on {branch}")
        return
    status, _ = gh(
        "POST",
        f"/repos/{REPO}/actions/workflows/ci.yml/dispatches",
        {"ref": branch},
        allow={204},
    )
    if status != 204:
        raise ApiError(f"CI dispatch for {branch} returned {status}")
    meaningful_changes.append(f"Dispatched CI on {branch}")


def qa_prompt(issue: dict[str, Any], pr: dict[str, Any], scope: GateState) -> str:
    number = int(issue["number"])
    pr_number = int(pr["number"])
    sha = str(pr["head"]["sha"])
    return f"""{QA_REQUEST} PR #{pr_number} HEAD {sha}

CI is green on the current head. Perform a final QA pass now against Issue #{number}'s actual Definition of Done and the current PR diff.

Required QA:
- inspect the complete current diff and relevant surrounding code;
- confirm no unrelated or generated-file churn ({scope.detail});
- verify tests/CI evidence and do not weaken validators/security safeguards;
- check security/CSP/SEO/RTL/mobile/accessibility when relevant to this issue;
- check Hebrew copy for language corruption, unsupported outcome promises, factual overclaims, or regressions when visible copy changed;
- for live-facing work, identify exact production URL(s) to validate after merge;
- preserve the scheduled Kesher content chain; do not generate or upload any new article/video.

If ANY defect exists, fix it on this SAME branch/PR, run the relevant checks, and do NOT emit a pass marker until the new PR head is validated.

If no defect remains, reply with this exact line, using the current SHA:
{QA_PASS} PR #{pr_number} HEAD {sha}

Do not open another PR. Do not ask the user a question.
"""


def repair_prompt(issue: dict[str, Any], pr: dict[str, Any], reason: str) -> str:
    return f"""Kesher Supervisor repair request for Issue #{issue['number']} / PR #{pr['number']}.

The current PR is not eligible to merge.
Exact blocker: {reason}

Work on the SAME PR/branch only. Diagnose the exact root cause, make the smallest safe correction, and run relevant focused checks plus `npm run check` when feasible. Do not weaken validators, CI, security gates, CSP, or safeguards. Remove unrelated changes if scope is broad. Do not create a replacement PR, article, video generation, or upload. When fixed, publish the corrected head to this same PR and let CI run.
"""


def ensure_session(
    issue: dict[str, Any],
    pr: dict[str, Any] | None,
    sessions: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> dict[str, Any] | None:
    pr_numbers = {int(pr["number"])} if pr else set()
    session = pick_session(sessions, int(issue["number"]), pr_numbers)
    marker_name = marker_session_from_comments(comments)
    if marker_name and (not session or session.get("name") != marker_name):
        try:
            _, marked = jules("GET", f"/{marker_name}")
            if repo_session(marked):
                session = marked
        except ApiError:
            pass
    if session:
        return session

    # Legacy adoption: PRs created by Jules commonly carry a task URL. Reuse it
    # before creating anything new so migration of existing work is idempotent.
    if pr:
        match = re.search(r"https://jules\.google\.com/task/(\d+)", str(pr.get("body") or ""))
        if match:
            legacy_name = f"sessions/{match.group(1)}"
            try:
                _, legacy = jules("GET", f"/{legacy_name}")
                if repo_session(legacy):
                    return legacy
            except ApiError:
                pass

    branch = str(pr["head"]["ref"]) if pr else "main"
    return create_session(issue, branch, int(pr["number"]) if pr else None)


def merge_pr(pr: dict[str, Any]) -> bool:
    number = int(pr["number"])
    sha = str(pr["head"]["sha"])
    if DRY_RUN:
        meaningful_changes.append(f"DRY-RUN PR #{number}: would merge")
        return False
    status, data = gh(
        "PUT",
        f"/repos/{REPO}/pulls/{number}/merge",
        {"merge_method": "squash", "sha": sha, "commit_title": f"Supervisor merge PR #{number}"},
        allow={200, 201, 405, 409},
    )
    if status in {200, 201} and data.get("merged"):
        meaningful_changes.append(f"PR #{number}: merged after CI + supervisor QA")
        return True
    warnings.append(f"PR #{number}: merge rejected ({status}) {data.get('message', '')}")
    return False


def dispatch_deploy() -> datetime | None:
    if DRY_RUN:
        meaningful_changes.append("DRY-RUN: would dispatch deploy.yml on main")
        return None
    before = datetime.now(timezone.utc)
    status, _ = gh(
        "POST",
        f"/repos/{REPO}/actions/workflows/deploy.yml/dispatches",
        {"ref": "main"},
        allow={204},
    )
    if status != 204:
        raise ApiError(f"deploy dispatch returned {status}")
    meaningful_changes.append("Dispatched deploy.yml on main")
    return before


def latest_deploy_after(after: datetime) -> dict[str, Any] | None:
    _, data = gh("GET", f"/repos/{REPO}/actions/workflows/deploy.yml/runs?branch=main&per_page=20")
    for run in data.get("workflow_runs") or []:
        created = parse_time(str(run.get("created_at") or ""))
        if created >= after:
            return run
    return None


def wait_for_deploy(after: datetime | None) -> GateState:
    if after is None:
        return GateState("pending", "dry-run deploy")
    deadline = time.monotonic() + DEPLOY_WAIT_SECONDS
    run_id = None
    while time.monotonic() < deadline:
        run = latest_deploy_after(after)
        if run:
            run_id = run.get("id")
            status = str(run.get("status") or "")
            conclusion = str(run.get("conclusion") or "")
            if status == "completed":
                if conclusion == "success":
                    return GateState("green", f"deploy run {run_id} succeeded")
                return GateState("failed", f"deploy run {run_id} concluded {conclusion}")
        time.sleep(DEPLOY_POLL_SECONDS)
    return GateState("pending", f"deploy run {run_id or 'not discovered'} did not finish within controller window")


def live_urls(issue: dict[str, Any], pr: dict[str, Any]) -> list[str]:
    text = f"{issue.get('body', '')}\n{pr.get('body', '')}"
    urls = re.findall(r"https://kesher\.saharoni\.com[^\s<>)\]\"']*", text)
    clean: list[str] = []
    for url in urls:
        url = url.rstrip(".,;:")
        if url not in clean:
            clean.append(url)
    if not clean:
        clean.append("https://kesher.saharoni.com/")
    return clean[:8]


def check_live(urls: list[str]) -> GateState:
    failures: list[str] = []
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": "kesher-task-supervisor-live-check"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                if int(response.status) != 200:
                    failures.append(f"{url} -> HTTP {response.status}")
        except Exception as exc:  # network evidence only
            failures.append(f"{url} -> {exc}")
    if failures:
        return GateState("failed", "; ".join(failures))
    return GateState("green", "HTTP 200: " + ", ".join(urls))


def reopen_issue(issue_number: int, reason: str) -> None:
    if DRY_RUN:
        meaningful_changes.append(f"DRY-RUN issue #{issue_number}: would reopen ({reason})")
        return
    gh("PATCH", f"/repos/{REPO}/issues/{issue_number}", {"state": "open"})
    comment_issue(issue_number, f"Kesher Supervisor reopened this issue after merge because final verification failed:\n\n{reason}")
    meaningful_changes.append(f"Issue #{issue_number}: reopened after failed final verification")


def close_issue_if_open(issue_number: int, note: str) -> None:
    _, issue = gh("GET", f"/repos/{REPO}/issues/{issue_number}")
    if issue.get("state") == "open":
        if DRY_RUN:
            meaningful_changes.append(f"DRY-RUN issue #{issue_number}: would close")
            return
        gh("PATCH", f"/repos/{REPO}/issues/{issue_number}", {"state": "closed", "state_reason": "completed"})
    comment_issue(issue_number, note)
    meaningful_changes.append(f"Issue #{issue_number}: verified Done")


def workflow_failure_id(issue: dict[str, Any]) -> int | None:
    match = re.search(
        r"<!-- kesher-supervisor-workflow-failure:(\d+) -->",
        str(issue.get("body") or ""),
    )
    return int(match.group(1)) if match else None


def sync_workflow_failure_issue(issue: dict[str, Any]) -> bool:
    """Return True when a synthetic workflow issue needs no Jules action this run."""
    workflow_id = workflow_failure_id(issue)
    if workflow_id is None:
        return False
    _, data = gh(
        "GET",
        f"/repos/{REPO}/actions/workflows/{workflow_id}/runs?branch=main&per_page=1",
    )
    runs = data.get("workflow_runs") or []
    if not runs:
        return False
    latest = runs[0]
    status = str(latest.get("status") or "")
    conclusion = str(latest.get("conclusion") or "")
    number = int(issue["number"])

    if status != "completed":
        # A newer recovery run is active. Do not create more code work while it is running.
        return True

    if conclusion == "success":
        if issue.get("state") == "open":
            if not DRY_RUN:
                gh(
                    "PATCH",
                    f"/repos/{REPO}/issues/{number}",
                    {"state": "closed", "state_reason": "completed"},
                )
                comment_issue(
                    number,
                    f"Kesher Supervisor auto-closed this workflow incident: latest main run "
                    f"{latest.get('html_url')} succeeded.",
                )
            meaningful_changes.append(
                f"Issue #{number}: workflow recovered on run {latest.get('id')}"
            )
        return True
    return False


def process_issue(
    issue: dict[str, Any],
    prs_for_issue: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
) -> None:
    number = int(issue["number"])
    comments = get_issue_comments(number)

    if sync_workflow_failure_issue(issue):
        return

    if issue_is_human_blocked(issue):
        return

    # Deduplicate multiple open PRs by choosing the most recently updated, never creating another.
    prs_for_issue.sort(key=lambda pr: parse_time(str(pr.get("updated_at") or pr.get("created_at") or "")), reverse=True)
    pr = prs_for_issue[0] if prs_for_issue else None
    if len(prs_for_issue) > 1:
        warnings.append(
            f"Issue #{number}: {len(prs_for_issue)} open PRs reference it; adopting PR #{pr['number']} and creating no duplicate"
        )

    session = ensure_session(issue, pr, sessions, comments)
    if session:
        try:
            activities = jules_activities(str(session["name"]))
        except ApiError as exc:
            warnings.append(f"Issue #{number}: cannot read Jules activities: {exc}")
            activities = []
        blocker = human_blocker(activities)
        if blocker and HUMAN_MARKER not in "\n".join(str(c.get("body") or "") for c in comments):
            comment_issue(
                number,
                f"{HUMAN_MARKER} issue={number} -->\n"
                f"Human-only blocker reported by Jules: **{blocker}**",
            )
            meaningful_changes.append(f"Issue #{number}: human blocker recorded")
            return
    else:
        activities = []

    if not pr:
        if not session:
            return
        state = str(session.get("state") or "").upper()
        if state in ACTIVE_STATES:
            return
        if state in FAILED_STATES:
            send_to_session(
                session,
                f"""Resume Issue #{number} autonomously after the failed/cancelled state. Re-read current main and the issue. Continue the SAME task; do not start a duplicate session or unrelated work. Produce one focused validated PR, or report HUMAN_BLOCKER only if a genuinely human-only action is unavoidable. Do not trigger article/video generation or upload.""",
                reason=f"Issue #{number} failed-session recovery",
            )
            return
        # COMPLETED with no currently linked open PR: recover same session instead of spending a new task.
        send_to_session(
            session,
            f"""Issue #{number} is still open and has no open PR linked to it, so the task is not Done. Continue this SAME session from current origin/main. If prior code was not delivered, recover delivery through Jules built-in GitHub submission. If the prior candidate is stale, reimplement only the smallest still-valid fix. Do not create duplicate content generation/upload. End with one focused PR or HUMAN_BLOCKER.""",
            reason=f"Issue #{number} delivery recovery",
        )
        return

    pr_number = int(pr["number"])
    branch = str(pr["head"]["ref"])
    sha = str(pr["head"]["sha"])

    checks = latest_checks(sha)
    ci = gate_state(checks)
    scope = scope_gate(issue, changed_files(pr_number))

    if scope.state == "failed":
        if session:
            send_to_session(session, repair_prompt(issue, pr, scope.detail), reason=f"PR #{pr_number} scope repair")
        return

    if ci.state == "missing":
        dispatch_ci(branch)
        return
    if ci.state == "pending":
        return
    if ci.state == "failed":
        if session:
            send_to_session(session, repair_prompt(issue, pr, f"CI failure: {ci.detail}"), reason=f"PR #{pr_number} CI repair")
        return

    if not session:
        return

    # CI and deterministic scope gates are green. Require structured QA tied to exact head SHA.
    if not qa_passed(activities, pr_number, sha):
        if not qa_already_requested(activities, pr_number, sha):
            send_to_session(session, qa_prompt(issue, pr, scope), reason=f"PR #{pr_number} final QA")
        return

    # Refresh PR so mergeability/head is current after QA.
    _, fresh_pr = gh("GET", f"/repos/{REPO}/pulls/{pr_number}")
    if fresh_pr.get("state") != "open" or fresh_pr.get("draft"):
        return
    if str(fresh_pr.get("base", {}).get("ref")) != "main":
        warnings.append(f"PR #{pr_number}: base is not main")
        return
    if str(fresh_pr.get("head", {}).get("sha")) != sha:
        return

    if not merge_pr(fresh_pr):
        return

    # GitHub may auto-close the issue because Jules PRs often use `Fixes #N`.
    # Keep it open until deploy/live verification has actually passed so a
    # controller crash cannot turn "merged" into a false Done state.
    _, post_merge_issue = gh("GET", f"/repos/{REPO}/issues/{number}")
    if post_merge_issue.get("state") != "open" and not DRY_RUN:
        gh("PATCH", f"/repos/{REPO}/issues/{number}", {"state": "open"})
        meaningful_changes.append(f"Issue #{number}: kept open pending deploy/live verification")

    deploy_started = dispatch_deploy()
    deploy = wait_for_deploy(deploy_started)
    if deploy.state != "green":
        reopen_issue(number, deploy.detail)
        return

    live = check_live(live_urls(issue, fresh_pr))
    if live.state != "green":
        reopen_issue(number, live.detail)
        return

    close_issue_if_open(
        number,
        f"Kesher Supervisor final verification passed after PR #{pr_number}: {deploy.detail}; {live.detail}.",
    )


def active_main_failures(all_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    _, data = gh("GET", f"/repos/{REPO}/actions/runs?branch=main&per_page=100")
    latest_by_name: dict[str, dict[str, Any]] = {}
    for run in data.get("workflow_runs") or []:
        name = str(run.get("name") or "")
        if name not in ALLOWED_MAIN_FAILURE_WORKFLOWS or name in latest_by_name:
            continue
        latest_by_name[name] = run

    existing_by_workflow: dict[int, dict[str, Any]] = {}
    for issue in all_issues:
        if "pull_request" in issue:
            continue
        workflow_id = workflow_failure_id(issue)
        if workflow_id is not None:
            existing_by_workflow[workflow_id] = issue

    adopted: list[dict[str, Any]] = []
    for name, run in latest_by_name.items():
        if str(run.get("status")) != "completed":
            continue
        conclusion = str(run.get("conclusion") or "")
        if conclusion not in {"failure", "timed_out", "action_required"}:
            continue

        workflow_id = int(run.get("workflow_id") or 0)
        existing = existing_by_workflow.get(workflow_id)
        if existing:
            if existing.get("state") != "open":
                if not DRY_RUN:
                    gh(
                        "PATCH",
                        f"/repos/{REPO}/issues/{existing['number']}",
                        {"state": "open", "state_reason": "reopened"},
                    )
                    comment_issue(
                        int(existing["number"]),
                        f"Kesher Supervisor reopened this incident for a new failing main run: "
                        f"{run.get('html_url')} (`{conclusion}`).",
                    )
                existing["state"] = "open"
                adopted.append(existing)
                meaningful_changes.append(
                    f"Issue #{existing['number']}: reopened for recurring workflow failure {name}"
                )
            continue

        marker = f"{WORKFLOW_MARKER}{workflow_id} -->"
        title = f"[Supervisor] Active workflow failure: {name}"
        body = (
            f"{marker}\n"
            f"The latest `{name}` run on `main` is failing and represents unowned open work.\n\n"
            f"Run: {run.get('html_url')}\n"
            f"Conclusion: `{conclusion}`\n"
            f"Head SHA: `{run.get('head_sha')}`\n\n"
            "Definition of Done:\n"
            "- diagnose the exact root cause;\n"
            "- apply only the smallest safe repo/workflow repair if the failure is code/config related;\n"
            "- if the failure is an external/retryable provider condition already owned by heartbeat/backoff, do not create duplicate recovery work;\n"
            "- keep existing security/CI/content idempotency safeguards;\n"
            "- get the relevant workflow green again;\n"
            "- for Deploy failures, verify the public site after recovery.\n\n"
            "Do not trigger duplicate scheduled article/video generation or upload."
        )
        if DRY_RUN:
            meaningful_changes.append(f"DRY-RUN: would create issue for active workflow failure {name}")
            continue
        _, issue = gh("POST", f"/repos/{REPO}/issues", {"title": title, "body": body}, allow={201})
        adopted.append(issue)
        meaningful_changes.append(f"Created Issue #{issue.get('number')} for active workflow failure {name}")
    return adopted


def main() -> int:
    if not GITHUB_TOKEN or not JULES_API_KEY:
        missing = [name for name, value in (("GITHUB_TOKEN", GITHUB_TOKEN), ("JULES_API_KEY", JULES_API_KEY)) if not value]
        print("Missing required secret(s): " + ", ".join(missing), file=sys.stderr)
        return 2

    all_repo_items = gh_pages(f"/repos/{REPO}/issues?state=all")
    issues = [
        i for i in all_repo_items
        if "pull_request" not in i and i.get("state") == "open"
    ]
    prs = gh_pages(f"/repos/{REPO}/pulls?state=open")
    sessions = jules_sessions()

    # Convert active unowned main failures into persistent deduplicated issues,
    # reopening the same incident on recurrence instead of creating duplicates.
    adopted = active_main_failures(all_repo_items)
    known_numbers = {int(i["number"]) for i in issues}
    issues.extend(i for i in adopted if int(i["number"]) not in known_numbers)

    mapping = linked_pr_map(prs)
    issues.sort(
        key=lambda i: (
            "p0" not in labels_of(i),
            "p1" not in labels_of(i),
            parse_time(str(i.get("created_at") or "")),
        )
    )

    print(
        json.dumps(
            {
                "inventory": {
                    "open_issues": len(issues),
                    "open_prs": len(prs),
                    "jules_sessions_scanned": len(sessions),
                },
                "dry_run": DRY_RUN,
            },
            ensure_ascii=False,
        )
    )

    for issue in issues:
        try:
            process_issue(issue, mapping.get(int(issue["number"]), []), sessions)
        except ApiError as exc:
            warnings.append(f"Issue #{issue.get('number')}: {exc}")
        except Exception as exc:  # isolate tasks: one broken item must not stop the inventory
            warnings.append(f"Issue #{issue.get('number')}: unexpected {type(exc).__name__}: {exc}")

    print("KESHER_SUPERVISOR_RESULT=" + json.dumps(
        {
            "meaningful_changes": meaningful_changes,
            "warnings": warnings,
            "new_sessions": new_sessions,
            "messages_sent": messages_sent,
        },
        ensure_ascii=False,
    ))
    # Warnings are reported but do not abort processing of other tasks. Hard auth/config failures returned earlier.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
