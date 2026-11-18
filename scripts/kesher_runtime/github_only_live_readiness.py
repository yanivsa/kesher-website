"""Fail-closed, read-only GH-only LIVE eligibility diagnosis.

This is NOT a live owner, a migration, a provider inventory, or an activation
path. It cannot dispatch article/NotebookLM/YouTube work or mutate Git refs.
It identifies the exact blockers before anyone requests a protected LIVE review.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys

from .github import GitHub, _unique_object
from .github_only_owner_store import PATH, REF, REPOSITORY, _blob_sha
from .github_owner_readiness import inventory
from .state import StateInvalid

WORKFLOW_REF = (
    REPOSITORY + "/.github/workflows/kesher-controller-liveness.yml@refs/heads/main"
)
_JOB = "github_owner_live_probe"
_ALLOWED_ACTIVATION = frozenset({"PREPARED_NOT_LIVE", "PROTECTED_VERIFIED"})


def _ledger(github):
    """Read exact immutable branch, commit and hash-verified ledger bytes."""
    api = "/repos/" + REPOSITORY
    ref = github.request("GET", api + "/git/ref/heads/" + REF)["object"]["sha"]
    if not isinstance(ref, str) or re.fullmatch(r"[0-9a-f]{40}", ref) is None:
        raise StateInvalid("GHONLY_LIVE_PROBE_INVALID_REF")
    commit = github.request("GET", api + "/git/commits/" + ref)
    if (commit.get("sha") != ref or
            not isinstance(commit.get("tree"), dict) or
            re.fullmatch(r"[0-9a-f]{40}", str(commit["tree"].get("sha", ""))) is None):
        raise StateInvalid("GHONLY_LIVE_PROBE_INVALID_COMMIT")
    content = github.request(
        "GET", api + "/contents/" + PATH + "?ref=" + ref,
    )
    if (not isinstance(content, dict) or
            content.get("encoding") != "base64" or
            not isinstance(content.get("content"), str) or
            re.fullmatch(r"[0-9a-f]{40}", str(content.get("sha", ""))) is None):
        raise StateInvalid("GHONLY_LIVE_PROBE_INVALID_BLOB")
    raw = base64.b64decode("".join(content["content"].split()), validate=True)
    if not 0 < len(raw) <= 1_000_000 or _blob_sha(raw) != content["sha"]:
        raise StateInvalid("GHONLY_LIVE_PROBE_BLOB_INTEGRITY")
    document = json.loads(raw, object_pairs_hook=_unique_object)
    if (not isinstance(document, dict) or document.get("schema_version") != 1
            or document.get("owner") != "github-only"
            or not isinstance(document.get("commands"), dict)
            or not isinstance(document.get("migration_basis"), dict)
            or document.get("activation") not in _ALLOWED_ACTIVATION):
        raise StateInvalid("GHONLY_LIVE_PROBE_INVALID_LEDGER")
    return document


def diagnose(github, *, expected_main, workflow_ref, event_name, repo):
    """No positive activation verdict: no standalone LIVE worker/proof exists."""
    if (not isinstance(expected_main, str) or
            re.fullmatch(r"[0-9a-f]{40}", expected_main) is None or
            workflow_ref != WORKFLOW_REF or event_name != "workflow_dispatch"
            or repo != REPOSITORY):
        raise StateInvalid("GHONLY_LIVE_PROBE_INVOCATION_INVALID")
    readiness = inventory(
        github, expected_main=expected_main, workflow_ref=workflow_ref,
        event_name=event_name, repo=repo,
    )
    ledger = _ledger(github)
    blockers = []
    if readiness.get("status") != "READY_FOR_REVIEWED_MIGRATION_ONLY":
        blockers.append("EXISTING_GITHUB_OWNER_OR_RUN_NOT_DRAINED")
    if ledger.get("reviewed_main_sha") != expected_main:
        blockers.append("PREPARE_MAIN_REVISION_STALE")
    if ledger.get("activation") != "PREPARED_NOT_LIVE":
        blockers.append("EXISTING_LIVE_CLAIM_REQUIRES_INDEPENDENT_VERIFICATION")
    if ledger.get("inventory_complete") is not False:
        blockers.append("PREPARE_INVENTORY_FLAG_UNEXPECTED")
    if ledger["commands"]:
        blockers.append("EXISTING_COMMAND_JOURNAL_REQUIRES_RECONCILIATION")
    if ledger["migration_basis"].get("legacy_blob_sha") != readiness.get("legacy_blob_sha"):
        blockers.append("LEGACY_STATE_CHANGED_SINCE_PREPARE")
    if ledger["migration_basis"].get("legacy_cycle") != readiness.get("legacy_cycle"):
        blockers.append("LEGACY_CYCLE_CHANGED_SINCE_PREPARE")

    # These cannot be proven by a GitHub-only owner probe. They MUST be
    # independently implemented and protected before any LIVE CAS/dispatch.
    blockers.extend((
        "PROTECTED_LIVE_TRANSITION_NOT_IMPLEMENTED",
        "SINGLE_WRITER_MEDIA_WORKER_NOT_ATTESTED",
        "FULL_PROVIDER_TASK_AND_YOUTUBE_INVENTORY_NOT_BOUND",
        "MEDIA_SOURCE_VOICE_VISUAL_QA_NOT_APPROVED",
    ))
    return {
        "status": "BLOCKED_PRODUCTION_LIVE",
        "read_only": True,
        "production_activated": False,
        "provider_dispatch": False,
        "prepared_epoch": ledger.get("epoch"),
        "reviewed_main_matches": ledger.get("reviewed_main_sha") == expected_main,
        "legacy_state_matches": (
            ledger["migration_basis"].get("legacy_blob_sha")
            == readiness.get("legacy_blob_sha")
        ),
        "blockers": sorted(set(blockers)),
        "no_new_schedule": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-revision", required=True)
    args = parser.parse_args(argv)
    try:
        if (os.environ.get("GITHUB_JOB") != _JOB or
                os.environ.get("GITHUB_SHA") != args.reviewed_revision):
            raise StateInvalid("GHONLY_LIVE_PROBE_EXACT_JOB_REQUIRED")
        report = diagnose(
            GitHub(os.environ.get("GH_TOKEN", "")),
            expected_main=args.reviewed_revision,
            workflow_ref=os.environ.get("GITHUB_WORKFLOW_REF", ""),
            event_name=os.environ.get("GITHUB_EVENT_NAME", ""),
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
        )
        print("KESHER_GHONLY_LIVE_DIAGNOSTIC " +
              json.dumps(report, ensure_ascii=True, sort_keys=True))
        # Explicitly fail closed; a green workflow cannot be mistaken for
        # proof of LIVE, and approval is not requested by this route.
        return 2
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        print("KESHER_GHONLY_LIVE_DIAGNOSTIC_UNTRUSTED", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
