#!/usr/bin/env python3
"""Upload a technically verified Kesher video even when Jules quality review rejects it.

Jules review remains advisory. YouTube/public-processing is the only publication gate.
"""

from __future__ import annotations

import re

import kesher_daily_pipeline as pipeline


ELIGIBLE_STATUSES = {"pending_review", "approved", "rejected", "uploading"}


def _candidate(state: dict) -> dict | None:
    candidates = [
        item
        for item in state.get("items", [])
        if item.get("technical_verified") is True
        and item.get("status") in ELIGIBLE_STATUSES
        and item.get("uploaded") is not True
        and not item.get("youtube_verification")
    ]
    if not candidates:
        return None
    if len(candidates) != 1:
        raise pipeline.PipelineError(f"Expected exactly one technically verified upload candidate, found {len(candidates)}")
    return candidates[0]


def _verify_immutable_evidence(item: dict) -> None:
    required = ("final_mp4", "final_sha256", "manifest_path", "manifest_sha256", "youtube_metadata")
    missing = [field for field in required if not item.get(field)]
    if missing:
        raise pipeline.PipelineError(f"Upload candidate is missing required fields: {', '.join(missing)}")

    video_path = pipeline.STATE_DIR / item["final_mp4"]
    manifest_path = pipeline.STATE_DIR / item["manifest_path"]
    if not video_path.is_file() or not manifest_path.is_file():
        raise pipeline.PipelineError("Technically verified upload candidate is missing MP4 or manifest")
    if pipeline.sha256_file(video_path) != item["final_sha256"]:
        raise pipeline.PipelineError("Final MP4 hash mismatch")
    if pipeline.sha256_file(manifest_path) != item["manifest_sha256"]:
        raise pipeline.PipelineError("Manifest hash mismatch")

    metadata = item["youtube_metadata"]
    title = str(metadata.get("title", ""))
    description = str(metadata.get("description", ""))
    if not title or not description:
        raise pipeline.PipelineError("YouTube metadata is incomplete")
    pipeline.require_hebrew(title, "YouTube title")
    pipeline.require_hebrew(description, "YouTube description", allow_url=True)
    if pipeline.SITE_URL not in description:
        raise pipeline.PipelineError("YouTube description is missing the Kesher URL")
    tags = metadata.get("tags") or []
    if not isinstance(tags, list):
        raise pipeline.PipelineError("YouTube tags must be a list")
    for tag in tags:
        pipeline.require_hebrew(str(tag), "YouTube tag")


def upload_advisory() -> int:
    state = pipeline.load_state()
    item = _candidate(state)
    if item is None:
        print("NO_TECHNICALLY_VERIFIED_UPLOAD")
        return 0

    _verify_immutable_evidence(item)
    review_summary = {
        gate: item.get(f"{gate}_review_status", "pending")
        for gate in ("visual", "semantic", "metadata")
    }
    print(
        "JULES_ADVISORY_ONLY "
        + " ".join(f"{gate}={status}" for gate, status in review_summary.items())
    )

    token = pipeline.youtube_access_token()
    pipeline.verify_authenticated_channel(token)
    video_path = pipeline.STATE_DIR / item["final_mp4"]

    session_uri = item.get("upload_session_uri")
    if not session_uri:
        session_uri = pipeline.start_resumable_upload(state, item, token, video_path)
        offset = 0
    else:
        offset = pipeline.resume_offset(session_uri, token, video_path.stat().st_size)

    video_id = pipeline.upload_bytes(session_uri, token, video_path, offset)
    item["youtube_id"] = video_id
    item["youtube_url"] = f"https://youtu.be/{video_id}"
    item["upload_response_at"] = pipeline.utc_now()
    pipeline.save_state(state)

    verification = pipeline.verify_public_upload(item, token)
    item["youtube_verification"] = verification
    item["uploaded"] = True
    item["status"] = "uploaded"
    item["uploaded_at"] = pipeline.utc_now()
    item["jules_review_advisory"] = review_summary
    item.pop("upload_session_uri", None)
    pipeline.save_state(state)
    print(f"UPLOADED_ADVISORY item={item['id']} url={item['youtube_url']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(upload_advisory())
    except (pipeline.PipelineError, OSError, ValueError) as exc:
        message = re.sub(r"https://accounts\.google\.com/\S+", "Google sign-in redirect", str(exc))
        print(f"YOUTUBE_ADVISORY_UPLOAD_BLOCKED {message}", file=__import__("sys").stderr)
        raise SystemExit(1)
