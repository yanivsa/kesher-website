#!/usr/bin/env python3
"""Read-only diagnostics for failed Jules article sessions.

This module never creates, mutates, approves, cancels, or deletes Jules work. It
uses the documented Sources, Sessions and Activities read APIs to explain why a
session that was expected to create a PR did not do so. Diagnostic text is
bounded before being written to GitHub Actions logs/artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
from pathlib import Path
from typing import Any

from scripts import jules_article_runner_core as core

MAX_ACTIVITY_PAGES = 100
MAX_DIAGNOSTIC_TEXT = 900


def _bounded(value: Any, limit: int = MAX_DIAGNOSTIC_TEXT) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def validate_configured_source(api_key: str) -> dict[str, Any]:
    """Verify that the configured Jules source resolves to this repo and main."""

    payload = core.request_json(
        "GET",
        f"{core.API_BASE}/{core.SOURCE}",
        core.jules_headers(api_key),
    )
    if not isinstance(payload, dict):
        raise core.ArticleRunnerError("JULES_SOURCE_ERROR", "configured Jules source response is invalid")

    repo = payload.get("githubRepo") or {}
    owner = str(repo.get("owner") or "")
    name = str(repo.get("repo") or "")
    branches = repo.get("branches") or []
    branch_names = {
        str(row.get("displayName") or "")
        for row in branches
        if isinstance(row, dict)
    }
    default_branch = str((repo.get("defaultBranch") or {}).get("displayName") or "")
    expected_owner, expected_repo = core.REPO.split("/", 1)

    ok = owner == expected_owner and name == expected_repo and (
        "main" in branch_names or default_branch == "main"
    )
    if not ok:
        raise core.ArticleRunnerError(
            "JULES_SOURCE_MISMATCH",
            f"configured Jules source resolved to {owner}/{name} default={default_branch or 'unknown'}",
        )

    return {
        "name": str(payload.get("name") or core.SOURCE),
        "owner": owner,
        "repo": name,
        "default_branch": default_branch,
        "main_available": True,
    }


def list_session_activities(api_key: str, session: str) -> list[dict[str, Any]]:
    """Read every activity page for one exact Jules session."""

    sid = str(session or "").removeprefix("sessions/").strip()
    if not sid:
        raise core.ArticleRunnerError("JULES_ACTIVITY_ERROR", "session id is missing")

    activities: list[dict[str, Any]] = []
    token = ""
    seen: set[str] = set()
    for _ in range(MAX_ACTIVITY_PAGES):
        query = {"pageSize": "100"}
        if token:
            query["pageToken"] = token
        payload = core.request_json(
            "GET",
            f"{core.API_BASE}/sessions/{sid}/activities?{urllib.parse.urlencode(query)}",
            core.jules_headers(api_key),
        )
        rows = payload.get("activities") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise core.ArticleRunnerError("JULES_ACTIVITY_ERROR", "Jules activities response is invalid")
        activities.extend(row for row in rows if isinstance(row, dict))

        next_token = str((payload or {}).get("nextPageToken") or "").strip()
        if not next_token:
            break
        if next_token in seen:
            raise core.ArticleRunnerError("JULES_ACTIVITY_ERROR", "Jules activity pagination repeated a page token")
        seen.add(next_token)
        token = next_token
    else:
        raise core.ArticleRunnerError(
            "JULES_ACTIVITY_ERROR",
            f"Jules activity inventory exceeded {MAX_ACTIVITY_PAGES} pages",
        )

    activities.sort(key=lambda row: (str(row.get("createTime") or ""), str(row.get("id") or "")))
    return activities


def summarize_activities(activities: list[dict[str, Any]]) -> dict[str, Any]:
    agent_messages: list[str] = []
    progress: list[str] = []
    descriptions: list[str] = []
    change_sets = 0
    patch_fingerprints: list[str] = []
    failed_reason = ""

    for activity in activities:
        description = _bounded(activity.get("description"), 500)
        if description:
            descriptions.append(description)

        agent = activity.get("agentMessaged") or {}
        if isinstance(agent, dict) and agent.get("agentMessage"):
            agent_messages.append(_bounded(agent.get("agentMessage")))

        update = activity.get("progressUpdated") or {}
        if isinstance(update, dict):
            text = " — ".join(
                part for part in (_bounded(update.get("title"), 300), _bounded(update.get("description"), 600)) if part
            )
            if text:
                progress.append(text)

        failed = activity.get("sessionFailed") or {}
        if isinstance(failed, dict) and failed.get("reason"):
            failed_reason = _bounded(failed.get("reason"))

        for artifact in activity.get("artifacts") or []:
            if not isinstance(artifact, dict):
                continue
            change_set = artifact.get("changeSet")
            if not isinstance(change_set, dict):
                continue
            change_sets += 1
            patch = str((change_set.get("gitPatch") or {}).get("patch") or "")
            if patch:
                patch_fingerprints.append(hashlib.sha256(patch.encode("utf-8")).hexdigest()[:16])

    return {
        "activity_count": len(activities),
        "change_set_count": change_sets,
        "change_set_fingerprints": patch_fingerprints[-4:],
        "last_agent_message": agent_messages[-1] if agent_messages else "",
        "last_progress": progress[-1] if progress else "",
        "last_description": descriptions[-1] if descriptions else "",
        "session_failed_reason": failed_reason,
    }


def diagnose(api_key: str, session: str) -> dict[str, Any]:
    source = validate_configured_source(api_key)
    activities = list_session_activities(api_key, session)
    summary = summarize_activities(activities)
    result = {"source": source, "session": session, **summary}
    print("JULES_ARTICLE_DIAGNOSTIC " + json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
    return result


def attach_to_result(result_path: Path, diagnostic: dict[str, Any]) -> None:
    """Attach bounded diagnostics to the already-emitted structured result."""

    if not result_path.is_file():
        return
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return
    compact = {
        "source": diagnostic.get("source"),
        "activity_count": diagnostic.get("activity_count", 0),
        "change_set_count": diagnostic.get("change_set_count", 0),
        "change_set_fingerprints": diagnostic.get("change_set_fingerprints", []),
        "last_agent_message": _bounded(diagnostic.get("last_agent_message")),
        "last_progress": _bounded(diagnostic.get("last_progress")),
        "last_description": _bounded(diagnostic.get("last_description")),
        "session_failed_reason": _bounded(diagnostic.get("session_failed_reason")),
    }
    payload["diagnostic"] = compact
    reason = compact["last_agent_message"] or compact["session_failed_reason"] or compact["last_progress"] or compact["last_description"]
    if reason:
        original = _bounded(payload.get("message"), 500)
        payload["message"] = _bounded(f"{original}; Jules diagnostic: {reason}" if original else f"Jules diagnostic: {reason}")
    temp = result_path.with_suffix(result_path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(result_path)
