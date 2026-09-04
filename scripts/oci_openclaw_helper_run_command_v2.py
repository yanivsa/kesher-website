#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import oci_openclaw_helper_run_command as base


CLOUDFLARE_REPAIR = "openclaw_offline_mount_repair_cloudflare.sh"
EARLY_REPAIR = "openclaw_offline_mount_repair_early.sh"
BASE_REPAIR = "openclaw_offline_mount_repair_base.sh"


def pinned_wrapper(script_file: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if not repo or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("GITHUB_REPOSITORY_OR_SHA_MISSING")

    primary = Path(script_file)
    files = [primary]
    if primary.name == CLOUDFLARE_REPAIR:
        files.extend([
            primary.with_name(EARLY_REPAIR),
            primary.with_name(BASE_REPAIR),
        ])
    elif primary.name == EARLY_REPAIR:
        files.extend([primary.with_name(BASE_REPAIR)])

    # Preserve deterministic order while avoiding duplicate downloads.
    unique_files: list[Path] = []
    seen: set[str] = set()
    for local in files:
        rel = local.as_posix().lstrip("./")
        if rel not in seen:
            unique_files.append(local)
            seen.add(rel)
    files = unique_files

    commands = [
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        "root=$(mktemp -d)",
        "cleanup() { rc=$?; rm -rf \"$root\"; if [ \"$rc\" -ne 0 ]; then echo OFFLINE_REPAIR_WRAPPER_FAILED_RC=$rc; fi; exit \"$rc\"; }",
        "trap cleanup EXIT",
        "echo OFFLINE_REPAIR_WRAPPER_STARTED=true",
    ]
    for local in files:
        data = local.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        rel = local.as_posix().lstrip("./")
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{quote(rel, safe='/')}"
        commands.extend([
            f"mkdir -p \"$root/{Path(rel).parent.as_posix()}\"",
            f"curl -fsSL --retry 5 --retry-all-errors --retry-delay 2 '{url}' -o \"$root/{rel}\"",
            f"printf '%s  %s\\n' '{digest}' \"$root/{rel}\" | sha256sum -c -",
            f"echo OFFLINE_REPAIR_WRAPPER_FETCHED_{local.name.upper().replace('.', '_').replace('-', '_')}=true",
        ])

    primary_rel = primary.as_posix().lstrip("./")
    commands.extend([
        "cd \"$root\"",
        "sudo_deadline=$((SECONDS + 180))",
        "until sudo -n true 2>/dev/null; do",
        "  if [ \"$SECONDS\" -ge \"$sudo_deadline\" ]; then echo OFFLINE_REPAIR_WRAPPER_SUDO_NOT_READY=true; exit 1; fi",
        "  sleep 5",
        "done",
        "echo OFFLINE_REPAIR_WRAPPER_SUDO_READY=true",
        f"sudo -n env OPENCLAW_REPAIR_NO_POWEROFF=1 bash '{primary_rel}'",
    ])
    wrapper = "\n".join(commands) + "\n"
    if len(wrapper.encode()) > 3900:
        raise RuntimeError("OCI_RUN_COMMAND_WRAPPER_TOO_LARGE")
    return wrapper


_original_enable_run_command = base.enable_run_command


def enable_run_command_with_conflict_retry(compute, inst) -> None:
    """Retry only OCI's transient post-launch instance-modification conflict."""
    deadline = time.time() + 180
    attempt = 0
    while True:
        attempt += 1
        latest = compute.get_instance(inst.id).data
        try:
            _original_enable_run_command(compute, latest)
            return
        except base.oci.exceptions.ServiceError as exc:
            transient = (
                exc.status == 409
                and exc.code == "Conflict"
                and "currently being modified" in (exc.message or "").lower()
            )
            if not transient or time.time() >= deadline:
                raise
            delay = min(5 * attempt, 20)
            print(
                f"OCI_RUN_COMMAND_PLUGIN_UPDATE_CONFLICT_RETRY attempt={attempt} delay={delay}",
                flush=True,
            )
            time.sleep(delay)


base.pinned_wrapper = pinned_wrapper
base.enable_run_command = enable_run_command_with_conflict_retry

if __name__ == "__main__":
    raise SystemExit(base.main())
