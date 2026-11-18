"""Durable, duplicate-safe external-effect journal for the GH-only owner.

This code NEVER calls NotebookLM, YouTube or GitHub Actions dispatch.
Before a future separately reviewed worker makes an external API request it must
CAS-persist the exact effect intent. Unknown provider acknowledgement must be
reconciled by read-only provider inventory, never retried as a new creation.
This primitive is inert until a genuinely protected LIVE owner and sole-writer
worker have been independently attested.
"""
from __future__ import annotations

import base64
import copy
import json
import re

from .github import GitHubError
from .github_only_owner_policy import OwnerLedgerBlocked, command_identity
from .github_only_owner_store import (
    GitHubOnlyLedgerStore, LedgerSnapshot, PATH, REF, _blob_sha,
)
from .handover_github import UPDATE_REFS
from .identity import canonical_json, digest, require_sha
from .state import StateConflict, StateInvalid

_EFFECTS = frozenset((
    "notebooklm_long", "youtube_long", "notebooklm_short", "youtube_short",
))
_RUN = re.compile(r"[1-9][0-9]*:[1-9][0-9]*")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_UUID = re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}")
_VIDEO = re.compile(r"[A-Za-z0-9_-]{11}")
_ORDER = {
    "notebooklm_long": None,
    "youtube_long": "notebooklm_long",
    "notebooklm_short": "youtube_long",
    "youtube_short": "notebooklm_short",
}


def _require_identity(ledger, *, epoch, command_id, run_id,
                      slot, slug, source_sha256, operation, ordinal):
    if (ledger.get("owner") != "github-only"
            or ledger.get("schema_version") != 1
            or ledger.get("activation") != "PROTECTED_VERIFIED"
            or ledger.get("inventory_complete") is not True
            or ledger.get("epoch") != epoch):
        raise OwnerLedgerBlocked("GHONLY_EFFECT_PROTECTED_LIVE_REQUIRED")
    if (not isinstance(slug, str) or _SLUG.fullmatch(slug) is None
            or not isinstance(source_sha256, str)
            or _SHA256.fullmatch(source_sha256) is None):
        raise OwnerLedgerBlocked("GHONLY_EFFECT_SOURCE_IDENTITY_INVALID")
    if (not isinstance(run_id, str) or _RUN.fullmatch(run_id) is None
            or command_identity(slot=slot, source_sha256=source_sha256,
                                operation=operation, ordinal=ordinal) != command_id):
        raise OwnerLedgerBlocked("GHONLY_EFFECT_CLAIM_IDENTITY_MISMATCH")
    command = ledger.get("commands", {}).get(command_id)
    if (not isinstance(command, dict)
            or command.get("run_id") != run_id
            or command.get("epoch") != epoch
            or command.get("reviewed_main_sha") != ledger.get("reviewed_main_sha")
            or command.get("phase") not in (
                "CLAIMED", "DISPATCH_UNKNOWN", "WAITING_PROVIDER", "OUTPUT_CREATED",
            )):
        raise OwnerLedgerBlocked("GHONLY_EFFECT_COMMAND_NOT_CLAIMED_BY_RUN")
    return command


class GitHubOnlyEffectJournal:
    """One persisted intent per exact source/kind/attempt, no blind retries."""

    def __init__(self, store: GitHubOnlyLedgerStore):
        if not isinstance(store, GitHubOnlyLedgerStore):
            raise StateInvalid("GHONLY_EFFECT_EXACT_STORE_REQUIRED")
        self.store = store

    def _load_current(self, loaded):
        if not isinstance(loaded, LedgerSnapshot):
            raise StateInvalid("GHONLY_EFFECT_SNAPSHOT_REQUIRED")
        for sha in (loaded.ref_sha, loaded.tree_sha, loaded.blob_sha, loaded.main_sha):
            require_sha(sha, 40)
        actual = self.store.load(reviewed_main_sha=loaded.main_sha)
        if actual != loaded:
            raise StateConflict("GHONLY_EFFECT_SNAPSHOT_STALE")
        return loaded.document

    def _cas(self, loaded, new_doc, *, command_id, name):
        api = self.store.api
        gh = self.store.github
        if gh.request("GET", api + "/git/ref/heads/main")["object"]["sha"] != loaded.main_sha:
            raise StateConflict("GHONLY_EFFECT_MAIN_MOVED_BEFORE_CAS")
        raw = (canonical_json(new_doc) + "\n").encode("utf-8")
        expected_blob = _blob_sha(raw)
        result = gh.request("POST", api + "/git/blobs", {
            "content": base64.b64encode(raw).decode("ascii"), "encoding": "base64",
        })
        if result.get("sha") != expected_blob:
            raise StateInvalid("GHONLY_EFFECT_BLOB_WRITE_MISMATCH")
        tree = gh.request("POST", api + "/git/trees", {
            "base_tree": loaded.tree_sha,
            "tree": [{"path": PATH, "mode": "100644", "type": "blob",
                      "sha": expected_blob}],
        })["sha"]
        require_sha(tree, 40)
        commit = gh.request("POST", api + "/git/commits", {
            "message": "state: GH-only media effect " + name + " " + command_id,
            "tree": tree, "parents": [loaded.ref_sha],
        })["sha"]
        require_sha(commit, 40)
        repo = gh.request("GET", api)
        if not isinstance(repo.get("node_id"), str) or not repo["node_id"]:
            raise StateInvalid("GHONLY_EFFECT_REPOSITORY_ID_MISSING")
        token = digest({
            "before": loaded.ref_sha, "after": commit, "main": loaded.main_sha,
            "command": command_id, "kind": name,
        })
        mutation = {
            "repositoryId": repo["node_id"], "clientMutationId": token,
            "refUpdates": [
                {"name": "refs/heads/main", "beforeOid": loaded.main_sha,
                 "afterOid": loaded.main_sha, "force": False},
                {"name": "refs/heads/" + REF, "beforeOid": loaded.ref_sha,
                 "afterOid": commit, "force": False},
            ],
        }
        ack = gh.request("POST", "/graphql", {
            "query": UPDATE_REFS, "variables": {"input": mutation},
        })
        if ack.get("errors"):
            raise StateConflict("GHONLY_EFFECT_CAS_REJECTED")
        if ack.get("data", {}).get("updateRefs", {}).get("clientMutationId") != token:
            raise GitHubError(None, "Effect outcome unknown; reconcile remote", uncertain=True)
        observed = self.store.load(reviewed_main_sha=loaded.main_sha)
        if observed.ref_sha != commit or observed.document != new_doc:
            raise StateConflict("GHONLY_EFFECT_READBACK_CHANGED")
        return observed

    def begin(self, loaded, *, epoch, command_id, run_id, slot, slug,
              source_sha256, operation, ordinal=1, effect_kind, request_sha256):
        """Persist intent BEFORE touching a provider. Never grants execution.

        The future worker must re-observe the LIVE owner and provider before it
        makes the one external call. A repeated/uncertain call is never admitted
        by this method after the first durable intent exists.
        """
        if effect_kind not in _EFFECTS or not isinstance(request_sha256, str) or (
                _SHA256.fullmatch(request_sha256) is None):
            raise OwnerLedgerBlocked("GHONLY_EFFECT_REQUEST_INVALID")
        doc = self._load_current(loaded)
        command = _require_identity(
            doc, epoch=epoch, command_id=command_id, run_id=run_id,
            slot=slot, slug=slug, source_sha256=source_sha256,
            operation=operation, ordinal=ordinal,
        )
        effects = command.get("effects") or {}
        if not isinstance(effects, dict):
            raise OwnerLedgerBlocked("GHONLY_EFFECT_JOURNAL_MALFORMED")
        old = effects.get(effect_kind)
        if old is not None:
            if (old.get("request_sha256") == request_sha256
                    and old.get("source_sha256") == source_sha256
                    and old.get("source_slug") == slug):
                return "ALREADY_RECORDED_NO_RETRY", loaded
            raise OwnerLedgerBlocked("GHONLY_EFFECT_CONFLICTING_RETRY")
        if any(isinstance(row, dict) and row.get("phase") == "INTENT_RECORDED"
               for row in effects.values()):
            raise OwnerLedgerBlocked("GHONLY_EFFECT_UNCERTAIN_REMOTE_CALL")
        previous = _ORDER[effect_kind]
        if previous and not (isinstance(effects.get(previous), dict)
                             and effects[previous].get("phase") == "VERIFIED_OUTPUT"):
            raise OwnerLedgerBlocked("GHONLY_EFFECT_PREDECESSOR_NOT_VERIFIED")
        new_doc = copy.deepcopy(doc)
        new_command = new_doc["commands"][command_id]
        new_command.setdefault("effects", {})[effect_kind] = {
            "phase": "INTENT_RECORDED",
            "source_slug": slug,
            "source_sha256": source_sha256,
            "request_sha256": request_sha256,
            "provider_id": None,
            "receipt_sha256": None,
        }
        written = self._cas(loaded, new_doc, command_id=command_id, name=effect_kind)
        return "INTENT_RECORDED", written

    def observe(self, loaded, *, epoch, command_id, run_id, slot, slug,
                source_sha256, operation, ordinal=1, effect_kind,
                request_sha256, provider_id, receipt_sha256):
        """Bind one independently observed remote ID; NOT a publication grant.

        The caller is responsible for separately verifying source, channel,
        geometry, voice, visual/editorial approval and public availability.
        This journal does NOT mark media public or approve the next stage.
        """
        if (effect_kind not in _EFFECTS
                or not isinstance(receipt_sha256, str)
                or _SHA256.fullmatch(receipt_sha256) is None
                or not isinstance(request_sha256, str)
                or _SHA256.fullmatch(request_sha256) is None):
            raise OwnerLedgerBlocked("GHONLY_EFFECT_OBSERVATION_INVALID")
        pattern = _UUID if effect_kind.startswith("notebooklm_") else _VIDEO
        if not isinstance(provider_id, str) or pattern.fullmatch(provider_id) is None:
            raise OwnerLedgerBlocked("GHONLY_EFFECT_PROVIDER_ID_INVALID")
        doc = self._load_current(loaded)
        command = _require_identity(
            doc, epoch=epoch, command_id=command_id, run_id=run_id,
            slot=slot, slug=slug, source_sha256=source_sha256,
            operation=operation, ordinal=ordinal,
        )
        effect = (command.get("effects") or {}).get(effect_kind)
        if not isinstance(effect, dict) or (
                effect.get("request_sha256") != request_sha256
                or effect.get("source_sha256") != source_sha256
                or effect.get("source_slug") != slug):
            raise OwnerLedgerBlocked("GHONLY_EFFECT_MISSING_EXACT_INTENT")
        receipt = {
            **effect, "phase": "REMOTE_ID_OBSERVED",
            "provider_id": provider_id, "receipt_sha256": receipt_sha256,
        }
        if effect.get("phase") == "REMOTE_ID_OBSERVED":
            if effect == receipt:
                return "ALREADY_OBSERVED_NO_RETRY", loaded
            raise OwnerLedgerBlocked("GHONLY_EFFECT_CONFLICTING_REMOTE_RECEIPT")
        if effect.get("phase") != "INTENT_RECORDED":
            raise OwnerLedgerBlocked("GHONLY_EFFECT_INVALID_TRANSITION")
        next_doc = copy.deepcopy(doc)
        next_doc["commands"][command_id]["effects"][effect_kind] = receipt
        observed = self._cas(loaded, next_doc, command_id=command_id,
                             name=effect_kind + "-observed")
        return "REMOTE_ID_OBSERVED", observed
