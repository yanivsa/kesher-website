#!/usr/bin/env python3
"""Final runtime patch: explicit deploy after a GITHUB_TOKEN merge plus staged recovery.

GitHub deliberately suppresses normal push-triggered workflow recursion for
changes made with the repository GITHUB_TOKEN. The supervisor therefore uses
workflow_dispatch exactly once after its own merge, then verifies that exact
run against the captured main SHA before live validation.

This layer also teaches the Kesher Supervisor how to recover from repeated
Jules failures without blindly resending the same instruction. Repair and
recovery messages progress through a five-stage ladder and use a pattern
library for recurring Kesher failure modes.
"""

from __future__ import annotations

import importlib.util
import os
import pathlib
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

RUNTIME_PATH = pathlib.Path(__file__).with_name("kesher_task_supervisor_runtime.py")
spec = importlib.util.spec_from_file_location("kesher_task_supervisor_runtime_impl", RUNTIME_PATH)
runtime = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = runtime
spec.loader.exec_module(runtime)

base = runtime.base
EXPECTED_DEPLOY_SHA = ""

RECOVERY_MARKER = "KESHER_RECOVERY_STAGE"
RECOVERY_MAX_STAGE = max(1, min(5, int(os.environ.get("SUPERVISOR_RECOVERY_MAX_STAGE", "5"))))
RECOVERY_PLAYBOOK_PATH = ".github/jules-templates/recovery-playbook.md"
RECOVERY_REASON_TERMS = (
    "repair",
    "recovery",
    "failed-session",
    "delivery recovery",
    "scope",
    "ci failure",
    "merge",
    "blocker",
)


def select_supervisor_deploy(
    runs: list[dict[str, Any]], expected_sha: str, after: datetime
) -> dict[str, Any] | None:
    for run in runs:
        if str(run.get("event") or "") != "workflow_dispatch":
            continue
        if str(run.get("head_sha") or "") != expected_sha:
            continue
        if base.parse_time(str(run.get("created_at") or "")) < after:
            continue
        return run
    return None


def dispatch_supervisor_deploy() -> datetime | None:
    global EXPECTED_DEPLOY_SHA
    if base.DRY_RUN:
        base.meaningful_changes.append("DRY-RUN: would dispatch one deploy.yml workflow_dispatch")
        return None

    EXPECTED_DEPLOY_SHA = runtime.current_main_sha()
    started = datetime.now(timezone.utc) - timedelta(seconds=5)
    status, _ = base.gh(
        "POST",
        f"/repos/{base.REPO}/actions/workflows/deploy.yml/dispatches",
        {"ref": "main"},
        allow={204},
    )
    if status != 204:
        raise base.ApiError(f"deploy workflow_dispatch returned {status}")
    base.meaningful_changes.append(
        f"Dispatched one deploy.yml run for merged main {EXPECTED_DEPLOY_SHA[:12]}"
    )
    return started


def wait_for_supervisor_deploy(after: datetime | None) -> base.GateState:
    if after is None:
        return base.GateState("pending", "dry-run deploy")
    expected_sha = EXPECTED_DEPLOY_SHA
    if not expected_sha:
        return base.GateState("failed", "missing captured main SHA for deploy verification")

    deadline = time.monotonic() + base.DEPLOY_WAIT_SECONDS
    last_seen = "none"
    while time.monotonic() < deadline:
        _, data = base.gh(
            "GET",
            f"/repos/{base.REPO}/actions/workflows/deploy.yml/runs?branch=main&event=workflow_dispatch&per_page=20",
        )
        run = select_supervisor_deploy(data.get("workflow_runs") or [], expected_sha, after)
        if run:
            last_seen = str(run.get("id") or "unknown")
            status = str(run.get("status") or "")
            conclusion = str(run.get("conclusion") or "")
            if status == "completed":
                if conclusion == "success":
                    return base.GateState(
                        "green",
                        f"supervisor deploy run {last_seen} succeeded for main {expected_sha[:12]}",
                    )
                return base.GateState(
                    "failed",
                    f"supervisor deploy run {last_seen} concluded {conclusion} for main {expected_sha[:12]}",
                )
        time.sleep(base.DEPLOY_POLL_SECONDS)

    return base.GateState(
        "pending",
        f"supervisor deploy run {last_seen} for main {expected_sha[:12]} did not finish within controller window",
    )


def _activity_stream(activities: list[dict[str, Any]]) -> list[tuple[str, str]]:
    ordered: list[tuple[datetime, int, str, str]] = []
    for index, activity in enumerate(activities):
        timestamp = base.parse_time(
            str(
                activity.get("createTime")
                or activity.get("updateTime")
                or activity.get("created_at")
                or ""
            )
        )
        agent = activity.get("agentMessaged")
        if isinstance(agent, dict) and agent.get("agentMessage"):
            ordered.append((timestamp, index, "agent", str(agent["agentMessage"])))
        user = activity.get("userMessaged")
        if isinstance(user, dict) and user.get("userMessage"):
            ordered.append((timestamp, index, "user", str(user["userMessage"])))
    ordered.sort(key=lambda item: (item[0], item[1]))
    return [(side, message) for _, _, side, message in ordered]


def _recovery_kind(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("too broad", "unrelated", "dirty", "mergeable=false", "scope repair", "changed files")):
        return "branch-contamination"
    if any(term in lowered for term in ("ci failure", "check-runs", "check run", "workflow failure")):
        return "ci-failure"
    if any(term in lowered for term in ("צמצום חרדי", "hebrew", "language corruption", "same string", "occurrence", "regenerate")):
        return "generated-text"
    if any(term in lowered for term in (".pyc", "generated-file", "generated file", "artifact churn")):
        return "generated-artifact"
    if any(term in lowered for term in ("launched", "evidence", "unsupported", "overclaim", "source url", "ad id")):
        return "evidence-overclaim"
    if any(term in lowered for term in ("backfill", "duplicate sha", "missing=0", "broken=0", "hero image")):
        return "image-backfill"
    if any(term in lowered for term in ("deploy", "production url", "live verification", "live-facing")):
        return "deploy-live"
    return "generic"


def _recovery_key(prompt: str, reason: str) -> str:
    haystack = f"{reason}\n{prompt}"
    issue_match = re.search(r"Issue #(\d+)", haystack, flags=re.IGNORECASE)
    pr_match = re.search(r"PR #(\d+)", haystack, flags=re.IGNORECASE)
    issue = issue_match.group(1) if issue_match else "na"
    pr = pr_match.group(1) if pr_match else "na"
    return f"issue-{issue}-pr-{pr}-{_recovery_kind(haystack)}"


def _recovery_state(
    activities: list[dict[str, Any]], key: str
) -> tuple[int, bool, list[str]]:
    """Return (next_stage, may_send, recent_agent_messages).

    A stage only advances after Jules has produced an observable agent response
    to the previous recovery instruction. This prevents the hourly controller
    from spamming a session while Jules is still working.
    """
    stream = _activity_stream(activities)
    marker = f"{RECOVERY_MARKER} key={key} stage="
    prior_positions: list[int] = []
    prior_stages: list[int] = []
    recent_agents: list[str] = []

    for index, (side, message) in enumerate(stream):
        if side == "agent":
            recent_agents.append(message)
        if side != "user" or marker not in message:
            continue
        match = re.search(re.escape(marker) + r"(\d+)", message)
        if match:
            prior_positions.append(index)
            prior_stages.append(int(match.group(1)))

    if not prior_positions:
        return 1, True, recent_agents[-3:]

    last_position = prior_positions[-1]
    responded = any(side == "agent" for side, _ in stream[last_position + 1 :])
    if not responded:
        return min(prior_stages[-1], RECOVERY_MAX_STAGE), False, recent_agents[-3:]

    return min(prior_stages[-1] + 1, RECOVERY_MAX_STAGE), True, recent_agents[-3:]


def _pattern_strategy(kind: str) -> str:
    strategies = {
        "branch-contamination": (
            "Treat the current branch history as suspect. Fetch current origin/main, derive an explicit allowlist "
            "of files required by the Issue/PR intent, reconstruct the SAME branch from clean main, and re-apply "
            "only the intended changes. Before push, prove `git diff --name-only origin/main...HEAD` matches the "
            "allowlist. Preserve the existing PR identity; never open a replacement PR."
        ),
        "ci-failure": (
            "Open the exact failing job/step logs, reproduce the narrow failing command when possible, and isolate "
            "the first causal failure rather than downstream noise. Do not weaken validators or required checks. "
            "Fix the cause, rerun the focused check, then the repository validation suite."
        ),
        "generated-text": (
            "Search every occurrence of the bad text, then trace it upstream to the source/template/generator. "
            "Fix the source of truth, regenerate the affected artifact exactly once, and assert zero bad occurrences "
            "before commit. Do not hand-edit only a generated output if regeneration would restore the defect."
        ),
        "generated-artifact": (
            "Remove accidental generated/binary artifacts from the PR and identify why they were tracked. Confirm "
            "the intended source files remain and that ignore/build rules prevent recurrence. Verify the final diff "
            "contains no unrelated generated churn."
        ),
        "evidence-overclaim": (
            "Switch to evidence-first output. Every material competitor/ads/account-state claim needs a verifiable "
            "source URL, identifier, or dated account-side evidence. Downgrade or remove unsupported claims. Never "
            "say `launched` or equivalent unless account-side activation is actually evidenced."
        ),
        "image-backfill": (
            "Build a deterministic inventory first. Repair missing/broken/duplicate images and metadata from that "
            "inventory, then run the validator and require machine-checkable totals such as missing=0, broken=0, "
            "duplicate SHA=0 before declaring completion."
        ),
        "deploy-live": (
            "Tie verification to the exact merged main SHA and exact deploy run. Inspect deploy logs on failure, fix "
            "only the causal repo/config defect, then verify the required production URL(s) and acceptance behavior."
        ),
        "generic": (
            "Change technique rather than repeating the previous edit. Build a minimal reproduction or deterministic "
            "invariant, identify the upstream source of the defect, make the smallest safe fix, and prove the blocker "
            "is gone before pushing."
        ),
    }
    return strategies[kind]


def _stage_instruction(stage: int, kind: str, recent_agents: list[str]) -> str:
    if stage == 1:
        return (
            "Stage 1 — focused repair. Diagnose the exact root cause, make the smallest safe fix, and prove the "
            "specific blocker is gone with a deterministic check before push."
        )
    if stage == 2:
        return (
            "Stage 2 — re-diagnose. Do NOT repeat the previous edit or command sequence. Re-read current main, the "
            "complete PR diff, relevant logs, and the source of truth. Explain in your own working notes why the "
            "previous attempt did not satisfy the blocker, then fix the upstream cause and add a pre/post invariant."
        )
    if stage == 3:
        return "Stage 3 — strategy change. " + _pattern_strategy(kind)
    if stage == 4:
        evidence = "\n\n".join(message[-700:] for message in recent_agents[-3:]) or "No prior agent summary available."
        return (
            "Stage 4 — controller coaching. Explicitly list what has already been attempted and why it failed to "
            "satisfy the acceptance criteria. Choose a materially different mechanism, not a wording variation. "
            "Inspect the final diff and machine-checkable evidence before claiming completion.\n\n"
            f"Recent Jules evidence to learn from:\n{evidence}"
        )
    return (
        "Stage 5 — deep recovery. Treat the previous implementation approach as invalid. Reconstruct from a clean "
        "source of truth (for code: current main while preserving the SAME branch/PR) or reimplement only the minimum "
        "accepted intent. Prove every acceptance criterion with machine-checkable evidence. If and only if progress "
        "is impossible because of a genuine external human-only dependency, report `HUMAN_BLOCKER: <minimal exact "
        "action>`. Otherwise continue autonomously; do not ask the user and do not create parallel work."
    )


def _is_recovery_reason(reason: str) -> bool:
    lowered = reason.lower()
    if "final qa" in lowered:
        return False
    return any(term in lowered for term in RECOVERY_REASON_TERMS)


def send_to_session_with_recovery(
    session: dict[str, Any], prompt: str, *, reason: str
) -> bool:
    """Wrap runtime messaging with a five-stage autonomous recovery ladder."""
    if not _is_recovery_reason(reason):
        return RUNTIME_SEND_TO_SESSION(session, prompt, reason=reason)

    name = str(session.get("name") or "")
    try:
        activities = base.jules_activities(name) if name.startswith("sessions/") else []
    except Exception:
        activities = []

    key = _recovery_key(prompt, reason)
    stage, may_send, recent_agents = _recovery_state(activities, key)
    if not may_send:
        return False

    kind = _recovery_kind(f"{reason}\n{prompt}")
    stage_instruction = _stage_instruction(stage, kind, recent_agents)
    enriched = f"""{prompt}

KESHER AUTONOMOUS RECOVERY LADDER
Read and follow `{RECOVERY_PLAYBOOK_PATH}`. This is recovery stage {stage}/{RECOVERY_MAX_STAGE} for `{key}`.
You must not repeat a failed approach unchanged. Each higher stage requires a materially different diagnostic or repair strategy.

{stage_instruction}

Global recovery invariants:
- continue the SAME Issue/session/branch/PR whenever one exists;
- no duplicate Issue, PR, Jules session, article, video, upload, or manual content retry;
- never bypass CI, validators, security gates, CSP, or safeguards;
- compare the final state against the real Definition of Done, not merely a green check;
- when content is involved, preserve one article per slot and one video per article;
- do not declare Done until the exact blocker is demonstrably absent.

{RECOVERY_MARKER} key={key} stage={stage}
"""
    sent = RUNTIME_SEND_TO_SESSION(
        session,
        enriched,
        reason=f"{reason} recovery-stage-{stage}",
    )
    if sent:
        base.meaningful_changes.append(
            f"{name}: advanced autonomous recovery {key} to stage {stage}/{RECOVERY_MAX_STAGE}"
        )
    return sent


# Override the intermediate runtime's push-observation policy. This explicit
# dispatch is safe because workflow_dispatch is the documented recursion-safe
# way to trigger a workflow from another workflow using GITHUB_TOKEN.
RUNTIME_SEND_TO_SESSION = base.send_to_session
base.send_to_session = send_to_session_with_recovery
base.dispatch_deploy = dispatch_supervisor_deploy
base.wait_for_deploy = wait_for_supervisor_deploy


if __name__ == "__main__":
    raise SystemExit(base.main())
