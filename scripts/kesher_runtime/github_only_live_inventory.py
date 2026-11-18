"""Authenticated, read-only NotebookLM/YouTube reconciliation before GH-only LIVE.

Never calls provider creation, retries a task, authorizes video/publication,
writes state, or returns a fabricated owner proof. Both scans are recomputed
after the protected human review; a prior green job is not an inventory fence.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess

from .github_only_owner_store import REPOSITORY
from .identity import canonical_json
from .state import StateInvalid

NOTEBOOK = "e101e7d7-5305-45b3-a611-21a5475ceb63"
HISTORICAL_TASKS = (
    "077ede84-dd9c-4a07-b2b6-56acdad27be7",
    "5b742ce5-3bd4-421a-aaea-02641f3e10d0",
    "63b37426-9fd2-49e3-a2ce-a412fc347484",
    "12c218a9-9912-4f65-869b-3517cacb57a6",
    "488e8ec8-264f-48c3-88ff-b17df3f9b1d6",
    "1495a541-b862-4d28-b855-28f1a1eef03d",
    "57b334e9-772d-4c58-837b-bc8fe24c4df2",
    "7e7cabb9-7d29-43a7-8e52-a0932f6a4452",
)
_TASK = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}")
_TERMINAL = frozenset(("completed", "rejected", "failed", "cancelled"))
_PENDING = frozenset(("generating", "running", "queued", "pending", "in_progress", "waiting", "processing"))


def _provider_json(args, *, runner=subprocess.run):
    try:
        result = runner(
            ["notebooklm", *args, "--json"], capture_output=True,
            text=True, check=False, timeout=150,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise StateInvalid("GHONLY_PROVIDER_READ_FAILED") from exc
    if result.returncode:
        # Never print authenticated provider stderr/stdout: may contain tokens.
        raise StateInvalid("GHONLY_PROVIDER_READ_NONZERO")
    try:
        return json.loads(result.stdout)
    except (TypeError, ValueError) as exc:
        raise StateInvalid("GHONLY_PROVIDER_RESPONSE_NOT_JSON") from exc


def _rows(value, key):
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = value.get(key, value.get("items"))
    else:
        rows = None
    if not isinstance(rows, list) or not all(isinstance(x, dict) for x in rows):
        raise StateInvalid("GHONLY_PROVIDER_INVENTORY_INCOMPLETE")
    return rows


def inspect_provider_catalog(*, command=_provider_json):
    auth = command(["auth", "check", "--test"])
    if (not isinstance(auth, dict) or auth.get("status") != "ok"
            or (auth.get("checks") or {}).get("token_fetch") is not True):
        raise StateInvalid("GHONLY_NOTEBOOKLM_AUTH_UNVERIFIED")
    videos = _rows(command(["artifact", "list", "--type", "video", "--notebook", NOTEBOOK]), "artifacts")
    sources = _rows(command(["source", "list", "--notebook", NOTEBOOK]), "sources")
    if len(videos) < len(HISTORICAL_TASKS) or not sources:
        raise StateInvalid("GHONLY_NOTEBOOKLM_SOURCE_OR_VIDEO_CATALOG_INCOMPLETE")

    identifiers = {}
    for row in videos:
        keys = {row.get(k) for k in ("id", "task_id", "artifact_id")
                if isinstance(row.get(k), str) and row.get(k)}
        if not keys:
            raise StateInvalid("GHONLY_NOTEBOOKLM_VIDEO_WITHOUT_ID")
        status = row.get("status", row.get("state"))
        if not isinstance(status, str):
            raise StateInvalid("GHONLY_NOTEBOOKLM_UNTRUSTED_STATUS")
        status = status.lower().strip()
        if status in _PENDING:
            # Unknown active work can produce duplicate media on a second wake.
            raise StateInvalid("GHONLY_NOTEBOOKLM_ACTIVE_EXTERNAL_TASK")
        if status not in _TERMINAL:
            raise StateInvalid("GHONLY_NOTEBOOKLM_UNKNOWN_EXTERNAL_TASK_STATUS")
        for key in keys:
            if key in identifiers and identifiers[key] is not row:
                raise StateInvalid("GHONLY_NOTEBOOKLM_DUPLICATE_VIDEO_ID")
            identifiers[key] = row

    statuses = []
    for task_id in HISTORICAL_TASKS:
        row = identifiers.get(task_id)
        if row is None:
            raise StateInvalid("GHONLY_NOTEBOOKLM_HISTORICAL_TASK_NOT_FOUND")
        observed = str(row.get("status", row.get("state"))).lower().strip()
        if observed not in _TERMINAL:
            raise StateInvalid("GHONLY_NOTEBOOKLM_HISTORICAL_TASK_UNSETTLED")
        statuses.append([task_id, observed])

    source_ids = [row.get("id", row.get("source_id")) for row in sources]
    if not all(isinstance(k, str) and k for k in source_ids) or len(set(source_ids)) != len(source_ids):
        raise StateInvalid("GHONLY_NOTEBOOKLM_SOURCE_CATALOG_UNTRUSTED")

    # Stable fingerprint reflects ALL status+ID rows. Any change between
    # preflight and approved activation causes a fresh-read disagreement.
    video_fingerprint = hashlib.sha256(canonical_json(sorted(
        [[sorted({x.get(k) for k in ("id", "task_id", "artifact_id")
                  if isinstance(x.get(k), str) and x.get(k)}),
          str(x.get("status", x.get("state"))).lower().strip()] for x in videos]
    )).encode()).hexdigest()
    return {
        "notebooklm_authenticated": True,
        "sources_count": len(sources),
        "videos_count": len(videos),
        "known_historical_task_count": len(statuses),
        "historical_tasks_sha256": hashlib.sha256(canonical_json(statuses).encode()).hexdigest(),
        "video_catalog_sha256": video_fingerprint,
        "no_active_notebooklm_tasks": True,
    }


def inspect_live_inventory(*, command=_provider_json, channel=None):
    from .ghonly_youtube_gap_audit import audit_channel
    from scripts.kesher_owner_vantage_short import youtube_client

    catalog = inspect_provider_catalog(command=command)
    yt = audit_channel((channel or youtube_client)())
    if (yt.get("channel_verified") is not True
            or yt.get("youtube_scan_complete") is not True
            or yt.get("unresolved_video_fingerprints")
            or not isinstance(yt.get("items"), list)):
        raise StateInvalid("GHONLY_YOUTUBE_INVENTORY_UNTRUSTED")
    # Do not claim permission to generate or upload; the audit explicitly
    # keeps media source/voice/visual/editorial approvals separate.
    items = yt["items"]
    if len(items) != 7 or not all(
        isinstance(row, dict) and row.get("youtube_scan_complete") is True
        and row.get("new_provider_generation_authorized") is False
        and row.get("upload_authorized") is False
        for row in items
    ):
        raise StateInvalid("GHONLY_YOUTUBE_SOURCE_AUDIT_INCOMPLETE")
    if any(row.get("slug") == "couple-conversation-stuck-pursue-withdraw-cycle"
           and (row.get("exact_match_count") or row.get("legacy_candidate_count"))
           for row in items):
        raise StateInvalid("GHONLY_CURRENT_SOURCE_HAS_EXISTING_VIDEO_CANDIDATE")
    public_counts = [[row["date"], row["slug"], row["exact_match_count"],
                      row["legacy_candidate_count"]] for row in items]
    return {
        **catalog,
        "youtube_authenticated": True,
        "youtube_scan_complete": True,
        "youtube_uploads_count": yt.get("uploaded_playlist_count"),
        "youtube_resolved_count": yt.get("resolved_video_count"),
        "youtube_confirmed_deleted_count": yt.get("confirmed_deleted_tombstones"),
        "youtube_targets_sha256": hashlib.sha256(canonical_json(public_counts).encode()).hexdigest(),
        "provider_mutations": False,
        "video_publication_authorized": False,
    }


def main():
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_WORKFLOW_REF") != REPOSITORY
              + "/.github/workflows/kesher-controller-liveness.yml@refs/heads/main"
            or os.environ.get("GITHUB_JOB") not in
            {"github_owner_live_inventory", "github_owner_live"}):
        print("GHONLY_LIVE_INVENTORY_WRONG_INVOCATION")
        return 2
    try:
        report = inspect_live_inventory()
        print("KESHER_GHONLY_PROVIDER_READ_ONLY " + canonical_json(report))
        return 0
    except (RuntimeError, OSError, ValueError, TypeError, KeyError):
        print("GHONLY_LIVE_PROVIDER_INVENTORY_BLOCKED")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
