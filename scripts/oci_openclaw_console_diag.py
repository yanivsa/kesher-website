#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import time

import oci

NAME = "openclaw-e2-tailscale"


def redact(line: str) -> str:
    line = re.sub(r"https?://\S+", "<REDACTED_URL>", line)
    line = re.sub(r"\btskey-[A-Za-z0-9_-]+", "<REDACTED_TSKEY>", line)
    line = re.sub(r"\b(?:[A-Za-z0-9+/]{80,}={0,2})\b", "<REDACTED_BLOB>", line)
    return line[:500]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(cfg)
    compartment = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)

    rows = compute.list_instances(compartment_id=compartment, display_name=NAME).data
    rows = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    if not rows:
        print("CONSOLE_DIAG_INSTANCE_FOUND=false")
        return 0
    rows.sort(key=lambda x: x.time_created, reverse=True)
    inst = rows[0]
    print("CONSOLE_DIAG_INSTANCE_FOUND=true")
    print("CONSOLE_DIAG_INSTANCE_STATE=" + str(inst.lifecycle_state))
    print("CONSOLE_DIAG_CREATED=" + str(inst.time_created))

    h = compute.capture_console_history(
        oci.core.models.CaptureConsoleHistoryDetails(
            instance_id=inst.id,
            display_name="openclaw-redacted-diagnostic",
        )
    ).data
    deadline = time.time() + 180
    while time.time() < deadline:
        h = compute.get_console_history(h.id).data
        if h.lifecycle_state == "SUCCEEDED":
            break
        if h.lifecycle_state == "FAILED":
            print("CONSOLE_DIAG_CAPTURE_FAILED=true")
            return 0
        time.sleep(3)
    else:
        print("CONSOLE_DIAG_CAPTURE_TIMEOUT=true")
        return 0

    data = compute.get_console_history_content(h.id).data
    if isinstance(data, bytes):
        text = data.decode("utf-8", "replace")
    else:
        text = str(data)
    print("CONSOLE_DIAG_BYTES=" + str(len(text.encode("utf-8", "replace"))))

    markers = [
        "OPENCLAW_TAILSCALE_BOOTSTRAP_START",
        "OpenClaw",
        "TAILSCALE_AUTH_BEGIN",
        "login.tailscale.com",
        "TAILSCALE_AUTH_COMPLETE",
        "TAILSCALE_UP_FAILED",
        "OPENCLAW_TAILSCALE_READY",
        "OPENCLAW_GATEWAY_WAIT_TIMEOUT",
        "cloud-init",
        "Cloud-init",
        "ERROR",
        "Error",
        "FAILED",
        "Traceback",
    ]
    for m in markers:
        print("CONSOLE_DIAG_HAS_" + re.sub(r"[^A-Za-z0-9]+", "_", m).strip("_").upper() + "=" + ("true" if m in text else "false"))

    interesting = []
    needles = (
        "cloud-init", "cloud-init[", "openclaw", "tailscale", "error", "failed",
        "traceback", "runcmd", "package", "apt", "oom", "killed process"
    )
    for raw in text.splitlines():
        low = raw.lower()
        if any(n in low for n in needles):
            interesting.append(redact(raw))
    print("CONSOLE_DIAG_INTERESTING_BEGIN")
    for line in interesting[-60:]:
        print(line)
    print("CONSOLE_DIAG_INTERESTING_END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
