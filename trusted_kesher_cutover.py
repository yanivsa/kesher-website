"""Administrator-owned composition for the external KESHER cutover service.

This module composes the already-reviewed cutover contracts. It never creates
provider evidence, initializes durable state, initializes the invocation ledger,
or activates production. Native resource boundaries remain an independent
administrator prerequisite and are injected only from the local service host.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.kesher_runtime.authority_topology import executable_digest, inventory, policy
from scripts.kesher_runtime.cutover_auth import ActionsIdentity
from scripts.kesher_runtime.cutover_service import CutoverApplication, InvocationJournal
from scripts.kesher_runtime.exclusion import REQUIRED_RESOURCES
from scripts.kesher_runtime.github import _unique_object
from scripts.kesher_runtime.handover import OWNER
from scripts.kesher_runtime.identity import digest, require_sha
from scripts.kesher_runtime.live_cutover import build_runtime
from scripts.kesher_runtime.production_ports import PrerequisitePort
from scripts.kesher_runtime.state import StateInvalid


_REQUIRED_ENV = (
    "KESHER_CUTOVER_REVIEW_FILE",
    "KESHER_CUTOVER_MATERIAL_FILE",
    "KESHER_CUTOVER_CLOSURE_FILE",
    "KESHER_CUTOVER_BINDINGS_FILE",
    "KESHER_CUTOVER_REGISTRATIONS_FILE",
    "KESHER_CUTOVER_KEY_BINDING_FILE",
    "KESHER_CUTOVER_NATIVE_FACTORY",
    "KESHER_CUTOVER_OIDC_AUDIENCE",
    "KESHER_CUTOVER_JOURNAL",
    "KESHER_CUTOVER_EPOCH",
    "KESHER_CUTOVER_OWNER",
    "KESHER_GITHUB_REPOSITORY",
    "KESHER_GITHUB_REPOSITORY_ID",
)
_JSON_ENV = {
    "review": "KESHER_CUTOVER_REVIEW_FILE",
    "material": "KESHER_CUTOVER_MATERIAL_FILE",
    "closure": "KESHER_CUTOVER_CLOSURE_FILE",
    "bindings": "KESHER_CUTOVER_BINDINGS_FILE",
    "registrations": "KESHER_CUTOVER_REGISTRATIONS_FILE",
    "key_binding": "KESHER_CUTOVER_KEY_BINDING_FILE",
}
_EXTERNAL_RESOURCES = set(REQUIRED_RESOURCES) - {"github"}
_FACTORY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _fail(reason: str) -> None:
    raise StateInvalid(reason)


def _exact_https_origin(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and parsed.path == ""
            and parsed.query == ""
            and parsed.fragment == ""
        )
    except ValueError:
        return False


def _environment() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in _REQUIRED_ENV:
        value = os.environ.get(name, "").strip()
        if not value:
            _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
        values[name] = value
    root = os.environ.get("KESHER_CUTOVER_ROOT", "").strip()
    values["KESHER_CUTOVER_ROOT"] = root or str(Path(__file__).resolve().parent)
    if not _REPOSITORY.fullmatch(values["KESHER_GITHUB_REPOSITORY"]):
        _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
    if not values["KESHER_GITHUB_REPOSITORY_ID"].isdecimal() or int(values["KESHER_GITHUB_REPOSITORY_ID"]) <= 0:
        _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
    if values["KESHER_CUTOVER_OWNER"] != OWNER:
        _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
    if not _exact_https_origin(values["KESHER_CUTOVER_OIDC_AUDIENCE"]):
        _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
    return values


def _read_json(path_value: str) -> Any:
    try:
        path = Path(path_value)
        if not path.is_absolute() or not path.is_file():
            _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
        raw = path.read_bytes()
        if not raw or len(raw) > 4 * 1024 * 1024:
            _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
        return json.loads(raw, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError, TypeError):
        _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")


def _load_material(env: dict[str, str]) -> dict[str, Any]:
    loaded = {name: _read_json(env[var]) for name, var in _JSON_ENV.items()}
    if not all(isinstance(loaded[name], dict) for name in ("review", "material", "closure", "bindings", "registrations", "key_binding")):
        _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
    return loaded


def _validate_journal(path_value: str) -> InvocationJournal:
    path = Path(path_value)
    try:
        if not path.is_absolute() or not path.is_file():
            _fail("CUTOVER_INVOCATION_LEDGER_REQUIRED")
        uri = "file:" + str(path) + "?mode=rw"
        with sqlite3.connect(uri, uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            rows = db.execute("PRAGMA table_info(invocations)").fetchall()
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        expected = [
            (0, "epoch", "TEXT", 1, None, 1),
            (1, "run", "TEXT", 1, None, 2),
        ]
        if rows != expected or tables != {"invocations"}:
            _fail("CUTOVER_INVOCATION_LEDGER_REQUIRED")
    except (OSError, sqlite3.Error):
        _fail("CUTOVER_INVOCATION_LEDGER_REQUIRED")
    return InvocationJournal(path)


def _load_native_factory(spec: str):
    if not _FACTORY.fullmatch(spec):
        _fail("CUTOVER_NATIVE_FACTORY_REQUIRED")
    module_name, function_name = spec.split(":", 1)
    try:
        function = getattr(importlib.import_module(module_name), function_name)
    except (ImportError, AttributeError, ValueError):
        _fail("CUTOVER_NATIVE_FACTORY_REQUIRED")
    if not callable(function):
        _fail("CUTOVER_NATIVE_FACTORY_REQUIRED")
    return function


def _port(value: Any) -> bool:
    return callable(getattr(value, "inspect", None)) and callable(getattr(value, "exclude", None))


def _native_bundle(factory) -> dict[str, Any]:
    try:
        bundle = factory()
    except StateInvalid:
        raise
    except Exception:
        _fail("CUTOVER_COMPLETE_NATIVE_BUNDLE_REQUIRED")
    required = {"github", "github_boundary", "external_ports", "separation_observer", "key"}
    if not isinstance(bundle, dict) or set(bundle) != required:
        _fail("CUTOVER_COMPLETE_NATIVE_BUNDLE_REQUIRED")
    if not callable(getattr(bundle["github"], "request", None)) or not _port(bundle["github_boundary"]):
        _fail("CUTOVER_COMPLETE_NATIVE_BUNDLE_REQUIRED")
    ports = bundle["external_ports"]
    if not isinstance(ports, dict) or set(ports) != _EXTERNAL_RESOURCES:
        _fail("CUTOVER_COMPLETE_NATIVE_BUNDLE_REQUIRED")
    for resource, value in ports.items():
        if isinstance(value, PrerequisitePort) or not _port(value):
            _fail("CUTOVER_REAL_NATIVE_PORT_REQUIRED")
        if getattr(value, "resource", resource) != resource:
            _fail("CUTOVER_REAL_NATIVE_PORT_REQUIRED")
    if not callable(bundle["separation_observer"]) or not callable(bundle["key"]):
        _fail("CUTOVER_COMPLETE_NATIVE_BUNDLE_REQUIRED")
    return bundle


def _verify_installed_review(
    *,
    root: Path,
    repo: str,
    review: dict[str, Any],
    material: dict[str, Any],
    closure: dict[str, Any],
    bindings: dict[str, Any],
    registrations: dict[str, Any],
    key_binding: dict[str, Any],
    github=None,
) -> None:
    """Freshly bind the installed bytes and administrator custody material."""
    try:
        require_sha(review["main_sha"], 40)
        for name in (
            "policy_sha256",
            "code_sha256",
            "closed_evidence_sha256",
            "registrations_sha256",
            "migration_material_sha256",
        ):
            require_sha(review[name])
        rules = policy(root)
        definitions = inventory(root, rules)
        if (
            review.get("repo") != repo
            or review["policy_sha256"] != digest({"policy": rules, "definitions": definitions})
            or review["code_sha256"] != executable_digest(root)
            or review["closed_evidence_sha256"] != closure.get("retained_evidence")
            or review["registrations_sha256"] != digest(registrations)
            or review["migration_material_sha256"] != digest(material)
            or set(bindings) != set(REQUIRED_RESOURCES)
            or any(not isinstance(value, str) or not value for value in bindings.values())
            or key_binding.get("name") != "NOTEBOOKLM_STATE_KEY"
            or key_binding.get("available") is not True
            or not isinstance(key_binding.get("updated_at"), str)
            or not key_binding["updated_at"]
        ):
            _fail("CUTOVER_INDEPENDENT_INSTALLED_REVIEW_REQUIRED")
        if github is not None:
            observed = github.request("GET", "/repos/" + repo + "/git/ref/heads/main")
            if observed.get("object", {}).get("sha") != review["main_sha"]:
                _fail("CUTOVER_REVIEWED_MAIN_CHANGED")
    except (KeyError, TypeError, ValueError, OSError):
        _fail("CUTOVER_INDEPENDENT_INSTALLED_REVIEW_REQUIRED")


def build() -> CutoverApplication:
    """Build one fail-closed application; construction itself has no live effect."""
    env = _environment()
    initial_env = dict(env)
    root = Path(env["KESHER_CUTOVER_ROOT"]).resolve()
    if not root.is_dir():
        _fail("CUTOVER_TRUSTED_SERVICE_CONFIG_REQUIRED")
    loaded = _load_material(env)
    journal = _validate_journal(env["KESHER_CUTOVER_JOURNAL"])
    native = _native_bundle(_load_native_factory(env["KESHER_CUTOVER_NATIVE_FACTORY"]))
    repo = env["KESHER_GITHUB_REPOSITORY"]

    _verify_installed_review(root=root, repo=repo, github=native["github"], **loaded)

    runtime = build_runtime(
        github=native["github"],
        repo=repo,
        root=root,
        epoch=env["KESHER_CUTOVER_EPOCH"],
        owner=env["KESHER_CUTOVER_OWNER"],
        bindings=loaded["bindings"],
        boundary=native["github_boundary"],
        external_ports=native["external_ports"],
        review=loaded["review"],
        key_binding=loaded["key_binding"],
        registered_bindings=loaded["registrations"],
        separation_observer=native["separation_observer"],
        material=loaded["material"],
        closure=loaded["closure"],
        key=native["key"],
    )
    identity = ActionsIdentity(
        native["github"],
        repo=repo,
        repository_id=env["KESHER_GITHUB_REPOSITORY_ID"],
        main_sha=loaded["review"]["main_sha"],
        audience=env["KESHER_CUTOVER_OIDC_AUDIENCE"],
    )

    def review_check() -> None:
        current_env = _environment()
        if current_env != initial_env:
            _fail("CUTOVER_INSTALLED_CONFIGURATION_CHANGED")
        current = _load_material(current_env)
        if digest(current) != digest(loaded):
            _fail("CUTOVER_INSTALLED_CONFIGURATION_CHANGED")
        _validate_journal(current_env["KESHER_CUTOVER_JOURNAL"])
        _verify_installed_review(root=root, repo=repo, github=native["github"], **current)

    return CutoverApplication(
        runtime=runtime,
        identity=identity,
        journal=journal,
        epoch=env["KESHER_CUTOVER_EPOCH"],
        reviewed_revision=loaded["review"]["main_sha"],
        review_check=review_check,
    )
