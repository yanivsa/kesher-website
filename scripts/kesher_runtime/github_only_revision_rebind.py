"""Protected revision roll-forward for the *existing* GitHub-only LIVE owner.

Never activates a new controller, resets commands, changes provider credentials,
dispatches a workflow, or authorizes publication. Both sides of the existing
kesher-cutover review get independent GitHub and provider inventories.
A genuine GitHub environment review and multi-ref CAS are mandatory.
"""
from __future__ import annotations

import argparse
import base64
import copy
import json
import os
import re
import sys

from .github import GitHub, GitHubError
from .github_only_live_activation import _loaded_owner, _reviewed_run, WORKFLOW_REF
from .github_only_live_inventory import inspect_live_inventory
from .github_owner_readiness import inventory
from .github_only_owner_store import REF, PATH, REPOSITORY, _blob_sha
from .handover_github import UPDATE_REFS
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

_RUN = re.compile(r"[1-9][0-9]*:[1-9][0-9]*")
_HASH = re.compile(r"[0-9a-f]{64}")


def _eligible(github, *, expected_main: str, epoch: str, report: dict):
    require_sha(expected_main, 40)
    if (not isinstance(epoch, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", epoch)
            or not isinstance(report, dict)
            or report.get("notebooklm_authenticated") is not True
            or report.get("youtube_authenticated") is not True
            or report.get("no_active_notebooklm_tasks") is not True
            or report.get("youtube_scan_complete") is not True
            or report.get("known_historical_task_count") != 8
            or report.get("provider_mutations") is not False):
        raise StateInvalid("GHONLY_REBIND_INVENTORY_NOT_AUTHENTICATED")
    check = inventory(
        github, expected_main=expected_main, workflow_ref=WORKFLOW_REF,
        event_name="workflow_dispatch", repo=REPOSITORY,
    )
    if (check.get("status") != "READY_FOR_REVIEWED_MIGRATION_ONLY"
            or check.get("pending") != []
            or check.get("provider_dispatch") is not False):
        raise StateInvalid("GHONLY_REBIND_COMPETING_OWNER_OR_RUN")
    old_ref, tree, ledger = _loaded_owner(github, expected_main)
    owner = ledger.get("protected_live")
    old_sha = ledger.get("reviewed_main_sha")
    if (ledger.get("schema_version") != 1
            or ledger.get("owner") != "github-only"
            or ledger.get("activation") != "PROTECTED_VERIFIED"
            or ledger.get("inventory_complete") is not True
            or ledger.get("epoch") != epoch
            or ledger.get("commands") != {}
            or not isinstance(owner, dict)
            or owner.get("single_writer") != "github-only"
            or owner.get("media_qa_required") is not True
            or owner.get("source_publication_authorized") is not False
            or not isinstance(owner.get("inventory_sha256"), str)
            or not _HASH.fullmatch(owner["inventory_sha256"])
            or owner.get("legacy_blob_sha")
                    != ledger.get("migration_basis", {}).get("legacy_blob_sha")
            or owner.get("legacy_blob_sha") != check.get("legacy_blob_sha")
            or not isinstance(old_sha, str)
            or not re.fullmatch(r"[a-f0-9]{40}", old_sha)
            or old_sha == expected_main):
        raise StateInvalid("GHONLY_REBIND_LIVE_OWNER_NOT_ELIGIBLE")
    initial = owner.get("approved_review_run")
    if not isinstance(initial, str) or not _RUN.fullmatch(initial):
        raise StateInvalid("GHONLY_REBIND_ORIGINAL_LIVE_REVIEW_MISSING")
    _reviewed_run(github, initial, old_sha)
    approvals = owner.get("code_revision_reviews", [])
    if (not isinstance(approvals, list) or len(approvals) > 64
            or any(not isinstance(x, dict) or "approved_review_run" not in x
                   for x in approvals)):
        raise StateInvalid("GHONLY_REBIND_HISTORY_INVALID")
    compare = github.request(
        "GET", "/repos/" + REPOSITORY + "/compare/" + old_sha + "..." + expected_main,
    )
    if (compare.get("status") != "ahead"
            or type(compare.get("ahead_by")) is not int
            or compare["ahead_by"] < 1
            or compare.get("behind_by") != 0
            or (compare.get("base_commit") or {}).get("sha") != old_sha
            or (compare.get("merge_base_commit") or {}).get("sha") != old_sha):
        raise StateInvalid("GHONLY_REBIND_NOT_DESCENDANT_OF_VERIFIED_MAIN")
    return old_ref, tree, ledger, digest(report)


def preflight(github, *, expected_main, epoch, report=None):
    read = inspect_live_inventory() if report is None else report
    _, _, old, fingerprint = _eligible(
        github, expected_main=expected_main, epoch=epoch, report=read,
    )
    return {"status": "READY_FOR_REVIEWED_REVISION_REBIND",
            "prior_main": old["reviewed_main_sha"], "new_main": expected_main,
            "inventory_sha256": fingerprint,
            "provider_dispatch": False, "publication_authorized": False}


def rebind(github, *, expected_main, epoch, reviewer_run,
           reviewed_inventory_sha256, report=None):
    require_sha(expected_main, 40)
    if not isinstance(reviewed_inventory_sha256, str) or not _HASH.fullmatch(
            reviewed_inventory_sha256):
        raise StateInvalid("GHONLY_REBIND_MISSING_INVENTORY_FINGERPRINT")
    _reviewed_run(github, reviewer_run, expected_main)
    read = inspect_live_inventory() if report is None else report
    old_ref, tree, previous, fingerprint = _eligible(
        github, expected_main=expected_main, epoch=epoch, report=read,
    )
    if fingerprint != reviewed_inventory_sha256:
        raise StateConflict("GHONLY_REBIND_PROVIDER_INVENTORY_CHANGED_AFTER_REVIEW")
    next_ledger = copy.deepcopy(previous)
    next_ledger["reviewed_main_sha"] = expected_main
    next_ledger["protected_live"].setdefault("code_revision_reviews", []).append({
        "previous_main": previous["reviewed_main_sha"],
        "reviewed_main": expected_main,
        "approved_review_run": reviewer_run,
        "inventory_sha256": fingerprint,
        "prior_ledger_ref": old_ref,
    })
    api = "/repos/" + REPOSITORY
    raw = (canonical_json(next_ledger) + "\n").encode("utf-8")
    blob = _blob_sha(raw)
    if github.request("GET", api + "/git/ref/heads/main")["object"]["sha"] != expected_main:
        raise StateConflict("GHONLY_REBIND_MAIN_CHANGED_BEFORE_CAS")
    created = github.request("POST", api + "/git/blobs", {
        "content": base64.b64encode(raw).decode("ascii"), "encoding": "base64",
    })
    if created.get("sha") != blob:
        raise StateInvalid("GHONLY_REBIND_BLOB_WRITE_CORRUPT")
    new_tree = github.request("POST", api + "/git/trees", {
        "base_tree": tree,
        "tree": [{"path": PATH, "mode": "100644", "type": "blob", "sha": blob}],
    })["sha"]
    require_sha(new_tree, 40)
    candidate = github.request("POST", api + "/git/commits", {
        "message": "state: protected Kesher GH-only revision rebind",
        "tree": new_tree, "parents": [old_ref],
    })["sha"]
    require_sha(candidate, 40)
    repo = github.request("GET", api)
    if (repo.get("full_name") != REPOSITORY
            or not isinstance(repo.get("node_id"), str)
            or not repo["node_id"]):
        raise StateInvalid("GHONLY_REBIND_REPO_IDENTITY_MISSING")
    key = digest({
        "previous": old_ref, "next": candidate, "main": expected_main,
        "reviewer_run": reviewer_run, "inventory": fingerprint,
    })
    ack = github.request("POST", "/graphql", {
        "query": UPDATE_REFS,
        "variables": {"input": {
            "repositoryId": repo["node_id"], "clientMutationId": key,
            "refUpdates": [
                {"name": "refs/heads/main", "beforeOid": expected_main,
                 "afterOid": expected_main, "force": False},
                {"name": "refs/heads/" + REF, "beforeOid": old_ref,
                 "afterOid": candidate, "force": False},
            ],
        }},
    })
    if ack.get("errors"):
        raise StateConflict("GHONLY_REBIND_CAS_CONFLICT")
    if ack.get("data", {}).get("updateRefs", {}).get("clientMutationId") != key:
        raise GitHubError(None, "Rebind receipt uncertain; re-read, do not retry",
                          uncertain=True)
    ref, _, observed = _loaded_owner(github, expected_main)
    if ref != candidate or observed != next_ledger:
        raise StateConflict("GHONLY_REBIND_IMMUTABLE_READBACK_MISMATCH")
    return {"status": "PROTECTED_REVIEWED_REVISION_REBOUND",
            "reviewed_main_sha": expected_main, "ledger_ref": candidate,
            "provider_dispatch": False, "publication_authorized": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("preflight", "rebind"))
    parser.add_argument("--reviewed-revision", required=True)
    parser.add_argument("--epoch", required=True)
    parser.add_argument("--inventory-sha256", default="")
    args = parser.parse_args(argv)
    wanted = ("github_owner_rebind_inventory" if args.stage == "preflight"
              else "github_owner_rebind")
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
            or os.environ.get("GITHUB_REF") != "refs/heads/main"
            or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or os.environ.get("GITHUB_WORKFLOW_REF") != WORKFLOW_REF
            or os.environ.get("GITHUB_SHA") != args.reviewed_revision
            or os.environ.get("GITHUB_JOB") != wanted):
        print("GHONLY_REBIND_WRONG_PROTECTED_JOB", file=sys.stderr)
        return 2
    try:
        gh = GitHub(os.environ.get("GH_TOKEN", ""))
        if args.stage == "preflight":
            result = preflight(
                gh, expected_main=args.reviewed_revision, epoch=args.epoch,
            )
            if os.environ.get("GITHUB_OUTPUT"):
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
                    f.write("inventory_sha256=" + result["inventory_sha256"] + "\n")
        else:
            result = rebind(
                gh, expected_main=args.reviewed_revision, epoch=args.epoch,
                reviewer_run=os.environ.get("GITHUB_RUN_ID", "") + ":"
                             + os.environ.get("GITHUB_RUN_ATTEMPT", ""),
                reviewed_inventory_sha256=args.inventory_sha256,
            )
        print("KESHER_GHONLY_REBIND " + canonical_json(result))
        return 0
    except (RuntimeError, ValueError, OSError, TypeError, KeyError):
        print("KESHER_GHONLY_REBIND_BLOCKED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
