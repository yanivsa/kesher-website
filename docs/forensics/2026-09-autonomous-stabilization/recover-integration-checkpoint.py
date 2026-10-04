#!/usr/bin/env python3
"""Verify the non-ready checkpoint; optionally restore raw bytes to a fresh local checkout.

No fetch, push, PR, deployment, provider request, state write, or recovered code
execution occurs. The default is verification only. An explicit --restore-dir
creates a detached checkout at the historical reconstruction base, never main.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MANIFEST = HERE / "integration-unvalidated-recovery-manifest-20261002.json"


def verify():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    archive = HERE / manifest["archive_name"]
    if archive.is_symlink() or hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["archive_sha256"]:
        raise ValueError("Recovery archive checksum mismatch")
    expected = {row["path"]: row for row in manifest["files"]}
    if len(expected) != len(manifest["files"]):
        raise ValueError("Duplicate manifest paths")
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if {member.name for member in members} != set(expected) or len(members) != len(expected):
            raise ValueError("Archive inventory differs from manifest")
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or any(part in {".", "..", ""} for part in name.parts) or not member.isfile():
                raise ValueError("Unsafe archive path or non-regular member")
            row = expected[member.name]
            data = tar.extractfile(member).read()
            if (len(data) != row["size"] or member.mode != int(row["mode"], 8)
                    or hashlib.sha256(data).hexdigest() != row["sha256"]):
                raise ValueError("Recovery member identity mismatch: " + member.name)
    return manifest, archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore-dir", type=Path, help="Explicit fresh directory for unvalidated historical draft")
    args = parser.parse_args()
    manifest, archive = verify()
    print(f"Verified {len(manifest['files'])} members; archive {manifest['archive_sha256']}")
    print("Integration BLOCKED. This archive contains an unvalidated draft with known unresolved defects.")
    if args.restore_dir is None:
        return 0
    target = args.restore_dir.expanduser().absolute()
    if target.exists() or target.is_symlink():
        parser.error("Restore destination must not exist")
    subprocess.run([
        "git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
        "-c", "protocol.allow=never", "-C", str(REPO), "worktree", "add",
        "--detach", str(target), manifest["base_sha"],
    ], check=True)
    trusted_root = target.resolve()
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            output = target / member.name
            # Do not traverse a base-tree link, even for a safe archive member.
            parent = output.parent
            while parent != target:
                if parent.is_symlink():
                    raise ValueError("Base checkout has a linked archive parent")
                parent = parent.parent
            if output.is_symlink() or not output.resolve().is_relative_to(trusted_root):
                raise ValueError("Refusing linked/outside restore target")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(tar.extractfile(member).read())
            output.chmod(member.mode)
    for row in manifest["files"]:
        output = target / row["path"]
        if hashlib.sha256(output.read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Restored bytes differ from manifest")
    (target / "UNVALIDATED_RECOVERY_NOTICE.txt").write_text(
        "Historical unvalidated integration draft. Known stale authority pins and incomplete tests.\n"
        "Do not push, deploy, activate, execute providers or treat this as handover approval.\n"
        "Use integration-handoff-20261002.md in the source checkpoint for manual finalization.\n",
        encoding="utf-8",
    )
    print(f"Restored raw draft at {target}; detached historical base {manifest['base_sha']}.")
    print("No recovered code was executed. The checkpoint branch and remote refs were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
