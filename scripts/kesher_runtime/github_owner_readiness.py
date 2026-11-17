"""Read-only audit for owner-approved GitHub-only controller architecture.

Never mutates GitHub, invokes a provider, certifies native fencing or authorizes
a production cutover. The owner has approved *design* of the alternative, not
fabrication of missing task/provider evidence.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys

from .github import GitHub
from .state import StateInvalid
from .worker_entry import REPOSITORY

OLD_CONTROLLER_ID = 337960554
ACTIVE = frozenset(("queued", "in_progress", "waiting", "pending", "requested"))
TRACKED = ("kesher-daily-video.yml", "kesher-short-v4.yml",
           "kesher-article-generation.yml", "kesher-article-worker.yml",
           "kesher-media-worker.yml")
STATUS = {"disabled_manually", "disabled_inactivity"}
MAX_PER_PAGE = 100


def inventory(github, *, expected_main, workflow_ref, event_name, repo):
    if (repo != REPOSITORY or event_name != "workflow_dispatch"
            or workflow_ref != REPOSITORY
            + "/.github/workflows/kesher-production-cutover.yml@refs/heads/main"
            or not re.fullmatch(r"[0-9a-f]{40}", expected_main)):
        raise StateInvalid("GITHUB_OWNER_PROBE_EXACT_WORKFLOW_REQUIRED")
    api = "/repos/" + REPOSITORY
    main = github.request("GET", api + "/git/ref/heads/main")["object"]["sha"]
    if main != expected_main:
        raise StateInvalid("GITHUB_OWNER_PROBE_STALE_MAIN")
    workflow = github.request("GET", api + f"/actions/workflows/{OLD_CONTROLLER_ID}")
    if workflow.get("id") != OLD_CONTROLLER_ID:
        raise StateInvalid("GITHUB_OWNER_PROBE_LEGACY_IDENTITY_UNKNOWN")
    # Filter server-side for every active status: all-run pagination would
    # conceal old queued identities beneath hundreds of finished runs.
    affected = []
    for target in (OLD_CONTROLLER_ID, *TRACKED):
        for status in sorted(ACTIVE):
            response = github.request(
                "GET", api + f"/actions/workflows/{target}/runs?status={status}&per_page=100"
            )
            rows = response.get("workflow_runs")
            total = response.get("total_count", len(rows) if isinstance(rows, list) else None)
            if (not isinstance(rows, list) or type(total) is not int
                    or total != len(rows) or len(rows) >= MAX_PER_PAGE):
                raise StateInvalid("GITHUB_OWNER_PROBE_INCOMPLETE_ACTIVE_RUN_INVENTORY")
            for row in rows:
                # A stale or unexpected status-filter response is not proof of quiet.
                if row.get("status") != status or type(row.get("id")) is not int:
                    raise StateInvalid("GITHUB_OWNER_PROBE_UNTRUSTED_ACTIVE_RUN_RECORD")
                affected.append({"workflow": target, "run": row["id"], "status": status})
    stateblob = github.request("GET", api + "/contents/.kesher-controller/state.json?ref=automation-state")
    if (stateblob.get("encoding") != "base64" or not isinstance(stateblob.get("content"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", str(stateblob.get("sha", "")))):
        raise StateInvalid("GITHUB_OWNER_PROBE_STATE_PROVENANCE_REQUIRED")
    raw = base64.b64decode("".join(stateblob["content"].split()), validate=True)
    if len(raw) > 5_000_000:
        raise StateInvalid("GITHUB_OWNER_PROBE_STATE_OVERSIZED")
    snapshot = json.loads(raw)
    if snapshot.get("schema_version") != 5 or "handover" in snapshot or "github_exclusion" in snapshot:
        raise StateInvalid("GITHUB_OWNER_PROBE_UNEXPECTED_STATE_OWNER")
    if workflow.get("state") not in STATUS:
        affected.append({"workflow": OLD_CONTROLLER_ID, "run": None, "status": "OLD_CONTROLLER_NOT_DISABLED"})
    return {
        "mode": "github_only_readiness",
        "approved_design_only": True,
        "main_sha": main,
        "legacy_blob_sha": stateblob["sha"],
        "legacy_cycle": snapshot.get("cycle"),
        "pending": affected,
        "status": "BLOCKED_EXISTING_OWNER_OR_TASK" if affected else "READY_FOR_REVIEWED_MIGRATION_ONLY",
        "production_activated": False,
        "provider_dispatch": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-revision", required=True)
    args = parser.parse_args(argv)
    try:
        if os.environ.get("GITHUB_SHA") != args.reviewed_revision:
            raise StateInvalid("GITHUB_OWNER_PROBE_CHECKOUT_MISMATCH")
        result = inventory(
            GitHub(os.environ.get("GH_TOKEN", "")),
            expected_main=args.reviewed_revision,
            workflow_ref=os.environ.get("GITHUB_WORKFLOW_REF", ""),
            event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
        )
        print("KESHER_GITHUB_OWNER_PREFLIGHT " + json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "READY_FOR_REVIEWED_MIGRATION_ONLY" else 2
    except (ValueError, KeyError, TypeError, OSError, RuntimeError):
        print("KESHER_GITHUB_OWNER_PREFLIGHT_BLOCKED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
