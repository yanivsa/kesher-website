#!/usr/bin/env python3
"""Runtime safety policy layered on the generic Kesher task supervisor.

Keeps repo-shared concerns out of Kesher supervision and observes the normal
push-triggered deployment instead of dispatching a duplicate deploy run.
"""

from __future__ import annotations

import importlib.util
import pathlib
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


def issue_text(issue: dict[str, Any]) -> str:
    return f"{issue.get('title', '')}\n{issue.get('body', '')}".lower()


def is_kesher_issue(issue: dict[str, Any]) -> bool:
    text = issue_text(issue)
    if any(term in text for term in EXCLUDED_PROJECT_TERMS) and "kesher" not in text:
        return False
    return any(term in text for term in KESHER_TERMS) or base.workflow_failure_id(issue) is not None


def is_human_only_issue(issue: dict[str, Any]) -> bool:
    text = issue_text(issue)
    return any(term in text for term in HUMAN_ONLY_TERMS)


def process_issue_scoped(
    issue: dict[str, Any],
    prs_for_issue: list[dict[str, Any]],
    sessions: list[dict[str, Any]],
) -> None:
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
    """Require a successful automatic deploy for the current main SHA.

    This prevents an unrelated earlier deploy inside the timestamp window from
    being mistaken for the deployment that contains the just-merged change.
    """
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


ORIGINAL_PROCESS_ISSUE = base.process_issue
base.process_issue = process_issue_scoped
base.dispatch_deploy = observe_push_deploy
base.wait_for_deploy = wait_for_push_deploy


if __name__ == "__main__":
    raise SystemExit(base.main())
