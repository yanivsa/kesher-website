#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import oci

DEFAULT_INSTANCE_NAME = "openclaw-e2-plan-b"
RUN_COMMAND_PLUGIN = "Compute Instance Run Command"
TERMINAL = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELED", "EXPIRED"}
STUCK_ACCEPTED_SECONDS = 120


def find_instance(compute, compartment_id: str, instance_name: str):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=instance_name).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    if not live:
        raise RuntimeError("OPENCLAW_INSTANCE_NOT_FOUND")
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0]


def enable_run_command(compute, inst):
    cfg = inst.agent_config
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
    print("OCI_RUN_COMMAND_PLUGIN_REQUESTED=true", flush=True)
    time.sleep(15)


def print_run_command_plugin_status(plugin_client, compartment_id: str, instance_id: str):
    try:
        plugin = plugin_client.get_instance_agent_plugin(
            instanceagent_id=instance_id,
            compartment_id=compartment_id,
            plugin_name=RUN_COMMAND_PLUGIN,
        ).data
        status = getattr(plugin, "status", None) or "UNKNOWN"
        print(f"OCI_RUN_COMMAND_PLUGIN_STATUS={status}", flush=True)
    except oci.exceptions.ServiceError as exc:
        print(f"OCI_RUN_COMMAND_PLUGIN_STATUS=ERROR_{exc.status}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--script-file", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--instance-name", default=DEFAULT_INSTANCE_NAME)
    args = ap.parse_args()

    config = oci.config.from_file(args.config, "DEFAULT")
    oci.config.validate_config(config)
    compartment_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    agent = oci.compute_instance_agent.ComputeInstanceAgentClient(config)
    plugin_client = oci.compute_instance_agent.PluginClient(config)
    inst = find_instance(compute, compartment_id, args.instance_name)
    print(f"OCI_INSTANCE_NAME={args.instance_name}", flush=True)
    print(f"OCI_INSTANCE_STATE={inst.lifecycle_state}", flush=True)
    enable_run_command(compute, inst)
    print_run_command_plugin_status(plugin_client, compartment_id, inst.id)
    script = Path(args.script_file).read_text()

    details = oci.compute_instance_agent.models.CreateInstanceAgentCommandDetails(
        compartment_id=compartment_id,
        execution_time_out_in_seconds=args.timeout,
        display_name="openclaw-maintenance",
        target=oci.compute_instance_agent.models.InstanceAgentCommandTarget(instance_id=inst.id),
        content=oci.compute_instance_agent.models.InstanceAgentCommandContent(
            source=oci.compute_instance_agent.models.InstanceAgentCommandSourceViaTextDetails(
                source_type="TEXT", text=script
            ),
            output=oci.compute_instance_agent.models.InstanceAgentCommandOutputViaTextDetails(
                output_type="TEXT"
            ),
        ),
    )
    created = agent.create_instance_agent_command(details).data
    print(f"OCI_AGENT_COMMAND_ID={created.id}", flush=True)
    print(f"OCI_INSTANCE_ID={inst.id}", flush=True)

    deadline = time.time() + args.timeout + 120
    last = None
    accepted_since = None
    reboot_attempted = False
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
        state = getattr(execution, "lifecycle_state", None)
        delivery = getattr(execution, "delivery_state", None)
        key = (state, delivery)
        if key != last:
            print(f"OCI_AGENT_STATE={state} delivery={delivery}", flush=True)
            last = key

        if state == "ACCEPTED" and delivery == "VISIBLE":
            if accepted_since is None:
                accepted_since = time.time()
            elif not reboot_attempted and time.time() - accepted_since >= STUCK_ACCEPTED_SECONDS:
                print("OCI_AGENT_STUCK_ACCEPTED=true", flush=True)
                print_run_command_plugin_status(plugin_client, compartment_id, inst.id)
                compute.instance_action(inst.id, "SOFTRESET")
                reboot_attempted = True
                print("OCI_AGENT_SOFTRESET_REQUESTED=true", flush=True)
                deadline = max(deadline, time.time() + args.timeout + 120)
        else:
            accepted_since = None

        content = getattr(execution, "content", None)
        exit_code = getattr(content, "exit_code", None) if content else None
        if state in TERMINAL or exit_code is not None:
            text = getattr(content, "text", "") or ""
            message = getattr(content, "message", "") or ""
            print(f"OCI_AGENT_EXIT_CODE={exit_code}", flush=True)
            if message:
                print("OCI_AGENT_MESSAGE=" + json.dumps(message[:1000]), flush=True)
            print("OCI_AGENT_OUTPUT_BEGIN", flush=True)
            print(text, flush=True)
            print("OCI_AGENT_OUTPUT_END", flush=True)
            return 0 if exit_code in (None, 0) and state not in {"FAILED", "TIMED_OUT", "CANCELED", "EXPIRED"} else 2
        time.sleep(5)
    raise TimeoutError("OCI_AGENT_COMMAND_WAIT_TIMEOUT")


if __name__ == "__main__":
    raise SystemExit(main())
