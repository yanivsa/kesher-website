#!/usr/bin/env python3
"""Isolated Kesher V6 intervention/reconciliation foundation.

V6 remains non-production-dispatching. It owns an independent pipeline/state
namespace and emits identity-bound shadow reports for parity and incident
learning without creating article/media/provider children.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, MutableMapping

if __package__:
    from . import kesher_e2e_delivery_guard as delivery_guard
    from . import kesher_intervention_policy as intervention
else:
    import kesher_e2e_delivery_guard as delivery_guard
    import kesher_intervention_policy as intervention

PIPELINE_ID = "v6"
STATE_REF = "automation-state-v6"
ARTIFACT_NAMESPACE = "kesher-v6"
CONCURRENCY_GROUP = "kesher-content-controller-v6"
CANARY_MODE_SHADOW = "shadow"


class V6InterventionReconciler:
    """V6-facing adapter for the shared three-check intervention contract."""

    def __init__(self, state: MutableMapping[str, Any]):
        self.state = state
        self.state.setdefault("pipeline_id", PIPELINE_ID)
        self.state.setdefault("state_ref", STATE_REF)
        self.state.setdefault("artifact_namespace", ARTIFACT_NAMESPACE)

    def observe(
        self,
        *,
        slug: str,
        content_sha256: str,
        stage: str,
        progress: dict[str, Any],
        check_token: str,
        controller_action_token: str | None,
        now: datetime,
        failure_signature: str = intervention.DEFAULT_FAILURE_SIGNATURE,
    ) -> intervention.InterventionDecision:
        return intervention.observe_incident(
            state=self.state,
            pipeline_id=PIPELINE_ID,
            slug=slug,
            content_sha256=content_sha256,
            stage=stage,
            failure_signature=failure_signature,
            progress=progress,
            check_token=check_token,
            controller_action_token=controller_action_token,
            now=now,
        )


def _required_identity(value: str | None, field: str) -> str:
    resolved = str(value or "").strip()
    if not resolved:
        raise ValueError(f"{field} is required for V6 shadow canary")
    return resolved


def _mutation_disabled() -> dict[str, bool]:
    return {
        "production_dispatch_enabled": False,
        "article_dispatch_enabled": False,
        "provider_dispatch_enabled": False,
        "upload_enabled": False,
    }


def shadow_canary_report(
    *,
    slug: str,
    content_sha256: str,
    stage: str,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a read-only canary envelope bound to one exact existing identity."""
    identity = {
        "slug": _required_identity(slug, "slug"),
        "content_sha256": _required_identity(content_sha256, "content_sha256"),
        "stage": _required_identity(stage, "stage"),
    }
    return {
        "pipeline_id": PIPELINE_ID,
        "state_ref": STATE_REF,
        "artifact_namespace": ARTIFACT_NAMESPACE,
        "concurrency_group": CONCURRENCY_GROUP,
        "canary_mode": CANARY_MODE_SHADOW,
        "identity": identity,
        "progress": dict(progress or {}),
        **_mutation_disabled(),
    }


def v5_v6_parity_report(
    *,
    v5_state: dict[str, Any],
    slug: str,
    content_sha256: str,
    stage: str,
) -> dict[str, Any]:
    """Mirror one exact V5 identity and fail closed without public A+B+C."""
    identity = {
        "slug": _required_identity(slug, "slug"),
        "content_sha256": _required_identity(content_sha256, "content_sha256"),
    }
    stage_name = _required_identity(stage, "stage")
    v5_source = v5_state.get("source") or {}
    observed_identity = {
        "slug": str(v5_source.get("slug") or v5_source.get("id") or "").strip(),
        "content_sha256": str(v5_source.get("content_sha256") or "").strip(),
    }
    if observed_identity != identity:
        raise ValueError("exact V5 source identity does not match V6 canary target")

    stage_key = {
        "article": "article",
        "overview": "long_video",
        "long_video": "long_video",
        "short": "short",
    }.get(stage_name, stage_name)
    stage_state = v5_state.get(stage_key) or {}
    delivery_complete, deliverables = delivery_guard.delivery_contract(v5_state)
    green_without_delivery = bool(v5_state.get("workflow_success") is True and not delivery_complete)
    takeover = v5_state.get("direct_takeover_required")

    return {
        "pipeline_id": PIPELINE_ID,
        "state_ref": STATE_REF,
        "artifact_namespace": ARTIFACT_NAMESPACE,
        "canary_mode": CANARY_MODE_SHADOW,
        "stage": stage_name,
        "status": "complete" if delivery_complete else "incomplete",
        "parity": delivery_complete,
        "source_identity": identity,
        "task_identity": stage_state.get("task_id"),
        "artifact_identity": stage_state.get("artifact_id"),
        "provider_identity": stage_state.get("provider_id") or stage_state.get("provider_identity"),
        "article_url": deliverables["article_url"],
        "overview_url": deliverables["overview_youtube_url"],
        "short_url": deliverables["short_youtube_url"],
        "portrait_verification": deliverables["short_portrait_verified"],
        "workflow_success_without_public_abc": green_without_delivery,
        "direct_takeover_required": bool(
            (isinstance(takeover, dict) and takeover.get("required") is True)
            or takeover is True
            or green_without_delivery
        ),
        "duplicate_dispatch_blocked": True,
        **_mutation_disabled(),
    }


def _latest_current_v5_incident(v5_state: dict[str, Any]) -> dict[str, Any] | None:
    source = v5_state.get("source") or {}
    cycle = str(v5_state.get("cycle") or "")
    matches = []
    for current in (v5_state.get("interventions") or {}).values():
        if not isinstance(current, dict) or str(current.get("pipeline_id") or "") != "v5":
            continue
        stage = str(current.get("stage") or "")
        if stage == "article":
            relevant = str(current.get("slug") or "") == f"article-slot-{cycle}"
        else:
            relevant = bool(
                str(current.get("slug") or "") == str(source.get("slug") or "")
                and str(current.get("content_sha256") or "")
                == str(source.get("content_sha256") or "")
            )
        if relevant:
            matches.append(current)
    if not matches:
        return None
    return sorted(matches, key=lambda row: str(row.get("last_observed_at") or ""), reverse=True)[0]


def v5_incident_shadow_report(v5_state: dict[str, Any]) -> dict[str, Any]:
    """Explain what V6 would do for V5's latest incident, without doing it."""
    if not isinstance(v5_state, dict):
        raise ValueError("V5 state must be an object")
    source = v5_state.get("source") or {}
    delivery_complete, deliverables = delivery_guard.delivery_contract(v5_state)
    incident = _latest_current_v5_incident(v5_state)
    strike = int((incident or {}).get("strike_count") or 0)
    owner = str((incident or {}).get("owner") or ("done" if delivery_complete else "controller"))
    action = str(
        (incident or {}).get("last_action")
        or ("done" if delivery_complete else intervention.OBSERVE_CONTROLLER)
    )
    takeover = v5_state.get("direct_takeover_required")
    return {
        "pipeline_id": PIPELINE_ID,
        "observed_pipeline_id": str(v5_state.get("pipeline_id") or "v5"),
        "state_ref": STATE_REF,
        "artifact_namespace": ARTIFACT_NAMESPACE,
        "canary_mode": CANARY_MODE_SHADOW,
        "status": "complete" if delivery_complete else "incomplete",
        "source_identity": {
            "slug": str(source.get("slug") or ""),
            "content_sha256": str(source.get("content_sha256") or ""),
        },
        "stage": (incident or {}).get("stage"),
        "failure_signature": (incident or {}).get("failure_signature"),
        "idempotency_key": (incident or {}).get("idempotency_key"),
        "strike": strike,
        "recommended_owner": owner,
        "recommended_action": action,
        "article_url": deliverables["article_url"],
        "overview_url": deliverables["overview_youtube_url"],
        "short_url": deliverables["short_youtube_url"],
        "direct_takeover_required": bool(
            strike >= 3
            or (isinstance(takeover, dict) and takeover.get("required") is True)
            or takeover is True
        ),
        "duplicate_dispatch_blocked": True,
        **_mutation_disabled(),
    }


def _self_check() -> dict[str, Any]:
    """Return machine-readable isolation evidence without dispatching providers."""
    state: dict[str, Any] = {}
    reconciler = V6InterventionReconciler(state)
    now = datetime.now(timezone.utc)
    decision = reconciler.observe(
        slug="v6-self-check",
        content_sha256="self-check-sha",
        stage="validation",
        progress={"stage": "validation", "status": "pending"},
        check_token=intervention.jerusalem_hour_token(now),
        controller_action_token=None,
        now=now,
        failure_signature="SELF_CHECK_PENDING",
    )
    return {
        "pipeline_id": PIPELINE_ID,
        "state_ref": STATE_REF,
        "artifact_namespace": ARTIFACT_NAMESPACE,
        "concurrency_group": CONCURRENCY_GROUP,
        "production_dispatch_enabled": False,
        "intervention_action": decision.action,
        "strike": decision.strike,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--report-json", action="store_true")
    parser.add_argument("--canary-shadow", action="store_true")
    parser.add_argument("--analyze-v5-state")
    parser.add_argument("--slug")
    parser.add_argument("--content-sha256")
    parser.add_argument("--stage")
    args = parser.parse_args()

    if args.analyze_v5_state:
        payload = json.loads(Path(args.analyze_v5_state).read_text(encoding="utf-8"))
        print(json.dumps(v5_incident_shadow_report(payload), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.canary_shadow:
        try:
            payload = shadow_canary_report(
                slug=args.slug,
                content_sha256=args.content_sha256,
                stage=args.stage,
            )
        except ValueError as exc:
            parser.error(str(exc))
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if not (args.self_check or args.report_json):
        parser.error(
            "V6 is shadow/manual only; use --self-check, --report-json, --canary-shadow or --analyze-v5-state"
        )
    print(json.dumps(_self_check(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
