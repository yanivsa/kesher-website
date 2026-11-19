"""One source-bound GH-only media recovery canary using the *existing* engine.

READ-ONLY toward NotebookLM and YouTube. A completed, retained video task is
retrieved exactly once, never regenerated or uploaded. The trusted GH-only
ledger must have a genuine approved revision matching this workflow and no
inflight owner commands. All QA evidence is ephemeral in a GitHub artifact,
never misrepresented as a public video or an editorial approval.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from .github import GitHub
from .github_only_live_activation import _reviewed_run
from .github_only_live_inventory import (
    HISTORICAL_TASKS, NOTEBOOK, _provider_json, _rows, inspect_live_inventory,
)
from .github_only_owner_store import GitHubOnlyLedgerStore, REPOSITORY
from .identity import canonical_json
from .state import StateConflict, StateInvalid

SOURCE_SLOT = "2026-11-11"
SOURCE_SLUG = "gratitude-relationship-genuine-thank-you"
SOURCE_SHA256 = "d4921756c12061359fca7cefea175387b534735d1af841a59e46a392edcc8c5f"
ORIGINAL_ITEM_ID = "video-20261113-003733-d4921756c1"
NOTEBOOK_TASK_ID = "63b37426-9fd2-49e3-a2ce-a412fc347484"
WORKFLOW_REF = REPOSITORY + "/.github/workflows/kesher-media-worker.yml@refs/heads/main"
MAX_MEDIA_BYTES = 1024 * 1024 * 1024
_HASH = re.compile(r"[a-f0-9]{64}")


def validate_ledger(github, *, expected_main: str, repo: str, event: str,
                    workflow_ref: str, job: str):
    if (repo != REPOSITORY or event != "workflow_dispatch"
            or workflow_ref != WORKFLOW_REF or job != "github_only_canary"
            or not isinstance(expected_main, str)
            or re.fullmatch(r"[0-9a-f]{40}", expected_main) is None):
        raise StateInvalid("GHONLY_CANARY_EXACT_WORKFLOW_AND_SHA_REQUIRED")
    store = GitHubOnlyLedgerStore(github)
    snap = store.load(reviewed_main_sha=expected_main)
    ledger = snap.document
    live = ledger.get("protected_live") or {}
    if (ledger.get("activation") != "PROTECTED_VERIFIED"
            or ledger.get("inventory_complete") is not True
            or ledger.get("owner") != "github-only"
            or ledger.get("reviewed_main_sha") != expected_main
            or ledger.get("commands") != {}
            or live.get("single_writer") != "github-only"
            or live.get("media_qa_required") is not True
            or live.get("source_publication_authorized") is not False
            or not isinstance(live.get("approved_review_run"), str)
            or not _HASH.fullmatch(str(live.get("inventory_sha256", "")))):
        raise StateInvalid("GHONLY_CANARY_PROTECTED_OWNER_REQUIRED")
    _reviewed_run(github, live["approved_review_run"],
                  ledger["migration_basis"].get("approved_live_main",
                  ledger["protected_live"].get("approved_live_main",
                  ledger.get("initial_protected_main_sha", ""))) or expected_main)
    reviews = live.get("code_revision_reviews") or []
    if reviews:
        latest = reviews[-1]
        if (not isinstance(latest, dict)
                or latest.get("reviewed_main") != expected_main):
            raise StateInvalid("GHONLY_CANARY_REVISION_REVIEW_STALE")
        _reviewed_run(github, latest["approved_review_run"], expected_main)
    return snap


def exact_provider_task(*, command=_provider_json):
    if NOTEBOOK_TASK_ID not in HISTORICAL_TASKS:
        raise StateInvalid("GHONLY_CANARY_UNRECONCILED_TASK_ID")
    videos = _rows(command([
        "artifact", "list", "--type", "video", "--notebook", NOTEBOOK,
    ]), "artifacts")
    matches = [row for row in videos
               if NOTEBOOK_TASK_ID in (row.get("id"), row.get("task_id"),
                                       row.get("artifact_id"))]
    if len(matches) != 1:
        raise StateInvalid("GHONLY_CANARY_EXACT_TASK_NOT_UNIQUE")
    row = matches[0]
    if str(row.get("status", row.get("state"))).lower() != "completed":
        raise StateInvalid("GHONLY_CANARY_ORIGINAL_TASK_NOT_COMPLETED")
    return row


def original_media_qa(path: Path, *, core=None):
    from scripts import kesher_daily_pipeline as engine
    core = core or engine
    if (not path.is_file() or path.is_symlink()
            or not 1024 < path.stat().st_size <= MAX_MEDIA_BYTES):
        raise StateInvalid("GHONLY_CANARY_MEDIA_MISSING_OR_OVERSIZED")
    if path.suffix.lower() != ".mp4":
        raise StateInvalid("GHONLY_CANARY_MEDIA_NOT_MP4")
    media = core.ffprobe(path)
    if (media.get("width", 0) < 960 or media.get("height", 0) < 540
            or media["width"] <= media["height"]
            or media.get("duration", 0) < 60 or media.get("duration", 0) > 1800
            or not media.get("audio_codec") or not media.get("codec")):
        raise StateInvalid("GHONLY_CANARY_TECHNICAL_MEDIA_REJECTED")
    # Pitch is only a machine heuristic. Unknown pitch or passing one pitch
    # threshold does NOT attest a woman's voice or replace human listening.
    pitch = core.estimate_voice_pitch(path)
    media_sha = core.sha256_file(path)
    if not _HASH.fullmatch(media_sha):
        raise StateInvalid("GHONLY_CANARY_MEDIA_HASH_INVALID")
    if pitch is None or pitch < core.FEMALE_PITCH_MIN_HZ:
        label = "VOICE_QA_HOLD"
    else:
        label = "TECHNICAL_ACCEPTED_EDITORIAL_HOLD"
    return {"qa_status": label,
            "raw_mp4_sha256": media_sha,
            "media": media,
            "pitch_hz": round(pitch, 2) if pitch is not None else None,
            "source_slug": SOURCE_SLUG,
            "source_sha256": SOURCE_SHA256,
            "notebook_task_id": NOTEBOOK_TASK_ID,
            "original_item_id": ORIGINAL_ITEM_ID,
            "original_provider_output": True,
            "owner_visual_review_approved": False,
            "owner_audio_review_approved": False,
            "youtube_upload_authorized": False,
            "provider_generation_authorized": False}


def run_canary(github, *, expected_main: str, report_dir: Path):
    from scripts import kesher_daily_pipeline as core
    # Admission before reading provider secrets. All external operations below
    # are authenticated LIST/GET or DOWNLOAD; never an API create/generate.
    validate_ledger(
        github, expected_main=expected_main,
        repo=os.environ.get("GITHUB_REPOSITORY", ""),
        event=os.environ.get("GITHUB_EVENT_NAME", ""),
        workflow_ref=os.environ.get("GITHUB_WORKFLOW_REF", ""),
        job=os.environ.get("GITHUB_JOB", ""),
    )
    source = core.article_by_slug(SOURCE_SLUG)
    if (source.get("slug") != SOURCE_SLUG
            or source.get("date") != SOURCE_SLOT
            or source.get("content_sha256") != SOURCE_SHA256):
        raise StateInvalid("GHONLY_CANARY_AUTHORITATIVE_SOURCE_CHANGED")
    read = inspect_live_inventory()
    if (read.get("no_active_notebooklm_tasks") is not True
            or read.get("youtube_scan_complete") is not True
            or read.get("provider_mutations") is not False):
        raise StateInvalid("GHONLY_CANARY_EXTERNAL_TASK_INVENTORY_UNSAFE")
    exact_provider_task()
    report_dir.mkdir(parents=True, exist_ok=True)
    media_path = report_dir / "original-notebooklm-long.mp4"
    args = [
        "notebooklm", "download", "video", str(media_path),
        "--notebook", NOTEBOOK, "--artifact", NOTEBOOK_TASK_ID, "--force",
    ]
    # Never invoke a second generation; do not copy original auth to logs.
    result = subprocess.run(
        args, capture_output=True, text=True,
        check=False, timeout=900,
    )
    if result.returncode:
        raise StateInvalid("GHONLY_CANARY_EXACT_PROVIDER_DOWNLOAD_FAILED")
    qa = original_media_qa(media_path, core=core)
    qa["github_main_sha"] = expected_main
    qa["notebook_id"] = NOTEBOOK
    report = report_dir / "qa.json"
    report.write_text(canonical_json(qa) + "\n", encoding="utf-8")
    # Prevent accidental public exposure of media bytes. GitHub keeps QA text
    # only; private video download is erased before artifact capture.
    media_path.unlink()
    print("KESHER_GHONLY_MEDIA_CANARY " + canonical_json(qa))
    return qa


def main():
    if (os.environ.get("GITHUB_SHA") != os.environ.get("REVIEWED_REVISION")
            or os.environ.get("GITHUB_REF") != "refs/heads/main"):
        print("GHONLY_CANARY_IMMUTABLE_MAIN_REQUIRED", file=sys.stderr)
        return 2
    try:
        run_canary(
            GitHub(os.environ.get("GH_TOKEN", "")),
            expected_main=os.environ["GITHUB_SHA"],
            report_dir=Path(os.environ.get("KESHER_CANARY_OUTPUT", "/tmp/kesher-ghonly-qa")),
        )
        return 0
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.TimeoutExpired):
        print("GHONLY_MEDIA_CANARY_QA_HOLD_OR_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
