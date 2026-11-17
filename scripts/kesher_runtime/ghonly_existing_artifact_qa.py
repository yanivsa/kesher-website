"""Ephemeral technical inspection of existing source-bound NotebookLM tasks.

NO provider creation, no YouTube upload, no article mutation, no state write.
This runs only in the EXISTING manual preflight, after provider authentication.
FFprobe and source identifiers are NOT evidence of female voice, visual QA,
source body equality, rights, publisher ownership or production activation.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = "yanivsa/kesher-website"
WORKFLOW = REPO + "/.github/workflows/kesher-daily-video.yml@refs/heads/main"
NOTEBOOK = "e101e7d7-5305-45b3-a611-21a5475ceb63"

# Original task identities and article body SHA recovered from archived artifacts
# 14177014196 / 14181168035. No new tasks may be spawned.
TARGETS = (
    ("2026-11-11", "gratitude-relationship-genuine-thank-you", "long",
     "d4921756c12061359fca7cefea175387b534735d1af841a59e46a392edcc8c5f",
     "63b37426-9fd2-49e3-a2ce-a412fc347484"),
    ("2026-11-11", "gratitude-relationship-genuine-thank-you", "short",
     "d4921756c12061359fca7cefea175387b534735d1af841a59e46a392edcc8c5f",
     "12c218a9-9912-4f65-869b-3517cacb57a6"),
    ("2026-11-12", "invisible-support-couples-responsive-help", "long",
     "c612b113ea3939a9ca60beb2e88d87e7b639c563e5469ae72715b05cf54a3ea6",
     "488e8ec8-264f-48c3-88ff-b17df3f9b1d6"),
    ("2026-11-12", "invisible-support-couples-responsive-help", "short",
     "c612b113ea3939a9ca60beb2e88d87e7b639c563e5469ae72715b05cf54a3ea6",
     "1495a541-b862-4d28-b855-28f1a1eef03d"),
)


class QAReadOnlyBlocked(ValueError):
    pass


def _safe_command(args, *, timeout):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, check=False, timeout=timeout)
    if result.returncode != 0:
        # NEVER print raw stderr or stdout; provider output might contain secrets.
        raise QAReadOnlyBlocked("READONLY_PROVIDER_CALL_FAILED")
    return result.stdout


def _catalog():
    raw = _safe_command(["notebooklm", "artifact", "list", "--type", "video",
                         "--notebook", NOTEBOOK, "--json"], timeout=150)
    payload = json.loads(raw)
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("artifacts", payload.get("items"))
    else:
        rows = None
    if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows):
        raise QAReadOnlyBlocked("INVALID_PROVIDER_CATALOG")
    ids = [x.get("id") for x in rows]
    if len(rows) != len(set(ids)) or not all(isinstance(v, str) and v for v in ids):
        raise QAReadOnlyBlocked("AMBIGUOUS_PROVIDER_IDS")
    return {x["id"]: x for x in rows}


def _inspect(path: Path):
    output = _safe_command(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height:format=duration",
         "-of", "json", str(path)], timeout=90)
    data = json.loads(output)
    streams = data.get("streams")
    if not isinstance(streams, list):
        raise QAReadOnlyBlocked("INVALID_FFPROBE")
    video = [x for x in streams if x.get("codec_type") == "video"]
    audio = [x for x in streams if x.get("codec_type") == "audio"]
    if len(video) != 1 or not audio:
        raise QAReadOnlyBlocked("MISSING_VIDEO_OR_AUDIO_STREAM")
    w, h = video[0].get("width"), video[0].get("height")
    duration = float(data.get("format", {}).get("duration", 0))
    if type(w) is not int or type(h) is not int or not 0 < duration < 3600:
        raise QAReadOnlyBlocked("INVALID_VIDEO_GEOMETRY_OR_DURATION")
    return {"width": w, "height": h, "duration_seconds": round(duration, 3),
            "video_codec": video[0].get("codec_name"),
            "audio_codec": audio[0].get("codec_name")}


def audit_one(item, catalog, temporary_root: Path):
    date, slug, kind, source_sha, artifact_id = item
    record = catalog.get(artifact_id)
    if not record or record.get("status", record.get("state")) != "completed":
        raise QAReadOnlyBlocked("EXACT_PROVIDER_TASK_NOT_COMPLETED")
    path = temporary_root / (artifact_id + ".mp4")
    # Download the exact ALREADY-COMPLETED artifact; never POST/generate.
    try:
        _safe_command(["notebooklm", "download", "video", str(path),
                       "--notebook", NOTEBOOK, "--artifact", artifact_id,
                       "--force"], timeout=420)
        if not path.is_file() or path.stat().st_size < 1024:
            raise QAReadOnlyBlocked("EXACT_VIDEO_BYTES_MISSING")
        media = _inspect(path)
        with path.open("rb") as fd:
            sha = hashlib.file_digest(fd, "sha256").hexdigest()
        # Exact geometry contract: Short 9:16; Long 16:9.
        correct_ratio = (media["width"] * 16 == media["height"] * 9
                         if kind == "short" else
                         media["width"] * 9 == media["height"] * 16)
        return {
            "date": date, "slug": slug, "kind": kind,
            "persisted_source_sha256": source_sha,
            "existing_provider_artifact_id": artifact_id,
            "original_task_reused": True,
            "downloaded_sha256": sha,
            "bytes": path.stat().st_size,
            "technical_media": media,
            "technical_aspect_ratio_pass": correct_ratio,
            "source_body_verified": False,
            "female_hebrew_voice_verified": False,
            "visual_qa_verified": False,
            "licensing_verified": False,
            "generation_authorized": False,
            "upload_authorized": False,
            "production_activated": False,
        }
    finally:
        path.unlink(missing_ok=True)


def main():
    if (
        os.environ.get("GITHUB_REPOSITORY") != REPO
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("GITHUB_WORKFLOW_REF") != WORKFLOW
        or os.environ.get("KESHER_RECOVERY_READ_ONLY") != "true"
    ):
        print("GHONLY_EXISTING_ARTIFACT_QA_UNTRUSTED_INVOCATION", file=sys.stderr)
        return 2
    try:
        catalog = _catalog()
        with tempfile.TemporaryDirectory(prefix="kesher-ghonly-artifacts-") as root:
            for item in TARGETS:
                result = audit_one(item, catalog, Path(root))
                print("GHONLY_EXISTING_ARTIFACT_QA " +
                      json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        return 0
    except (QAReadOnlyBlocked, json.JSONDecodeError, OSError, ValueError,
            subprocess.TimeoutExpired):
        print("GHONLY_EXISTING_ARTIFACT_QA_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
