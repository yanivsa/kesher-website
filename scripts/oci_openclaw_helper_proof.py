#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

import oci

RUN_COMMAND_PLUGIN = "Compute Instance Run Command"
TERMINAL = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELED"}
REQUIRED = {
    "OPENCLAW_GATEWAY_RPC_OK=true",
    "TAILSCALE_SERVE_ACTIVE=true",
    "OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true",
    "OPENCLAW_OFFLINE_REPAIR_COMPLETE=true",
    "OPENCLAW_OFFLINE_PROOF_COMPLETE=true",
}
MARKER_RE = re.compile(r"(?:OPENCLAW|TAILSCALE)_[A-Z0-9_]+=[^\r\n]*")
URL_RE = re.compile(r"OPENCLAW_READY_URL=(https://[A-Za-z0-9._-]+/?)")


def enable_run_command(compute, inst) -> None:
    cfg = inst.agent_config
    plugins = []
    found = False
    for p in list(getattr(cfg, "plugins_config", None) or []):
        desired = p.desired_state
        if p.name == RUN_COMMAND_PLUGIN:
            desired = "ENABLED"
            found = True
        plugins.append(oci.core.models.InstanceAgentPluginConfigDetails(name=p.name, desired_state=desired))
    if not found:
        plugins.append(oci.core.models.InstanceAgentPluginConfigDetails(name=RUN_COMMAND_PLUGIN, desired_state="ENABLED"))
    compute.update_instance(
        inst.id,
        oci.core.models.UpdateInstanceDetails(
            agent_config=oci.core.models.UpdateInstanceAgentConfigDetails(
                is_monitoring_disabled=getattr(cfg, "is_monitoring_disabled", None),
                is_management_disabled=False,
                are_all_plugins_disabled=False,
                plugins_config=plugins,
            )
        ),
    )
    print("OCI_PROOF_PLUGIN_REQUESTED=true", flush=True)


def wait_plugin(config, compartment_id: str, instance_id: str, timeout: int = 600) -> None:
    client = oci.compute_instance_agent.PluginClient(config)
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            rows = client.list_instance_agent_plugins(
                compartment_id=compartment_id,
                instanceagent_id=instance_id,
                name=RUN_COMMAND_PLUGIN,
            ).data
            status = rows[0].status if rows else "MISSING"
        except oci.exceptions.ServiceError as exc:
            transient = exc.status in {404, 409} or (
                exc.status == 400 and exc.code == "InvalidParameter" and "not present for instance" in (exc.message or "")
            )
            if transient:
                status = "REGISTERING"
            else:
                raise
        if status != last:
            print(f"OCI_PROOF_PLUGIN_STATUS={status}", flush=True)
            last = status
        if status == "RUNNING":
            time.sleep(20)
            return
        time.sleep(5)
    raise TimeoutError("OCI_PROOF_PLUGIN_NOT_RUNNING")


def pinned_wrapper(script_file: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if not repo or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("GITHUB_REPOSITORY_OR_SHA_MISSING")
    local = Path(script_file)
    data = local.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rel = local.as_posix().lstrip("./")
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{quote(rel, safe='/')}"
    return f"""#!/usr/bin/env bash
set -Eeuo pipefail
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
curl -fsSL --retry 5 --retry-delay 2 '{url}' -o "$tmp"
printf '%s  %s\n' '{digest}' "$tmp" | sha256sum -c -
sudo -n bash "$tmp"
"""


def safe_markers(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).strip()[-700:] for m in MARKER_RE.finditer(text)))[-80:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--state-json", required=True)
    ap.add_argument("--script-file", required=True)
    ap.add_argument("--result-json", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    config = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(config)
    compartment_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    agent = oci.compute_instance_agent.ComputeInstanceAgentClient(config)
    state = json.loads(Path(args.state_json).read_text())
    helper_id = state["helper_id"]
    inst = compute.get_instance(helper_id).data
    if inst.lifecycle_state != "RUNNING":
        raise RuntimeError(f"PROOF_HELPER_NOT_RUNNING_{inst.lifecycle_state}")

    enable_run_command(compute, inst)
    wait_plugin(config, compartment_id, helper_id)
    details = oci.compute_instance_agent.models.CreateInstanceAgentCommandDetails(
        compartment_id=compartment_id,
        execution_time_out_in_seconds=args.timeout,
        display_name="openclaw-offline-proof",
        target=oci.compute_instance_agent.models.InstanceAgentCommandTarget(instance_id=helper_id),
        content=oci.compute_instance_agent.models.InstanceAgentCommandContent(
            source=oci.compute_instance_agent.models.InstanceAgentCommandSourceViaTextDetails(
                source_type="TEXT", text=pinned_wrapper(args.script_file)
            ),
            output=oci.compute_instance_agent.models.InstanceAgentCommandOutputViaTextDetails(output_type="TEXT"),
        ),
    )
    created = agent.create_instance_agent_command(details).data
    print(f"OCI_PROOF_AGENT_COMMAND_ID={created.id}", flush=True)
    deadline = time.time() + args.timeout + 180
    last = None
    while time.time() < deadline:
        try:
            execution = agent.get_instance_agent_command_execution(
                instance_agent_command_id=created.id,
                instance_id=helper_id,
            ).data
        except oci.exceptions.ServiceError as exc:
            if exc.status == 404:
                time.sleep(5)
                continue
            raise
        lifecycle = getattr(execution, "lifecycle_state", None)
        delivery = getattr(execution, "delivery_state", None)
        key = (lifecycle, delivery)
        if key != last:
            print(f"OCI_PROOF_AGENT_STATE={lifecycle} delivery={delivery}", flush=True)
            last = key
        content = getattr(execution, "content", None)
        exit_code = getattr(content, "exit_code", None) if content else None
        if lifecycle in TERMINAL or exit_code is not None:
            text = getattr(content, "text", "") or ""
            markers = safe_markers(text)
            for marker in markers:
                print(marker, flush=True)
            failures = [m for m in markers if m.startswith("OPENCLAW_OFFLINE_PROOF_FAILED=") or m.startswith("OPENCLAW_FINALIZE_FAILED=")]
            if failures:
                raise RuntimeError(failures[-1])
            missing = REQUIRED.difference(set(markers))
            urls = URL_RE.findall(text)
            if lifecycle != "SUCCEEDED" or exit_code != 0 or missing or not urls:
                raise RuntimeError(
                    f"OPENCLAW_OFFLINE_PROOF_FAILED state={lifecycle} exit={exit_code} missing={','.join(sorted(missing)) if missing else 'none'} url={'present' if urls else 'missing'}"
                )
            url = urls[-1]
            dns = url.removeprefix("https://").rstrip("/")
            Path(args.result_json).write_text(json.dumps({
                "status": "ready",
                "dns": dns,
                "ready_url": url if url.endswith("/") else url + "/",
                "proof": "preserved-boot-disk-finalizer-log-and-ready-file",
            }))
            print("OPENCLAW_OFFLINE_PROOF_VERIFIED=true", flush=True)
            return 0
        time.sleep(5)
    raise TimeoutError("OPENCLAW_OFFLINE_PROOF_WAIT_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
