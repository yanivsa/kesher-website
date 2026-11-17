"""Durable GitHub-only claim journal; deliberately NOT a live controller.

This is only a storage primitive. It cannot bootstrap or approve an owner,
clear provider uncertainty, install an exclusive credential fence, or dispatch
article/media actions. A separately reviewed protected activation is required.
Two competing writers on automation-state cannot both win the same Git-ref CAS.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from dataclasses import dataclass

from .github import GitHubError, _unique_object
from .github_only_owner_policy import OwnerLedgerBlocked, plan_dispatch
from .handover_github import UPDATE_REFS
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

REPOSITORY = "yanivsa/kesher-website"
REF = "automation-state"
PATH = ".kesher-controller/github-only-owner.json"
_RUN_ID = re.compile(r"[1-9][0-9]*:[1-9][0-9]*")


def _blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


@dataclass(frozen=True)
class LedgerSnapshot:
    """An immutable read of one commit/tree/blob and its exact main revision."""
    ref_sha: str
    tree_sha: str
    blob_sha: str
    main_sha: str
    encoded: str

    @property
    def document(self):
        return json.loads(self.encoded, object_pairs_hook=_unique_object)


class GitHubOnlyLedgerStore:
    """No default bootstrap, no retry of an uncertain mutation, no dispatch."""

    def __init__(self, github, repo=REPOSITORY):
        if repo != REPOSITORY:
            raise StateInvalid("GITHUB_ONLY_EXACT_REPOSITORY_REQUIRED")
        self.github = github
        self.api = "/repos/" + repo

    def load(self, *, reviewed_main_sha: str) -> LedgerSnapshot:
        require_sha(reviewed_main_sha, 40)
        main = self.github.request("GET", self.api + "/git/ref/heads/main")["object"]["sha"]
        if main != reviewed_main_sha:
            raise StateConflict("GITHUB_ONLY_MAIN_REVISION_CHANGED")
        ref = self.github.request("GET", self.api + "/git/ref/heads/" + REF)["object"]["sha"]
        require_sha(ref, 40)
        commit = self.github.request("GET", self.api + "/git/commits/" + ref)
        if commit.get("sha") != ref or not isinstance(commit.get("tree"), dict):
            raise StateInvalid("GITHUB_ONLY_REF_COMMIT_UNTRUSTED")
        tree = commit["tree"]["sha"]
        require_sha(tree, 40)
        record = self.github.request(
            "GET", self.api + "/contents/" + PATH + "?ref=" + ref, allow_404=True
        )
        if record is None:
            raise StateInvalid("GITHUB_ONLY_LEDGER_NOT_BOOTSTRAPPED")
        blob = record.get("sha")
        require_sha(blob, 40)
        if record.get("encoding") != "base64" or not isinstance(record.get("content"), str):
            raise StateInvalid("GITHUB_ONLY_LEDGER_ENCODING_INVALID")
        raw = base64.b64decode("".join(record["content"].split()), validate=True)
        if len(raw) > 1_000_000 or _blob_sha(raw) != blob:
            raise StateInvalid("GITHUB_ONLY_LEDGER_BLOB_INTEGRITY_FAILURE")
        document = json.loads(raw, object_pairs_hook=_unique_object)
        if (not isinstance(document, dict) or document.get("schema_version") != 1
                or document.get("owner") != "github-only"
                or document.get("reviewed_main_sha") != reviewed_main_sha
                or not isinstance(document.get("commands"), dict)):
            raise StateInvalid("GITHUB_ONLY_LEDGER_SCHEMA_OR_OWNER_INVALID")
        return LedgerSnapshot(
            ref_sha=ref, tree_sha=tree, blob_sha=blob, main_sha=main,
            encoded=canonical_json(document),
        )

    def claim(
        self, loaded: LedgerSnapshot, *, epoch: str, command_id: str,
        workflow_run: str, observed_provider_tasks: dict,
        pending_github_runs: list,
    ) -> tuple[str, LedgerSnapshot]:
        """Persist the sole claim and independently read back; never call a provider.

        The caller must independently prove real protected activation, complete
        provider inventory and writer exclusivity. A JSON activation field is
        NOT, by itself, authorization to publish.
        """
        if not isinstance(loaded, LedgerSnapshot):
            raise StateInvalid("GITHUB_ONLY_SNAPSHOT_REQUIRED")
        for value in (loaded.ref_sha, loaded.tree_sha, loaded.blob_sha, loaded.main_sha):
            require_sha(value, 40)
        if not isinstance(workflow_run, str) or not _RUN_ID.fullmatch(workflow_run):
            raise StateInvalid("GITHUB_ONLY_EXACT_RUN_ATTEMPT_REQUIRED")
        # A caller-supplied dataclass, even with a real ref SHA, is not
        # proof of activation. Re-read immutable Git bytes before deciding.
        actual = self.load(reviewed_main_sha=loaded.main_sha)
        if actual != loaded:
            raise StateConflict("GITHUB_ONLY_SNAPSHOT_NOT_CURRENT")
        ledger = loaded.document
        decision = plan_dispatch(
            ledger=ledger, expected_epoch=epoch,
            reviewed_main_sha=loaded.main_sha, command_id=command_id,
            observed_provider_tasks=observed_provider_tasks,
            pending_github_runs=pending_github_runs,
        )
        if decision == "NOOP":
            return "NOOP", loaded
        if decision != "CLAIM_REQUIRED":
            raise StateInvalid("GITHUB_ONLY_UNEXPECTED_DECISION")
        current_main = self.github.request(
            "GET", self.api + "/git/ref/heads/main"
        )["object"]["sha"]
        if current_main != loaded.main_sha:
            raise StateConflict("GITHUB_ONLY_MAIN_CHANGED_BEFORE_CLAIM")
        next_ledger = copy.deepcopy(ledger)
        next_ledger["commands"][command_id] = {
            "phase": "CLAIMED", "run_id": workflow_run,
            "epoch": epoch, "reviewed_main_sha": loaded.main_sha,
            "provider_inventory_sha256": digest(observed_provider_tasks),
        }
        raw = (canonical_json(next_ledger) + "\n").encode("utf-8")
        expected_blob = _blob_sha(raw)
        blob = self.github.request("POST", self.api + "/git/blobs", {
            "content": base64.b64encode(raw).decode("ascii"), "encoding": "base64",
        })["sha"]
        if blob != expected_blob:
            raise StateInvalid("GITHUB_ONLY_WRITTEN_BLOB_MISMATCH")
        tree = self.github.request("POST", self.api + "/git/trees", {
            "base_tree": loaded.tree_sha,
            "tree": [{"path": PATH, "mode": "100644", "type": "blob", "sha": blob}],
        })["sha"]
        require_sha(tree, 40)
        commit = self.github.request("POST", self.api + "/git/commits", {
            "message": "state: Kesher github-only claim " + command_id,
            "tree": tree, "parents": [loaded.ref_sha],
        })["sha"]
        require_sha(commit, 40)
        repo_id = self.github.request("GET", self.api)["node_id"]
        if not isinstance(repo_id, str) or not repo_id:
            raise StateInvalid("GITHUB_ONLY_REPO_IDENTITY_MISSING")
        receipt_id = digest({
            "before": loaded.ref_sha, "after": commit,
            "main": loaded.main_sha, "command": command_id,
        })
        request = {
            "repositoryId": repo_id, "clientMutationId": receipt_id,
            "refUpdates": [
                {"name": "refs/heads/main", "beforeOid": loaded.main_sha,
                 "afterOid": loaded.main_sha, "force": False},
                {"name": "refs/heads/" + REF, "beforeOid": loaded.ref_sha,
                 "afterOid": commit, "force": False},
            ],
        }
        result = self.github.request(
            "POST", "/graphql", {"query": UPDATE_REFS, "variables": {"input": request}}
        )
        # Never replay a failed/unknown multi-ref mutation. Re-observe next run.
        if result.get("errors"):
            raise StateConflict("GITHUB_ONLY_REF_CAS_REJECTED")
        if result.get("data", {}).get("updateRefs", {}).get("clientMutationId") != receipt_id:
            raise GitHubError(None, "Claim acknowledgment unknown; reload", uncertain=True)
        observed = self.load(reviewed_main_sha=loaded.main_sha)
        if observed.ref_sha != commit or observed.document != next_ledger:
            raise StateConflict("GITHUB_ONLY_CLAIM_READBACK_CHANGED")
        return "CLAIMED", observed
