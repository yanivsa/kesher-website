from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping
from zoneinfo import ZoneInfo

OBSERVE_CONTROLLER = "observe_controller"
ESCALATE_JULES = "escalate_jules"
DIRECT_TAKEOVER = "direct_takeover"
PROGRESS_RESET = "progress_reset"

# Legacy action names remain import-compatible for old state/readers, but new
# hourly decisions never emit them. The production ladder is Controller → Jules → Direct.
FORCE_CONTROLLER_RECOVERY = "force_controller_recovery"
WAIT_AFTER_CONTROLLER_ACTION = "wait_after_controller_action"
DEFAULT_FAILURE_SIGNATURE = "STALLED"

# Only durable work/provider/deliverable fields count as progress. Poll timestamps,
# workflow conclusions and log freshness are deliberately excluded.
DURABLE_PROGRESS_FIELDS = (
    "stage",
    "status",
    "slug",
    "content_sha256",
    "item_id",
    "task_id",
    "provider_id",
    "artifact_id",
    "source_id",
    "article_url",
    "youtube_id",
    "youtube_url",
    "verified",
    "portrait_verified",
    "signature_verified",
    "width",
    "height",
)


@dataclass(frozen=True)
class InterventionDecision:
    incident_key: str
    strike: int
    action: str
    progress_reset: bool = False
    controller_action_observed: bool = False
    failure_signature: str = ""
    idempotency_key: str = ""
    owner: str = "controller"


def _required(value: Any, field: str) -> str:
    resolved = str(value or "").strip()
    if not resolved:
        raise ValueError(f"{field} is required")
    return resolved


def incident_key(
    *,
    pipeline_id: str,
    slug: str,
    content_sha256: str,
    stage: str,
    failure_signature: str = DEFAULT_FAILURE_SIGNATURE,
) -> str:
    """Return the stable identity of one exact stalled failure mode.

    `failure_signature` defaults to STALLED only for legacy callers. New
    supervisor callers should always pass the observed failure signature.
    """
    values = (
        _required(pipeline_id, "pipeline_id"),
        _required(slug, "slug"),
        _required(content_sha256, "content_sha256"),
        _required(stage, "stage"),
        _required(failure_signature, "failure_signature"),
    )
    return "|".join(values)


def incident_idempotency_key(
    *,
    pipeline_id: str,
    slug: str,
    content_sha256: str,
    stage: str,
    failure_signature: str = DEFAULT_FAILURE_SIGNATURE,
) -> str:
    """Deterministic key shared by supervisor and Jules repair handoff."""
    key = incident_key(
        pipeline_id=pipeline_id,
        slug=slug,
        content_sha256=content_sha256,
        stage=stage,
        failure_signature=failure_signature,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def durable_progress_fingerprint(progress: Mapping[str, Any] | None) -> str:
    """Hash only evidence that represents durable progress.

    A new poll timestamp, log line or a GitHub workflow conclusion by itself is
    not progress. This prevents false strike resets while a provider remains at
    the same actual stage/artifact identity.
    """
    source = progress or {}
    durable = {field: source.get(field) for field in DURABLE_PROGRESS_FIELDS}
    payload = json.dumps(durable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def jerusalem_hour_token(now: datetime | None = None) -> str:
    """One strike opportunity per local Chief-of-Staff hourly check."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local = current.astimezone(ZoneInfo("Asia/Jerusalem"))
    return local.strftime("%Y-%m-%dT%H")


def _decision(current: Mapping[str, Any], key: str, *, progress_reset: bool = False) -> InterventionDecision:
    return InterventionDecision(
        incident_key=key,
        strike=int(current.get("strike_count") or 0),
        action=str(current.get("last_action") or OBSERVE_CONTROLLER),
        progress_reset=progress_reset,
        controller_action_observed=bool(current.get("controller_action_observed")),
        failure_signature=str(current.get("failure_signature") or ""),
        idempotency_key=str(current.get("idempotency_key") or ""),
        owner=str(current.get("owner") or "controller"),
    )


def observe_incident(
    *,
    state: MutableMapping[str, Any],
    pipeline_id: str,
    slug: str,
    content_sha256: str,
    stage: str,
    failure_signature: str = DEFAULT_FAILURE_SIGNATURE,
    progress: Mapping[str, Any] | None,
    check_token: str,
    controller_action_token: str | None,
    now: datetime,
) -> InterventionDecision:
    """Apply the bounded Controller → Jules → Direct hourly contract.

    Check 1 leaves ownership with the production Controller. Check 2 hands the
    same exact incident to an idempotent Jules repair session. Check 3 requires
    direct supervisor takeover. Repeated polls with the same check token do not
    manufacture strikes. Any durable progress resets the strike sequence.
    """
    key = incident_key(
        pipeline_id=pipeline_id,
        slug=slug,
        content_sha256=content_sha256,
        stage=stage,
        failure_signature=failure_signature,
    )
    idempotency = incident_idempotency_key(
        pipeline_id=pipeline_id,
        slug=slug,
        content_sha256=content_sha256,
        stage=stage,
        failure_signature=failure_signature,
    )
    fingerprint = durable_progress_fingerprint(progress)
    interventions = state.setdefault("interventions", {})
    current = interventions.get(key)
    now_iso = now.astimezone(timezone.utc).isoformat()

    if not isinstance(current, dict):
        current = {
            "pipeline_id": pipeline_id,
            "slug": slug,
            "content_sha256": content_sha256,
            "stage": stage,
            "failure_signature": failure_signature,
            "idempotency_key": idempotency,
            "owner": "controller",
            "strike_count": 1,
            "last_check_token": check_token,
            "last_fingerprint": fingerprint,
            "last_controller_action_token": controller_action_token,
            "controller_action_observed": False,
            "last_observed_at": now_iso,
            "last_action": OBSERVE_CONTROLLER,
            "direct_takeover_required": False,
        }
        interventions[key] = current
        return _decision(current, key)

    previous_fingerprint = str(current.get("last_fingerprint") or "")
    if fingerprint != previous_fingerprint:
        current.update(
            {
                "strike_count": 0,
                "last_check_token": check_token,
                "last_fingerprint": fingerprint,
                "last_controller_action_token": controller_action_token,
                "controller_action_observed": False,
                "last_observed_at": now_iso,
                "last_action": PROGRESS_RESET,
                "owner": "controller",
                "direct_takeover_required": False,
                "jules_repair": None,
            }
        )
        return _decision(current, key, progress_reset=True)

    # Multiple polls during the same local-hour observation cannot advance strikes.
    if str(current.get("last_check_token") or "") == str(check_token):
        return _decision(current, key)

    strike = min(3, int(current.get("strike_count") or 0) + 1)
    previous_controller_token = current.get("last_controller_action_token")
    token_changed = bool(controller_action_token) and controller_action_token != previous_controller_token
    controller_acted = bool(current.get("controller_action_observed")) or token_changed

    if strike >= 3:
        action = DIRECT_TAKEOVER
        owner = "direct"
    elif strike == 2:
        action = ESCALATE_JULES
        owner = "jules"
    else:
        action = OBSERVE_CONTROLLER
        owner = "controller"

    current.update(
        {
            "strike_count": strike,
            "last_check_token": check_token,
            "last_controller_action_token": controller_action_token or previous_controller_token,
            "controller_action_observed": controller_acted,
            "last_observed_at": now_iso,
            "last_action": action,
            "owner": owner,
            "direct_takeover_required": action == DIRECT_TAKEOVER,
        }
    )
    return _decision(current, key)


def mark_controller_action(
    state: MutableMapping[str, Any],
    *,
    incident_key: str,
    action_token: str,
    now: datetime,
) -> None:
    """Record Controller activity without delaying the next-hour Jules escalation."""
    interventions = state.get("interventions")
    if not isinstance(interventions, dict):
        return
    current = interventions.get(incident_key)
    if not isinstance(current, dict):
        return
    current["last_controller_action_token"] = action_token
    current["controller_action_observed"] = True
    current["last_controller_action_at"] = now.astimezone(timezone.utc).isoformat()
    # Keep the hourly decision itself unchanged. A Controller action during S1
    # must not turn S2 into another waiting/recovery window.
    current["direct_takeover_required"] = False


def mark_jules_action(
    state: MutableMapping[str, Any],
    *,
    incident_key: str,
    session_id: str,
    now: datetime,
) -> None:
    """Persist the exact S2 Jules repair handoff for idempotent later checks."""
    interventions = state.get("interventions")
    if not isinstance(interventions, dict):
        return
    current = interventions.get(incident_key)
    if not isinstance(current, dict):
        return
    current["jules_repair"] = {
        "session_id": str(session_id),
        "idempotency_key": str(current.get("idempotency_key") or ""),
        "sent_at": now.astimezone(timezone.utc).isoformat(),
    }
    current["owner"] = "jules"
    current["last_action"] = ESCALATE_JULES
    current["direct_takeover_required"] = False


def clear_incident(
    state: MutableMapping[str, Any],
    *,
    pipeline_id: str,
    slug: str,
    content_sha256: str,
    stage: str,
    failure_signature: str | None = None,
) -> None:
    interventions = state.get("interventions")
    if not isinstance(interventions, dict):
        return
    if failure_signature:
        interventions.pop(
            incident_key(
                pipeline_id=pipeline_id,
                slug=slug,
                content_sha256=content_sha256,
                stage=stage,
                failure_signature=failure_signature,
            ),
            None,
        )
        return
    # Backward-compatible cleanup for callers that predate failure signatures.
    prefix = "|".join((str(pipeline_id), str(slug), str(content_sha256), str(stage))) + "|"
    for key in list(interventions):
        if str(key).startswith(prefix):
            interventions.pop(key, None)
