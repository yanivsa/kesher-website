#!/usr/bin/env python3
"""Promote the last usable same-source video after the third fresh attempt fails.

This is a narrow fail-safe for the production Video Overview pipeline. It never
creates a new source, generation or upload. It only promotes an existing local
artifact for the same authoritative source identity when three fresh attempts
have already been consumed and no public upload exists.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any

STATE_DIR = Path(os.environ.get("KESHER_STATE_DIR", ".kesher-video-state"))
STATE_FILE = STATE_DIR / "state.json"
FINAL_ATTEMPT = 3
FALLBACK_PROMOTION_ENABLED = False


def is_fallback_promotion_enabled() -> bool:
    """Production-safe gate for fallback promotion. Default: DISABLED."""
    env_val = os.environ.get("KESHER_ENABLE_FALLBACK_PROMOTION", "").strip().lower()
    if env_val in {"1", "true", "yes"}:
        return True
    return FALLBACK_PROMOTION_ENABLED


def _slug(item: dict[str, Any]) -> str:
    source = item.get("source") or {}
    return str(source.get("slug") or source.get("id") or "").strip()


def _source_hash(item: dict[str, Any]) -> str:
    return str((item.get("source") or {}).get("content_sha256") or "").strip()


class ArtifactArchiveFetcher:
    """Locates and extracts exact candidate media from zip archives."""

    def __init__(self, archives: list[Path] | Path | None = None) -> None:
        if isinstance(archives, Path):
            self.archives = [archives]
        elif isinstance(archives, list):
            self.archives = [Path(p) for p in archives]
        else:
            self.archives = []

    def restore_media(self, item: dict[str, Any], target_dir: Path) -> bool:
        final_name = str(item.get("final_mp4") or "").strip()
        expected_sha = str(item.get("final_sha256") or "").strip().lower()
        if not final_name or len(expected_sha) != 64 or not all(c in "0123456789abcdef" for c in expected_sha):
            return False

        archives_to_check = list(self.archives)
        env_archive = os.environ.get("KESHER_ARTIFACT_ARCHIVE", "").strip()
        if env_archive:
            archives_to_check.append(Path(env_archive))

        for archive_path in archives_to_check:
            if not archive_path.is_file():
                continue
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    names = zf.namelist()
                    if "state.json" in names:
                        try:
                            state_data = json.loads(zf.read("state.json").decode("utf-8"))
                            items = [row for row in state_data.get("items", []) if isinstance(row, dict)]
                            item_matches = [row for row in items if str(row.get("id") or "") == str(item.get("id") or "")]
                            if not item_matches:
                                continue
                            matched = item_matches[0]
                            if str(matched.get("final_sha256") or "").lower() != expected_sha:
                                continue
                        except Exception:
                            continue

                    if final_name not in names:
                        continue

                    data = zf.read(final_name)
                    actual_sha = hashlib.sha256(data).hexdigest()
                    if actual_sha != expected_sha:
                        continue

                    target_dir.mkdir(parents=True, exist_ok=True)
                    (target_dir / final_name).write_bytes(data)
                    return True
            except Exception:
                continue

        return False


def _positive_voice_only_rejection(item: dict[str, Any], state_dir: Path | None = None) -> bool:
    """Positively prove from structured evidence that the ONLY technical failure is the female voice pitch criterion."""
    s_dir = state_dir or STATE_DIR
    manifest_data = item.get("manifest")
    if not isinstance(manifest_data, dict):
        manifest_name = str(item.get("manifest_path") or "").strip()
        if not manifest_name:
            return False
        manifest_path = s_dir / manifest_name
        if not manifest_path.is_file():
            return False
        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return False

    if not isinstance(manifest_data, dict):
        return False

    if str(manifest_data.get("item_id") or "") != str(item.get("id") or ""):
        return False
    manifest_source = manifest_data.get("source") or {}
    item_source = item.get("source") or {}
    if (
        str(manifest_source.get("slug") or "") != _slug(item)
        or str(manifest_source.get("content_sha256") or "") != _source_hash(item)
    ):
        return False
    final_name = str(item.get("final_mp4") or "").strip()
    final_sha = str(item.get("final_sha256") or "").strip().lower()
    if not final_name or len(final_sha) != 64 or not all(c in "0123456789abcdef" for c in final_sha):
        return False
    if str(manifest_data.get("final_mp4") or "") != final_name:
        return False
    if str(manifest_data.get("final_sha256") or "").lower() != final_sha:
        return False

    reasons = manifest_data.get("rejection_reasons")
    if not isinstance(reasons, list) or not reasons:
        return False

    failure_signature = str(item.get("failure_signature") or manifest_data.get("failure_signature") or "")
    if failure_signature != "wrong_narrator_gender":
        return False

    forbidden_tokens = (
        "corrupt", "audio_track_corrupt", "error", "failed", "codec", "stream",
        "missing", "invalid", "duration", "aspect", "dimension", "width", "height",
        "metadata", "title", "description", "tag", "timeline", "overlay",
    )
    voice_tokens = ("קול גברי", "קול נשי", "גובה צליל", "female voice", "male voice", "pitch")

    for reason in reasons:
        r_str = str(reason).lower()
        if any(tok in r_str for tok in forbidden_tokens):
            return False
        if not any(vt in r_str for vt in voice_tokens):
            return False

    media = item.get("media") or manifest_data.get("media")
    if not isinstance(media, dict):
        return False
    codec = str(media.get("codec") or "").lower()
    if codec not in {"h264", "avc1"}:
        return False
    audio_codec = str(media.get("audio_codec") or "").lower()
    if not audio_codec:
        return False

    try:
        width = int(media.get("width") or 0)
        height = int(media.get("height") or 0)
        duration = float(media.get("duration") or 0)
    except (TypeError, ValueError):
        return False

    if width != 1280 or height != 720:
        if width <= height or not (1.70 <= (width / height if height else 0) <= 1.82):
            return False

    if not (90.0 <= duration <= 183.5):
        return False

    content_duration = float(
        item.get("content_duration_seconds")
        or manifest_data.get("content_duration_seconds")
        or duration
    )
    if abs(duration - content_duration) > 0.15:
        return False

    sig_overlay = item.get("signature_overlay") if "signature_overlay" in item else manifest_data.get("signature_overlay")
    if sig_overlay is not True:
        return False
    sig_sha = str(
        item.get("signature_asset_sha256")
        or item.get("signature_sha256")
        or manifest_data.get("signature_asset_sha256")
        or manifest_data.get("signature_sha256")
        or ""
    ).strip()
    if len(sig_sha) != 64:
        return False

    meta = item.get("youtube_metadata") or manifest_data.get("youtube_metadata")
    if not isinstance(meta, dict):
        return False
    if not meta.get("title") or not meta.get("description") or not meta.get("tags"):
        return False
    canon = str(item_source.get("canonical_url") or "")
    if canon and canon not in str(meta.get("description") or ""):
        return False

    raw_sha = str(item.get("raw_sha256") or manifest_data.get("raw_sha256") or "").strip()
    if len(raw_sha) != 64:
        return False
    visual_pipeline = str(item.get("visual_pipeline") or manifest_data.get("visual_pipeline") or "")
    if visual_pipeline != "remotion-v1-notebooklm-audio":
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
    expected_sha = str(item.get("final_sha256") or "").strip().lower()
    if not final_name or len(expected_sha) != 64 or not all(c in "0123456789abcdef" for c in expected_sha):
        return False

    final_path = s_dir / final_name
    if final_path.is_file() and final_path.stat().st_size >= 1024:
        actual_sha = hashlib.sha256(final_path.read_bytes()).hexdigest()
        if actual_sha == expected_sha:
            return True
        return False

    fetcher = artifact_fetcher or ArtifactArchiveFetcher()
    try:
        if callable(fetcher):
            success = fetcher(item, s_dir)
        elif hasattr(fetcher, "restore_media"):
            success = fetcher.restore_media(item, s_dir)
        else:
            success = False

        if success and final_path.is_file() and final_path.stat().st_size >= 1024:
            actual_sha = hashlib.sha256(final_path.read_bytes()).hexdigest()
            if actual_sha == expected_sha:
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
    if not is_fallback_promotion_enabled():
        return None

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

    s_dir = state_dir or STATE_DIR
    s_file = s_dir / "state.json"

    # CAS Verification: check against authoritative state
    if s_file.is_file():
        try:
            authoritative = json.loads(s_file.read_text(encoding="utf-8"))
            auth_items = [r for r in authoritative.get("items", []) if isinstance(r, dict)]
            completed = [
                r for r in auth_items
                if _slug(r) == slug and _source_hash(r) == source_hash
                and (
                    r.get("uploaded") is True
                    or (r.get("technical_verified") is True and r.get("status") in {"pending_review", "approved", "uploaded"})
                )
                and r.get("status") not in {"superseded", "rejected"}
            ]
            if completed:
                # Prior completion exists in authoritative state! Fallback CAS loses!
                return None
            if authoritative.get("fallback_winner"):
                fw = authoritative["fallback_winner"]
                if fw.get("slug") == slug and fw.get("content_sha256") == source_hash and fw.get("fallback_committed") is True:
                    matching = [r for r in items if r.get("id") == fw.get("winner_item_id")]
                    return matching[0] if matching else None
        except Exception:
            pass

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

    rev = int(state.get("state_revision", 1)) + 1
    state["state_revision"] = rev
    state["fallback_winner"] = {
        "slug": slug,
        "content_sha256": source_hash,
        "winner_item_id": chosen["id"],
        "fallback_committed": True,
        "revision": rev,
        "committed_at": latest_attempt.get("updated_at") or chosen.get("updated_at") or "",
    }

    for row in items:
        if row is chosen:
            continue
        if _slug(row) == slug and _source_hash(row) == source_hash and row.get("uploaded") is not True:
            row["status"] = "superseded"
            row["superseded_reason"] = "final_attempt_fallback_selected_other_existing_artifact"
            row["upload_eligible"] = False
            row["superseded_at"] = (
                latest_attempt.get("updated_at")
                or chosen.get("updated_at")
                or ""
            )

    chosen["technical_verified"] = True
    chosen["status"] = "pending_review"
    chosen["upload_eligible"] = True
    chosen["final_attempt_fallback"] = True
    chosen["voice_gate_waived_after_attempt"] = FINAL_ATTEMPT
    chosen["fallback_reason"] = "third_attempt_failed_use_last_usable_same_source_artifact"
    chosen["updated_at"] = latest_attempt.get("updated_at") or chosen.get("updated_at")

    if s_file.is_file():
        try:
            import fcntl
            lock_path = s_file.with_name(s_file.name + ".lock")
            with open(lock_path, "a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    authoritative = json.loads(s_file.read_text(encoding="utf-8"))
                    authoritative["state_revision"] = rev
                    authoritative["fallback_winner"] = copy.deepcopy(state["fallback_winner"])
                    auth_items = authoritative.get("items", [])
                    for a_row in auth_items:
                        if a_row.get("id") == chosen["id"]:
                            a_row.update(chosen)
                        elif _slug(a_row) == slug and _source_hash(a_row) == source_hash and a_row.get("uploaded") is not True:
                            a_row["status"] = "superseded"
                            a_row["superseded_reason"] = "final_attempt_fallback_selected_other_existing_artifact"
                            a_row["upload_eligible"] = False
                    temp_file = s_file.with_suffix(".json.tmp")
                    with open(temp_file, "w", encoding="utf-8") as handle:
                        handle.write(json.dumps(authoritative, ensure_ascii=False, indent=2) + "\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    temp_file.replace(s_file)
                finally:
                    try:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
        except Exception:
            pass

    return chosen


def main() -> int:
    if not is_fallback_promotion_enabled():
        print("FALLBACK_WINNER_AUTHORITY_UNAVAILABLE")
        return 0
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
