#!/usr/bin/env python3
"""Create a minimal, secret-free evidence tree that Jules can read from Git."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

try:
    from kesher_daily_pipeline import REVIEW_FRAME_COUNT
except ImportError:
    from scripts.kesher_daily_pipeline import REVIEW_FRAME_COUNT


class EvidenceError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_source(state_dir: Path, relative: str) -> Path:
    candidate = (state_dir / relative).resolve()
    root = state_dir.resolve()
    if candidate == root or root not in candidate.parents:
        raise EvidenceError(f"Evidence path escapes state directory: {relative}")
    if not candidate.is_file():
        raise EvidenceError(f"Evidence file is missing: {relative}")
    return candidate


def copy_verified(
    state_dir: Path,
    output_dir: Path,
    relative: str,
    expected_sha256: str,
) -> None:
    source = safe_source(state_dir, relative)
    actual = sha256_file(source)
    if actual != expected_sha256:
        raise EvidenceError(f"Evidence hash mismatch: {relative}")
    destination = output_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def prepare(state_dir: Path, output_dir: Path) -> dict[str, Any]:
    state_path = state_dir / "state.json"
    if not state_path.is_file():
        raise EvidenceError("state.json is missing")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    pending = [item for item in state.get("items", []) if item.get("status") == "pending_review"]
    if len(pending) != 1:
        raise EvidenceError(f"Expected one pending item, found {len(pending)}")
    item = pending[0]
    if item.get("technical_verified") is not True:
        raise EvidenceError("Pending item is not technically verified")

    scalar_files = [
        ("manifest_path", "manifest_sha256"),
        ("transcript_path", "transcript_sha256"),
        ("source_path", "source_file_sha256"),
        ("visual_review_path", "visual_review_sha256"),
    ]
    if item.get("motion_plan_path") and item.get("motion_plan_sha256"):
        scalar_files.append(("motion_plan_path", "motion_plan_sha256"))

    for path_key, hash_key in scalar_files:
        relative = item.get(path_key)
        expected = item.get(hash_key)
        if not isinstance(relative, str) or not isinstance(expected, str):
            raise EvidenceError(f"Missing evidence identity: {path_key}")
        copy_verified(state_dir, output_dir, relative, expected)

    frame_paths = item.get("frame_paths") or []
    frame_hashes = item.get("frame_sha256") or {}
    if len(frame_paths) != REVIEW_FRAME_COUNT or set(frame_paths) != set(frame_hashes):
        raise EvidenceError(f"Exactly {REVIEW_FRAME_COUNT} identified frames are required")
    for relative in frame_paths:
        copy_verified(state_dir, output_dir, relative, frame_hashes[relative])

    sanitized = copy.deepcopy(item)
    for key in ("raw_mp4", "final_mp4"):
        sanitized.pop(key, None)
    evidence_state = {
        "version": state.get("version"),
        "items": [sanitized],
        "evidence_scope": "frames-transcript-source-manifest-only",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "state.json").write_text(
        json.dumps(evidence_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return sanitized


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    item = prepare(args.state_dir, args.output_dir)
    print(f"JULES_EVIDENCE_PREPARED item={item['id']} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
