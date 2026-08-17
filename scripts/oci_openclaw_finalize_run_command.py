#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import oci

RUN_COMMAND_PLUGIN = "Compute Instance Run Command"
TERMINAL = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELED"}
REQUIRED = {
    "OPENCLAW_GATEWAY_RPC_OK=true",
    "TAILSCALE_SERVE_ACTIVE=true",
    "OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true",
}
SAFE_RE = re.compile(
    r"(?:OPENCLAW_(?:FINALIZE_[A-Z0-9_]+|GATEWAY_RPC_OK|TAILSCALE_DNS|READY_URL|OFFLINE_FINALIZE_SUCCESS)|"
    r"TAILSCALE_(?:BACKEND_STATE|SERVE_ACTIVE))=[^\r\n]*"
)


def live_named(compute, compartment_id: str, name: str):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=name).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0] if live else None


def enable_run_command(compute, inst) -> None:
    cfg = inst.agent_config
    plugins = []
    found = False
    for p in list(getattr(cfg, "plugins_config", None) or []):
        desired = p.desired_state
        if p.name == RUN_COMMAND_PLUGIN:
            desired = "ENABLED"
            found = True
        plugins.append(
            oci.core.models.InstanceAgentPluginConfigDetails(name=p.name, desired_state=desired)
        )
    if not found:
        plugins.append(
            oci.core.models.InstanceAgentPluginConfigDetails(
                name=RUN_COMMAND_PLUGIN, desired_state="ENABLED"
            )
        )
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
    print("OPENCLAW_TARGET_RUN_COMMAND_PLUGIN_REQUESTED=true", flush=True)


def wait_plugin(config, compartment_id: str, instance_id: str, timeout: int) -> None:
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
            transient = (
                exc.status == 400
                and exc.code == "InvalidParameter"
                and "not present for instance" in (exc.message or "")
            )
            if exc.status in {404, 409} or transient:
                status = "REGISTERING"
            else:
                raise
        if status != last:
            print(f"OPENCLAW_TARGET_RUN_COMMAND_PLUGIN_STATUS={status}", flush=True)
            last = status
        if status == "RUNNING":
            time.sleep(15)
            return
        time.sleep(5)
    raise TimeoutError("OPENCLAW_TARGET_RUN_COMMAND_PLUGIN_NOT_RUNNING")


def safe_markers(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).strip()[-700:] for m in SAFE_RE.finditer(text)))[-60:]


def command_text() -> str:
    return r'''#!/usr/bin/env bash
set -Eeuo pipefail
FINAL=/usr/local/sbin/openclaw-offline-finalize.sh
sudo -n test -x "$FINAL"
set +e
out="$(sudo -n "$FINAL" 2>&1)"
rc=$?
set -e
printf '%s\n' "$out"
exit "$rc"
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--instance-name", default="openclaw-e2-tailscale")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()

    config = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(config)
    compartment_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    agent = oci.compute_instance_agent.ComputeInstanceAgentClient(config)

    inst = live_named(compute, compartment_id, args.instance_name)
    if not inst:
        raise RuntimeError("OPENCLAW_FINAL_VM_NOT_FOUND")
    if inst.lifecycle_state != "RUNNING":
        raise RuntimeError(f"OPENCLAW_FINAL_VM_NOT_RUNNING_{inst.lifecycle_state}")
    print(f"OPENCLAW_TARGET_INSTANCE_ID={inst.id}", flush=True)

    enable_run_command(compute, inst)
    wait_plugin(config, compartment_id, inst.id, min(args.timeout, 600))

    details = oci.compute_instance_agent.models.CreateInstanceAgentCommandDetails(
        compartment_id=compartment_id,
        execution_time_out_in_seconds=args.timeout,
        display_name="openclaw-finalize-and-verify",
        target=oci.compute_instance_agent.models.InstanceAgentCommandTarget(instance_id=inst.id),
        content=oci.compute_instance_agent.models.InstanceAgentCommandContent(
            source=oci.compute_instance_agent.models.InstanceAgentCommandSourceViaTextDetails(
                source_type="TEXT", text=command_text()
            ),
            output=oci.compute_instance_agent.models.InstanceAgentCommandOutputViaTextDetails(
                output_type="TEXT"
            ),
        ),
    )
    created = agent.create_instance_agent_command(details).data
    print(f"OPENCLAW_TARGET_AGENT_COMMAND_ID={created.id}", flush=True)

    deadline = time.time() + args.timeout + 180
    last = None
    while time.time() < deadline:
        try:
            execution = agent.get_instance_agent_command_execution(
                instance_agent_command_id=created.id,
                instance_id=inst.id,
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
            print(f"OPENCLAW_TARGET_AGENT_STATE={lifecycle} delivery={delivery}", flush=True)
            last = key
        if delivery == "EXPIRED":
            raise RuntimeError("OPENCLAW_TARGET_AGENT_COMMAND_DELIVERY_EXPIRED")

        content = getattr(execution, "content", None)
        exit_code = getattr(content, "exit_code", None) if content else None
        if lifecycle in TERMINAL or exit_code is not None:
            text = getattr(content, "text", "") or ""
            markers = safe_markers(text)
            for marker in markers:
                print(marker, flush=True)
            print(f"OPENCLAW_TARGET_AGENT_EXIT_CODE={exit_code}", flush=True)

            failures = [m for m in markers if m.startswith("OPENCLAW_FINALIZE_FAILED=")]
            if failures:
                raise RuntimeError(failures[-1])
            missing = REQUIRED.difference(set(markers))
            urls = [m.split("=", 1)[1].strip() for m in markers if m.startswith("OPENCLAW_READY_URL=")]
            if lifecycle != "SUCCEEDED" or exit_code != 0 or missing or not urls:
                suffix = ",".join(sorted(missing)) if missing else "none"
                raise RuntimeError(
                    f"OPENCLAW_TARGET_FINALIZE_FAILED state={lifecycle} exit={exit_code} missing={suffix} url={'present' if urls else 'missing'}"
                )
            url = urls[-1]
            if not re.fullmatch(r"https://[A-Za-z0-9._-]+/?", url):
                raise RuntimeError("OPENCLAW_READY_URL_INVALID")
            dns = url.removeprefix("https://").rstrip("/")
            Path(args.result_json).write_text(json.dumps({
                "status": "ready",
                "instance_id": inst.id,
                "dns": dns,
                "ready_url": url if url.endswith("/") else url + "/",
            }))
            print("OPENCLAW_TARGET_RUN_COMMAND_VERIFY_OK=true", flush=True)
            return 0
        time.sleep(5)

    raise TimeoutError("OPENCLAW_TARGET_RUN_COMMAND_WAIT_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
