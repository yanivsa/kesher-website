#!/usr/bin/env python3
"""Read-only evidence and recovery classification for Kesher Master Supervisor V2.

Shadow mode is deliberately incapable of dispatching workflows, mutating GitHub,
calling Jules, or writing controller state. It reads the authoritative V5 state,
article source and durable media artifacts, then emits the exact recovery intent
that a later live phase may be allowed to execute.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

if __package__:
    from . import kesher_content_controller_v5 as v5
    from .kesher_master_supervisor import (
        EvidenceSnapshot,
        IncidentIdentity,
        RecoveryCommand,
        semantic_evidence_hash,
    )
else:
    import kesher_content_controller_v5 as v5
    from kesher_master_supervisor import (
        EvidenceSnapshot,
        IncidentIdentity,
        RecoveryCommand,
        semantic_evidence_hash,
    )


PIPELINE_ID = "v5"
CONTROLLER_STATE_REF = "automation-state"
CONTROLLER_STATE_PATH = ".kesher-controller/state.json"


def _newest(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return v5._newest(rows)


def _exact_items(state: dict[str, Any], source: dict[str, str]) -> list[dict[str, Any]]:
    return v5._exact_items(state if isinstance(state, dict) else {}, source)


def _article_for_cycle(posts: list[dict[str, Any]], cycle: str) -> dict[str, Any] | None:
    rows = [
        row for row in (posts or [])
        if isinstance(row, dict) and str(row.get("date") or "").strip() == cycle
    ]
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError(f"AUTHORITATIVE_ARTICLE_AMBIGUOUS: cycle={cycle} count={len(rows)}")
    return rows[0]


def _verified_overview(item: dict[str, Any] | None, source: dict[str, str]) -> bool:
    if not isinstance(item, dict):
        return False
    return bool(
        item.get("technical_verified") is True
        and item.get("signature_fullscreen") is True
        and v5.core.verified_youtube_item(item, source["slug"])
    )


def _short_portrait(item: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict):
        return False
    media = item.get("media") if isinstance(item.get("media"), dict) else {}
    try:
        width = int(media.get("width") or 0)
        height = int(media.get("height") or 0)
    except (TypeError, ValueError):
        return False
    return width > 0 and height > width


def _binding_is_stale(controller_state: dict[str, Any], exact_long: dict[str, Any] | None) -> bool:
    if not isinstance(exact_long, dict):
        return False
    stage = controller_state.get("long_video") if isinstance(controller_state.get("long_video"), dict) else {}
    expected = {
        "item_id": str(exact_long.get("id") or "").strip(),
        "provider_id": str(exact_long.get("task_id") or "").strip(),
        "artifact_id": str(exact_long.get("artifact_id") or "").strip(),
        "source_id": str(exact_long.get("source_id") or "").strip(),
    }
    comparisons = 0
    for field, valid in expected.items():
        stored = str(stage.get(field) or "").strip()
        if not stored or not valid:
            continue
        comparisons += 1
        if stored != valid:
            return True
    return False if comparisons else False


def _image_guard_failure(controller_state: dict[str, Any]) -> bool:
    error = controller_state.get("last_error") if isinstance(controller_state.get("last_error"), dict) else {}
    code = str(error.get("code") or "").strip()
    stage = str(error.get("stage") or "").strip()
    return code == "ARTICLE_IMAGE_GUARD_FAILED" or (
        stage == "image" and code in {"IMAGE_ATTEMPTS_EXHAUSTED", "TRUSTED_IMAGE_REQUIRED"}
    )


def _classification(
    controller_state: dict[str, Any],
    source: dict[str, str],
    exact_long: dict[str, Any] | None,
    exact_short: dict[str, Any] | None,
) -> tuple[str | None, str | None, str | None]:
    """Return (stage, stable failure signature, deterministic proposed action)."""
    if _image_guard_failure(controller_state):
        return "image", "ARTICLE_IMAGE_GUARD_FAILED", "repair_trusted_image_same_pr"

    if _binding_is_stale(controller_state, exact_long):
        return "long_video", "STALE_SOURCE_BINDING", "rebind_exact_source"

    if isinstance(exact_long, dict):
        long_status = str(exact_long.get("status") or "").strip()
        if (
            long_status == "rejected"
            and exact_long.get("uploaded") is not True
            and exact_long.get("signature_fullscreen") is not True
        ):
            return (
                "long_video",
                "OVERVIEW_SIGNATURE_FULLSCREEN_MISSING",
                "rebuild_exact_overview",
            )
        if (
            exact_long.get("technical_verified") is True
            and exact_long.get("signature_fullscreen") is True
            and exact_long.get("uploaded") is not True
            and long_status in {"approved", "pending_review", "downloaded", "rejected"}
        ):
            return "long_video", "YOUTUBE_UPLOAD_MISSING", "retry_exact_upload"

    if _verified_overview(exact_long, source):
        if exact_short is None:
            return "short", "SHORT_MISSING", "continue_exact_short"
        if not _short_portrait(exact_short):
            return "short", "SHORT_NOT_PORTRAIT", "rebuild_exact_short"

    error = controller_state.get("last_error") if isinstance(controller_state.get("last_error"), dict) else {}
    code = str(error.get("code") or "").strip()
    stage = str(error.get("stage") or "controller").strip() or "controller"
    if code and str(controller_state.get("status") or "") == "blocked":
        return stage, code, "escalate_unknown_failure"
    return None, None, None


def build_shadow_report(
    *,
    controller_state: dict[str, Any],
    posts: list[dict[str, Any]],
    video_state: dict[str, Any],
    short_state: dict[str, Any],
    observed_at: str | None = None,
    workflow_run_id: str = "",
) -> dict[str, Any]:
    cycle = str(controller_state.get("cycle") or "").strip()
    observed = observed_at or datetime.now(timezone.utc).isoformat()
    if not cycle:
        return {
            "mode": "shadow",
            "status": "controller_state_missing_cycle",
            "incident_id": None,
            "failure_signature": "CONTROLLER_STATE_MISSING_CYCLE",
            "proposed_action": None,
            "would_dispatch": False,
            "observed_at": observed,
        }

    try:
        post = _article_for_cycle(posts, cycle)
    except ValueError as exc:
        return {
            "mode": "shadow",
            "status": "blocked",
            "incident_id": None,
            "failure_signature": str(exc).split(":", 1)[0],
            "proposed_action": "inspect_authoritative_article_ambiguity",
            "would_dispatch": False,
            "observed_at": observed,
        }

    if post is None:
        return {
            "mode": "shadow",
            "status": "waiting_for_authoritative_article",
            "incident_id": None,
            "failure_signature": None,
            "proposed_action": None,
            "would_dispatch": False,
            "observed_at": observed,
            "controller_status": controller_state.get("status"),
        }

    source = v5.article_source_identity(post)
    long_rows = _exact_items(video_state, source)
    short_rows = _exact_items(short_state, source)
    exact_long = _newest(long_rows)
    exact_short = _newest(short_rows)
    stage, failure_signature, proposed_action = _classification(
        controller_state, source, exact_long, exact_short
    )

    exact: dict[str, Any] = {
        "slug": source["slug"],
        "content_sha256": source["content_sha256"],
        "item_id": exact_long.get("id") if isinstance(exact_long, dict) else None,
        "task_id": exact_long.get("task_id") if isinstance(exact_long, dict) else None,
        "artifact_id": exact_long.get("artifact_id") if isinstance(exact_long, dict) else None,
        "source_id": exact_long.get("source_id") if isinstance(exact_long, dict) else None,
        "short_item_id": exact_short.get("id") if isinstance(exact_short, dict) else None,
        "pr_number": (controller_state.get("article") or {}).get("pr_number")
        if isinstance(controller_state.get("article"), dict)
        else None,
    }

    if not failure_signature or not stage or not proposed_action:
        return {
            "mode": "shadow",
            "status": "healthy_or_in_flight",
            "incident_id": None,
            "failure_signature": None,
            "proposed_action": None,
            "would_dispatch": False,
            "observed_at": observed,
            "controller_status": controller_state.get("status"),
            "exact": exact,
        }

    incident = IncidentIdentity(
        PIPELINE_ID,
        source["slug"],
        source["content_sha256"],
        stage,
    )
    evidence_item = exact_short if stage == "short" and exact_short is not None else exact_long
    evidence = EvidenceSnapshot(
        incident=incident,
        failure_signature=failure_signature,
        item_id=str((evidence_item or {}).get("id") or ""),
        task_id=str((exact_long or {}).get("task_id") or ""),
        artifact_id=str((exact_long or {}).get("artifact_id") or ""),
        workflow_run_id=str(workflow_run_id or ""),
        observed_at=observed,
    )
    evidence_hash = semantic_evidence_hash(evidence)
    command = RecoveryCommand.build(
        incident=incident,
        action=proposed_action,
        evidence_hash=evidence_hash,
        item_id=str((evidence_item or {}).get("id") or ""),
        task_id=str((exact_long or {}).get("task_id") or ""),
        artifact_id=str((exact_long or {}).get("artifact_id") or ""),
    )
    return {
        "mode": "shadow",
        "status": "incident_detected",
        "incident_id": incident.key,
        "failure_signature": failure_signature,
        "evidence_hash": evidence_hash,
        "proposed_action": proposed_action,
        "recovery_command_id": command.command_id,
        "would_dispatch": False,
        "observed_at": observed,
        "controller_status": controller_state.get("status"),
        "exact": exact,
    }


def collect_live_shadow_report(*, repo: str, token: str, workflow_run_id: str = "") -> dict[str, Any]:
    """Collect production evidence using GET-only GitHub API operations."""
    client = v5.V5GitHubClient(repo, token)
    controller_state = client.contents_json(CONTROLLER_STATE_PATH, CONTROLLER_STATE_REF)
    posts = client.contents_json("src/data/posts.json", "main")
    if not isinstance(controller_state, dict):
        raise v5.core.ControllerError("CONTROLLER_STATE_INVALID")
    if not isinstance(posts, list):
        raise v5.core.ControllerError("ARTICLE_SOURCE_INVALID")
    video_state = client.newest_video_state()
    short_state = client.newest_short_state()
    return build_shadow_report(
        controller_state=controller_state,
        posts=posts,
        video_state=video_state,
        short_state=short_state,
        workflow_run_id=workflow_run_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shadow", action="store_true")
    args = parser.parse_args()
    if not args.shadow:
        print("MASTER_SUPERVISOR_REFUSES_NON_SHADOW_MODE", file=sys.stderr)
        return 2
    repo = str(os.environ.get("GITHUB_REPOSITORY") or "yanivsa/kesher-website").strip()
    token = str(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if not token:
        print("MASTER_SUPERVISOR_GITHUB_TOKEN_MISSING", file=sys.stderr)
        return 2
    report = collect_live_shadow_report(
        repo=repo,
        token=token,
        workflow_run_id=str(os.environ.get("KESHER_TRIGGER_RUN_ID") or ""),
    )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
