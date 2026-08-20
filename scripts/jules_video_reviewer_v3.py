#!/usr/bin/env python3
"""Strict advisory Jules review adapter for Kesher Pipeline v3.

The mature session/evidence parser remains in ``jules_video_reviewer`` for this
migration. This adapter replaces only the publication semantics: Jules records
an honest quality decision, while the independent technical gate owns upload.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from . import jules_video_reviewer as legacy
except ImportError:
    import jules_video_reviewer as legacy


FINAL_MARKER = legacy.FINAL_MARKER
MAX_REVIEW_SESSION_ATTEMPTS = legacy.MAX_REVIEW_SESSION_ATTEMPTS
REMOTION_POLICY_VERSION = legacy.REMOTION_POLICY_VERSION
REVIEW_SCHEMA_VERSION = legacy.REVIEW_SCHEMA_VERSION
REVIEW_FRAME_COUNT = legacy.REVIEW_FRAME_COUNT
PROJECT_DIR = Path(__file__).resolve().parents[1]
REMOTION_POLICY_PATH = PROJECT_DIR / ".github" / "prompts" / "jules-remotion-video-upgrade.md"
ReviewError = legacy.ReviewError
review_json_example = legacy.review_json_example
validate_structured_contract = legacy.validate_structured_contract
validate_decision = legacy.validate_decision
parse_decision = legacy.parse_decision


def load_remotion_policy() -> str:
    try:
        policy = REMOTION_POLICY_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ReviewError(f"Durable Remotion policy is unreadable: {REMOTION_POLICY_PATH}") from exc
    if not policy:
        raise ReviewError("Durable Remotion policy is empty")
    versions = re.findall(r"(?m)^Policy-Version:\s*(\d+)\s*$", policy)
    if versions != [str(REMOTION_POLICY_VERSION)]:
        raise ReviewError(
            f"Durable Remotion policy version mismatch: expected {REMOTION_POLICY_VERSION}, found {versions}"
        )
    if "Jules review is strict and advisory" not in policy:
        raise ReviewError("Durable Remotion policy no longer declares strict advisory Jules review")
    if "MUST NOT block upload" not in policy:
        raise ReviewError("Durable Remotion policy no longer protects technical publication authority")
    return policy


def build_prompt(evidence_root: str, item: dict[str, Any], hashes: dict[str, Any]) -> str:
    policy = load_remotion_policy()
    example_json = json.dumps(review_json_example(item["id"]), ensure_ascii=False, indent=2)
    return f"""Perform one strict READ-ONLY Kesher Video Overview quality review. Do not edit the repository, create a branch/commit/changeSet/PR, generate another video, contact NotebookLM, or contact YouTube.

The exact secret-free evidence is already checked out in `{evidence_root}` on this session's starting branch. Do not use `gh`, GitHub APIs, network downloads, or files outside that directory. If the directory or a required file is missing, report the blocker and do not invent evidence.

Expected item: `{item['id']}`.
Expected evidence hashes (must recompute locally with sha256sum and match exactly):
{json.dumps(hashes, ensure_ascii=False, indent=2)}

The following durable repository policy is authoritative for this review. Apply it as written; do not replace it with remembered or generic Remotion guidance.

--- BEGIN DURABLE REMOTION POLICY ---
{policy}
--- END DURABLE REMOTION POLICY ---

Open `{evidence_root}/state.json` and locate the exact item. Open and visually inspect EACH of its {REVIEW_FRAME_COUNT} `frame_paths` plus `visual_review_path` using the available image-viewing capability. Read the COMPLETE Hebrew transcript, COMPLETE Hebrew source file, manifest, source title/topic, YouTube title, description and every tag.

IMPORTANT: Jules is the STRICT ADVISORY reviewer for this exact MP4. Return an honest `approved` or `rejected` quality decision and concrete findings. Your result MUST NOT block upload: publication permission belongs exclusively to the independent technical gate. Do not soften a finding to keep the schedule moving, and do not describe your decision as upload authorization.

Machine contract: return `schema_version={REVIEW_SCHEMA_VERSION}` and `policy_version={REMOTION_POLICY_VERSION}` exactly. `decision` MUST be `approved` only when visual, semantic and metadata statuses are all approved; otherwise it MUST be `rejected`. A rejected decision MUST contain at least one concrete `blocking_issues` object with `gate`, stable uppercase `code`, and factual Hebrew `message`; here `blocking_issues` means quality defects for later repair, not publication blockers. An approved decision MUST have an empty `blocking_issues` list. `recommendations` are optional non-blocking Hebrew improvements.

Apply these strict review dimensions:
1. Technical is already machine-verified. Independently confirm the manifest identifies a 16:9 H.264 video lasting 90-180 seconds. Recompute every checked-out file hash. The MP4 is deliberately excluded; confirm its expected final SHA-256 is identical in state.json, the manifest and the expected hashes above.
2. Visual creative review: inspect all {REVIEW_FRAME_COUNT} sampled frames and evaluate compliance with the durable Source-Video-First Remotion policy above. You MUST reject slide/card-like compositions, text-heavy panels, timeline or diagram layouts, repeated identical frames, or generic illustrative visuals instead of a continuous natural visual story.
3. Semantic: compare all {REVIEW_FRAME_COUNT} frames and the complete narration transcript with the complete source file. Reject topic mismatch, unsupported claims, or a missing central subject. Small stylistic paraphrases or natural spoken-language variations are acceptable when the original meaning is preserved.
4. Metadata: compare title, description and every tag with source and transcript. Reject unsupported metadata, default/generic metadata, English, or missing `https://kesher.saharoni.com`. Separately confirm that `generation_prompt` explicitly requests a female Hebrew voice (`השתמש בקול של אישה ישראלית, חם, טבעי, ברור ומקצועי לכל אורך הקריינות.`).

You may complete the review only after doing the actual file reads and image inspection. Notes must be factual Hebrew. Finish with `{FINAL_MARKER}` on its own line followed by exactly one JSON object and no Markdown fence. The JSON must contain exactly {REVIEW_FRAME_COUNT} frame hashes and exactly {REVIEW_FRAME_COUNT} frame observations. Use this shape:
{example_json}
"""


def main() -> int:
    legacy.REMOTION_POLICY_PATH = REMOTION_POLICY_PATH
    legacy.load_remotion_policy = load_remotion_policy
    legacy.build_prompt = build_prompt
    return legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())
