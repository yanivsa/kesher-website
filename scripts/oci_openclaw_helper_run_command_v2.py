#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import quote

import oci_openclaw_helper_run_command as base


def pinned_wrapper(script_file: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if not repo or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("GITHUB_REPOSITORY_OR_SHA_MISSING")

    primary = Path(script_file)
    files = [primary]
    if primary.name == "openclaw_offline_mount_repair_early.sh":
        files.append(primary.with_name("openclaw_offline_mount_repair_base.sh"))

    commands = [
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        "root=$(mktemp -d)",
        "trap 'rm -rf \"$root\"' EXIT",
    ]
    for local in files:
        data = local.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        rel = local.as_posix().lstrip("./")
        url = f"https://raw.githubusercontent.com/{repo}/{sha}/{quote(rel, safe='/')}"
        commands.extend([
            f"mkdir -p \"$root/{Path(rel).parent.as_posix()}\"",
            f"curl -fsSL --retry 5 --retry-delay 2 '{url}' -o \"$root/{rel}\"",
            f"printf '%s  %s\\n' '{digest}' \"$root/{rel}\" | sha256sum -c -",
        ])

    primary_rel = primary.as_posix().lstrip("./")
    commands.extend([
        "cd \"$root\"",
        f"sudo -n env OPENCLAW_REPAIR_NO_POWEROFF=1 bash '{primary_rel}'",
    ])
    wrapper = "\n".join(commands) + "\n"
    if len(wrapper.encode()) > 3900:
        raise RuntimeError("OCI_RUN_COMMAND_WRAPPER_TOO_LARGE")
    return wrapper


base.pinned_wrapper = pinned_wrapper

if __name__ == "__main__":
    raise SystemExit(base.main())
