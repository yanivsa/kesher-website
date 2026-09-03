from __future__ import annotations

from enum import Enum
from typing import Any

MAX_SHORT_ATTEMPTS = 5
MAX_FRESH_GENERATION_ATTEMPTS = 4
FIFTH_ATTEMPT_RECOVERY_ONLY = True


class ShortDecision(str, Enum):
    GENERATE = "generate"
    RECOVER = "recover"
    RELEASE_WITHOUT_SHORT = "release_without_short"


def decide_short_action(
    attempt_count: int,
    *,
    has_recoverable_identity: bool,
) -> ShortDecision:
    """Decide whether the controller may create or only recover Short work.

    Attempts 1-4 may start fresh semantic/video generation. After four failed
    fresh attempts, a fifth controller turn is allowed only to finish an exact
    persisted provider/upload identity. If there is nothing exact to recover,
    the article is released as complete without a Short.
    """
    attempts = max(0, int(attempt_count))
    if attempts < MAX_FRESH_GENERATION_ATTEMPTS:
        return ShortDecision.GENERATE
    if (
        attempts == MAX_FRESH_GENERATION_ATTEMPTS
        and FIFTH_ATTEMPT_RECOVERY_ONLY
        and has_recoverable_identity
    ):
        return ShortDecision.RECOVER
    return ShortDecision.RELEASE_WITHOUT_SHORT


def has_recoverable_short_identity(item: dict[str, Any] | None) -> bool:
    if not isinstance(item, dict):
        return False
    return bool(
        item.get("source_id")
        or item.get("task_id")
        or item.get("artifact_id")
        or item.get("raw_mp4")
        or item.get("final_mp4")
        or item.get("upload_session_uri")
        or item.get("youtube_id")
    )
