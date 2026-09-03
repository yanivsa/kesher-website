#!/usr/bin/env python3
"""Adaptive recovery layer for the Kesher task supervisor.

This module extends runtime_v2 without replacing its proven inventory, CI,
deploy, idempotency, or Jules-session logic. It adds three missing invariants:

1. a deterministic blocker fingerprint that survives dynamic SHA/URL changes;
2. retry de-escalation when a relevant PR head changes;
3. a machine-readable supervisor takeover state after a failed Stage 5.
"""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import re
import sys
from typing import Any

RUNTIME_V2_PATH = pathlib.Path(__file__).with_name("kesher_task_supervisor_runtime_v2.py")
spec = importlib.util.spec_from_file_location("kesher_task_supervisor_runtime_v2_impl", RUNTIME_V2_PATH)
runtime_v2 = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = runtime_v2
spec.loader.exec_module(runtime_v2)

base = runtime_v2.base
TAKEOVER_MARKER = "SUPERVISOR_TAKEOVER_REQUIRED"
TAKEOVER_COMMENT_MARKER = "kesher-supervisor-takeover"


def _normalized_blocker_detail(prompt: str, reason: str) -> str:
    """Return stable blocker text with volatile identifiers removed."""
    text = f"{reason}\n{prompt}".lower()
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"\b[0-9a-f]{7,40}\b", "<sha>", text)
    text = re.sub(r"\b(issue|pr)\s*#\s*\d+\b", r"\1 #<n>", text)
    text = re.sub(r"\bsessions/\d+\b", "sessions/<n>", text)
    text = re.sub(r"\b\d+\b", "<n>", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _detail_fingerprint(prompt: str, reason: str) -> str:
    normalized = _normalized_blocker_detail(prompt, reason)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]


def _issue_pr_identity(prompt: str, reason: str) -> tuple[str, str]:
    haystack = f"{reason}\n{prompt}"
    issue_match = re.search(r"Issue #(\d+)", haystack, flags=re.IGNORECASE)
    pr_match = re.search(r"PR #(\d+)", haystack, flags=re.IGNORECASE)
    return (
        issue_match.group(1) if issue_match else "na",
        pr_match.group(1) if pr_match else "na",
    )


def _adaptive_recovery_key(prompt: str, reason: str, kind: str) -> str:
    issue, pr = _issue_pr_identity(prompt, reason)
    fingerprint = _detail_fingerprint(prompt, reason)
    return f"issue-{issue}-pr-{pr}-{kind}-fp-{fingerprint}"


def _head_token(prompt: str) -> str:
    matches = re.findall(
        r"(?i)(?:\bHEAD\b|current\s+head)\s*[`:=]*\s*([0-9a-f]{7,40})",
        prompt,
    )
    return matches[-1].lower() if matches else "na"


def _marker_state(
    activities: list[dict[str, Any]],
    key: str,
    current_head: str,
    *,
    initial_stage: int = 1,
) -> tuple[int, bool, list[str], bool]:
    """Return stage, may_send, recent agents, takeover_required.

    A changed concrete head is treated as meaningful progress and de-escalates
    the retry ladder to Stage 1. A Stage-5 response with no newer head becomes
    a takeover state instead of an endless Stage-5 resend loop.
    """
    stream = runtime_v2._activity_stream(activities)
    marker = f"{runtime_v2.RECOVERY_MARKER} key={key} stage="
    entries: list[tuple[int, int, str]] = []
    recent_agents: list[str] = []

    for index, (side, message) in enumerate(stream):
        if side == "agent":
            recent_agents.append(message)
        if side != "user" or marker not in message:
            continue
        stage_match = re.search(re.escape(marker) + r"(\d+)", message)
        if not stage_match:
            continue
        head_match = re.search(r"\bhead=([0-9a-f]{7,40}|na)\b", message, flags=re.IGNORECASE)
        entries.append(
            (
                index,
                int(stage_match.group(1)),
                (head_match.group(1).lower() if head_match else "na"),
            )
        )

    if not entries:
        stage = max(1, min(runtime_v2.RECOVERY_MAX_STAGE, initial_stage))
        return stage, True, recent_agents[-3:], False

    last_position, last_stage, last_head = entries[-1]

    if current_head != "na" and last_head != "na" and current_head != last_head:
        return 1, True, recent_agents[-3:], False

    responded = any(side == "agent" for side, _ in stream[last_position + 1 :])
    if not responded:
        return min(last_stage, runtime_v2.RECOVERY_MAX_STAGE), False, recent_agents[-3:], False

    if last_stage >= runtime_v2.RECOVERY_MAX_STAGE:
        return runtime_v2.RECOVERY_MAX_STAGE, False, recent_agents[-3:], True

    return min(last_stage + 1, runtime_v2.RECOVERY_MAX_STAGE), True, recent_agents[-3:], False


def _record_takeover(session: dict[str, Any], key: str, reason: str) -> bool:
    issue_match = re.search(r"issue-(\d+)-", key)
    if not issue_match:
        base.warnings.append(f"{session.get('name')}: takeover state missing issue identity ({key})")
        return False

    issue_number = int(issue_match.group(1))
    marker = f"<!-- {TAKEOVER_COMMENT_MARKER} fingerprint={key} -->"
    comments = base.get_issue_comments(issue_number)
    if any(marker in str(comment.get("body") or "") for comment in comments):
        return False

    note = (
        f"{marker}\n"
        f"{TAKEOVER_MARKER}\n\n"
        f"The autonomous Jules recovery ladder exhausted Stage {runtime_v2.RECOVERY_MAX_STAGE} "
        f"for blocker fingerprint `{key}` and Jules produced a response without observable "
        f"head progress. Do not create a duplicate session/PR. A supervisor-capable executor "
        f"should continue the same Issue/branch/PR with a narrow deterministic repair.\n\n"
        f"Last recovery reason: `{reason}`"
    )
    if base.DRY_RUN:
        base.meaningful_changes.append(
            f"DRY-RUN Issue #{issue_number}: would record {TAKEOVER_MARKER} for {key}"
        )
        return True

    base.comment_issue(issue_number, note)
    base.meaningful_changes.append(
        f"Issue #{issue_number}: recorded {TAKEOVER_MARKER} for {key}"
    )
    return True


def send_to_session_with_adaptive_recovery(
    session: dict[str, Any], prompt: str, *, reason: str
) -> bool:
    """Recovery wrapper with progress reset, fingerprints and final takeover."""
    name = str(session.get("name") or "")
    try:
        activities = base.jules_activities(name) if name.startswith("sessions/") else []
    except Exception:
        activities = []

    # A genuine external/human blocker is terminal for autonomous retries.
    if base.human_blocker(activities):
        return False

    if not runtime_v2._should_use_recovery(reason, activities):
        return runtime_v2._send_with_transient_jules_retry(session, prompt, reason=reason)

    history_text = "\n".join(message for _, message in runtime_v2._activity_stream(activities)[-30:])
    kind = runtime_v2._recovery_kind(f"{reason}\n{prompt}\n{history_text}")
    key = _adaptive_recovery_key(prompt, reason, kind)
    current_head = _head_token(prompt)
    legacy_attempts = runtime_v2._legacy_attempt_count(activities, kind)
    initial_stage = min(3, 1 + legacy_attempts)
    stage, may_send, recent_agents, takeover_required = _marker_state(
        activities,
        key,
        current_head,
        initial_stage=initial_stage,
    )

    if takeover_required:
        _record_takeover(session, key, reason)
        return False
    if not may_send:
        return False

    stage_instruction = runtime_v2._stage_instruction(stage, kind, recent_agents)
    enriched = f"""{prompt}

KESHER AUTONOMOUS RECOVERY LADDER V3
Read and follow `{runtime_v2.RECOVERY_PLAYBOOK_PATH}`. This is recovery stage {stage}/{runtime_v2.RECOVERY_MAX_STAGE} for `{key}`.
The blocker fingerprint is stable across volatile SHA/URL changes. A genuinely new HEAD de-escalates the retry ladder so new progress is evaluated before escalation.
You must not repeat a failed approach unchanged.

{stage_instruction}

Global recovery invariants:
- continue the SAME Issue/session/branch/PR whenever one exists;
- no duplicate Issue, PR, Jules session, article, video, upload, or manual content retry;
- never bypass CI, validators, security gates, CSP, or safeguards;
- pending/missing CI is observation time, not a retry attempt;
- stop autonomous retries immediately on a genuine HUMAN_BLOCKER;
- compare final state against the real Definition of Done, not merely a green check;
- do not declare Done until the exact blocker is demonstrably absent.

{runtime_v2.RECOVERY_MARKER} key={key} stage={stage} head={current_head}
"""
    sent = runtime_v2._send_with_transient_jules_retry(
        session,
        enriched,
        reason=f"{reason} recovery-stage-{stage}",
    )
    if sent:
        base.meaningful_changes.append(
            f"{name}: adaptive recovery {key} stage {stage}/{runtime_v2.RECOVERY_MAX_STAGE} head={current_head}"
        )
    return sent


# runtime_v2 already patched process_issue/deploy safely. Replace only the
# messaging policy; all inventory, CI, merge, deploy and live checks stay intact.
base.send_to_session = send_to_session_with_adaptive_recovery


if __name__ == "__main__":
    raise SystemExit(base.main())
