#!/usr/bin/env python3
"""Repair missing immutable evidence for one exact technically verified Video Overview.

This never creates a new NotebookLM task or source binding. It revalidates the
existing authoritative provider MP4 under the same durable item identity.
"""

from __future__ import annotations

import argparse

from scripts import kesher_daily_pipeline as pipeline

IMMUTABLE_EVIDENCE_FIELDS = (
    "transcript_path",
    "transcript_sha256",
    "source_path",
    "source_file_sha256",
    "manifest_path",
    "manifest_sha256",
    "visual_review_path",
    "visual_review_sha256",
    "frame_paths",
    "frame_sha256",
)


def evidence_complete(item: dict) -> bool:
    return all(item.get(field) for field in IMMUTABLE_EVIDENCE_FIELDS)


def repair_pending_evidence(item_id: str) -> int:
    state = pipeline.load_state()
    matches = [item for item in state["items"] if item.get("id") == item_id]
    if len(matches) != 1:
        raise pipeline.PipelineError("Evidence repair item was not found uniquely")
    item = matches[0]
    if item.get("status") != "pending_review" or item.get("technical_verified") is not True:
        raise pipeline.PipelineError("Evidence repair requires one technically verified pending-review item")
    if item.get("uploaded") is True or item.get("youtube_verification"):
        raise pipeline.PipelineError("Evidence repair refuses an already published item")
    if evidence_complete(item):
        raise pipeline.PipelineError("Immutable evidence is already complete; repair is not applicable")

    required_identity = ("notebook_id", "source_id", "task_id", "artifact_id", "source", "youtube_metadata")
    if any(not item.get(field) for field in required_identity):
        raise pipeline.PipelineError("Provider identity is incomplete; refusing evidence repair")

    raw_name = str(item.get("raw_mp4") or "").strip()
    raw_path = pipeline.STATE_DIR / raw_name
    if not raw_name or not raw_path.is_file():
        raise pipeline.PipelineError("Authoritative NotebookLM MP4 is missing; refusing evidence repair")
    expected_raw_sha = str(item.get("raw_sha256") or "").strip()
    if not expected_raw_sha or pipeline.sha256_file(raw_path) != expected_raw_sha:
        raise pipeline.PipelineError("Authoritative NotebookLM MP4 hash mismatch")

    item.setdefault("evidence_history", []).append(
        {
            "recorded_at": pipeline.utc_now(),
            "status": item.get("status"),
            "final_mp4": item.get("final_mp4"),
            "final_sha256": item.get("final_sha256"),
            "manifest_path": item.get("manifest_path"),
            "manifest_sha256": item.get("manifest_sha256"),
            "visual_review_path": item.get("visual_review_path"),
            "visual_review_sha256": item.get("visual_review_sha256"),
            "frame_paths": item.get("frame_paths"),
            "frame_sha256": item.get("frame_sha256"),
            "review_notes": item.get("review_notes"),
            "reason": "immutable_evidence_repair",
        }
    )
    for field in IMMUTABLE_EVIDENCE_FIELDS:
        item.pop(field, None)
    item["status"] = "downloaded"
    item["technical_verified"] = False
    item["visual_review_status"] = "pending"
    item["semantic_review_status"] = "pending"
    item["metadata_review_status"] = "pending"
    item["review_notes"] = {"technical": "", "visual": "", "semantic": "", "metadata": ""}
    item["evidence_repair_started_at"] = pipeline.utc_now()
    pipeline.save_state(state)

    pipeline.validate_and_manifest(state, item, raw_path)
    print(f"VIDEO_EVIDENCE_REPAIRED item={item_id} status={item.get('status')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--item-id", required=True)
    args = parser.parse_args()
    return repair_pending_evidence(args.item_id)


if __name__ == "__main__":
    raise SystemExit(main())
