"""Protected GitHub-only LIVE authority transition, no provider dispatch.

The preflight must independently observe GitHub drain plus *complete, live*
NotebookLM/YouTube reads BEFORE a GitHub environment approval is requested.
After a real protected reviewer approves, re-read the same external sources,
check GitHub's actual review record, and atomically transition the existing
immutable GitHub-only ledger by dual-ref main+automation-state CAS.

This DOES NOT run a media worker or upload a video. LIVE publication requires
a separately attested and journaled sole worker and exact media QA.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import sys

from .github import GitHub, GitHubError, _unique_object
from .github_only_owner_store import PATH, REF, REPOSITORY, _blob_sha
from .github_owner_readiness import inventory
from .handover_github import UPDATE_REFS
from .github_only_live_inventory import inspect_live_inventory
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

WORKFLOW_REF = REPOSITORY + "/.github/workflows/kesher-controller-liveness.yml@refs/heads/main"
_RUN = re.compile(r"[1-9][0-9]*:[1-9][0-9]*")
_EPOCH = re.compile(r"[A-Za-z0-9_-]{1,128}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _loaded_owner(github, expected_main):
    require_sha(expected_main, 40)
    api = "/repos/" + REPOSITORY
    current_main = github.request("GET", api + "/git/ref/heads/main")["object"]["sha"]
    if current_main != expected_main:
        raise StateConflict("GHONLY_LIVE_MAIN_MOVED")
    old_ref = github.request("GET", api + "/git/ref/heads/" + REF)["object"]["sha"]
    require_sha(old_ref, 40)
    commit = github.request("GET", api + "/git/commits/" + old_ref)
    if commit.get("sha") != old_ref or not isinstance(commit.get("tree"), dict):
        raise StateInvalid("GHONLY_LIVE_STATE_COMMIT_UNTRUSTED")
    tree = commit["tree"]["sha"]
    require_sha(tree, 40)
    payload = github.request("GET", api + "/contents/" + PATH + "?ref=" + old_ref)
    if (not isinstance(payload, dict) or payload.get("encoding") != "base64"
            or not isinstance(payload.get("content"), str)):
        raise StateInvalid("GHONLY_LIVE_LEDGER_ENCODING_INVALID")
    raw = base64.b64decode("".join(payload["content"].split()), validate=True)
    if (not 0 < len(raw) < 1_000_000
            or _blob_sha(raw) != payload.get("sha")):
        raise StateInvalid("GHONLY_LIVE_LEDGER_BLOB_UNTRUSTED")
    doc = json.loads(raw, object_pairs_hook=_unique_object)
    if (not isinstance(doc, dict) or doc.get("schema_version") != 1
            or doc.get("owner") != "github-only"
            or not isinstance(doc.get("commands"), dict)
            or not isinstance(doc.get("migration_basis"), dict)):
        raise StateInvalid("GHONLY_LIVE_LEDGER_SCHEMA_INVALID")
    return old_ref, tree, doc


def _reviewed_run(github, reviewer_run):
    if not isinstance(reviewer_run, str) or not _RUN.fullmatch(reviewer_run):
        raise StateInvalid("GHONLY_LIVE_GENUINE_RUN_REQUIRED")
    run_id = reviewer_run.split(":")[0]
    api = "/repos/" + REPOSITORY
    run = github.request("GET", api + "/actions/runs/" + run_id)
    if (str(run.get("id")) != run_id
            or run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != "main"):
        raise StateInvalid("GHONLY_LIVE_RUN_NOT_TRUSTED")
    reviews = github.request("GET", api + "/actions/runs/" + run_id + "/approvals")
    if not isinstance(reviews, list) or not any(
        isinstance(row, dict)
        and row.get("state", "").lower() == "approved"
        and (row.get("user") or {}).get("login") == "yanivsa"
        and any(x.get("name") == "kesher-cutover"
                for x in (row.get("environments") or []))
        for row in reviews
    ):
        raise StateInvalid("GHONLY_LIVE_HUMAN_ENV_REVIEW_NOT_PROVEN")
    return reviewer_run


def _preflight(github, *, expected_main, epoch, report):
    if not isinstance(epoch, str) or _EPOCH.fullmatch(epoch) is None:
        raise StateInvalid("GHONLY_LIVE_EPOCH_INVALID")
    if (not isinstance(report, dict)
            or report.get("notebooklm_authenticated") is not True
            or report.get("youtube_authenticated") is not True
            or report.get("no_active_notebooklm_tasks") is not True
            or report.get("youtube_scan_complete") is not True
            or report.get("known_historical_task_count") != 8
            or report.get("provider_mutations") is not False):
        raise StateInvalid("GHONLY_LIVE_EXTERNAL_INVENTORY_INCOMPLETE")

    check = inventory(
        github, expected_main=expected_main, workflow_ref=WORKFLOW_REF,
        event_name="workflow_dispatch", repo=REPOSITORY,
    )
    if (check.get("status") != "READY_FOR_REVIEWED_MIGRATION_ONLY"
            or check.get("pending") != []
            or check.get("provider_dispatch") is not False
            or check.get("production_activated") is not False):
        raise StateInvalid("GHONLY_LIVE_COMPETING_GITHUB_AUTHORITY")
    old_ref, tree, doc = _loaded_owner(github, expected_main)
    if (doc.get("activation") != "PREPARED_NOT_LIVE"
            or doc.get("inventory_complete") is not False
            or doc.get("commands") != {}
            or doc.get("epoch") != epoch
            or not re.fullmatch(r"[0-9a-f]{40}", str(doc.get("reviewed_main_sha", "")))
            or doc["migration_basis"].get("legacy_blob_sha") != check.get("legacy_blob_sha")
            or doc["migration_basis"].get("legacy_cycle") != check.get("legacy_cycle")
            or not _RUN.fullmatch(str(doc["migration_basis"].get("approved_review_run", "")))):
        raise StateInvalid("GHONLY_LIVE_PREPARED_BASIS_NOT_SAFE")
    # No LIVE mutation or approval request can proceed if a second epoch
    # or command journal already exists. Keep PREPARE untouched until CAS.
    return old_ref, tree, doc, digest(report)


def preflight(github, *, expected_main, epoch, report=None):
    require_sha(expected_main, 40)
    actual = inspect_live_inventory() if report is None else report
    _, _, _, inventory_sha = _preflight(
        github, expected_main=expected_main, epoch=epoch, report=actual,
    )
    return {"status": "READY_FOR_PROTECTED_LIVE_REVIEW", "inventory_sha256": inventory_sha,
            "provider_dispatch": False, "production_activated": False}


def activate(github, *, expected_main, epoch, reviewer_run,
             reviewed_inventory_sha256, report=None):
    require_sha(expected_main, 40)
    if (not isinstance(reviewed_inventory_sha256, str)
            or _SHA256.fullmatch(reviewed_inventory_sha256) is None):
        raise StateInvalid("GHONLY_LIVE_INVENTORY_REVIEW_DIGEST_REQUIRED")
    # Genuine environment approval must be checked by independent GitHub API,
    # not inferred from an input, local flag or owner Issue comment.
    _reviewed_run(github, reviewer_run)
    actual = inspect_live_inventory() if report is None else report
    old_ref, tree, prepared, fresh_inventory_sha = _preflight(
        github, expected_main=expected_main, epoch=epoch, report=actual,
    )
    if fresh_inventory_sha != reviewed_inventory_sha256:
        raise StateConflict("GHONLY_LIVE_PROVIDER_INVENTORY_CHANGED_SINCE_REVIEW")
    state = copy.deepcopy(prepared)
    state["activation"] = "PROTECTED_VERIFIED"
    state["inventory_complete"] = True
    state["reviewed_main_sha"] = expected_main
    state["protected_live"] = {
        "approved_review_run": reviewer_run,
        "inventory_sha256": fresh_inventory_sha,
        "legacy_blob_sha": prepared["migration_basis"]["legacy_blob_sha"],
        "source_publication_authorized": False,
        "media_qa_required": True,
        "single_writer": "github-only",
    }
    raw = (canonical_json(state) + "\n").encode("utf-8")
    blob_sha = _blob_sha(raw)
    api = "/repos/" + REPOSITORY
    if github.request("GET", api + "/git/ref/heads/main")["object"]["sha"] != expected_main:
        raise StateConflict("GHONLY_LIVE_MAIN_MOVED_BEFORE_CAS")
    written = github.request("POST", api + "/git/blobs", {
        "content": base64.b64encode(raw).decode("ascii"), "encoding": "base64",
    })
    if written.get("sha") != blob_sha:
        raise StateInvalid("GHONLY_LIVE_WRITTEN_BLOB_MISMATCH")
    new_tree = github.request("POST", api + "/git/trees", {
        "base_tree": tree,
        "tree": [{"path": PATH, "mode": "100644", "type": "blob", "sha": blob_sha}],
    })["sha"]
    require_sha(new_tree, 40)
    candidate = github.request("POST", api + "/git/commits", {
        "message": "state: protected Kesher GH-only LIVE owner",
        "tree": new_tree, "parents": [old_ref],
    })["sha"]
    require_sha(candidate, 40)
    ident = github.request("GET", api)
    if ident.get("full_name") != REPOSITORY or not ident.get("node_id"):
        raise StateInvalid("GHONLY_LIVE_REPOSITORY_UNTRUSTED")
    receipt = digest({
        "before": old_ref, "after": candidate,
        "main": expected_main, "run": reviewer_run,
        "inventory": fresh_inventory_sha,
    })
    mutation = {
        "repositoryId": ident["node_id"], "clientMutationId": receipt,
        "refUpdates": [
            {"name": "refs/heads/main", "beforeOid": expected_main,
             "afterOid": expected_main, "force": False},
            {"name": "refs/heads/" + REF, "beforeOid": old_ref,
             "afterOid": candidate, "force": False},
        ],
    }
    result = github.request("POST", "/graphql", {
        "query": UPDATE_REFS, "variables": {"input": mutation},
    })
    if result.get("errors"):
        raise StateConflict("GHONLY_LIVE_REF_CAS_REJECTED")
    if result.get("data", {}).get("updateRefs", {}).get("clientMutationId") != receipt:
        raise GitHubError(None, "Live acknowledgment unknown; read-only reconcile", uncertain=True)
    current_ref, _, current = _loaded_owner(github, expected_main)
    if current_ref != candidate or current != state:
        raise StateConflict("GHONLY_LIVE_POST_CAS_READBACK_MISMATCH")
    return {
        "status": "PROTECTED_VERIFIED",
        "production_activated": True,
        "provider_dispatch": False,
        "media_qa_required": True,
        "ledger_ref": candidate,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preflight", "activate"))
    parser.add_argument("--reviewed-revision", required=True)
    parser.add_argument("--epoch", required=True)
    parser.add_argument("--inventory-sha256", default="")
    args = parser.parse_args(argv)
    expected_job = "github_owner_live_inventory" if args.stage == "preflight" else "github_owner_live"
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
            or os.environ.get("GITHUB_JOB") != expected_job
            or os.environ.get("GITHUB_SHA") != args.reviewed_revision):
        print("GHONLY_LIVE_EXACT_JOB_REQUIRED", file=sys.stderr)
        return 2
    try:
        github = GitHub(os.environ.get("GH_TOKEN") or "")
        if args.stage == "preflight":
            result = preflight(github, expected_main=args.reviewed_revision, epoch=args.epoch)
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write("inventory_sha256=" + result["inventory_sha256"] + "\n")
        else:
            result = activate(
                github, expected_main=args.reviewed_revision,
                epoch=args.epoch,
                reviewer_run=os.environ.get("GITHUB_RUN_ID", "")
                             + ":" + os.environ.get("GITHUB_RUN_ATTEMPT", ""),
                reviewed_inventory_sha256=args.inventory_sha256,
            )
        print("KESHER_GHONLY_PROTECTED_LIVE " + canonical_json(result))
        return 0
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        print("KESHER_GHONLY_PROTECTED_LIVE_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
