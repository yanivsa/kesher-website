#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

from oci_openclaw_bootstrap import (
    ensure_network,
    instance_public_ip,
    load_config,
    log,
    wait,
)

NAME = "openclaw-e2-plan-b"
SHAPE = "VM.Standard.E2.1.Micro"
RUN_COMMAND_PLUGIN = "Compute Instance Run Command"


def existing_instance(compute, compartment_id):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=NAME).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    if not live:
        return None
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0]


def ensure_run_command_plugin(compute, instance):
    """Enable only the OCI management path we need, preserving other plugin choices."""
    cfg = instance.agent_config
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
    log(
        "OCI_AGENT_CONFIG_BEFORE",
        management_disabled=getattr(cfg, "is_management_disabled", None),
        all_plugins_disabled=getattr(cfg, "are_all_plugins_disabled", None),
        run_command_present=found,
    )
    compute.update_instance(
        instance.id,
        oci.core.models.UpdateInstanceDetails(
            agent_config=oci.core.models.UpdateInstanceAgentConfigDetails(
                is_monitoring_disabled=getattr(cfg, "is_monitoring_disabled", None),
                is_management_disabled=False,
                are_all_plugins_disabled=False,
                plugins_config=plugins,
            )
        ),
    )
    for _ in range(24):
        current = compute.get_instance(instance.id).data
        c = current.agent_config
        rc = next((p for p in (c.plugins_config or []) if p.name == RUN_COMMAND_PLUGIN), None)
        if (
            getattr(c, "is_management_disabled", None) is False
            and getattr(c, "are_all_plugins_disabled", None) is False
            and rc is not None
            and rc.desired_state == "ENABLED"
        ):
            log("OCI_RUN_COMMAND_PLUGIN_ENABLED", desired_state=rc.desired_state)
            time.sleep(15)
            return current
        time.sleep(5)
    log("OCI_RUN_COMMAND_PLUGIN_ENABLE_NOT_CONFIRMED")
    return compute.get_instance(instance.id).data


def run_agent_probe(config, compartment_id, instance_id):
    """Use OCI Run Command without reopening SSH to inspect maintenance access."""
    script = r'''set +e
echo "RUN_USER=$(id -un)"
echo "RUN_UID=$(id -u)"
if sudo -n true 2>/dev/null; then echo "RUN_SUDO_NOPASSWD=true"; else echo "RUN_SUDO_NOPASSWD=false"; fi
printf 'OPENCLAW_BIN='; command -v openclaw || true
[ -x /usr/local/bin/openclaw ] && echo 'OPENCLAW_USR_LOCAL=true' || echo 'OPENCLAW_USR_LOCAL=false'
[ -x /usr/bin/openclaw ] && echo 'OPENCLAW_USR_BIN=true' || echo 'OPENCLAW_USR_BIN=false'
systemctl is-active oracle-cloud-agent 2>/dev/null | sed 's/^/ORACLE_AGENT=/' || true
systemctl is-active tailscaled 2>/dev/null | sed 's/^/TAILSCALED=/' || true
'''
    try:
        agent = oci.compute_instance_agent.ComputeInstanceAgentClient(config)
        details = oci.compute_instance_agent.models.CreateInstanceAgentCommandDetails(
            compartment_id=compartment_id,
            execution_time_out_in_seconds=240,
            display_name="openclaw-maintenance-probe",
            target=oci.compute_instance_agent.models.InstanceAgentCommandTarget(instance_id=instance_id),
            content=oci.compute_instance_agent.models.InstanceAgentCommandContent(
                source=oci.compute_instance_agent.models.InstanceAgentCommandSourceViaTextDetails(
                    source_type="TEXT", text=script
                ),
                output=oci.compute_instance_agent.models.InstanceAgentCommandOutputViaTextDetails(
                    output_type="TEXT"
                ),
            ),
        )
        command = agent.create_instance_agent_command(details).data
        log("OCI_AGENT_PROBE_CREATED", command_id=command.id)
        deadline = time.time() + 330
        while time.time() < deadline:
            try:
                execution = agent.get_instance_agent_command_execution(
                    instance_agent_command_id=command.id,
                    instance_id=instance_id,
                ).data
            except ServiceError as exc:
                if exc.status == 404:
                    time.sleep(5)
                    continue
                raise
            state = getattr(execution, "lifecycle_state", None)
            delivery = getattr(execution, "delivery_state", None)
            content = getattr(execution, "content", None)
            exit_code = getattr(content, "exit_code", None) if content else None
            if exit_code is not None or state in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELED", "EXPIRED"}:
                text = getattr(content, "text", "") or ""
                log("OCI_AGENT_PROBE_DONE", state=state, delivery=delivery, exit_code=exit_code)
                print("OCI_AGENT_PROBE_OUTPUT_BEGIN", flush=True)
                print(text, flush=True)
                print("OCI_AGENT_PROBE_OUTPUT_END", flush=True)
                return True
            time.sleep(5)
        log("OCI_AGENT_PROBE_TIMEOUT")
        return False
    except ServiceError as exc:
        log("OCI_AGENT_PROBE_UNAVAILABLE", status=exc.status, code=exc.code, message=json.dumps((exc.message or "")[:200]))
        return False


def choose_image(compute, compartment_id):
    for os_name in ("Canonical Ubuntu", "Oracle Linux"):
        rows = compute.list_images(
            compartment_id=compartment_id,
            shape=SHAPE,
            operating_system=os_name,
            sort_by="TIMECREATED",
            sort_order="DESC",
        ).data
        rows = [x for x in rows if x.lifecycle_state == "AVAILABLE"]
        if rows:
            image = rows[0]
            log("E2_IMAGE_SELECTED", os=os_name, image_id=image.id, display_name=json.dumps(image.display_name))
            return os_name, image
    raise RuntimeError("NO_ALWAYS_FREE_COMPATIBLE_E2_IMAGE_FOUND")


def cloud_init():
    text = r'''#cloud-config
package_update: true
packages:
  - curl
  - ca-certificates
  - git
runcmd:
  - [ bash, -lc, "if ! swapon --show | grep -q /swapfile; then (fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048); chmod 600 /swapfile; mkswap /swapfile; swapon /swapfile; grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab; fi" ]
  - [ bash, -lc, "export HOME=/root; export OPENCLAW_NO_PROMPT=1; curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --no-prompt --no-onboard >>/var/log/openclaw-install.log 2>&1" ]
  - [ bash, -lc, "OPENCLAW_BIN=$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1); test -n \"$OPENCLAW_BIN\"; \"$OPENCLAW_BIN\" --version >/var/lib/openclaw-version.txt 2>&1; touch /var/lib/openclaw-installed" ]
'''
    return base64.b64encode(text.encode()).decode()


def retryable_capacity_error(exc: ServiceError) -> bool:
    text = f"{exc.code or ''} {exc.message or ''}".lower()
    needles = (
        "out of host capacity",
        "outofhostcapacity",
        "not available in the availability domain",
        "shape is not available",
        "shape not found",
        "unsupported shape",
    )
    return any(x in text for x in needles)


def retryable_ad_placement_error(exc: ServiceError) -> bool:
    return exc.status == 404 and (exc.code or "") == "NotAuthorizedOrNotFound"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ssh-public-key-file", required=True)
    ap.add_argument("--bootstrap-cidr", required=True)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()

    config = load_config(args.config)
    compartment_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    vnet = oci.core.VirtualNetworkClient(config)
    identity = oci.identity.IdentityClient(config)

    existing = existing_instance(compute, compartment_id)
    if existing:
        ip = instance_public_ip(compute, vnet, compartment_id, existing.id)
        log("OPENCLAW_PLAN_B_EXISTS", state=existing.lifecycle_state, shape=existing.shape, public_ip=ip)
        existing = ensure_run_command_plugin(compute, existing)
        agent_ok = run_agent_probe(config, compartment_id, existing.id)
        result = {
            "status": "existing",
            "instance_id": existing.id,
            "lifecycle_state": existing.lifecycle_state,
            "shape": existing.shape,
            "public_ip": ip,
            "agent_probe_ok": agent_ok,
        }
        Path(args.result_json).write_text(json.dumps(result))
        return 0

    _, subnet, sl = ensure_network(vnet, compartment_id, args.bootstrap_cidr)
    os_name, image = choose_image(compute, compartment_id)
    ssh_key = Path(args.ssh_public_key_file).read_text().strip()
    ads = identity.list_availability_domains(compartment_id=compartment_id).data

    errors = []
    for ad in ads:
        log("E2_INSTANCE_LAUNCH_ATTEMPT", ad=ad.name, shape=SHAPE)
        try:
            details = oci.core.models.LaunchInstanceDetails(
                availability_domain=ad.name,
                compartment_id=compartment_id,
                display_name=NAME,
                shape=SHAPE,
                source_details=oci.core.models.InstanceSourceViaImageDetails(
                    source_type="image",
                    image_id=image.id,
                ),
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=subnet.id,
                    assign_public_ip=True,
                    display_name=f"{NAME}-vnic",
                ),
                metadata={
                    "ssh_authorized_keys": ssh_key,
                    "user_data": cloud_init(),
                },
                freeform_tags={"managed-by": "chatgpt", "purpose": "openclaw-always-free-plan-b"},
            )
            instance = compute.launch_instance(details).data
            instance = wait(compute.get_instance, instance.id, desired=("RUNNING",), timeout=1200)
            ip = None
            for _ in range(24):
                ip = instance_public_ip(compute, vnet, compartment_id, instance.id)
                if ip:
                    break
                time.sleep(5)
            result = {
                "status": "created",
                "instance_id": instance.id,
                "availability_domain": ad.name,
                "lifecycle_state": instance.lifecycle_state,
                "shape": instance.shape,
                "memory_gb": 1,
                "public_ip": ip,
                "os": os_name,
                "security_list_id": sl.id,
                "plan": "B",
            }
            Path(args.result_json).write_text(json.dumps(result))
            log("OPENCLAW_PLAN_B_CREATED", ad=ad.name, state=instance.lifecycle_state, public_ip=ip)
            return 0
        except ServiceError as exc:
            err = {"status": exc.status, "code": exc.code, "message": (exc.message or "")[:240], "ad": ad.name}
            errors.append(err)
            log("E2_INSTANCE_LAUNCH_FAILED", **err)
            if retryable_capacity_error(exc) or retryable_ad_placement_error(exc):
                continue
            if exc.status == 400 and "shape" in (exc.message or "").lower():
                continue
            result = {"status": "blocked", "shape": SHAPE, "errors": errors}
            Path(args.result_json).write_text(json.dumps(result))
            return 0

    result = {"status": "blocked_after_all_ads", "shape": SHAPE, "errors": errors}
    Path(args.result_json).write_text(json.dumps(result))
    log("E2_PLAN_B_ALL_ADS_EXHAUSTED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log("OCI_PLAN_B_FAILED", type=type(exc).__name__, message=json.dumps(str(exc)[:300]))
        raise
