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
    "OFFLINE_REPAIR_TARGET_SSH_KEY_REMOVED=true",
    "OFFLINE_REPAIR_DISK_PATCHED=true",
    "OFFLINE_REPAIR_RUN_COMMAND_COMPLETE=true",
}
MARKER_RE = re.compile(r"OFFLINE_REPAIR_[A-Z0-9_]+=[^\r\n]*")


def enable_run_command(compute, inst, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    attempt = 0
    while True:
        attempt += 1
        current = compute.get_instance(inst.id).data
        cfg = current.agent_config
        plugins = []
        found = False
        for p in list(getattr(cfg, "plugins_config", None) or []):
            desired = p.desired_state
            if p.name == RUN_COMMAND_PLUGIN:
                desired = "ENABLED"
                found = True
            plugins.append(
                oci.core.models.InstanceAgentPluginConfigDetails(
                    name=p.name,
                    desired_state=desired,
                )
            )
        if not found:
            plugins.append(
                oci.core.models.InstanceAgentPluginConfigDetails(
                    name=RUN_COMMAND_PLUGIN,
                    desired_state="ENABLED",
                )
            )
        try:
            compute.update_instance(
                current.id,
                oci.core.models.UpdateInstanceDetails(
                    agent_config=oci.core.models.UpdateInstanceAgentConfigDetails(
                        is_monitoring_disabled=getattr(cfg, "is_monitoring_disabled", None),
                        is_management_disabled=False,
                        are_all_plugins_disabled=False,
                        plugins_config=plugins,
                    )
                ),
            )
            print("OCI_RUN_COMMAND_PLUGIN_REQUESTED=true", flush=True)
            return
        except oci.exceptions.ServiceError as exc:
            transient_modify_conflict = (
                exc.status == 409
                and exc.code == "Conflict"
                and "currently being modified" in (exc.message or "")
            )
            if not transient_modify_conflict or time.time() >= deadline:
                raise
            print(
                f"OCI_RUN_COMMAND_PLUGIN_UPDATE_RETRY=attempt_{attempt}",
                flush=True,
            )
            time.sleep(min(5 * attempt, 20))


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
            # Oracle documents that enabling a plugin can take up to ten
            # minutes. During that registration window the plugin endpoint can
            # report that the requested plugin is not present yet.
            transient_not_present = (
                exc.status == 400
                and exc.code == "InvalidParameter"
                and "not present for instance" in (exc.message or "")
            )
            if exc.status in {404, 409} or transient_not_present:
                status = "REGISTERING"
            else:
                raise
        if status != last:
            print(f"OCI_RUN_COMMAND_PLUGIN_STATUS={status}", flush=True)
            last = status
        if status == "RUNNING":
            # Give the minimal cloud-init sudoers file a short window to land.
            time.sleep(20)
            return
        time.sleep(5)
    raise TimeoutError("OCI_RUN_COMMAND_PLUGIN_NOT_RUNNING")


def pinned_wrapper(script_file: str) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    sha = os.environ.get("GITHUB_SHA", "")
    if not repo or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise RuntimeError("GITHUB_REPOSITORY_OR_SHA_MISSING")
    local = Path(script_file)
    data = local.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    rel = local.as_posix().lstrip("./")
    # Pin the download to the exact workflow commit and verify the bytes before
    # executing anything as root. No credentials are carried in this script.
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{quote(rel, safe='/')}"
    wrapper = f"""#!/usr/bin/env bash
set -Eeuo pipefail
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
curl -fsSL --retry 5 --retry-delay 2 '{url}' -o "$tmp"
printf '%s  %s\n' '{digest}' "$tmp" | sha256sum -c -
sudo -n env OPENCLAW_REPAIR_NO_POWEROFF=1 bash "$tmp"
"""
    if len(wrapper.encode()) > 3900:
        raise RuntimeError("OCI_RUN_COMMAND_WRAPPER_TOO_LARGE")
    return wrapper


def safe_markers(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0).strip()[-500:] for m in MARKER_RE.finditer(text)))[-50:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--state-json", required=True)
    ap.add_argument("--script-file", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    config = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(config)
    compartment_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    agent = oci.compute_instance_agent.ComputeInstanceAgentClient(config)

    state_path = Path(args.state_json)
    state = json.loads(state_path.read_text())
    helper_id = state["helper_id"]
    inst = compute.get_instance(helper_id).data
    if inst.lifecycle_state != "RUNNING":
        raise RuntimeError(f"HELPER_NOT_RUNNING_{inst.lifecycle_state}")

    enable_run_command(compute, inst)
    wait_plugin(config, compartment_id, helper_id)

    details = oci.compute_instance_agent.models.CreateInstanceAgentCommandDetails(
        compartment_id=compartment_id,
        execution_time_out_in_seconds=args.timeout,
        display_name="openclaw-offline-disk-repair",
        target=oci.compute_instance_agent.models.InstanceAgentCommandTarget(
            instance_id=helper_id
        ),
        content=oci.compute_instance_agent.models.InstanceAgentCommandContent(
            source=oci.compute_instance_agent.models.InstanceAgentCommandSourceViaTextDetails(
                source_type="TEXT",
                text=pinned_wrapper(args.script_file),
            ),
            output=oci.compute_instance_agent.models.InstanceAgentCommandOutputViaTextDetails(
                output_type="TEXT"
            ),
        ),
    )
    created = agent.create_instance_agent_command(details).data
    print(f"OCI_AGENT_COMMAND_ID={created.id}", flush=True)

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
            print(f"OCI_AGENT_STATE={lifecycle} delivery={delivery}", flush=True)
            last = key
        if delivery == "EXPIRED":
            raise RuntimeError("OCI_AGENT_COMMAND_DELIVERY_EXPIRED")

        content = getattr(execution, "content", None)
        exit_code = getattr(content, "exit_code", None) if content else None
        if lifecycle in TERMINAL or exit_code is not None:
            text = getattr(content, "text", "") or ""
            markers = safe_markers(text)
            for marker in markers:
                print(marker, flush=True)
            print(f"OCI_AGENT_EXIT_CODE={exit_code}", flush=True)

            missing = REQUIRED.difference(set(markers))
            if lifecycle != "SUCCEEDED" or exit_code != 0 or missing:
                suffix = ",".join(sorted(missing)) if missing else "none"
                raise RuntimeError(
                    f"OCI_HELPER_REPAIR_FAILED state={lifecycle} exit={exit_code} missing={suffix}"
                )

            state["helper_repair_verified"] = True
            state["helper_repair_proof"] = "oci-run-command-exit-and-markers"
            state_path.write_text(json.dumps(state))
            print("OFFLINE_REPAIR_HELPER_RUN_COMMAND_OK=true", flush=True)
            return 0
        time.sleep(5)

    raise TimeoutError("OCI_HELPER_RUN_COMMAND_WAIT_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
