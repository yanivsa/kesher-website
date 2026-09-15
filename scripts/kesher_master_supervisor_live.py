#!/usr/bin/env python3
"""Kesher Master Supervisor V2 live escalation engine.

The Master owns escalation, but never writes the V5 production state. It keeps
its own CAS-protected outbox/state on ``automation-supervisor-state`` and uses a
persist-before-side-effect protocol so a crash cannot blindly duplicate a
recovery command.

Escalation is bounded and deterministic for one stable incident fingerprint:
S1 Controller -> S2 Jules -> S3 direct exact recovery -> HUMAN_BLOCKER.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

if __package__:
    from . import jules_article_runner_core as jules
    from . import kesher_master_supervisor_shadow as shadow
else:
    import jules_article_runner_core as jules
    import kesher_master_supervisor_shadow as shadow


SUPERVISOR_STATE_REF = "automation-supervisor-state"
SUPERVISOR_STATE_PATH = ".kesher-master-supervisor/state.json"
SUPERVISOR_SCHEMA_VERSION = 1
REPO_DEFAULT = "yanivsa/kesher-website"
ACTIVE_LIFECYCLES = {"issued", "acknowledged", "running"}
TERMINAL_LIFECYCLES = {"verified", "failed", "timed_out"}
EXTERNAL_RUNNING_LIMIT_MINUTES = 90
UNCERTAIN_ISSUE_GRACE_MINUTES = 15


class SupervisorError(RuntimeError):
    pass


class SupervisorCasConflict(SupervisorError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def incident_fingerprint(report: dict[str, Any]) -> str:
    """Stable fingerprint including failure signature, as required by the contract."""
    return _stable_hash({
        "incident_id": str(report.get("incident_id") or "").strip(),
        "failure_signature": str(report.get("failure_signature") or "").strip(),
    })[:32]


def new_supervisor_state() -> dict[str, Any]:
    return {
        "schema_version": SUPERVISOR_SCHEMA_VERSION,
        "incidents": {},
        "commands": {},
        "updated_at": None,
    }


def _command_id(report: dict[str, Any], stage: str, strike: int) -> str:
    return "ksr-" + _stable_hash({
        "fingerprint": incident_fingerprint(report),
        "stage": stage,
        "strike": strike,
        "evidence_hash": str(report.get("evidence_hash") or ""),
        "action": str(report.get("proposed_action") or ""),
    })[:24]


def _marker(report: dict[str, Any], strike: int, stage: str) -> str:
    return (
        f"MASTER_ESCALATION fingerprint={incident_fingerprint(report)} "
        f"strike={strike} stage={stage}"
    )


def prepare_escalation(
    state: dict[str, Any],
    report: dict[str, Any],
    *,
    now: str,
    prior_action_terminal: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Prepare at most one action and persist it as issued before execution.

    This function is pure. The caller must CAS-save the returned state before
    executing ``execute_now=True``.
    """
    result = copy.deepcopy(state) if isinstance(state, dict) else new_supervisor_state()
    result.setdefault("schema_version", SUPERVISOR_SCHEMA_VERSION)
    result.setdefault("incidents", {})
    result.setdefault("commands", {})
    fp = incident_fingerprint(report)
    incidents = result["incidents"]
    commands = result["commands"]
    incident = incidents.get(fp)

    if not isinstance(incident, dict) or incident.get("status") == "resolved":
        incident = {
            "fingerprint": fp,
            "incident_id": report.get("incident_id"),
            "failure_signature": report.get("failure_signature"),
            "strike": 0,
            "status": "open",
            "active_command_id": None,
            "first_seen_at": now,
            "last_seen_at": now,
            "history": [],
        }
        incidents[fp] = incident
    else:
        incident["last_seen_at"] = now

    active_id = str(incident.get("active_command_id") or "")
    active = commands.get(active_id) if active_id else None
    if isinstance(active, dict) and str(active.get("lifecycle") or "") in ACTIVE_LIFECYCLES:
        if not prior_action_terminal:
            return result, {
                "stage": "WAIT",
                "executor": None,
                "execute_now": False,
                "command_id": active_id,
                "reason": "active_command_not_terminal",
            }
        return result, {
            "stage": "WAIT",
            "executor": None,
            "execute_now": False,
            "command_id": active_id,
            "reason": "terminal_claim_without_persisted_terminal_state",
        }

    if isinstance(active, dict) and str(active.get("lifecycle") or "") in TERMINAL_LIFECYCLES:
        incident["active_command_id"] = None

    strike = int(incident.get("strike") or 0) + 1
    if strike > 3:
        incident["strike"] = strike
        incident["status"] = "human_blocker"
        incident["active_command_id"] = None
        incident["marker"] = _marker(report, strike, "HUMAN_BLOCKER")
        incident.setdefault("history", []).append({
            "at": now,
            "event": "human_blocker",
            "failure_signature": report.get("failure_signature"),
        })
        result["updated_at"] = now
        return result, {
            "stage": "HUMAN_BLOCKER",
            "executor": None,
            "execute_now": False,
            "command_id": None,
            "reason": "same_incident_exhausted_s1_s2_s3",
        }

    stage, executor = {1: ("S1", "controller"), 2: ("S2", "jules"), 3: ("S3", "direct")}[strike]
    command_id = _command_id(report, stage, strike)
    if command_id in commands:
        incident["active_command_id"] = command_id
        return result, {
            "stage": "WAIT",
            "executor": None,
            "execute_now": False,
            "command_id": command_id,
            "reason": "deterministic_command_already_exists",
        }

    command = {
        "command_id": command_id,
        "fingerprint": fp,
        "incident_id": report.get("incident_id"),
        "failure_signature": report.get("failure_signature"),
        "evidence_hash": report.get("evidence_hash"),
        "proposed_action": report.get("proposed_action"),
        "exact": copy.deepcopy(report.get("exact") or {}),
        "strike": strike,
        "stage": stage,
        "executor": executor,
        "lifecycle": "issued",
        "issued_at": now,
        "updated_at": now,
        "metadata": {},
    }
    commands[command_id] = command
    incident["strike"] = strike
    incident["status"] = "recovering"
    incident["active_command_id"] = command_id
    incident["marker"] = _marker(report, strike, stage)
    incident.setdefault("history", []).append({
        "at": now,
        "event": "command_issued",
        "command_id": command_id,
        "stage": stage,
    })
    result["updated_at"] = now
    return result, {
        "stage": stage,
        "executor": executor,
        "execute_now": True,
        "command_id": command_id,
        "reason": "bounded_escalation",
    }


def mark_command_acknowledged(
    state: dict[str, Any], command_id: str, metadata: dict[str, Any], *, at: str
) -> dict[str, Any]:
    result = copy.deepcopy(state)
    command = result.setdefault("commands", {}).get(command_id)
    if not isinstance(command, dict):
        raise SupervisorError(f"unknown command: {command_id}")
    lifecycle = str(command.get("lifecycle") or "")
    if lifecycle in {"verified", "failed"}:
        return result
    if lifecycle not in {"issued", "acknowledged", "running", "timed_out"}:
        raise SupervisorError(f"cannot acknowledge command in lifecycle={lifecycle}")
    command["lifecycle"] = "acknowledged"
    command["metadata"] = {**(command.get("metadata") or {}), **(metadata or {})}
    command["acknowledged_at"] = at
    command["updated_at"] = at
    result["updated_at"] = at
    return result


def mark_command_running(
    state: dict[str, Any], command_id: str, metadata: dict[str, Any], *, at: str
) -> dict[str, Any]:
    result = mark_command_acknowledged(state, command_id, metadata, at=at)
    command = result["commands"][command_id]
    command["lifecycle"] = "running"
    command["running_at"] = command.get("running_at") or at
    command["updated_at"] = at
    result["updated_at"] = at
    return result


def mark_command_failed(
    state: dict[str, Any], command_id: str, reason: str, *, at: str
) -> dict[str, Any]:
    result = copy.deepcopy(state)
    command = result.setdefault("commands", {}).get(command_id)
    if not isinstance(command, dict):
        raise SupervisorError(f"unknown command: {command_id}")
    if str(command.get("lifecycle") or "") == "verified":
        return result
    command["lifecycle"] = "failed"
    command["failure_reason"] = str(reason)
    command["failed_at"] = at
    command["updated_at"] = at
    incident = result.setdefault("incidents", {}).get(str(command.get("fingerprint") or ""))
    if isinstance(incident, dict):
        incident["status"] = "open"
        incident.setdefault("history", []).append({
            "at": at,
            "event": "command_failed",
            "command_id": command_id,
            "reason": str(reason),
        })
    result["updated_at"] = at
    return result


def record_resolution(
    state: dict[str, Any], report: dict[str, Any], *, at: str
) -> dict[str, Any]:
    result = copy.deepcopy(state)
    fp = incident_fingerprint(report)
    incident = result.setdefault("incidents", {}).get(fp)
    if not isinstance(incident, dict):
        return result
    active_id = str(incident.get("active_command_id") or "")
    command = result.setdefault("commands", {}).get(active_id) if active_id else None
    if isinstance(command, dict) and str(command.get("lifecycle") or "") != "failed":
        command["lifecycle"] = "verified"
        command["verified_at"] = at
        command["updated_at"] = at
    incident["status"] = "resolved"
    incident["resolved_at"] = at
    incident["active_command_id"] = None
    incident.setdefault("history", []).append({"at": at, "event": "resolved"})
    result["updated_at"] = at
    return result


def resolve_absent_incidents(
    state: dict[str, Any], report: dict[str, Any], *, at: str
) -> tuple[dict[str, Any], bool]:
    """Close prior incidents when fresh exact-source evidence no longer shows them.

    Waiting for an authoritative article is intentionally not enough evidence to
    close anything. When a current incident exists, only other fingerprints for
    the same exact source are closed; the current fingerprint remains active.
    """
    exact = report.get("exact") if isinstance(report.get("exact"), dict) else {}
    slug = str(exact.get("slug") or "").strip()
    content_hash = str(exact.get("content_sha256") or "").strip()
    if not slug or not content_hash:
        return copy.deepcopy(state), False

    result = copy.deepcopy(state)
    incidents = result.setdefault("incidents", {})
    commands = result.setdefault("commands", {})
    prefix = f"v5|{slug}|{content_hash}|"
    current_fp = (
        incident_fingerprint(report)
        if report.get("status") == "incident_detected" and report.get("incident_id")
        else None
    )
    changed = False

    for fp, incident in incidents.items():
        if not isinstance(incident, dict):
            continue
        if fp == current_fp:
            continue
        if not str(incident.get("incident_id") or "").startswith(prefix):
            continue
        if str(incident.get("status") or "") == "resolved":
            continue
        active_id = str(incident.get("active_command_id") or "")
        command = commands.get(active_id) if active_id else None
        if isinstance(command, dict) and str(command.get("lifecycle") or "") != "failed":
            command["lifecycle"] = "verified"
            command["verified_at"] = at
            command["updated_at"] = at
        incident["status"] = "resolved"
        incident["resolved_at"] = at
        incident["active_command_id"] = None
        incident.setdefault("history", []).append({
            "at": at,
            "event": "resolved",
            "reason": "failure_absent_in_fresh_exact_evidence",
        })
        changed = True

    if changed:
        result["updated_at"] = at
    return result, changed


def should_hold_external_running(started_at: str, now: str) -> bool:
    started = _parse_timestamp(started_at)
    current = _parse_timestamp(now)
    if not started or not current or current < started:
        return False
    return (current - started).total_seconds() < EXTERNAL_RUNNING_LIMIT_MINUTES * 60


def build_incident_packet(
    report: dict[str, Any], *, strike: int, command_id: str
) -> dict[str, Any]:
    exact = copy.deepcopy(report.get("exact") or {})
    action = str(report.get("proposed_action") or "")
    dod_by_action = {
        "rebuild_exact_overview": "same-source Video Overview is technically valid, has the full-screen signature, is public on the correct YouTube channel, and processing succeeded",
        "retry_exact_upload": "same-source exact Overview item is public on the correct YouTube channel and processing succeeded without regenerating provider media",
        "continue_exact_short": "same-source Short is public, processing succeeded, and dimensions are portrait 9:16",
        "rebuild_exact_short": "same-source exact Short is rebuilt without fresh provider generation, public, succeeded, and portrait 9:16",
        "repair_trusted_image_same_pr": "the same article PR contains a trusted local hero image, image guard passes, CI passes, and no duplicate article PR is created",
        "rebind_exact_source": "controller bindings match the authoritative slug/content hash and exact provider/item identities without fresh generation",
    }
    return {
        "schema_version": 1,
        "command_id": command_id,
        "incident_id": report.get("incident_id"),
        "fingerprint": incident_fingerprint(report),
        "failure_signature": report.get("failure_signature"),
        "evidence_hash": report.get("evidence_hash"),
        "strike": int(strike),
        "stage": str(report.get("incident_id") or "").split("|")[-1],
        "proposed_action": action,
        "exact": exact,
        "definition_of_done": dod_by_action.get(
            action,
            "the exact incident is absent in fresh authoritative production evidence and all relevant CI/public verification gates pass",
        ),
        "constraints": {
            "reuse_existing_session_pr": True,
            "no_duplicate_generation_upload": True,
            "no_duplicate_article_pr": True,
            "never_bypass_ci_or_safeguards": True,
            "production_state_writer_remains_v5": True,
        },
    }


def direct_dispatch_spec(report: dict[str, Any]) -> dict[str, Any]:
    action = str(report.get("proposed_action") or "")
    exact = report.get("exact") if isinstance(report.get("exact"), dict) else {}
    slug = str(exact.get("slug") or "")
    content_hash = str(exact.get("content_sha256") or "")
    item_id = str(exact.get("item_id") or "")
    short_item_id = str(exact.get("short_item_id") or "")
    pr_number = exact.get("pr_number")

    if action == "rebuild_exact_overview" and item_id and slug:
        return {
            "workflow": "kesher-daily-video.yml",
            "inputs": {
                "operation": "rebuild",
                "rebuild_item_id": item_id,
                "target_slug": slug,
            },
        }
    if action == "retry_exact_upload" and slug:
        return {
            "workflow": "kesher-daily-video.yml",
            "inputs": {"operation": "upload", "target_slug": slug},
        }
    if action == "continue_exact_short" and slug and content_hash and item_id:
        return {
            "workflow": "kesher-short-v4.yml",
            "inputs": {
                "operation": "derive",
                "derive_slug": slug,
                "derive_content_sha256": content_hash,
                "derive_long_item_id": item_id,
            },
        }
    if action == "rebuild_exact_short" and short_item_id:
        return {
            "workflow": "kesher-short-v4.yml",
            "inputs": {"operation": "rebuild", "rebuild_item_id": short_item_id},
        }
    if action == "repair_trusted_image_same_pr" and pr_number:
        return {
            "workflow": "kesher-article-image.yml",
            "inputs": {"pr_number": str(pr_number)},
        }
    raise SupervisorError(f"NO_SAFE_DIRECT_ADAPTER: {action or 'missing_action'}")


class SupervisorStateStore:
    def __init__(self, api: Any):
        self.api = api

    def load(self) -> tuple[dict[str, Any], str | None]:
        state, sha = self.api.load_state_blob(SUPERVISOR_STATE_REF, SUPERVISOR_STATE_PATH)
        if not isinstance(state, dict):
            return new_supervisor_state(), sha
        if int(state.get("schema_version") or 0) != SUPERVISOR_SCHEMA_VERSION:
            raise SupervisorError("SUPERVISOR_STATE_SCHEMA_UNSUPPORTED")
        state.setdefault("incidents", {})
        state.setdefault("commands", {})
        return state, sha

    def save(self, state: dict[str, Any], *, expected_sha: str | None) -> str:
        return self.api.save_state_blob(
            SUPERVISOR_STATE_REF,
            SUPERVISOR_STATE_PATH,
            state,
            expected_sha,
        )


class GitHubApi:
    def __init__(self, repo: str, token: str):
        self.repo = repo
        self.token = token
        self.api = f"https://api.github.com/repos/{repo}"

    def _request(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        *,
        allow_404: bool = False,
        mutation: bool = False,
        cas_conflict: bool = False,
    ) -> Any:
        raw = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        attempts = 1 if mutation else 4
        last: Exception | None = None
        for attempt in range(attempts):
            req = urllib.request.Request(
                url,
                data=raw,
                method=method,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                    "User-Agent": "kesher-master-supervisor-v2",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    payload = response.read()
                    return json.loads(payload.decode("utf-8")) if payload else {}
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:1500]
                if allow_404 and exc.code == 404:
                    return None
                if cas_conflict and exc.code in {409, 422}:
                    raise SupervisorCasConflict(f"HTTP {exc.code}: {detail}") from exc
                if exc.code not in {429, 500, 502, 503, 504} or mutation:
                    raise SupervisorError(
                        f"GITHUB_HTTP_{exc.code}: {method} {url}: {detail}"
                    ) from exc
                last = exc
            except urllib.error.URLError as exc:
                if mutation:
                    raise SupervisorError(
                        f"GITHUB_MUTATION_OUTCOME_UNCERTAIN: {method} {url}: {exc}"
                    ) from exc
                last = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
        raise SupervisorError(f"GITHUB_TRANSIENT_FAILURE: {method} {url}: {last}")

    def _ensure_ref(self, ref: str) -> None:
        encoded = urllib.parse.quote(ref, safe="")
        if self._request("GET", f"{self.api}/git/ref/heads/{encoded}", allow_404=True):
            return
        main = self._request("GET", f"{self.api}/git/ref/heads/main")
        sha = str(((main or {}).get("object") or {}).get("sha") or "")
        if not sha:
            raise SupervisorError("MAIN_REF_MISSING")
        try:
            self._request(
                "POST",
                f"{self.api}/git/refs",
                {"ref": f"refs/heads/{ref}", "sha": sha},
                mutation=True,
                cas_conflict=True,
            )
        except SupervisorCasConflict:
            if not self._request(
                "GET", f"{self.api}/git/ref/heads/{encoded}", allow_404=True
            ):
                raise

    def load_state_blob(
        self, ref: str, path: str
    ) -> tuple[dict[str, Any] | None, str | None]:
        self._ensure_ref(ref)
        quoted_path = urllib.parse.quote(path, safe="/")
        payload = self._request(
            "GET",
            f"{self.api}/contents/{quoted_path}?ref={urllib.parse.quote(ref, safe='')}",
            allow_404=True,
        )
        if payload is None:
            return None, None
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise SupervisorError("SUPERVISOR_STATE_INVALID")
        try:
            state = json.loads(
                base64.b64decode(payload.get("content") or "").decode("utf-8")
            )
        except (ValueError, UnicodeDecodeError) as exc:
            raise SupervisorError("SUPERVISOR_STATE_INVALID") from exc
        return (
            state if isinstance(state, dict) else None,
            str(payload.get("sha") or "") or None,
        )

    def save_state_blob(
        self,
        ref: str,
        path: str,
        state: dict[str, Any],
        expected_sha: str | None,
    ) -> str:
        self._ensure_ref(ref)
        quoted_path = urllib.parse.quote(path, safe="/")
        body: dict[str, Any] = {
            "message": f"state: Kesher Master Supervisor {state.get('updated_at') or ''}",
            "content": base64.b64encode(
                (
                    json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
                ).encode("utf-8")
            ).decode("ascii"),
            "branch": ref,
        }
        if expected_sha:
            body["sha"] = expected_sha
        payload = self._request(
            "PUT",
            f"{self.api}/contents/{quoted_path}",
            body,
            mutation=True,
            cas_conflict=True,
        )
        sha = str(((payload or {}).get("content") or {}).get("sha") or "")
        if not sha:
            raise SupervisorError("SUPERVISOR_STATE_SAVE_INVALID_RESPONSE")
        return sha

    def dispatch_workflow(
        self, workflow: str, inputs: dict[str, str] | None = None
    ) -> None:
        body: dict[str, Any] = {"ref": "main"}
        if inputs:
            body["inputs"] = {str(k): str(v) for k, v in inputs.items()}
        encoded = urllib.parse.quote(workflow, safe="")
        self._request(
            "POST",
            f"{self.api}/actions/workflows/{encoded}/dispatches",
            body,
            mutation=True,
        )

    def workflow_runs(self, workflow: str, limit: int = 20) -> list[dict[str, Any]]:
        encoded = urllib.parse.quote(workflow, safe="")
        payload = self._request(
            "GET", f"{self.api}/actions/workflows/{encoded}/runs?per_page={limit}"
        )
        rows = payload.get("workflow_runs") if isinstance(payload, dict) else []
        return [row for row in (rows or []) if isinstance(row, dict)]

    def workflow_run_by_id(self, run_id: int | str) -> dict[str, Any] | None:
        payload = self._request(
            "GET", f"{self.api}/actions/runs/{run_id}", allow_404=True
        )
        return payload if isinstance(payload, dict) else None

    def active_external_media_run(self) -> dict[str, Any] | None:
        for workflow in ("kesher-daily-video.yml", "kesher-short-v4.yml"):
            for row in self.workflow_runs(workflow, 10):
                if str(row.get("event") or "") == "pull_request":
                    continue
                if str(row.get("status") or "") in {
                    "queued",
                    "pending",
                    "in_progress",
                    "waiting",
                    "requested",
                }:
                    return row
        return None

    def find_dispatched_run(
        self, workflow: str, issued_at: str
    ) -> dict[str, Any] | None:
        issued = _parse_timestamp(issued_at)
        candidates: list[dict[str, Any]] = []
        for row in self.workflow_runs(workflow, 30):
            if str(row.get("event") or "") != "workflow_dispatch":
                continue
            created = _parse_timestamp(str(row.get("created_at") or ""))
            if issued and created and created >= issued:
                candidates.append(row)
        candidates.sort(key=lambda row: str(row.get("created_at") or ""))
        return candidates[0] if candidates else None

    def get_pr(self, number: int) -> dict[str, Any] | None:
        payload = self._request(
            "GET", f"{self.api}/pulls/{number}", allow_404=True
        )
        return payload if isinstance(payload, dict) else None

    def pr_files(self, number: int) -> list[str]:
        payload = self._request(
            "GET", f"{self.api}/pulls/{number}/files?per_page=100"
        )
        return (
            [str(row.get("filename") or "") for row in payload if isinstance(row, dict)]
            if isinstance(payload, list)
            else []
        )

    def combined_status(self, sha: str) -> dict[str, Any]:
        payload = self._request("GET", f"{self.api}/commits/{sha}/status")
        return payload if isinstance(payload, dict) else {}

    def check_runs(self, sha: str) -> list[dict[str, Any]]:
        payload = self._request(
            "GET", f"{self.api}/commits/{sha}/check-runs?per_page=100"
        )
        rows = payload.get("check_runs") if isinstance(payload, dict) else []
        return [row for row in (rows or []) if isinstance(row, dict)]

    def merge_pr(self, number: int, sha: str) -> dict[str, Any]:
        payload = self._request(
            "PUT",
            f"{self.api}/pulls/{number}/merge",
            {
                "sha": sha,
                "merge_method": "merge",
                "commit_title": f"Master recovery: merge PR #{number}",
            },
            mutation=True,
        )
        return payload if isinstance(payload, dict) else {}


class JulesRecoveryClient:
    TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "CANCELED"}

    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def title(fingerprint: str) -> str:
        return f"Kesher recovery {fingerprint}"

    def list_exact(self, fingerprint: str) -> list[dict[str, Any]]:
        title = self.title(fingerprint)
        matches: list[dict[str, Any]] = []
        token = ""
        seen_tokens: set[str] = set()
        for _ in range(50):
            params = {"pageSize": "100"}
            if token:
                params["pageToken"] = token
            url = f"{jules.API_BASE}/sessions?{urllib.parse.urlencode(params)}"
            payload = jules.request_json(
                "GET",
                url,
                jules.jules_headers(self.api_key),
            )
            rows = payload.get("sessions") if isinstance(payload, dict) else []
            matches.extend(
                row
                for row in (rows or [])
                if isinstance(row, dict) and str(row.get("title") or "") == title
            )
            next_token = str(
                (payload or {}).get("nextPageToken") if isinstance(payload, dict) else ""
            ).strip()
            if not next_token:
                return matches
            if next_token in seen_tokens:
                raise SupervisorError("JULES_SESSION_PAGINATION_LOOP")
            seen_tokens.add(next_token)
            token = next_token
        raise SupervisorError("JULES_SESSION_PAGINATION_LIMIT")

    def get(self, session_id: str) -> dict[str, Any]:
        sid = str(session_id).removeprefix("sessions/")
        payload = jules.request_json(
            "GET",
            f"{jules.API_BASE}/sessions/{sid}",
            jules.jules_headers(self.api_key),
        )
        return payload if isinstance(payload, dict) else {}

    def acquire_or_continue(self, packet: dict[str, Any]) -> tuple[str, str]:
        fingerprint = str(packet["fingerprint"])
        exact = self.list_exact(fingerprint)
        if len(exact) > 1:
            raise SupervisorError("JULES_DUPLICATE_RECOVERY_SESSIONS")
        if len(exact) == 1:
            row = exact[0]
            name = jules.normalize_session_name(row)
            state_name = str(row.get("state") or "UNKNOWN").upper()
            if state_name not in self.TERMINAL:
                prompt = self._prompt(packet)
                jules.send_message(
                    self.api_key,
                    name.removeprefix("sessions/"),
                    prompt,
                )
                return name, "continued"
            return name, "terminal_existing"

        payload = {
            "title": self.title(fingerprint),
            "prompt": self._prompt(packet),
            "sourceContext": {
                "source": jules.SOURCE,
                "githubRepoContext": {"startingBranch": "main"},
            },
            "requirePlanApproval": False,
            "automationMode": "AUTO_CREATE_PR",
        }
        try:
            created = jules.request_json(
                "POST",
                f"{jules.API_BASE}/sessions",
                jules.jules_headers(self.api_key),
                payload,
                max_attempts=1,
            )
        except Exception:
            reconciled = self.list_exact(fingerprint)
            if len(reconciled) == 1:
                return (
                    jules.normalize_session_name(reconciled[0]),
                    "reconciled_uncertain_create",
                )
            if len(reconciled) > 1:
                raise SupervisorError("JULES_DUPLICATE_RECOVERY_SESSIONS")
            raise
        if not isinstance(created, dict):
            raise SupervisorError("JULES_RECOVERY_CREATE_INVALID")
        name = jules.normalize_session_name(created)
        if not name:
            raise SupervisorError("JULES_RECOVERY_CREATE_MISSING_ID")
        return name, "created"

    @staticmethod
    def _prompt(packet: dict[str, Any]) -> str:
        return (
            "KESHER MASTER SUPERVISOR INCIDENT PACKET\n"
            "Do not rediagnose from scratch. Treat this packet as the authoritative incident scope. "
            "Continue the same PR/branch when supplied; do not create duplicate content, provider generation, video, upload, issue, or PR. "
            "Make the narrowest code/config repair needed, run relevant tests, and create/update one recovery PR only.\n\n"
            + json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True)
        )


def _pr_urls(session: dict[str, Any]) -> list[str]:
    try:
        return jules.pr_urls(session)
    except Exception:
        return []


def _pr_number_from_url(url: str) -> int | None:
    match = re.search(r"/pull/(\d+)(?:\b|/|$)", str(url))
    return int(match.group(1)) if match else None


def _minutes_since(value: str, now: str) -> float | None:
    start = _parse_timestamp(value)
    current = _parse_timestamp(now)
    if not start or not current:
        return None
    return max(0.0, (current - start).total_seconds() / 60.0)


def _run_terminal_result(
    state: dict[str, Any],
    command_id: str,
    run: dict[str, Any],
    workflow: str,
    now: str,
) -> tuple[dict[str, Any], bool, str]:
    status = str(run.get("status") or "")
    if status != "completed":
        return (
            mark_command_running(
                state,
                command_id,
                {"workflow": workflow, "run_id": run.get("id")},
                at=now,
            ),
            False,
            "workflow_running",
        )
    return (
        mark_command_failed(
            state,
            command_id,
            f"{workflow} run {run.get('id')} completed but exact incident persisted",
            at=now,
        ),
        True,
        "workflow_completed_incident_persisted",
    )


def reconcile_active_command(
    state: dict[str, Any],
    report: dict[str, Any],
    *,
    api: Any,
    jules_client: JulesRecoveryClient | None,
    now: str,
) -> tuple[dict[str, Any], bool, str]:
    """Reconcile an issued command without blindly repeating an uncertain side effect."""
    result = copy.deepcopy(state)
    fp = incident_fingerprint(report)
    incident = result.get("incidents", {}).get(fp)
    if not isinstance(incident, dict):
        return result, False, "no_incident_state"
    command_id = str(incident.get("active_command_id") or "")
    command = result.get("commands", {}).get(command_id) if command_id else None
    if not isinstance(command, dict):
        return result, False, "no_active_command"
    lifecycle = str(command.get("lifecycle") or "")
    if lifecycle in TERMINAL_LIFECYCLES:
        return result, True, f"persisted_{lifecycle}"

    stage = str(report.get("incident_id") or "").split("|")[-1]
    if stage in {"long_video", "short"} and hasattr(api, "active_external_media_run"):
        external = api.active_external_media_run()
        if isinstance(external, dict):
            started = str(
                external.get("run_started_at") or external.get("created_at") or ""
            )
            if should_hold_external_running(started, now):
                return (
                    mark_command_running(
                        result,
                        command_id,
                        {
                            "external_run_id": external.get("id"),
                            "external_workflow": external.get("name"),
                        },
                        at=now,
                    ),
                    False,
                    "external_media_running_heartbeat_exception",
                )

    executor = str(command.get("executor") or "")
    metadata = command.get("metadata") if isinstance(command.get("metadata"), dict) else {}

    if executor in {"controller", "direct"}:
        run_id = metadata.get("run_id")
        workflow = str(metadata.get("workflow") or "")
        if not workflow and executor == "controller":
            workflow = "kesher-content-controller.yml"

        if run_id and hasattr(api, "workflow_run_by_id"):
            run = api.workflow_run_by_id(run_id)
            if isinstance(run, dict):
                return _run_terminal_result(result, command_id, run, workflow, now)

        if workflow and workflow != "recovery_pr_merge" and hasattr(api, "find_dispatched_run"):
            run = api.find_dispatched_run(
                workflow, str(command.get("issued_at") or "")
            )
            if run:
                return _run_terminal_result(result, command_id, run, workflow, now)

        if executor == "direct":
            prior_pr = _find_prior_recovery_pr(result, fp)
            if prior_pr and hasattr(api, "get_pr"):
                pr = api.get_pr(prior_pr)
                if isinstance(pr, dict) and pr.get("merged") is True:
                    merged_at = str(pr.get("merged_at") or command.get("issued_at") or "")
                    controller_run = (
                        api.find_dispatched_run(
                            "kesher-content-controller.yml", merged_at
                        )
                        if hasattr(api, "find_dispatched_run")
                        else None
                    )
                    if controller_run:
                        return _run_terminal_result(
                            result,
                            command_id,
                            controller_run,
                            "kesher-content-controller.yml",
                            now,
                        )
                    age = _minutes_since(merged_at, now)
                    if age is not None and age >= 1 and hasattr(api, "dispatch_workflow"):
                        api.dispatch_workflow("kesher-content-controller.yml")
                        return (
                            mark_command_acknowledged(
                                result,
                                command_id,
                                {
                                    "workflow": "recovery_pr_merge",
                                    "recovery_pr_number": prior_pr,
                                    "controller_dispatched_after_merge": True,
                                },
                                at=now,
                            ),
                            False,
                            "reconciled_merged_pr_and_woke_controller",
                        )

        age = _minutes_since(str(command.get("issued_at") or ""), now)
        if age is not None and age >= UNCERTAIN_ISSUE_GRACE_MINUTES:
            return (
                mark_command_failed(
                    result,
                    command_id,
                    "issued command had no discoverable workflow run after grace period; not blindly reissuing",
                    at=now,
                ),
                True,
                "uncertain_dispatch_timed_out",
            )
        return result, False, "issued_waiting_for_discoverable_run"

    if executor == "jules":
        session_id = str(metadata.get("session_id") or "")
        if not session_id and jules_client:
            exact_sessions = jules_client.list_exact(fp)
            if len(exact_sessions) == 1:
                session_id = jules.normalize_session_name(exact_sessions[0])
                result = mark_command_acknowledged(
                    result, command_id, {"session_id": session_id}, at=now
                )
            elif len(exact_sessions) > 1:
                return (
                    mark_command_failed(
                        result,
                        command_id,
                        "duplicate exact recovery sessions",
                        at=now,
                    ),
                    True,
                    "duplicate_jules_sessions",
                )
        if session_id and jules_client:
            session = jules_client.get(session_id)
            state_name = str(session.get("state") or "UNKNOWN").upper()
            if state_name not in JulesRecoveryClient.TERMINAL:
                return (
                    mark_command_running(
                        result, command_id, {"session_id": session_id}, at=now
                    ),
                    False,
                    "jules_running",
                )
            urls = _pr_urls(session)
            pr_number = _pr_number_from_url(urls[0]) if urls else None
            result = mark_command_failed(
                result,
                command_id,
                f"Jules state={state_name}; exact incident persisted",
                at=now,
            )
            if pr_number:
                result["commands"][command_id].setdefault("metadata", {})[
                    "recovery_pr_number"
                ] = pr_number
                result["commands"][command_id]["metadata"]["recovery_pr_url"] = urls[0]
            return result, True, "jules_terminal_incident_persisted"

        age = _minutes_since(str(command.get("issued_at") or ""), now)
        if age is not None and age >= UNCERTAIN_ISSUE_GRACE_MINUTES:
            return (
                mark_command_failed(
                    result,
                    command_id,
                    "issued Jules command had no exact session after grace period; not blindly creating another",
                    at=now,
                ),
                True,
                "uncertain_jules_create_timed_out",
            )
        return result, False, "jules_issued_waiting_reconcile"

    return result, False, "unknown_executor_wait"


def _find_prior_recovery_pr(state: dict[str, Any], fp: str) -> int | None:
    candidates = [
        row
        for row in state.get("commands", {}).values()
        if isinstance(row, dict)
        and row.get("fingerprint") == fp
        and row.get("executor") == "jules"
        and isinstance(row.get("metadata"), dict)
        and row["metadata"].get("recovery_pr_number")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda row: int(row.get("strike") or 0), reverse=True)
    return int(candidates[0]["metadata"]["recovery_pr_number"])


def _safe_recovery_pr_scope(files: list[str]) -> bool:
    if not files or len(files) > 12:
        return False
    forbidden_prefixes = (
        "src/data/posts.json",
        "public/images/generated/blog/",
        ".kesher-",
    )
    return not any(
        any(path.startswith(prefix) for prefix in forbidden_prefixes) for path in files
    )


def try_finalize_recovery_pr(api: Any, number: int) -> dict[str, Any] | None:
    pr = api.get_pr(number)
    if not pr or str(pr.get("state") or "") != "open" or pr.get("draft") is True:
        return None
    head = str((pr.get("head") or {}).get("sha") or "")
    if not head or not _safe_recovery_pr_scope(api.pr_files(number)):
        return None
    if pr.get("mergeable") is not True:
        return None

    status = api.combined_status(head)
    legacy_contexts = {
        str(row.get("context") or ""): str(row.get("state") or "")
        for row in (status.get("statuses") or [])
        if isinstance(row, dict)
    }
    checks = api.check_runs(head) if hasattr(api, "check_runs") else []
    verify_check_ok = any(
        str(row.get("name") or "") == "verify"
        and str(row.get("status") or "") == "completed"
        and str(row.get("conclusion") or "") == "success"
        for row in checks
    )
    verify_ok = legacy_contexts.get("verify") == "success" or verify_check_ok
    if not verify_ok:
        return None

    failed_checks = [
        row
        for row in checks
        if str(row.get("status") or "") == "completed"
        and str(row.get("conclusion") or "")
        in {"failure", "timed_out", "cancelled", "action_required"}
    ]
    if failed_checks:
        return None

    merged = api.merge_pr(number, head)
    if not isinstance(merged, dict) or merged.get("merged") is not True:
        raise SupervisorError(f"RECOVERY_PR_MERGE_FAILED: #{number}")
    return {"recovery_pr_number": number, "merge_sha": merged.get("sha")}


def execute_command(
    state: dict[str, Any],
    report: dict[str, Any],
    decision: dict[str, Any],
    *,
    api: Any,
    jules_client: JulesRecoveryClient | None,
    now: str,
) -> dict[str, Any]:
    command_id = str(decision.get("command_id") or "")
    executor = str(decision.get("executor") or "")

    if executor == "controller":
        workflow = "kesher-content-controller.yml"
        active = [
            row
            for row in api.workflow_runs(workflow, 10)
            if str(row.get("status") or "") != "completed"
        ]
        if not active:
            api.dispatch_workflow(workflow)
            metadata = {
                "workflow": workflow,
                "dispatch": "issued",
                "dispatched_at": now,
            }
        else:
            metadata = {
                "workflow": workflow,
                "dispatch": "already_active",
                "run_id": active[0].get("id"),
            }
        return mark_command_acknowledged(state, command_id, metadata, at=now)

    if executor == "jules":
        if not jules_client:
            return mark_command_failed(
                state, command_id, "JULES_API_KEY missing", at=now
            )
        command = state["commands"][command_id]
        packet = build_incident_packet(
            report,
            strike=int(command.get("strike") or 2),
            command_id=command_id,
        )
        session_id, mode = jules_client.acquire_or_continue(packet)
        return mark_command_acknowledged(
            state,
            command_id,
            {
                "session_id": session_id,
                "jules_mode": mode,
                "incident_packet": packet,
            },
            at=now,
        )

    if executor == "direct":
        fp = incident_fingerprint(report)
        prior_pr = _find_prior_recovery_pr(state, fp)
        if prior_pr:
            finalized = try_finalize_recovery_pr(api, prior_pr)
            if finalized:
                api.dispatch_workflow("kesher-content-controller.yml")
                return mark_command_acknowledged(
                    state,
                    command_id,
                    {
                        **finalized,
                        "workflow": "recovery_pr_merge",
                        "controller_dispatched_after_merge": True,
                    },
                    at=now,
                )
        try:
            spec = direct_dispatch_spec(report)
        except SupervisorError as exc:
            return mark_command_failed(state, command_id, str(exc), at=now)
        workflow = str(spec["workflow"])
        active = [
            row
            for row in api.workflow_runs(workflow, 10)
            if str(row.get("status") or "") != "completed"
        ]
        if not active:
            api.dispatch_workflow(workflow, spec.get("inputs") or {})
            metadata = {
                "workflow": workflow,
                "inputs": spec.get("inputs") or {},
                "dispatch": "issued",
                "dispatched_at": now,
            }
        else:
            metadata = {
                "workflow": workflow,
                "inputs": spec.get("inputs") or {},
                "dispatch": "already_active",
                "run_id": active[0].get("id"),
            }
        return mark_command_acknowledged(state, command_id, metadata, at=now)

    return mark_command_failed(
        state, command_id, f"unsupported executor: {executor}", at=now
    )


def _persist_after_side_effect(
    store: SupervisorStateStore, state: dict[str, Any]
) -> None:
    """Best-effort acknowledgement CAS. Never repeat the side effect on conflict."""
    fresh, fresh_sha = store.load()
    for key, value in state.get("commands", {}).items():
        current = fresh.get("commands", {}).get(key)
        if not isinstance(current, dict) or str(value.get("updated_at") or "") >= str(
            current.get("updated_at") or ""
        ):
            fresh.setdefault("commands", {})[key] = value
    for key, value in state.get("incidents", {}).items():
        current = fresh.get("incidents", {}).get(key)
        if not isinstance(current, dict) or str(value.get("last_seen_at") or "") >= str(
            current.get("last_seen_at") or ""
        ):
            fresh.setdefault("incidents", {})[key] = value
    fresh["updated_at"] = state.get("updated_at")
    try:
        store.save(fresh, expected_sha=fresh_sha)
    except SupervisorCasConflict:
        print("MASTER_SUPERVISOR_ACK_CAS_CONFLICT no-retry", flush=True)


def run_live(*, repo: str, token: str, jules_api_key: str) -> dict[str, Any]:
    observed_at = _now()
    report = shadow.collect_live_shadow_report(
        repo=repo,
        token=token,
        workflow_run_id=str(os.environ.get("KESHER_TRIGGER_RUN_ID") or ""),
    )
    report = {**report, "mode": "live"}

    api = GitHubApi(repo, token)
    store = SupervisorStateStore(api)
    state, sha = store.load()
    state, resolved_changed = resolve_absent_incidents(
        state, report, at=observed_at
    )

    if report.get("status") != "incident_detected":
        if resolved_changed:
            try:
                state_sha = store.save(state, expected_sha=sha)
            except SupervisorCasConflict:
                return {
                    **report,
                    "master_action": "cas_conflict_noop",
                    "execute_now": False,
                }
            return {
                **report,
                "master_action": "resolved_absent_incident",
                "execute_now": False,
                "state_sha": state_sha,
            }
        return {**report, "master_action": "none", "execute_now": False}

    jules_client = JulesRecoveryClient(jules_api_key) if jules_api_key else None
    reconciled, terminal, reconcile_reason = reconcile_active_command(
        state,
        report,
        api=api,
        jules_client=jules_client,
        now=observed_at,
    )
    state = reconciled
    state, decision = prepare_escalation(
        state,
        report,
        now=observed_at,
        prior_action_terminal=terminal,
    )

    try:
        persisted_sha = store.save(state, expected_sha=sha)
    except SupervisorCasConflict:
        return {
            **report,
            "master_action": "cas_conflict_noop",
            "reconcile_reason": reconcile_reason,
            "execute_now": False,
        }

    if not decision.get("execute_now"):
        return {
            **report,
            "master_action": decision.get("stage"),
            "command_id": decision.get("command_id"),
            "execute_now": False,
            "reconcile_reason": reconcile_reason,
            "state_sha": persisted_sha,
        }

    after = execute_command(
        state,
        report,
        decision,
        api=api,
        jules_client=jules_client,
        now=_now(),
    )
    _persist_after_side_effect(store, after)
    command = after["commands"][decision["command_id"]]
    return {
        **report,
        "master_action": decision.get("stage"),
        "executor": decision.get("executor"),
        "command_id": decision.get("command_id"),
        "execute_now": True,
        "reconcile_reason": reconcile_reason,
        "marker": _marker(
            report,
            int(command.get("strike") or 0),
            str(decision.get("stage")),
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if not args.live:
        print("MASTER_SUPERVISOR_REFUSES_NON_LIVE_ENTRYPOINT", file=sys.stderr)
        return 2
    repo = str(os.environ.get("GITHUB_REPOSITORY") or REPO_DEFAULT).strip()
    token = str(
        os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    ).strip()
    if not token:
        print("MASTER_SUPERVISOR_GITHUB_TOKEN_MISSING", file=sys.stderr)
        return 2
    try:
        result = run_live(
            repo=repo,
            token=token,
            jules_api_key=str(os.environ.get("JULES_API_KEY") or "").strip(),
        )
    except SupervisorCasConflict as exc:
        result = {
            "mode": "live",
            "master_action": "cas_conflict_noop",
            "error": str(exc),
        }
    except Exception as exc:
        print(
            f"MASTER_SUPERVISOR_FAILED {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
