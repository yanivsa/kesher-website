#!/usr/bin/env python3
"""Promote the last usable same-source video after the third fresh attempt fails.

This is a narrow fail-safe for the production Video Overview pipeline. It never
creates a new source, generation or upload. It only promotes an existing local
artifact for the same authoritative source identity when three fresh attempts
have already been consumed and no public upload exists.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

STATE_DIR = Path(os.environ.get("KESHER_STATE_DIR", ".kesher-video-state"))
STATE_FILE = STATE_DIR / "state.json"
FINAL_ATTEMPT = 3


def _slug(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def _source_hash(item: dict[str, Any]) -> str:
    return str((item.get("source") or {}).get("content_sha256") or "").strip()


def _voice_only_rejection(item: dict[str, Any]) -> bool:
    note = str((item.get("review_notes") or {}).get("technical") or "")
    if not note.startswith("נפסל טכנית"):
        return False
    lowered = note.lower()
    voice_markers = ("male voice", "קול גברי", "pitch")
    if not any(marker in lowered for marker in voice_markers):
        return False
    blockers = (
        "אינו בטווח 90–180",
        "אינו יחס אופקי",
        "לא H.264",
        "מטא־דאטה אינו עומד",
        "סגיר החתימה",
    )
    return not any(blocker in note for blocker in blockers)


def _usable_candidate(item: dict[str, Any], slug: str, source_hash: str) -> bool:
    if _slug(item) != slug or _source_hash(item) != source_hash:
        return False
    if item.get("uploaded") is True:
        return False
    final_name = str(item.get("final_mp4") or "").strip()
    if not final_name or not item.get("final_sha256"):
        return False
    final_path = STATE_DIR / final_name
    if not final_path.is_file() or final_path.stat().st_size < 1024:
        return False
    media = item.get("media") or {}
    try:
        width = int(media.get("width") or 0)
        height = int(media.get("height") or 0)
        duration = float(media.get("duration") or 0)
    except (TypeError, ValueError):
        return False
    if width <= height or not 1.70 <= (width / height if height else 0) <= 1.82:
        return False
    if not 90 <= duration <= 183.5:
        return False
    return item.get("technical_verified") is True or _voice_only_rejection(item)


def promote_last_usable_after_third_attempt(state: dict[str, Any]) -> dict[str, Any] | None:
    items = [row for row in state.get("items") or [] if isinstance(row, dict)]
    if not items:
        return None

    active = [
        row for row in items
        if row.get("uploaded") is not True
        and int(row.get("fresh_generation_attempt") or 0) >= FINAL_ATTEMPT
        and _slug(row)
        and _source_hash(row)
    ]
    if not active:
        return None

    latest_attempt = max(active, key=lambda row: (int(row.get("fresh_generation_attempt") or 0), str(row.get("updated_at") or "")))
    slug = _slug(latest_attempt)
    source_hash = _source_hash(latest_attempt)

    if any(
        row.get("uploaded") is True and _slug(row) == slug and _source_hash(row) == source_hash
        for row in items
    ):
        return None

    candidates = [row for row in items if _usable_candidate(row, slug, source_hash)]
    if not candidates:
        return None

    chosen = max(
        candidates,
        key=lambda row: (int(row.get("fresh_generation_attempt") or 0), str(row.get("updated_at") or "")),
    )
    for row in items:
        if row is chosen:
            continue
        if _slug(row) == slug and _source_hash(row) == source_hash and row.get("uploaded") is not True:
            if row.get("status") not in {"superseded", "uploaded"}:
                row["status"] = "superseded"
                row["superseded_reason"] = "final_attempt_fallback_selected_other_existing_artifact"

    chosen["technical_verified"] = True
    chosen["status"] = "pending_review"
    chosen["final_attempt_fallback"] = True
    chosen["voice_gate_waived_after_attempt"] = FINAL_ATTEMPT
    chosen["fallback_reason"] = "third_attempt_failed_use_last_usable_same_source_artifact"
    chosen["updated_at"] = latest_attempt.get("updated_at") or chosen.get("updated_at")
    return chosen


def main() -> int:
    if not STATE_FILE.is_file():
        print("FINAL_ATTEMPT_FALLBACK_NO_STATE")
        return 0
    state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    chosen = promote_last_usable_after_third_attempt(state)
    if chosen is None:
        print("FINAL_ATTEMPT_FALLBACK_NOT_APPLICABLE")
        return 0
    temp = STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(STATE_FILE)
    print(f"FINAL_ATTEMPT_FALLBACK_PROMOTED item={chosen.get('id')} slug={_slug(chosen)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
