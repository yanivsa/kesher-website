#!/usr/bin/env python3
"""Offline counterexamples for the media contract at 55563f42.

Run from any directory with PYTHONDONTWRITEBYTECODE=1 python3 <this-file>.
Exit 1 means one or more required invariants are violated; that is the expected
baseline result, not a provider failure. No network, provider, renderer, upload,
production-state write, or credential access is permitted by this probe.
"""
from __future__ import annotations

import json
import socket
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts import kesher_daily_pipeline as core
from scripts import kesher_e2e_delivery_guard as guard
from scripts import kesher_short_pipeline_v4 as short


def main() -> int:
    checks = []

    def record(identifier, invariant, actual, required):
        try:
            assert actual == required, invariant
        except AssertionError:
            passed = False
        else:
            passed = True
        checks.append({"id": identifier, "required_contract": invariant,
                       "required": required, "actual": actual, "passed": passed})

    with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
        item = {
            "youtube_id": "fixture-id",
            "youtube_metadata": {
                "title": "כותרת בעברית",
                "description": "תיאור\nhttps://kesher.saharoni.com/blog/exact\nhttps://kesher.saharoni.com",
            },
            "source": {"slug": "exact", "content_sha256": "a" * 64,
                       "canonical_url": "https://kesher.saharoni.com/blog/exact"},
        }
        row = {
            "snippet": {"channelId": core.YOUTUBE_CHANNEL_ID,
                        "title": "כותרת בעברית",
                        "description": "תיאור שונה\nhttps://kesher.saharoni.com/blog/wrong"},
            "status": {"privacyStatus": "public"},
            "processingDetails": {"processingStatus": "succeeded"},
        }
        with patch.object(core, "youtube_get", return_value={"items": [row]}):
            try:
                accepted = bool(core.verify_public_upload(item, "fixture-token", 0))
            except core.PipelineError:
                accepted = False
        record("M-GAP-01", "Remote metadata must contain the exact article URL and standalone site URL",
               accepted, False)

        with TemporaryDirectory() as temp:
            state_dir = Path(temp)
            segment = state_dir / "id-signature-segment.mp4"
            segment.write_bytes(b"old signature bytes")
            with patch.object(core, "STATE_DIR", state_dir), patch.object(
                short.subprocess, "run", side_effect=AssertionError("external process forbidden")
            ):
                try:
                    accepted = short.extract_signature_video_segment(
                        state_dir / "missing-current-final.mp4", "id"
                    )[0] == segment
                except (core.PipelineError, OSError, AssertionError):
                    accepted = False
            record("M-GAP-02", "Signature evidence must bind to the current final MP4, not merely item ID",
                   accepted, False)

            for name, contents in (
                ("sig.svg", "<svg/>"), ("id-short-final.mp4", "old final"),
                ("id-short-motion-plan.json", "{}"), ("id-short-remotion-props.json", "{}"),
            ):
                (state_dir / name).write_text(contents)
            candidate = {
                "id": "id", "enhancement_status": "enhancement_complete",
                "motion_plan_path": "id-short-motion-plan.json", "motion_plan_sha256": "wrong",
                "remotion_props_path": "id-short-remotion-props.json", "remotion_props_sha256": "wrong",
                "provider_video_format": "short",
            }
            with patch.object(core, "STATE_DIR", state_dir), patch.object(
                short, "prepare_signature_asset", return_value="sig.svg"
            ), patch.object(core, "ffprobe", return_value={"width": 1080, "height": 1920, "duration": 50}), patch.object(
                short, "build_motion_plan", side_effect=RuntimeError("cache was correctly rejected")
            ), patch.object(short.subprocess, "run", side_effect=AssertionError("external process forbidden")):
                try:
                    accepted = short.render_remotion_video(state_dir / "raw.mp4", candidate).name == "id-short-final.mp4"
                except (core.PipelineError, RuntimeError, OSError):
                    accepted = False
            record("M-GAP-03", "Short render cache must reject mismatched motion-plan and props hashes",
                   accepted, False)

        stale = {"signature_verified": True, "signature_fullscreen": True,
                 "signature_video_sha256": "old-hash", "signature_duration_seconds": 3,
                 "short_duration_seconds": 50, "media": {"duration": 53}}
        record("M-GAP-04", "Appended signature outro must not satisfy in-content overlay contract",
               guard._signature_verified(stale), False)
        shared = dict(stale, type="article_short", source_mode="direct-short",
                      visual_pipeline=short.VISUAL_PIPELINE, shared_provider_identity=True,
                      adopted_from_long_item_id="long-id", provider_video_format="explainer",
                      fresh_generation_attempt=1)
        record("M-GAP-05", "Canonical Short labels cannot override contradictory provider provenance",
               guard._short_origin_verified(shared), False)
        with patch.object(core, "estimate_voice_pitch", return_value=None):
            accepted = core.validate_female_voice(Path("fixture"), {"fresh_generation_attempt": 1})[0]
        record("M-GAP-06", "Inconclusive voice analysis must not be reported as positive voice verification",
               accepted, False)

    print(json.dumps({"network": "forbidden", "checks": checks,
                      "violations": sum(not check["passed"] for check in checks)},
                     ensure_ascii=False, indent=2))
    return int(any(not check["passed"] for check in checks))


if __name__ == "__main__":
    raise SystemExit(main())
