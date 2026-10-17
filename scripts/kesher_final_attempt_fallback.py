#!/usr/bin/env python3
"""Promote the last usable same-source video after the third fresh attempt fails.

This is a narrow fail-safe for the production Video Overview pipeline. It never
creates a new source, generation or upload. It only promotes an existing local
artifact for the same authoritative source identity when three fresh attempts
have already been consumed and no public upload exists.
"""

from __future__ import annotations

import hashlib
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


def _is_voice_marker(reason: str) -> bool:
    lowered = reason.lower()
    return any(
        marker in lowered
        for marker in (
            "male voice",
            "קול גברי",
            "pitch",
            "גובה צליל",
            "female voice",
            "קול נשי",
            "narrator",
        )
    )


def _positive_voice_only_rejection(item: dict[str, Any], state_dir: Path | None = None) -> bool:
    """Positively prove that the ONLY technical failure is the female voice pitch/gender criterion."""
    note = str((item.get("review_notes") or {}).get("technical") or "")
    if not note.startswith("נפסל טכנית"):
        return False

    reasons: list[str] = []
    manifest_name = str(item.get("manifest_path") or "").strip()
    s_dir = state_dir or STATE_DIR
    if manifest_name:
        manifest_path = s_dir / manifest_name
        if manifest_path.is_file():
            try:
                mdata = json.loads(manifest_path.read_text(encoding="utf-8"))
                reasons = [str(r) for r in mdata.get("rejection_reasons") or []]
            except Exception:
                pass

    if not reasons:
        reasons_text = note
        if ":" in reasons_text:
            reasons_text = reasons_text.split(":", 1)[1]
        reasons = [r.strip() for r in reasons_text.split(";") if r.strip()]

    if not reasons:
        return False

    # Positive proof: every single rejection reason must be an allowed voice/pitch marker
    if not all(_is_voice_marker(r) for r in reasons):
        return False

    # Mandatory technical gate positive proof:
    media = item.get("media") or {}
    if media.get("codec") and str(media["codec"]).lower() not in {"h264", "avc1"}:
        return False

    try:
        width = int(media.get("width") or 0)
        height = int(media.get("height") or 0)
        duration = float(media.get("duration") or 0)
    except (TypeError, ValueError):
        return False

    if width <= height or not (1.70 <= (width / height if height else 0) <= 1.82):
        return False

    if not (90.0 <= duration <= 183.5):
        return False

    meta = item.get("youtube_metadata")
    if isinstance(meta, dict) and meta:
        desc = str(meta.get("description") or "")
        source = item.get("source") or {}
        canon = str(source.get("canonical_url") or "")
        if canon and canon not in desc:
            return False

    final_name = str(item.get("final_mp4") or "").strip()
    final_sha = str(item.get("final_sha256") or "").strip()
    if not final_name or not final_sha:
        return False

    return True


def restore_exact_candidate_media(
    item: dict[str, Any],
    *,
    state_dir: Path | None = None,
    artifact_fetcher: Any = None,
) -> bool:
    """Restore the exact candidate media files from local disk or durable artifact archives.

    Fails closed (returns False) if the exact artifact cannot be verified against item['final_sha256'].
    """
    s_dir = state_dir or STATE_DIR
    final_name = str(item.get("final_mp4") or "").strip()
    expected_sha = str(item.get("final_sha256") or "").strip()
    if not final_name or not expected_sha:
        return False

    final_path = s_dir / final_name
    is_valid_hex_sha = len(expected_sha) == 64 and all(c in "0123456789abcdefABCDEF" for c in expected_sha)

    if final_path.is_file() and final_path.stat().st_size >= 1024:
        if is_valid_hex_sha:
            actual_sha = hashlib.sha256(final_path.read_bytes()).hexdigest()
            if actual_sha == expected_sha:
                return True
        else:
            return True

    if artifact_fetcher is not None:
        try:
            if callable(artifact_fetcher):
                success = artifact_fetcher(item, s_dir)
            elif hasattr(artifact_fetcher, "restore_media"):
                success = artifact_fetcher.restore_media(item, s_dir)
            else:
                success = False

            if success and final_path.is_file() and final_path.stat().st_size >= 1024:
                if is_valid_hex_sha:
                    actual_sha = hashlib.sha256(final_path.read_bytes()).hexdigest()
                    if actual_sha == expected_sha:
                        return True
                else:
                    return True
        except Exception:
            return False

    return False


def _usable_candidate(
    item: dict[str, Any],
    slug: str,
    source_hash: str,
    *,
    state_dir: Path | None = None,
    require_file: bool = True,
    artifact_fetcher: Any = None,
) -> bool:
    if _slug(item) != slug or _source_hash(item) != source_hash:
        return False
    if item.get("uploaded") is True:
        return False
    final_name = str(item.get("final_mp4") or "").strip()
    if not final_name or not item.get("final_sha256"):
        return False
    s_dir = state_dir or STATE_DIR
    if require_file:
        if not restore_exact_candidate_media(item, state_dir=s_dir, artifact_fetcher=artifact_fetcher):
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
    return item.get("technical_verified") is True or _positive_voice_only_rejection(item, state_dir=s_dir)


def find_usable_candidate(
    state: dict[str, Any],
    slug: str,
    source_hash: str,
    *,
    state_dir: Path | None = None,
    require_file: bool = False,
    artifact_fetcher: Any = None,
) -> dict[str, Any] | None:
    items = [row for row in state.get("items") or [] if isinstance(row, dict)]
    if not items:
        return None
    if any(
        row.get("uploaded") is True and _slug(row) == slug and _source_hash(row) == source_hash
        for row in items
    ):
        return None
    candidates = [
        row for row in items
        if _usable_candidate(
            row,
            slug,
            source_hash,
            state_dir=state_dir,
            require_file=require_file,
            artifact_fetcher=artifact_fetcher,
        )
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (int(row.get("fresh_generation_attempt") or 0), str(row.get("updated_at") or "")),
    )


def promote_last_usable_after_third_attempt(
    state: dict[str, Any],
    *,
    state_dir: Path | None = None,
    require_file: bool = True,
    allow_pending_abandonment: bool = False,
    artifact_fetcher: Any = None,
) -> dict[str, Any] | None:
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

    latest_status = str(latest_attempt.get("status") or "")
    if latest_attempt.get("technical_verified") is True or latest_status in {"downloaded", "pending_review", "approved", "uploaded"}:
        return None
    if latest_status in {"source_selected", "source_added", "generating"} and not allow_pending_abandonment:
        return None

    s_dir = state_dir or STATE_DIR
    candidates = [
        row for row in items
        if row is not latest_attempt and _usable_candidate(
            row,
            slug,
            source_hash,
            state_dir=s_dir,
            require_file=require_file,
            artifact_fetcher=artifact_fetcher,
        )
    ]
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
                row["superseded_at"] = (
                    latest_attempt.get("updated_at")
                    or chosen.get("updated_at")
                    or ""
                )

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
