"""Protected, manual PREPARE of a GitHub-only owner ledger (NO production).

Only the existing liveness workflow's manually approved kesher-cutover
environment may call this. It does not enable a controller, dispatch any
provider, publish a source, or change Schema5.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys

from .github import GitHub, GitHubError
from .github_only_owner_store import GitHubOnlyLedgerStore, PATH, REF, REPOSITORY, _blob_sha
from .github_owner_readiness import inventory
from .handover_github import UPDATE_REFS
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

_EPOCH = re.compile(r"[A-Za-z0-9_-]{1,128}")
_RUN = re.compile(r"[1-9][0-9]*:[1-9][0-9]*")
_WORKFLOW_REF = REPOSITORY + "/.github/workflows/kesher-controller-liveness.yml@refs/heads/main"


def prepare_owner(github, *, expected_main: str, epoch: str, reviewer_run: str,
                  workflow_ref: str, event_name: str, repository: str):
    """Persist PREPARED_NOT_LIVE only after fresh independent GitHub inventory.

    A duplicate exact epoch is a read-only NOOP. An uncertain GraphQL response
    must be reconciled through a later immutable read, never auto-retried.
    """
    require_sha(expected_main, 40)
    if not isinstance(epoch, str) or not _EPOCH.fullmatch(epoch):
        raise StateInvalid("GITHUB_ONLY_PREPARE_EPOCH_INVALID")
    if not isinstance(reviewer_run, str) or not _RUN.fullmatch(reviewer_run):
        raise StateInvalid("GITHUB_ONLY_PREPARE_RUN_INVALID")
    if (workflow_ref != _WORKFLOW_REF or event_name != "workflow_dispatch"
            or repository != REPOSITORY):
        raise StateInvalid("GITHUB_ONLY_PREPARE_PROTECTED_JOB_REQUIRED")
    check = inventory(github, expected_main=expected_main, workflow_ref=workflow_ref,
                      event_name=event_name, repo=repository)
    if (check.get("status") != "READY_FOR_REVIEWED_MIGRATION_ONLY"
            or check.get("pending") or check.get("production_activated") is not False
            or check.get("provider_dispatch") is not False):
        raise StateInvalid("GITHUB_ONLY_PREPARE_INVENTORY_NOT_CLEAN")
    old_orphans = check.get("quarantined_old_orphans")
    if (not isinstance(old_orphans, list) or len(old_orphans) > 1
            or any(item != {"workflow":337960554, "run":42522546178,
                            "reason":"ORPHAN_ZERO_JOBS_DISABLED_PREDECESSOR"}
                   for item in old_orphans)):
        raise StateInvalid("GITHUB_ONLY_PREPARE_UNEXPECTED_ORPHAN")
    api = "/repos/" + REPOSITORY
    main = github.request("GET", api + "/git/ref/heads/main")["object"]["sha"]
    if main != expected_main:
        raise StateConflict("GITHUB_ONLY_PREPARE_MAIN_MOVED")
    old_ref = github.request("GET", api + "/git/ref/heads/" + REF)["object"]["sha"]
    require_sha(old_ref, 40)
    commit = github.request("GET", api + "/git/commits/" + old_ref)
    if commit.get("sha") != old_ref or not isinstance(commit.get("tree"), dict):
        raise StateInvalid("GITHUB_ONLY_PREPARE_STATE_COMMIT_UNTRUSTED")
    tree = commit["tree"]["sha"]
    require_sha(tree, 40)
    original = github.request("GET", api + "/contents/.kesher-controller/state.json?ref=" + old_ref)
    if original.get("sha") != check.get("legacy_blob_sha"):
        raise StateConflict("GITHUB_ONLY_PREPARE_LEGACY_CHANGED")
    existing = github.request("GET", api + "/contents/" + PATH + "?ref=" + old_ref,
                              allow_404=True)
    if existing is not None:
        current = GitHubOnlyLedgerStore(github).load(reviewed_main_sha=expected_main)
        document = current.document
        if (document.get("epoch") == epoch
                and document.get("activation") == "PREPARED_NOT_LIVE"
                and document.get("migration_basis", {}).get("legacy_blob_sha")
                    == check["legacy_blob_sha"]
                and document.get("owner") == "github-only"):
            return {"status":"ALREADY_PREPARED_NOOP", "production_activated":False,
                    "ledger_ref": current.ref_sha}
        raise StateInvalid("GITHUB_ONLY_PREPARE_EXISTING_OWNER_REQUIRES_RECONCILIATION")
    document = {
        "schema_version": 1,
        "owner": "github-only",
        "epoch": epoch,
        "reviewed_main_sha": expected_main,
        "activation": "PREPARED_NOT_LIVE",
        "inventory_complete": False,
        "commands": {},
        "migration_basis": {
            "legacy_blob_sha": check["legacy_blob_sha"],
            "legacy_cycle": check["legacy_cycle"],
            "approved_review_run": reviewer_run,
            "readiness_sha256": digest(check),
            "quarantined_old_orphans": old_orphans,
        },
    }
    raw = (canonical_json(document) + "\n").encode("utf-8")
    sha = github.request("POST", api + "/git/blobs", {
        "content": base64.b64encode(raw).decode("ascii"), "encoding": "base64",
    })["sha"]
    if sha != _blob_sha(raw):
        raise StateInvalid("GITHUB_ONLY_PREPARE_BLOB_INTEGRITY_FAILURE")
    updated_tree = github.request("POST", api + "/git/trees", {
        "base_tree":tree,
        "tree":[{"path":PATH, "mode":"100644", "type":"blob", "sha":sha}],
    })["sha"]
    require_sha(updated_tree, 40)
    candidate = github.request("POST", api + "/git/commits", {
        "message":"state: protected Kesher github-only PREPARED_NOT_LIVE",
        "tree":updated_tree,"parents":[old_ref],
    })["sha"]
    require_sha(candidate, 40)
    repo = github.request("GET", api)
    if repo.get("full_name") != REPOSITORY or not repo.get("node_id"):
        raise StateInvalid("GITHUB_ONLY_PREPARE_REPOSITORY_MISMATCH")
    key = digest({"before":old_ref, "after":candidate,
                  "main":expected_main, "owner":reviewer_run})
    mutation = {
        "repositoryId":repo["node_id"],"clientMutationId":key,
        "refUpdates":[
            {"name":"refs/heads/main","beforeOid":expected_main,
             "afterOid":expected_main,"force":False},
            {"name":"refs/heads/"+REF,"beforeOid":old_ref,
             "afterOid":candidate,"force":False},
        ],
    }
    result = github.request("POST", "/graphql", {
        "query":UPDATE_REFS, "variables":{"input":mutation},
    })
    if result.get("errors"):
        raise StateConflict("GITHUB_ONLY_PREPARE_REF_CAS_REJECTED")
    if result.get("data",{}).get("updateRefs",{}).get("clientMutationId") != key:
        raise GitHubError(None, "Prepare receipt unknown; reload", uncertain=True)
    current = GitHubOnlyLedgerStore(github).load(reviewed_main_sha=expected_main)
    if current.ref_sha != candidate or current.document != document:
        raise StateConflict("GITHUB_ONLY_PREPARE_READBACK_CHANGED")
    return {"status":"PREPARED_NOT_LIVE", "production_activated":False,
            "ledger_ref":current.ref_sha}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-revision", required=True)
    parser.add_argument("--epoch", required=True)
    args = parser.parse_args(argv)
    try:
        if (os.environ.get("GITHUB_SHA") != args.reviewed_revision
                or os.environ.get("GITHUB_JOB") != "github_owner_prepare"):
            raise StateInvalid("GITHUB_ONLY_PREPARE_EXACT_PROTECTED_JOB_REQUIRED")
        result = prepare_owner(
            GitHub(os.environ.get("GH_TOKEN", "")),
            expected_main=args.reviewed_revision,
            epoch=args.epoch,
            reviewer_run=os.environ.get("GITHUB_RUN_ID", "") + ":"
                         + os.environ.get("GITHUB_RUN_ATTEMPT", ""),
            workflow_ref=os.environ.get("GITHUB_WORKFLOW_REF", ""),
            event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
            repository=os.environ.get("GITHUB_REPOSITORY", ""),
        )
        print("KESHER_GITHUB_ONLY_PREPARE " + json.dumps(result, sort_keys=True))
        return 0
    except (GitHubError, StateConflict, StateInvalid, KeyError, TypeError, ValueError):
        print("KESHER_GITHUB_ONLY_PREPARE_BLOCKED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
