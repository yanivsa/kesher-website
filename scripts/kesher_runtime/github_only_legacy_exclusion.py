"""Before any legacy bridge credentials, refuse a protected GitHub-only LIVE owner.

This read-only check does NOT grant provider dispatch to any new path.
It runs in the old workflow admission; the old disabled controller stays disabled.
All active/waiting legacy runs still require independent inventory at cutover.
"""
from __future__ import annotations

import base64
import json

from .github import _unique_object
from .github_only_owner_store import PATH, REF, REPOSITORY, _blob_sha
from .state import StateInvalid


def require_legacy_bridge_not_superseded(github) -> None:
    """Inspect exact GitHub state ref and immutable ledger bytes, fail closed.

    PREPARED_NOT_LIVE is *not* live authority; leave historical bridge policy
    unchanged during reviewed migration. A protected live activation excludes
    every old manual media/article worker. A missing, forged, or unknown state
    is not evidence permitting legacy execution.
    """
    api = "/repos/" + REPOSITORY
    sha = github.request("GET", api + "/git/ref/heads/" + REF)["object"]["sha"]
    if not isinstance(sha, str) or len(sha) != 40:
        raise StateInvalid("GHONLY_LEGACY_REF_IDENTITY_INVALID")
    row = github.request("GET", api + "/contents/" + PATH + "?ref=" + sha,
                         allow_404=True)
    if (not isinstance(row, dict) or row.get("encoding") != "base64"
            or not isinstance(row.get("content"), str)
            or not isinstance(row.get("sha"), str)):
        raise StateInvalid("GHONLY_LEDGER_REQUIRED_FOR_LEGACY_BRIDGE")
    raw = base64.b64decode("".join(row["content"].split()), validate=True)
    if not 0 < len(raw) <= 1_000_000 or _blob_sha(raw) != row["sha"]:
        raise StateInvalid("GHONLY_LEGACY_LEDGER_BLOB_INVALID")
    data = json.loads(raw, object_pairs_hook=_unique_object)
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or data.get("owner") != "github-only"
            or not isinstance(data.get("commands"), dict)
            or not isinstance(data.get("reviewed_main_sha"), str)
            or not isinstance(data.get("epoch"), str)):
        raise StateInvalid("GHONLY_LEGACY_LEDGER_INVALID")
    if data.get("activation") == "PROTECTED_VERIFIED":
        raise StateInvalid("GHONLY_LIVE_OWNER_EXCLUDES_LEGACY_BRIDGE")
    if data.get("activation") != "PREPARED_NOT_LIVE" or data["commands"]:
        raise StateInvalid("GHONLY_LEGACY_UNRECONCILED_OWNER")
    # Does not grant an old worker new authority; the existing bridge guard
    # must separately approve its Schema-5 state and exact workflow event.
