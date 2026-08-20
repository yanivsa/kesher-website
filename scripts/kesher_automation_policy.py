from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "config" / "kesher-automation-policy.json"
EXPECTED_SCHEMA_VERSION = 1


class AutomationPolicyError(RuntimeError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutomationPolicyError(f"Automation policy is unreadable: {path}") from exc
    if not isinstance(policy, dict):
        raise AutomationPolicyError("Automation policy must be a JSON object")
    if policy.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise AutomationPolicyError(
            f"Automation policy schema mismatch: expected {EXPECTED_SCHEMA_VERSION}"
        )

    article = policy.get("article")
    video = policy.get("video")
    invariants = policy.get("invariants")
    if not isinstance(article, dict) or not isinstance(video, dict) or not isinstance(invariants, dict):
        raise AutomationPolicyError("Automation policy is missing article/video/invariants sections")

    backoff = article.get("retry_backoff_minutes")
    if (
        article.get("generator") != "jules"
        or article.get("worker_session_attempts") != 1
        or not isinstance(backoff, list)
        or not backoff
        or any(not isinstance(value, int) or value <= 0 for value in backoff)
    ):
        raise AutomationPolicyError("Article automation policy is invalid")

    if (
        video.get("review_gate") != "mandatory"
        or video.get("jules_review_required") is not True
        or video.get("upload_requires_approved_review") is not True
    ):
        raise AutomationPolicyError("Video publication policy must keep Jules as a mandatory gate")

    required_invariants = (
        "one_article_per_slot",
        "one_video_per_article",
        "workers_are_single_attempt",
        "controller_owns_retries",
        "heartbeat_is_recovery_only",
    )
    if any(invariants.get(name) is not True for name in required_invariants):
        raise AutomationPolicyError("Required Kesher automation invariants are not enabled")
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
    if value < 3:
        raise AutomationPolicyError("At least three durable video-state artifacts must be retained")
    return value
