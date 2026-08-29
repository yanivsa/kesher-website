#!/usr/bin/env python3
"""Runtime safety policy layered on the generic Kesher task supervisor.

Keeps repo-shared concerns out of Kesher supervision, adopts unlinked Kesher
PRs idempotently, suppresses repeated Jules instructions, and observes the
normal push-triggered deployment instead of dispatching a duplicate deploy.
"""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

BASE_PATH = pathlib.Path(__file__).with_name("kesher_task_supervisor.py")
spec = importlib.util.spec_from_file_location("kesher_task_supervisor_base", BASE_PATH)
base = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = base
spec.loader.exec_module(base)

EXCLUDED_PROJECT_TERMS = (
    "openclaw",
    "tailscale",
    "oracle cloud",
    "oci always free",
    "oci helper",
    "wolt",
)

KESHER_TERMS = (
    "kesher",
    "kesher.saharoni.com",
    "shira saharoni",
    "שירה סהרוני",
    "couples",
    "couple",
    "זוג",
    "parenting",
    "הורים",
    "article",
    "מאמר",
    "notebooklm",
    "remotion",
    "google ads",
    "google business profile",
    "hero image",
    "content controller",
    "seo",
    "cro",
)

HUMAN_ONLY_TERMS = (
    "continuous phone video verification",
    "phone video verification",
    "sms phone verification",
    "2fa",
    "two-factor authentication",
)

ORPHAN_MARKER = "<!-- kesher-supervisor-orphan-pr:"
MESSAGE_MARKER = "KESHER_SUPERVISOR_MESSAGE"
ORPHAN_PR_MAP: dict[int, list[dict[str, Any]]] = {}


def issue_text(issue: dict[str, Any]) -> str:
    return f"{issue.get('title', '')}\n{issue.get('body', '')}".lower()


def is_kesher_issue(issue: dict[str, Any]) -> bool:
    text = issue_text(issue)
    if any(term in text for term in EXCLUDED_PROJECT_TERMS) and "kesher" not in text:
        return False
    return any(term in text for term in KESHER_TERMS) or base.workflow_failure_id(issue) is not None


def is_kesher_pr(pr: dict[str, Any]) -> bool:
    title = str(pr.get("title") or "")
    if title.lower().startswith("chore(deps):"):
        return False
    user = pr.get("user") or {}
    if isinstance(user, dict) and "dependabot" in str(user.get("login") or "").lower():
        return False
    return is_kesher_issue({"title": title, "body": str(pr.get("body") or "")})


def is_human_only_issue(issue: dict[str, Any]) -> bool:
    text = issue_text(issue)
    return any(term in text for term in HUMAN_ONLY_TERMS)


def orphan_pr_number(issue: dict[str, Any]) -> int | None:
    match = re.search(r"<!-- kesher-supervisor-orphan-pr:(\d+) -->", str(issue.get("body") or ""))
    return int(match.group(1)) if match else None


def existing_orphan_issues(all_issues: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for issue in all_issues:
        if "pull_request" in issue:
            continue
        pr_number = orphan_pr_number(issue)
        if pr_number is not None:
            result[pr_number] = issue
    return result


def adopt_orphan_kesher_prs(all_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create/reopen one tracking Issue per unlinked open Kesher PR.

    This lets an Issue-centric controller supervise PRs such as content PRs
    that were created without a `Fixes #...` reference, without touching
    Dependabot or other projects sharing the repository.
    """
    prs = base.gh_pages(f"/repos/{base.REPO}/pulls?state=open")
    open_issue_numbers = {
        int(issue["number"])
        for issue in all_issues
        if "pull_request" not in issue and issue.get("state") == "open"
    }
    ordinary_map = ORIGINAL_LINKED_PR_MAP(prs)
    linked_open_prs = {
        int(pr["number"])
        for issue_number, linked in ordinary_map.items()
        if issue_number in open_issue_numbers
        for pr in linked
    }
    existing = existing_orphan_issues(all_issues)
    adopted: list[dict[str, Any]] = []

    for pr in prs:
        pr_number = int(pr["number"])
        if pr_number in linked_open_prs or not is_kesher_pr(pr):
            continue

        issue = existing.get(pr_number)
        if issue is not None:
            if issue.get("state") != "open":
                if not base.DRY_RUN:
                    base.gh(
                        "PATCH",
                        f"/repos/{base.REPO}/issues/{issue['number']}",
                        {"state": "open", "state_reason": "reopened"},
                    )
                    base.comment_issue(
                        int(issue["number"]),
                        f"Kesher Supervisor reopened this tracking issue because PR #{pr_number} is open again.",
                    )
                issue["state"] = "open"
                base.meaningful_changes.append(
                    f"Issue #{issue['number']}: reopened to continue unlinked PR #{pr_number}"
                )
            adopted.append(issue)
            ORPHAN_PR_MAP[int(issue["number"])] = [pr]
            continue

        marker = f"{ORPHAN_MARKER}{pr_number} -->"
        body = (
            f"{marker}\n"
            f"Kesher Supervisor adopted an open Kesher PR that had no open Issue reference.\n\n"
            f"PR: {pr.get('html_url') or pr.get('url')}\n"
            f"Title: {pr.get('title')}\n\n"
            "Original PR intent/body:\n"
            f"{str(pr.get('body') or '')[:12000]}\n\n"
            "Definition of Done for this tracking item:\n"
            "- keep and repair this exact PR/branch; never create a replacement PR;\n"
            "- preserve the PR's intended scope and remove unrelated changes;\n"
            "- require current CI/validators green;\n"
            "- require final supervisor QA on the exact head SHA;\n"
            "- merge only when safe, then verify the normal main deploy and live site;\n"
            "- do not create a second article/video generation/upload while repairing an existing content PR."
        )
        if base.DRY_RUN:
            base.meaningful_changes.append(f"DRY-RUN: would adopt unlinked Kesher PR #{pr_number}")
            continue
        _, issue = base.gh(
            "POST",
            f"/repos/{base.REPO}/issues",
            {"title": f"[Supervisor] Adopt unlinked Kesher PR #{pr_number}: {str(pr.get('title') or '')[:100]}", "body": body},
            allow={201},
        )
        adopted.append(issue)
        ORPHAN_PR_MAP[int(issue["number"])] = [pr]
        base.meaningful_changes.append(
            f"Created Issue #{issue.get('number')} to adopt unlinked Kesher PR #{pr_number}"
        )

    return adopted


def active_work_items(all_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    adopted = ORIGINAL_ACTIVE_MAIN_FAILURES(all_issues)
    adopted.extend(adopt_orphan_kesher_prs(all_issues))
    return adopted


def linked_pr_map_with_orphans(prs: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    mapping = ORIGINAL_LINKED_PR_MAP(prs)
    mapping.update(ORPHAN_PR_MAP)
    return mapping


def sync_closed_orphan_pr(issue: dict[str, Any]) -> bool:
    """Finish/close tracking issues when their adopted PR closed externally."""
    pr_number = orphan_pr_number(issue)
    if pr_number is None:
        return False

    status, pr = base.gh(
        "GET",
        f"/repos/{base.REPO}/pulls/{pr_number}",
        allow={404},
    )
    if status == 404:
        return True
    if pr.get("state") == "open":
        return False

    issue_number = int(issue["number"])
    if not pr.get("merged"):
        if issue.get("state") == "open" and not base.DRY_RUN:
            base.gh(
                "PATCH",
                f"/repos/{base.REPO}/issues/{issue_number}",
                {"state": "closed", "state_reason": "not_planned"},
            )
            base.comment_issue(
                issue_number,
                f"Kesher Supervisor closed this tracking item because PR #{pr_number} was closed without merge.",
            )
        base.meaningful_changes.append(f"Issue #{issue_number}: orphan PR #{pr_number} closed without merge")
        return True

    merged_at = base.parse_time(str(pr.get("merged_at") or pr.get("closed_at") or ""))
    _, data = base.gh(
        "GET",
        f"/repos/{base.REPO}/actions/workflows/deploy.yml/runs?branch=main&per_page=20",
    )
    deploy = next(
        (
            run
            for run in data.get("workflow_runs") or []
            if base.parse_time(str(run.get("created_at") or "")) >= merged_at
            and str(run.get("status") or "") == "completed"
            and str(run.get("conclusion") or "") == "success"
        ),
        None,
    )
    if not deploy:
        return True

    live = base.check_live(["https://kesher.saharoni.com/"])
    if live.state != "green":
        return True

    base.close_issue_if_open(
        issue_number,
        f"Kesher Supervisor verified externally merged PR #{pr_number}: deploy run {deploy.get('id')} succeeded; {live.detail}.",
    )
    return True


def process_issue_scoped(
    issue: dict[str, Any],
    prs_for_issue: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
) -> None:
    if sync_closed_orphan_pr(issue):
        return

    if not is_kesher_issue(issue):
        return

    if is_human_only_issue(issue):
        number = int(issue["number"])
        comments = base.get_issue_comments(number)
        marker = f"<!-- kesher-supervisor-human-blocker issue={number} -->"
        if marker not in "\n".join(str(c.get("body") or "") for c in comments):
            base.comment_issue(
                number,
                marker
                + "\nKesher Supervisor classified this task as human-only. "
                + "Do not create a Jules coding task. Complete the minimum external verification action described in the issue, then remove/resolve the blocker.",
            )
            base.meaningful_changes.append(f"Issue #{number}: human-only blocker recorded; no Jules task created")
        return

    return ORIGINAL_PROCESS_ISSUE(issue, prs_for_issue, sessions)


def observe_push_deploy() -> datetime:
    """Do not dispatch deploy.yml; merge-to-main already triggers it."""
    base.meaningful_changes.append("Awaiting normal push-triggered deploy; duplicate deploy dispatch suppressed")
    return datetime.now(timezone.utc) - timedelta(minutes=2)


def current_main_sha() -> str:
    _, ref = base.gh("GET", f"/repos/{base.REPO}/git/ref/heads/main")
    return str((ref.get("object") or {}).get("sha") or "")


def wait_for_push_deploy(after: datetime | None) -> base.GateState:
    """Require a successful automatic deploy for the current main SHA."""
    if after is None:
        return base.GateState("pending", "dry-run deploy")

    deadline = time.monotonic() + base.DEPLOY_WAIT_SECONDS
    last_seen = "none"
    while time.monotonic() < deadline:
        expected_sha = current_main_sha()
        _, data = base.gh(
            "GET",
            f"/repos/{base.REPO}/actions/workflows/deploy.yml/runs?branch=main&per_page=20",
        )
        candidates = []
        for run in data.get("workflow_runs") or []:
            created = base.parse_time(str(run.get("created_at") or ""))
            if created < after:
                continue
            if str(run.get("head_sha") or "") != expected_sha:
                continue
            candidates.append(run)

        if candidates:
            run = candidates[0]
            last_seen = str(run.get("id") or "unknown")
            status = str(run.get("status") or "")
            conclusion = str(run.get("conclusion") or "")
            if status == "completed":
                if conclusion == "success":
                    return base.GateState(
                        "green",
                        f"automatic deploy run {last_seen} succeeded for main {expected_sha[:12]}",
                    )
                return base.GateState(
                    "failed",
                    f"automatic deploy run {last_seen} concluded {conclusion} for main {expected_sha[:12]}",
                )
        time.sleep(base.DEPLOY_POLL_SECONDS)

    return base.GateState(
        "pending",
        f"automatic deploy run {last_seen} for current main did not finish within controller window",
    )


def pr_head_for_prompt(prompt: str) -> str:
    match = re.search(r"PR #(\d+)", prompt)
    if not match:
        return ""
    try:
        _, pr = base.gh("GET", f"/repos/{base.REPO}/pulls/{int(match.group(1))}")
        return str((pr.get("head") or {}).get("sha") or "")
    except Exception:
        return ""


def latest_agent_signature(session: dict[str, Any], activities: list[dict[str, Any]]) -> str:
    messages = base.activity_messages(activities, "agent")
    if not messages:
        return str(session.get("name") or "no-agent-message")
    return hashlib.sha256(messages[-1].encode("utf-8")).hexdigest()[:16]


def send_to_session_dedup(session: dict[str, Any], prompt: str, *, reason: str) -> bool:
    """Send at most one identical instruction per PR head / agent response.

    A new PR head creates a new generation for repair/QA. For tasks without a
    PR, a new Jules agent response creates a new generation. No observable
    change means the same hourly instruction is not resent.
    """
    name = str(session.get("name") or "")
    if not name.startswith("sessions/"):
        return False

    try:
        activities = base.jules_activities(name)
    except Exception:
        activities = []

    generation = pr_head_for_prompt(prompt) or latest_agent_signature(session, activities)
    digest = hashlib.sha256(f"{reason}\n{generation}\n{prompt}".encode("utf-8")).hexdigest()[:20]
    marker = f"{MESSAGE_MARKER} {digest}"
    if any(marker in message for message in base.activity_messages(activities, "user")):
        return False

    return ORIGINAL_SEND_TO_SESSION(session, f"{prompt}\n\n{marker}", reason=reason)


ORIGINAL_PROCESS_ISSUE = base.process_issue
ORIGINAL_ACTIVE_MAIN_FAILURES = base.active_main_failures
ORIGINAL_LINKED_PR_MAP = base.linked_pr_map
ORIGINAL_SEND_TO_SESSION = base.send_to_session

base.process_issue = process_issue_scoped
base.active_main_failures = active_work_items
base.linked_pr_map = linked_pr_map_with_orphans
base.send_to_session = send_to_session_dedup
base.dispatch_deploy = observe_push_deploy
base.wait_for_deploy = wait_for_push_deploy


if __name__ == "__main__":
    raise SystemExit(base.main())
