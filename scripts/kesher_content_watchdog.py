from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

ARTICLE_NUDGE_AFTER = timedelta(minutes=15)
ARTICLE_RESTART_AFTER = timedelta(minutes=25)
MAX_ARTICLE_WORKER_RESTARTS = 2
MEDIA_STALL_AFTER = timedelta(minutes=20)
MAX_MEDIA_RECOVERIES = 3


def _parse(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def observe_article(
    stage: dict[str, Any],
    *,
    identity: str,
    run_started_at: Any,
    session_id: str | None,
    fingerprint: str | None,
    now: datetime,
) -> dict[str, Any]:
    now_utc = now.astimezone(timezone.utc)
    current = stage.get("watchdog")
    if not isinstance(current, dict) or current.get("identity") != identity:
        current = {
            "identity": identity,
            "session_id": session_id,
            "last_progress_at": _iso(_parse(run_started_at) or now_utc),
            "last_fingerprint": fingerprint,
            "last_nudge_at": None,
            "nudge_count": 0,
            "worker_restart_count": 0,
            "last_restart_at": None,
            "last_restart_run_id": None,
        }
        stage["watchdog"] = current
        return current

    current.setdefault("session_id", session_id)
    current.setdefault("last_progress_at", _iso(_parse(run_started_at) or now_utc))
    current.setdefault("last_fingerprint", fingerprint)
    current.setdefault("last_nudge_at", None)
    current.setdefault("nudge_count", 0)
    current.setdefault("worker_restart_count", 0)
    current.setdefault("last_restart_at", None)
    current.setdefault("last_restart_run_id", None)

    if session_id:
        current["session_id"] = session_id
    previous = str(current.get("last_fingerprint") or "")
    incoming = str(fingerprint or "")
    if incoming and previous and incoming != previous:
        current["last_fingerprint"] = incoming
        current["last_progress_at"] = _iso(now_utc)
        current["last_nudge_at"] = None
        current["nudge_count"] = 0
    elif incoming and not previous:
        current["last_fingerprint"] = incoming
    return current


def article_decision(stage: dict[str, Any], *, now: datetime, active_run_id: Any) -> str:
    current = stage.get("watchdog")
    if not isinstance(current, dict):
        return "wait"
    if not str(current.get("session_id") or "").strip():
        return "wait"

    progress_at = _parse(current.get("last_progress_at"))
    restart_at = _parse(current.get("last_restart_at"))
    baseline = max([value for value in (progress_at, restart_at) if value is not None], default=now.astimezone(timezone.utc))
    idle = now.astimezone(timezone.utc) - baseline
    nudge_count = int(current.get("nudge_count") or 0)
    restart_count = int(current.get("worker_restart_count") or 0)

    if idle >= ARTICLE_RESTART_AFTER and nudge_count >= 1:
        if restart_count >= MAX_ARTICLE_WORKER_RESTARTS:
            return "blocked"
        if str(current.get("last_restart_run_id") or "") == str(active_run_id or ""):
            return "wait"
        return "restart"
    if idle >= ARTICLE_NUDGE_AFTER and nudge_count == 0:
        return "nudge"
    return "wait"


def mark_article_nudge(stage: dict[str, Any], *, now: datetime) -> None:
    current = stage["watchdog"]
    current["nudge_count"] = int(current.get("nudge_count") or 0) + 1
    current["last_nudge_at"] = _iso(now.astimezone(timezone.utc))


def mark_article_restart(stage: dict[str, Any], *, now: datetime, run_id: Any) -> None:
    current = stage["watchdog"]
    current["worker_restart_count"] = int(current.get("worker_restart_count") or 0) + 1
    current["last_restart_at"] = _iso(now.astimezone(timezone.utc))
    current["last_restart_run_id"] = run_id
    current["last_nudge_at"] = None
    current["nudge_count"] = 0


def observe_media(
    stage: dict[str, Any],
    *,
    identity: str,
    fingerprint: str | None,
    now: datetime,
) -> dict[str, Any]:
    """Track durable provider progress without creating a second media identity."""
    now_utc = now.astimezone(timezone.utc)
    current = stage.get("watchdog")
    if not isinstance(current, dict) or current.get("identity") != identity:
        current = {
            "identity": identity,
            "last_progress_at": _iso(now_utc),
            "last_fingerprint": fingerprint,
            "recovery_count": 0,
            "last_recovery_at": None,
        }
        stage["watchdog"] = current
        return current

    current.setdefault("last_progress_at", _iso(now_utc))
    current.setdefault("last_fingerprint", fingerprint)
    current.setdefault("recovery_count", 0)
    current.setdefault("last_recovery_at", None)
    previous = str(current.get("last_fingerprint") or "")
    incoming = str(fingerprint or "")
    if incoming and previous and incoming != previous:
        current["last_fingerprint"] = incoming
        current["last_progress_at"] = _iso(now_utc)
        current["recovery_count"] = 0
        current["last_recovery_at"] = None
    elif incoming and not previous:
        current["last_fingerprint"] = incoming
    return current


def media_decision(stage: dict[str, Any], *, now: datetime) -> str:
    current = stage.get("watchdog")
    if not isinstance(current, dict):
        return "wait"
    progress_at = _parse(current.get("last_progress_at"))
    recovery_at = _parse(current.get("last_recovery_at"))
    baseline = max(
        [value for value in (progress_at, recovery_at) if value is not None],
        default=now.astimezone(timezone.utc),
    )
    idle = now.astimezone(timezone.utc) - baseline
    if idle < MEDIA_STALL_AFTER:
        return "wait"
    if int(current.get("recovery_count") or 0) >= MAX_MEDIA_RECOVERIES:
        return "blocked"
    return "recover"


def mark_media_recovery(stage: dict[str, Any], *, now: datetime) -> None:
    current = stage["watchdog"]
    current["recovery_count"] = int(current.get("recovery_count") or 0) + 1
    current["last_recovery_at"] = _iso(now.astimezone(timezone.utc))
