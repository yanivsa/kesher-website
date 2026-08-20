#!/usr/bin/env python3
"""Fail-closed guard immediately before the Kesher YouTube upload side effect."""

from __future__ import annotations

import json
import os
from pathlib import Path

try:
    from .kesher_automation_policy import load_policy
except ImportError:
    from kesher_automation_policy import load_policy


class UploadGuardError(RuntimeError):
    pass


def source_date(item: dict) -> str:
    source = item.get("source") or {}
    return str(
        item.get("israel_date")
        or source.get("date")
        or item.get("created_at")
        or item.get("updated_at")
        or "9999-12-31"
    )


def unresolved(item: dict) -> bool:
    return bool(
        isinstance(item, dict)
        and item.get("uploaded") is not True
        and item.get("status") in {
            "source_selected", "source_added", "generating", "downloaded",
            "pending_review", "approved", "rejected", "uploading",
        }
    )


def select_upload_candidate(state: dict) -> dict:
    candidates = sorted(
        [item for item in state.get("items") or [] if unresolved(item)],
        key=lambda item: (
            source_date(item),
            str(item.get("created_at") or ""),
            str(item.get("id") or ""),
        ),
    )
    if not candidates:
        raise UploadGuardError("No unresolved video item exists for upload")
    return candidates[0]


def validate_candidate(item: dict) -> None:
    policy = load_policy()
    video_policy = policy["video"]
    if (
        video_policy.get("review_gate") != "mandatory"
        or video_policy.get("jules_review_required") is not True
        or video_policy.get("upload_requires_approved_review") is not True
    ):
        raise UploadGuardError("Automation policy no longer requires mandatory Jules approval")

    if item.get("technical_verified") is not True:
        raise UploadGuardError("Upload candidate is not technically verified")
    if item.get("status") not in {"approved", "uploading"}:
        raise UploadGuardError(f"Upload candidate status is not approved: {item.get('status')}")

    statuses = [item.get(f"{gate}_review_status") for gate in ("visual", "semantic", "metadata")]
    if statuses != ["approved", "approved", "approved"]:
        raise UploadGuardError("Jules visual/semantic/metadata approval is incomplete")

    reviewer = item.get("reviewer") or {}
    if reviewer.get("type") != "jules" or not reviewer.get("session") or not item.get("reviewed_at"):
        raise UploadGuardError("Upload candidate has no authoritative Jules reviewer identity")

    final_sha = str(item.get("final_sha256") or "")
    approved_sha = str(item.get("review_approved_for_sha256") or "")
    if not final_sha or approved_sha != final_sha:
        raise UploadGuardError("Jules approval is not bound to the exact final MP4 SHA-256")

    required_hashes = (
        "manifest_sha256",
        "transcript_sha256",
        "source_file_sha256",
        "visual_review_sha256",
    )
    if any(not item.get(field) for field in required_hashes):
        raise UploadGuardError("Upload candidate is missing immutable review evidence hashes")
    frame_hashes = item.get("frame_sha256")
    if not isinstance(frame_hashes, dict) or not frame_hashes:
        raise UploadGuardError("Upload candidate is missing frame evidence hashes")

    source = item.get("source") or {}
    if not (source.get("slug") or source.get("id")) or not source.get("content_sha256"):
        raise UploadGuardError("Upload candidate source identity is incomplete")


def main() -> int:
    state_dir = Path(os.environ.get("KESHER_STATE_DIR", ".kesher-video-state"))
    state_path = state_dir / "state.json"
    if not state_path.is_file():
        raise UploadGuardError("Video state.json is missing")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or not isinstance(state.get("items"), list):
        raise UploadGuardError("Video state schema is invalid")
    item = select_upload_candidate(state)
    validate_candidate(item)
    print(
        "VIDEO_UPLOAD_GUARD_OK "
        f"item={item.get('id')} sha256={item.get('final_sha256')} "
        f"jules_session={(item.get('reviewer') or {}).get('session')}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (UploadGuardError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"VIDEO_UPLOAD_GUARD_BLOCKED {exc}")
        raise SystemExit(1)
