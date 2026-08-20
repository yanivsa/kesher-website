from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "kesher-production-contract.json"
EXPECTED_CONTRACT_VERSION = 3


class AutomationPolicyError(RuntimeError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutomationPolicyError(f"Production contract is unreadable: {path}") from exc
    if not isinstance(policy, dict):
        raise AutomationPolicyError("Production contract must be a JSON object")
    if policy.get("contract_version") != EXPECTED_CONTRACT_VERSION:
        raise AutomationPolicyError(
            f"Production contract mismatch: expected version {EXPECTED_CONTRACT_VERSION}"
        )

    scheduler = policy.get("scheduler")
    article = policy.get("article")
    image = policy.get("image")
    video = policy.get("video")
    invariants = policy.get("invariants")
    if not all(isinstance(section, dict) for section in (scheduler, article, image, video, invariants)):
        raise AutomationPolicyError(
            "Production contract is missing scheduler/article/image/video/invariants sections"
        )

    if (
        scheduler.get("owner") != "kesher-content-controller"
        or scheduler.get("heartbeat_minutes") != 15
        or scheduler.get("failure_recovery") != "heartbeat"
    ):
        raise AutomationPolicyError("Scheduler contract is invalid")

    backoff = article.get("retry_backoff_minutes")
    if (
        article.get("generator") != "jules"
        or article.get("worker_session_attempts") != 1
        or not isinstance(backoff, list)
        or not backoff
        or any(not isinstance(value, int) or value <= 0 for value in backoff)
    ):
        raise AutomationPolicyError("Article automation contract is invalid")

    if (
        image.get("required_for_article") is not True
        or image.get("worker_owner") != "github-actions"
        or image.get("fallback_must_be_local") is not True
    ):
        raise AutomationPolicyError("Image production contract is invalid")

    if (
        video.get("publication_gate") != "technical"
        or video.get("jules_review") != "advisory"
        or video.get("queue_order") != "fifo"
        or video.get("durable_state_artifacts_to_keep") != 3
        or video.get("durable_state_retention_days") != 14
    ):
        raise AutomationPolicyError(
            "Video contract must use technical publication, advisory Jules, FIFO, and 3 snapshots/14 days"
        )

    required_invariants = (
        "one_article_per_slot",
        "one_video_per_article",
        "workers_are_single_attempt",
        "controller_owns_retries",
        "heartbeat_is_recovery_only",
        "provider_ids_are_persisted_before_followup",
        "youtube_insert_is_idempotent",
    )
    if any(invariants.get(name) is not True for name in required_invariants):
        raise AutomationPolicyError("Required Kesher production invariants are not enabled")

    # Derived convenience flag for legacy consumers. Unlike the removed
    # mandatory-gate aliases, this cannot contradict the canonical contract.
    video["jules_is_advisory"] = video["jules_review"] == "advisory"
    return policy


def article_retry_backoff_minutes(failure_streak: int, policy: dict[str, Any] | None = None) -> int:
    current = policy or load_policy()
    values = current["article"]["retry_backoff_minutes"]
    index = max(0, min(int(failure_streak) - 1, len(values) - 1))
    minutes = int(values[index])
    threshold = int(current["article"].get("circuit_breaker_after_same_failure") or 0)
    if threshold and int(failure_streak) >= threshold:
        minutes = max(minutes, int(current["article"].get("circuit_breaker_minutes") or minutes))
    return minutes


def durable_video_state_artifacts_to_keep(policy: dict[str, Any] | None = None) -> int:
    current = policy or load_policy()
    value = int(current["video"].get("durable_state_artifacts_to_keep") or 0)
    if value != 3:
        raise AutomationPolicyError("Exactly three durable video-state artifacts must be retained")
    return value
