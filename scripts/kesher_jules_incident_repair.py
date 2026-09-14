from __future__ import annotations

import json
import re
import time
from typing import Any

if __package__:
    from . import jules_article_runner_core as core
else:
    import jules_article_runner_core as core

PROMPT_VERSION = 1
LOOKUP_ATTEMPTS_AFTER_UNCERTAIN_CREATE = 4
LOOKUP_DELAY_SECONDS = 5


class IncidentRepairError(RuntimeError):
    pass


def incident_session_title(idempotency_key: str) -> str:
    key = str(idempotency_key or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", key):
        raise IncidentRepairError("incident idempotency key must be a 64-character SHA-256")
    return f"Kesher incident {key[:16]}"


def build_repair_prompt(
    *,
    pipeline_id: str,
    slug: str,
    content_sha256: str,
    stage: str,
    failure_signature: str,
    idempotency_key: str,
    evidence: dict[str, Any] | None = None,
) -> str:
    evidence_json = json.dumps(evidence or {}, ensure_ascii=False, indent=2, sort_keys=True)
    return f"""Repair ONE existing Kesher production incident autonomously.

Prompt version: {PROMPT_VERSION}
Pipeline: {pipeline_id}
Slug: {slug}
Content SHA-256: {content_sha256}
Stage: {stage}
Failure signature: {failure_signature}
Incident idempotency key: {idempotency_key}

Durable evidence:
{evidence_json}

Execution contract:
1. Inspect current main, the existing PR/workflow/controller state and this exact incident evidence before acting.
2. Work ONLY on the existing identity above. Preserve every existing source_id, task_id, provider_id and artifact_id whenever present.
3. Do NOT create a new article.
4. Do NOT start a new NotebookLM provider generation or any other provider generation.
5. Do NOT create a second video/Short identity and Do NOT upload a new YouTube video. Resume/repair the existing identity only when repo code/config/workflow work can enable that recovery.
6. Do not create a duplicate Jules session or duplicate content task.
7. If a repository change is required, make the smallest safe fix, run focused regression checks, and create at most ONE repair PR for this incident. Reuse an already-open matching repair PR if one exists.
8. If no repository change is required, do not manufacture a diff. Report the exact blocker/evidence in this same session so the supervisor can take S3 ownership if needed.
9. Never weaken authentication, publication verification, deduplication, source matching, YouTube privacy/processing checks, or V6 shadow isolation.
10. Continue autonomously; do not ask the user to choose a topic, approve a plan, or start a provider job.
"""


def _list_sessions(api_key: str, title: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    page_token = ""
    seen_tokens: set[str] = set()
    for _ in range(core.MAX_SESSION_LIST_PAGES):
        query = {"pageSize": "100"}
        if page_token:
            query["pageToken"] = page_token
        import urllib.parse

        payload = core.request_json(
            "GET",
            f"{core.API_BASE}/sessions?{urllib.parse.urlencode(query)}",
            core.jules_headers(api_key),
        )
        sessions = payload.get("sessions") if isinstance(payload, dict) else None
        if not isinstance(sessions, list):
            raise IncidentRepairError("Jules incident session list response is invalid")
        for session in sessions:
            if isinstance(session, dict) and str(session.get("title") or "") == title:
                rows.append(session)
        next_token = str((payload or {}).get("nextPageToken") or "").strip()
        if not next_token:
            break
        if next_token in seen_tokens:
            raise IncidentRepairError("Jules incident session pagination repeated a token")
        seen_tokens.add(next_token)
        page_token = next_token
    else:
        raise IncidentRepairError("Jules incident session inventory exceeded safe pagination limit")
    return rows


def list_active_incident_sessions(api_key: str, title: str) -> list[dict[str, Any]]:
    rows = []
    for session in _list_sessions(api_key, title):
        state = str(session.get("state") or "UNKNOWN").upper()
        if state == "COMPLETED" or state in core.TERMINAL_FAILURES:
            continue
        if not core.normalize_session_name(session):
            continue
        rows.append(session)
    rows.sort(key=lambda row: (str(row.get("createTime") or ""), core.normalize_session_name(row)))
    return rows


def send_message(api_key: str, session: str, prompt: str) -> None:
    sid = str(session).removeprefix("sessions/")
    core.request_json(
        "POST",
        f"{core.API_BASE}/sessions/{sid}:sendMessage",
        core.jules_headers(api_key),
        {"prompt": prompt},
        max_attempts=1,
    )


def create_session(api_key: str, title: str, prompt: str) -> str:
    payload = {
        "title": title,
        "prompt": prompt,
        "sourceContext": {
            "source": core.SOURCE,
            "githubRepoContext": {"startingBranch": "main"},
        },
        "requirePlanApproval": False,
        "automationMode": "AUTO_CREATE_PR",
    }
    created = core.request_json(
        "POST",
        f"{core.API_BASE}/sessions",
        core.jules_headers(api_key),
        payload,
        max_attempts=1,
    )
    if not isinstance(created, dict):
        raise IncidentRepairError("Jules incident create response is invalid")
    name = core.normalize_session_name(created)
    if not name:
        raise IncidentRepairError("Jules incident create response is missing session identity")
    return name


def acquire_or_nudge_session(*, api_key: str, idempotency_key: str, prompt: str) -> str:
    """Reuse one exact repair session or create at most one new session.

    The mutation POST is never blindly retried. If its response is uncertain,
    lookup by the deterministic title reconciles whether Jules actually created
    the session before allowing the caller to fail closed.
    """
    title = incident_session_title(idempotency_key)
    active = list_active_incident_sessions(api_key, title)
    if len(active) > 1:
        identities = ",".join(core.normalize_session_name(row) for row in active[:8])
        raise IncidentRepairError(f"duplicate active Jules incident sessions detected: {identities}")
    if len(active) == 1:
        name = core.normalize_session_name(active[0])
        send_message(
            api_key,
            name,
            "Continue the exact existing incident repair. Re-read current evidence, keep the same identities, and finish the smallest safe repair.\n\n" + prompt,
        )
        return name

    try:
        return create_session(api_key, title, prompt)
    except (IncidentRepairError, core.ArticleRunnerError) as exc:
        original = exc

    last_error: Exception | None = None
    for attempt in range(LOOKUP_ATTEMPTS_AFTER_UNCERTAIN_CREATE):
        if attempt:
            time.sleep(LOOKUP_DELAY_SECONDS)
        try:
            recovered = list_active_incident_sessions(api_key, title)
        except (IncidentRepairError, core.ArticleRunnerError) as exc:
            last_error = exc
            continue
        if len(recovered) > 1:
            raise IncidentRepairError("duplicate active Jules incident sessions after uncertain create") from original
        if len(recovered) == 1:
            return core.normalize_session_name(recovered[0])

    detail = f"Jules incident create response was uncertain: {original}"
    if last_error is not None:
        detail += f"; final reconciliation error: {last_error}"
    raise IncidentRepairError(detail) from original
