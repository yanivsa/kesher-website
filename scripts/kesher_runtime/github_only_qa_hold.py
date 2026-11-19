"""Fail-closed, immutable QA HOLD for one already completed NotebookLM Long.

A successfully completed GitHub Action is NOT a publishable video. This
preapproved one-source repair is intentionally NOT a general producer: it
verifies the original human-reviewed GitHub run, the original immutable
source/task receipts, provider COMPLETED readback and exact QA artifact
digest before allowing a protected main-SHA revision roll-forward.

The original command is NEVER removed, replayed or marked PUBLISHED. Its
reviewed-main SHA remains its original audit identity even after a safe
protected rebind of the *owner*. A corrected video MUST use a separately
reviewed next attempt, after explicit QA/asset review.
"""
from __future__ import annotations

import re

from .github_only_live_activation import _reviewed_run
from .github_only_live_inventory import NOTEBOOK, _provider_json, _rows
from .github_only_owner_store import REPOSITORY
from .state import StateInvalid

COMMAND_ID = "149ed4c8a86a3da1a8ceca9195d782039e3458cf8553cd1647add649a473fbf9"
SOURCE_SHA = "e5a57c64f85a2e56d355c73b4abe052c5052aa1addb074fcea677262c8b77616"
SOURCE_SLUG = "couple-conversation-stuck-pursue-withdraw-cycle"
ORIGINAL_REVIEWED_MAIN = "1eccad173d19e2842f3f7b1e6379c7f55f2cad89"
ORIGINAL_RUN = "44462713412:1"
ORIGINAL_SOURCE_ID = "12c4d5f7-a321-43fb-bca5-31af47cce735"
ORIGINAL_TASK_ID = "625dcd51-8649-4db1-a170-935423104a33"
ORIGINAL_ARTIFACT_ID = 14500927475
ORIGINAL_ARTIFACT_NAME = "kesher-ghonly-protected-production-qa-44462713412"
ORIGINAL_ARCHIVE_DIGEST = "sha256:006038e7ee560540aa1cdf0ef0ef709b5fb7d8cb4ee6b94e2f757c76c319c1e6"
QA_JSON_SHA = "79d51e94fede962d5cb0fea734cb05eaa41c9c8e2b2401e06d4355bdf5b04aff"
MEDIA_SHA = "1dfb29be062b68a658e484f0ffe3bb787d0610a78bc0ff65f67bb58bc9439021"
CONTACT_SHEET_SHA = "079b51874fe42a15954049199c819fe6da78831701fcf208714f034e6e1d3fd7"
TRANSCRIPT_SHA = "6d0fc1a8185abe543fe01b5135474a7dd701e9a7608b266baa1a74914d452dba"
SOURCE_REQUEST = "c8bed63fce44ef8ec2aaf94cda1ab98c2a16ee28d130f690e5ee037b694cc5aa"
SOURCE_RECEIPT = "26c303d0b84f6e645ba6d4a2dee877efb4d8d6889d5e2b32ea5bf2dda86870ec"
LONG_REQUEST = "890cf06bb7eb9e1b95148c00cba66c3473de2337a940474138a7c4cb3f97a3f5"
LONG_RECEIPT = "0ac57833c1eefa332d37e091939e8a16fa26ee05aef635a9b3a76f8afe2ed071"

SEALED_EVIDENCE = {
    "status": "QA_HOLD", "reason": "SLIDE_LIKE_VISUAL_AND_UNAPPROVED_AUDIO",
    "original_run": ORIGINAL_RUN,
    "original_task_id": ORIGINAL_TASK_ID,
    "source_sha256": SOURCE_SHA,
    "source_slug": SOURCE_SLUG,
    "qa_artifact_id": ORIGINAL_ARTIFACT_ID,
    "qa_archive_digest": ORIGINAL_ARCHIVE_DIGEST,
    "qa_json_sha256": QA_JSON_SHA,
    "original_media_sha256": MEDIA_SHA,
    "contact_sheet_sha256": CONTACT_SHEET_SHA,
    "transcript_sha256": TRANSCRIPT_SHA,
    "originally_reviewed_main_sha": ORIGINAL_REVIEWED_MAIN,
    "visual_editorial_approved": False,
    "audio_editorial_approved": False,
    "semantic_source_review_approved": False,
    "long_publish_authorized": False,
    "short_generation_authorized": False,
    "youtube_upload_authorized": False,
}


def hold_basis(document):
    """Allow only the exact existing task, never generic or pending commands."""
    cmds = document.get("commands")
    if cmds == {}:
        return None
    if not isinstance(cmds, dict) or set(cmds) != {COMMAND_ID}:
        raise StateInvalid("GHONLY_QA_HOLD_UNRELATED_COMMAND_BLOCKED")
    item = cmds[COMMAND_ID]
    if (not isinstance(item, dict)
            or item.get("epoch") != document.get("epoch")
            or item.get("run_id") != ORIGINAL_RUN
            or item.get("reviewed_main_sha") != ORIGINAL_REVIEWED_MAIN
            or item.get("phase") not in ("CLAIMED", "QA_HOLD")):
        raise StateInvalid("GHONLY_QA_HOLD_WRONG_COMMAND_IDENTITY")
    effects = item.get("effects")
    if not isinstance(effects, dict) or set(effects) != {
            "notebooklm_source", "notebooklm_long"}:
        raise StateInvalid("GHONLY_QA_HOLD_UNVERIFIED_EXTRA_EFFECT")
    source = effects["notebooklm_source"]
    long = effects["notebooklm_long"]
    for kind, row, phase, provider_id, request, receipt in (
        ("source", source, "VERIFIED_OUTPUT", ORIGINAL_SOURCE_ID, SOURCE_REQUEST, SOURCE_RECEIPT),
        ("long", long, "REMOTE_ID_OBSERVED", ORIGINAL_TASK_ID, LONG_REQUEST, LONG_RECEIPT),
    ):
        if (not isinstance(row, dict)
                or row.get("phase") != phase
                or row.get("provider_id") != provider_id
                or row.get("request_sha256") != request
                or row.get("receipt_sha256") != receipt
                or row.get("source_sha256") != SOURCE_SHA
                or row.get("source_slug") != SOURCE_SLUG):
            raise StateInvalid("GHONLY_QA_HOLD_UNTRUSTED_" + kind.upper() + "_RECEIPT")
    if (source.get("evidence_kind") != "source_fulltext"
            or source.get("qa_sha256") != SOURCE_SHA):
        raise StateInvalid("GHONLY_QA_HOLD_SOURCE_NOT_QA_VERIFIED")
    if item["phase"] == "QA_HOLD":
        if item.get("quality_checkpoint") != SEALED_EVIDENCE:
            raise StateInvalid("GHONLY_QA_HOLD_EVIDENCE_TAMPERED")
    elif item.get("quality_checkpoint") is not None:
        raise StateInvalid("GHONLY_QA_HOLD_PREEXISTING_UNTRUSTED_EVIDENCE")
    return SEALED_EVIDENCE


def verified_qa_hold(github, document, *, command=_provider_json):
    """Verify fresh external provider + GitHub readbacks without mutation.

    Completeness check of all active providers is enforced independently by
    the caller's before/after protected inventory checks. This exact task is
    checked again here to ensure it is COMPLETED and never still generating.
    """
    evidence = hold_basis(document)
    if evidence is None:
        return None
    api = "/repos/" + REPOSITORY
    run = github.request("GET", api + "/actions/runs/" + ORIGINAL_RUN.split(":")[0])
    if (not isinstance(run, dict)
            or str(run.get("id")) != ORIGINAL_RUN.split(":")[0]
            or run.get("head_sha") != ORIGINAL_REVIEWED_MAIN
            or run.get("path") != ".github/workflows/kesher-media-worker.yml"
            or run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != "main"
            or str(run.get("run_attempt")) != "1"
            or run.get("status") != "completed"
            or run.get("conclusion") != "success"):
        raise StateInvalid("GHONLY_QA_HOLD_ORIGINAL_PRODUCTION_RUN_UNTRUSTED")
    _reviewed_run(github, ORIGINAL_RUN, ORIGINAL_REVIEWED_MAIN)

    # Before first seal, the original immutable QA ZIP must still be available
    # and its exact digest must match the independently inspected evidence.
    # After seal, its digest is durable in Git history and artifact expiry is
    # not allowed to erase that proof or resume production.
    if document["commands"][COMMAND_ID]["phase"] != "QA_HOLD":
        artifacts = github.request(
            "GET", api + "/actions/runs/" + ORIGINAL_RUN.split(":")[0] + "/artifacts",
        )
        if not isinstance(artifacts, dict) or not isinstance(artifacts.get("artifacts"), list):
            raise StateInvalid("GHONLY_QA_HOLD_ARTIFACT_LIST_UNTRUSTED")
        matching = [x for x in artifacts["artifacts"] if isinstance(x, dict)
                    and x.get("id") == ORIGINAL_ARTIFACT_ID]
        if (len(matching) != 1
                or matching[0].get("name") != ORIGINAL_ARTIFACT_NAME
                or matching[0].get("digest") != ORIGINAL_ARCHIVE_DIGEST
                or matching[0].get("expired") is not False
                or (matching[0].get("workflow_run") or {}).get("head_sha")
                    != ORIGINAL_REVIEWED_MAIN
                or (matching[0].get("workflow_run") or {}).get("id")
                    != int(ORIGINAL_RUN.split(":")[0])):
            raise StateInvalid("GHONLY_QA_HOLD_ORIGINAL_ARTIFACT_HASH_MISMATCH")
    videos = _rows(command([
        "artifact", "list", "--type", "video", "--notebook", NOTEBOOK,
    ]), "artifacts")
    matched = [row for row in videos
               if ORIGINAL_TASK_ID in {row.get(k) for k in ("id", "task_id", "artifact_id")
                                       if isinstance(row.get(k), str)}]
    if (len(matched) != 1
            or str(matched[0].get("status", matched[0].get("state", ""))).lower()
                .strip() != "completed"):
        raise StateInvalid("GHONLY_QA_HOLD_EXACT_PROVIDER_TASK_NOT_COMPLETED")
    return evidence
