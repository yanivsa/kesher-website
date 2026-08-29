#!/usr/bin/env python3
"""Runtime safety policy layered on the generic Kesher task supervisor.

Keeps repo-shared concerns out of Kesher supervision and observes the normal
push-triggered deployment instead of dispatching a duplicate deploy run.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
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
    """Do not dispatch deploy.yml; merge-to-main already triggers it.

    Return a slightly earlier timestamp so the base poller can discover the
    push-triggered run even if GitHub creates it a few seconds before this call.
    """
    base.meaningful_changes.append("Awaiting normal push-triggered deploy; duplicate deploy dispatch suppressed")
    return datetime.now(timezone.utc) - timedelta(minutes=2)


ORIGINAL_PROCESS_ISSUE = base.process_issue
base.process_issue = process_issue_scoped
base.dispatch_deploy = observe_push_deploy


if __name__ == "__main__":
    raise SystemExit(base.main())
