from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, MutableMapping
from zoneinfo import ZoneInfo

OBSERVE_CONTROLLER = "observe_controller"
FORCE_CONTROLLER_RECOVERY = "force_controller_recovery"
WAIT_AFTER_CONTROLLER_ACTION = "wait_after_controller_action"
DIRECT_TAKEOVER = "direct_takeover"
PROGRESS_RESET = "progress_reset"

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


def incident_key(*, pipeline_id: str, slug: str, content_sha256: str, stage: str) -> str:
    """Return the stable identity of one stalled unit of work."""
    values = (pipeline_id, slug, content_sha256, stage)
    if any(not str(value or "").strip() for value in values):
        raise ValueError("pipeline_id, slug, content_sha256 and stage are required")
    return "|".join(str(value).strip() for value in values)


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


def observe_incident(
    *,
    state: MutableMapping[str, Any],
    pipeline_id: str,
    slug: str,
    content_sha256: str,
    stage: str,
    progress: Mapping[str, Any] | None,
    check_token: str,
    controller_action_token: str | None,
    now: datetime,
) -> InterventionDecision:
    """Apply the bounded three-check intervention contract.

    Check 1 gives the Controller one window. Check 2 forces a same-identity
    recovery only when the Controller has not already acted. Check 3 requires
    direct supervisor takeover. Repeated polls with the same check token do not
    advance strikes. Any durable progress resets the strike sequence.
    """
    key = incident_key(
        pipeline_id=pipeline_id,
        slug=slug,
        content_sha256=content_sha256,
        stage=stage,
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
            "strike_count": 1,
            "last_check_token": check_token,
            "last_fingerprint": fingerprint,
            "last_controller_action_token": controller_action_token,
            "last_observed_at": now_iso,
            "last_action": OBSERVE_CONTROLLER,
            "direct_takeover_required": False,
        }
        interventions[key] = current
        return InterventionDecision(key, 1, OBSERVE_CONTROLLER)

    previous_fingerprint = str(current.get("last_fingerprint") or "")
    if fingerprint != previous_fingerprint:
        current.update(
            {
                "strike_count": 0,
                "last_check_token": check_token,
                "last_fingerprint": fingerprint,
                "last_controller_action_token": controller_action_token,
                "last_observed_at": now_iso,
                "last_action": PROGRESS_RESET,
                "direct_takeover_required": False,
            }
        )
        return InterventionDecision(key, 0, PROGRESS_RESET, progress_reset=True)

    # The Controller runs much more frequently than the Chief-of-Staff check.
    # Multiple polls in one local-hour observation must not manufacture strikes.
    if str(current.get("last_check_token") or "") == str(check_token):
        strike = int(current.get("strike_count") or 0)
        action = str(current.get("last_action") or OBSERVE_CONTROLLER)
        return InterventionDecision(
            key,
            strike,
            action,
            controller_action_observed=action == WAIT_AFTER_CONTROLLER_ACTION,
        )

    strike = int(current.get("strike_count") or 0) + 1
    previous_controller_token = current.get("last_controller_action_token")
    controller_acted = bool(controller_action_token) and controller_action_token != previous_controller_token

    if strike >= 3:
        action = DIRECT_TAKEOVER
        strike = 3
    elif strike == 2 and controller_acted:
        action = WAIT_AFTER_CONTROLLER_ACTION
    elif strike == 2:
        action = FORCE_CONTROLLER_RECOVERY
    else:
        action = OBSERVE_CONTROLLER

    current.update(
        {
            "strike_count": strike,
            "last_check_token": check_token,
            "last_controller_action_token": controller_action_token,
            "last_observed_at": now_iso,
            "last_action": action,
            "direct_takeover_required": action == DIRECT_TAKEOVER,
        }
    )
    return InterventionDecision(
        key,
        strike,
        action,
        controller_action_observed=controller_acted,
    )


def mark_controller_action(
    state: MutableMapping[str, Any],
    *,
    incident_key: str,
    action_token: str,
    now: datetime,
) -> None:
    """Record a targeted Controller recovery so one hourly check cannot duplicate it."""
    interventions = state.get("interventions")
    if not isinstance(interventions, dict):
        return
    current = interventions.get(incident_key)
    if not isinstance(current, dict):
        return
    current["last_controller_action_token"] = action_token
    current["last_controller_action_at"] = now.astimezone(timezone.utc).isoformat()
    current["last_action"] = WAIT_AFTER_CONTROLLER_ACTION
    current["direct_takeover_required"] = False


def clear_incident(
    state: MutableMapping[str, Any],
    *,
    pipeline_id: str,
    slug: str,
    content_sha256: str,
    stage: str,
) -> None:
    interventions = state.get("interventions")
    if not isinstance(interventions, dict):
        return
    interventions.pop(
        incident_key(
            pipeline_id=pipeline_id,
            slug=slug,
            content_sha256=content_sha256,
            stage=stage,
        ),
        None,
    )
