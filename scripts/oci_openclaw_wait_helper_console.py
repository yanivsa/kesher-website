#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

SUCCESS = "OFFLINE_REPAIR_DISK_PATCHED=true"
REQUIRED = {
    "OFFLINE_REPAIR_TARGET_SSH_KEY_REMOVED=true",
    SUCCESS,
}
FAIL_PREFIXES = (
    "OFFLINE_REPAIR_SCRIPT_FAILED_RC=",
    "OFFLINE_REPAIR_DATA_DISK_NOT_FOUND=true",
    "OFFLINE_REPAIR_TARGET_ROOT_NOT_FOUND=true",
)
MARKER_RE = re.compile(r"(OFFLINE_REPAIR_[A-Z0-9_]+=[^\r\n]*)")


def delete_history(compute, history_id: str) -> None:
    try:
        compute.delete_console_history(history_id)
    except ServiceError as exc:
        if exc.status != 404:
            print(f"OFFLINE_REPAIR_CONSOLE_HISTORY_DELETE_WARN={exc.status}", flush=True)


def purge_histories(compute, compartment_id: str, instance_id: str) -> None:
    rows = compute.list_console_histories(
        compartment_id=compartment_id,
        instance_id=instance_id,
        limit=50,
    ).data
    for row in rows:
        delete_history(compute, row.id)
    if rows:
        print(f"OFFLINE_REPAIR_CONSOLE_HISTORIES_PURGED={len(rows)}", flush=True)


def capture_text(compute, instance_id: str) -> str:
    hist = compute.capture_console_history(
        oci.core.models.CaptureConsoleHistoryDetails(
            instance_id=instance_id,
            display_name="openclaw-helper-repair-verification",
        )
    ).data
    try:
        for _ in range(60):
            obj = compute.get_console_history(hist.id).data
            if obj.lifecycle_state == "SUCCEEDED":
                break
            if obj.lifecycle_state == "FAILED":
                raise RuntimeError("HELPER_CONSOLE_CAPTURE_FAILED")
            time.sleep(2)
        else:
            raise TimeoutError("HELPER_CONSOLE_CAPTURE_TIMEOUT")

        data = compute.get_console_history_content(hist.id).data
        if hasattr(data, "content"):
            data = data.content
        if hasattr(data, "read"):
            data = data.read()
        if isinstance(data, bytes):
            return data.decode("utf-8", "replace")
        return str(data)
    finally:
        delete_history(compute, hist.id)


def markers(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        match = MARKER_RE.search(raw)
        if match:
            out.append(match.group(1).strip()[-500:])
    # Preserve order while removing duplicates from repeated console captures.
    return list(dict.fromkeys(out))[-100:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--state-json", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    cfg = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(cfg)
    compute = oci.core.ComputeClient(cfg)
    state_path = Path(args.state_json)
    state = json.loads(state_path.read_text())
    helper_id = state["helper_id"]

    purge_histories(compute, cfg["tenancy"], helper_id)
    deadline = time.time() + args.timeout
    last: list[str] = []

    while time.time() < deadline:
        helper = compute.get_instance(helper_id).data
        if helper.lifecycle_state in {"TERMINATED", "TERMINATING"}:
            raise RuntimeError("HELPER_TERMINATED_BEFORE_REPAIR_COMPLETED")

        current = markers(capture_text(compute, helper_id))
        if current != last:
            for line in current:
                print(line, flush=True)
            last = current

        failures = [line for line in current if line.startswith(FAIL_PREFIXES)]
        if failures:
            raise RuntimeError(failures[-1])

        if SUCCESS in current:
            missing = REQUIRED.difference(set(current))
            if missing:
                raise RuntimeError(
                    "HELPER_SUCCESS_MISSING_REQUIRED_MARKERS_" + "_".join(sorted(missing))
                )
            state["helper_repair_verified"] = True
            state_path.write_text(json.dumps(state))
            print("OFFLINE_REPAIR_HELPER_CONSOLE_OK=true", flush=True)
            return 0

        time.sleep(15)

    if last:
        print("OFFLINE_REPAIR_HELPER_LAST_MARKERS_BEGIN", flush=True)
        for line in last:
            print(line, flush=True)
        print("OFFLINE_REPAIR_HELPER_LAST_MARKERS_END", flush=True)
    raise TimeoutError("HELPER_REPAIR_CONSOLE_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
