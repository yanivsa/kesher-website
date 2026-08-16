#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import oci

SUCCESS = "OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true"
FAIL_PREFIX = "OPENCLAW_FINALIZE_FAILED="
SAFE_PREFIXES = (
    "OPENCLAW_FINALIZE_START=",
    "TAILSCALE_BACKEND_STATE=",
    "OPENCLAW_GATEWAY_RPC_OK=",
    "TAILSCALE_SERVE_ACTIVE=",
    "OPENCLAW_TAILSCALE_DNS=",
    "OPENCLAW_READY_URL=",
    "OPENCLAW_OFFLINE_FINALIZE_SUCCESS=",
    "OPENCLAW_FINALIZE_FAILED=",
)


def capture_text(compute, instance_id: str) -> str:
    hist = compute.capture_console_history(
        oci.core.models.CaptureConsoleHistoryDetails(
            instance_id=instance_id,
            display_name="openclaw-final-verification",
        )
    ).data
    for _ in range(36):
        obj = compute.get_console_history(hist.id).data
        if obj.lifecycle_state == "SUCCEEDED":
            break
        if obj.lifecycle_state == "FAILED":
            raise RuntimeError("OPENCLAW_CONSOLE_CAPTURE_FAILED")
        time.sleep(2)
    else:
        raise TimeoutError("OPENCLAW_CONSOLE_CAPTURE_TIMEOUT")

    data = compute.get_console_history_content(hist.id).data
    if hasattr(data, "content"):
        data = data.content
    if hasattr(data, "read"):
        data = data.read()
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return str(data)


def safe_markers(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(SAFE_PREFIXES):
            # Only the known marker vocabulary is ever printed by this verifier.
            out.append(line[-500:])
    return out[-50:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--instance-name", default="openclaw-e2-tailscale")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()

    cfg = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(cfg)
    compute = oci.core.ComputeClient(cfg)
    comp = cfg["tenancy"]

    rows = compute.list_instances(compartment_id=comp, display_name=args.instance_name).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    if not live:
        raise RuntimeError("OPENCLAW_FINAL_VM_NOT_FOUND")
    live.sort(key=lambda x: x.time_created, reverse=True)
    inst = live[0]
    print(f"OPENCLAW_CONSOLE_INSTANCE_STATE={inst.lifecycle_state}", flush=True)

    deadline = time.time() + args.timeout
    last_markers: list[str] = []
    while time.time() < deadline:
        text = capture_text(compute, inst.id)
        markers = safe_markers(text)
        if markers != last_markers:
            for line in markers:
                print(line, flush=True)
            last_markers = markers

        failures = [x for x in markers if x.startswith(FAIL_PREFIX)]
        if failures:
            raise RuntimeError(failures[-1])

        if SUCCESS in markers:
            required = {
                "OPENCLAW_GATEWAY_RPC_OK=true",
                "TAILSCALE_SERVE_ACTIVE=true",
            }
            if not required.issubset(set(markers)):
                raise RuntimeError("OPENCLAW_CONSOLE_SUCCESS_MISSING_REQUIRED_MARKERS")
            url_lines = [x for x in markers if x.startswith("OPENCLAW_READY_URL=")]
            if not url_lines:
                raise RuntimeError("OPENCLAW_CONSOLE_READY_URL_MISSING")
            url = url_lines[-1].split("=", 1)[1].strip()
            if not re.fullmatch(r"https://[A-Za-z0-9._-]+/?", url):
                raise RuntimeError("OPENCLAW_CONSOLE_READY_URL_INVALID")
            dns = url.removeprefix("https://").rstrip("/")
            Path(args.result_json).write_text(json.dumps({
                "status": "ready",
                "instance_id": inst.id,
                "dns": dns,
                "ready_url": url if url.endswith("/") else url + "/",
            }))
            print("OPENCLAW_CONSOLE_VERIFY_OK=true", flush=True)
            return 0

        time.sleep(15)

    if last_markers:
        print("OPENCLAW_CONSOLE_LAST_MARKERS_BEGIN", flush=True)
        for line in last_markers:
            print(line, flush=True)
        print("OPENCLAW_CONSOLE_LAST_MARKERS_END", flush=True)
    raise TimeoutError("OPENCLAW_CONSOLE_VERIFY_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
