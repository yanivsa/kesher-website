#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import oci

from oci_openclaw_bootstrap import (
    SECURITY_LIST_NAME,
    SUBNET_NAME,
    VCN_NAME,
    ensure_network,
    instance_public_ip,
    load_config,
    log,
    wait,
)
from oci_openclaw_offline_repair_v2 import (
    HELPER_NAME,
    SHAPE,
    ATTACH_NAME,
    NO_SSH_CIDR,
    cleanup_existing_helper,
    current_target_boot,
    wait_boot_available,
    wait_terminated,
    wait_volume_attachment,
)

RUN_COMMAND_PLUGIN = "Compute Instance Run Command"


def choose_run_command_image(compute, compartment_id: str):
    rows = compute.list_images(
        compartment_id=compartment_id,
        shape=SHAPE,
        operating_system="Oracle Linux",
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    rows = [x for x in rows if x.lifecycle_state == "AVAILABLE"]
    if not rows:
        raise RuntimeError("NO_ORACLE_LINUX_E2_IMAGE")
    return rows[0]


def helper_cloud_init() -> str:
    cloud_config = """#cloud-config
write_files:
  - path: /etc/sudoers.d/101-oracle-cloud-agent-run-command
    owner: root:root
    permissions: '0440'
    content: |
      ocarun ALL=(ALL) NOPASSWD:ALL
runcmd:
  - [ sh, -c, "visudo -cf /etc/sudoers.d/101-oracle-cloud-agent-run-command" ]
"""
    return base64.b64encode(cloud_config.encode()).decode()


def _ssh_rule_allows_untrusted(rule) -> bool:
    if str(getattr(rule, "protocol", "")) != "6":
        return False
    tcp = getattr(rule, "tcp_options", None)
    ports = getattr(tcp, "destination_port_range", None) if tcp else None
    if not ports:
        return True
    minimum = int(getattr(ports, "min", 0) or 0)
    maximum = int(getattr(ports, "max", 65535) or 65535)
    if not (minimum <= 22 <= maximum):
        return False
    return getattr(rule, "source", None) != NO_SSH_CIDR


def existing_closed_network(vnet, compartment_id: str):
    vcns = [
        x for x in vnet.list_vcns(compartment_id=compartment_id).data
        if x.lifecycle_state != "TERMINATED" and x.display_name == VCN_NAME
    ]
    if not vcns:
        return None
    vcn = vcns[0]

    sls = [
        x for x in vnet.list_security_lists(
            compartment_id=compartment_id, vcn_id=vcn.id
        ).data
        if x.lifecycle_state != "TERMINATED"
        and x.display_name == SECURITY_LIST_NAME
    ]
    subnets = [
        x for x in vnet.list_subnets(
            compartment_id=compartment_id, vcn_id=vcn.id
        ).data
        if x.lifecycle_state != "TERMINATED" and x.display_name == SUBNET_NAME
    ]
    if not sls or not subnets:
        return None

    sl = sls[0]
    unsafe = [
        rule for rule in (sl.ingress_security_rules or [])
        if _ssh_rule_allows_untrusted(rule)
    ]
    if unsafe:
        raise RuntimeError("OPENCLAW_RECOVERY_NETWORK_PUBLIC_SSH_NOT_CLOSED")

    log("OPENCLAW_RECOVERY_NETWORK_REUSED_NO_UPDATE", security_list=sl.id)
    return vcn, subnets[0], sl


def wait_boot_volume_detached(
    compute,
    availability_domain: str,
    compartment_id: str,
    boot_id: str,
    timeout: int = 300,
) -> None:
    deadline = time.time() + timeout
    last_states = None
    while time.time() < deadline:
        rows = compute.list_boot_volume_attachments(
            availability_domain=availability_domain,
            compartment_id=compartment_id,
            boot_volume_id=boot_id,
        ).data
        blocking = [
            row for row in rows
            if str(getattr(row, "lifecycle_state", "")) != "DETACHED"
        ]
        states = tuple(sorted(str(getattr(row, "lifecycle_state", "UNKNOWN")) for row in blocking))
        if not blocking:
            log(
                "OFFLINE_REPAIR_BOOT_DETACHED_AFTER_TARGET_TERMINATION",
                boot_id=boot_id,
            )
            print("OFFLINE_REPAIR_BOOT_DETACHED_AFTER_TARGET_TERMINATION=true", flush=True)
            return
        if states != last_states:
            log(
                "OFFLINE_REPAIR_BOOT_ATTACHMENT_DRAIN_WAIT",
                boot_id=boot_id,
                states=json.dumps(states),
            )
            last_states = states
        time.sleep(5)
    raise TimeoutError("BOOT_VOLUME_ATTACHMENT_DRAIN_TIMEOUT")


def drain_stale_data_volume_attachments(
    compute,
    compartment_id: str,
    boot_id: str,
    timeout: int = 300,
) -> None:
    """Drain stale non-boot attachments for the preserved OpenClaw boot.

    OCI exposes boot attachments and data-volume attachments through different
    APIs. A terminated recovery helper can leave a non-shareable VolumeAttachment
    visible after the BootVolumeAttachment has already drained, which makes the
    next attach_volume call fail with HTTP 409. Only detach the exact preserved
    boot volume and only when its attachment belongs to the disposable helper or
    to an instance that is already terminating/terminated. Require two clean
    observations to absorb control-plane eventual consistency.
    """
    deadline = time.time() + timeout
    clean_observations = 0
    detach_requested: set[str] = set()
    last_states = None

    while time.time() < deadline:
        rows = compute.list_volume_attachments(
            compartment_id=compartment_id,
            volume_id=boot_id,
        ).data
        blocking = [
            row for row in rows
            if str(getattr(row, "lifecycle_state", "")) != "DETACHED"
        ]
        if not blocking:
            clean_observations += 1
            if clean_observations >= 2:
                log("OFFLINE_REPAIR_STALE_DATA_ATTACHMENT_DRAINED", boot_id=boot_id)
                print("OFFLINE_REPAIR_STALE_DATA_ATTACHMENT_DRAINED=true", flush=True)
                return
            time.sleep(5)
            continue

        clean_observations = 0
        states = tuple(sorted(str(getattr(row, "lifecycle_state", "UNKNOWN")) for row in blocking))
        if states != last_states:
            log(
                "OFFLINE_REPAIR_DATA_ATTACHMENT_DRAIN_WAIT",
                boot_id=boot_id,
                states=json.dumps(states),
            )
            last_states = states

        for row in blocking:
            state = str(getattr(row, "lifecycle_state", ""))
            if state == "DETACHING":
                continue
            instance_id = str(getattr(row, "instance_id", "") or "")
            try:
                inst = compute.get_instance(instance_id).data if instance_id else None
            except oci.exceptions.ServiceError as exc:
                if exc.status == 404:
                    inst = None
                else:
                    raise
            display_name = str(getattr(inst, "display_name", "") or "") if inst else ""
            lifecycle = str(getattr(inst, "lifecycle_state", "TERMINATED") or "TERMINATED") if inst else "TERMINATED"
            safe_to_detach = (
                display_name == HELPER_NAME
                or lifecycle in {"TERMINATING", "TERMINATED"}
            )
            if not safe_to_detach:
                raise RuntimeError(
                    "OPENCLAW_RECOVERY_DATA_ATTACHMENT_ON_UNEXPECTED_LIVE_INSTANCE_"
                    + display_name
                )
            if row.id not in detach_requested:
                log(
                    "OFFLINE_REPAIR_DETACHING_STALE_DATA_ATTACHMENT",
                    attachment_id=row.id,
                    instance_id=instance_id,
                    instance_name=display_name,
                    instance_state=lifecycle,
                )
                compute.detach_volume(row.id)
                detach_requested.add(row.id)
        time.sleep(5)

    raise TimeoutError("DATA_VOLUME_ATTACHMENT_DRAIN_TIMEOUT")


def _attach_preserved_boot(compute, helper_id: str, boot_id: str, compartment_id: str):
    details = oci.core.models.AttachParavirtualizedVolumeDetails(
        instance_id=helper_id,
        volume_id=boot_id,
        display_name=ATTACH_NAME,
        is_read_only=False,
    )
    try:
        return compute.attach_volume(details).data
    except oci.exceptions.ServiceError as exc:
        message = str(getattr(exc, "message", "") or exc)
        if exc.status != 409 or "shareable" not in message.lower():
            raise
        log("OFFLINE_REPAIR_ATTACH_409_RETRY_AFTER_DRAIN", boot_id=boot_id)
        print("OFFLINE_REPAIR_ATTACH_409_RETRY_AFTER_DRAIN=true", flush=True)
        drain_stale_data_volume_attachments(compute, compartment_id, boot_id)
        return compute.attach_volume(details).data


def prepare(args) -> int:
    cfg = load_config(args.config)
    compartment_id = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)
    vnet = oci.core.VirtualNetworkClient(cfg)
    block = oci.core.BlockstorageClient(cfg)

    target, boot_id = current_target_boot(compute, block, compartment_id)
    log("OFFLINE_REPAIR_BOOT_IDENTIFIED", boot_id=boot_id)

    network = existing_closed_network(vnet, compartment_id)
    if network is None:
        network = ensure_network(vnet, compartment_id, NO_SSH_CIDR)
    _, subnet, sl = network
    cleanup_existing_helper(compute, compartment_id, boot_id)

    if target:
        log("OFFLINE_REPAIR_TERMINATING_TARGET_PRESERVE_BOOT", target_id=target.id)
        compute.terminate_instance(target.id, preserve_boot_volume=True)
        wait_terminated(compute, target.id)

    boot = wait_boot_available(block, boot_id)
    wait_boot_volume_detached(
        compute,
        boot.availability_domain,
        compartment_id,
        boot_id,
    )
    drain_stale_data_volume_attachments(compute, compartment_id, boot_id)

    live_e2 = [
        x for x in compute.list_instances(compartment_id=compartment_id).data
        if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE
    ]
    log("OFFLINE_REPAIR_LIVE_E2_BEFORE_HELPER", count=len(live_e2))
    if len(live_e2) >= 2:
        raise RuntimeError("ALWAYS_FREE_E2_LIMIT_GUARD_BEFORE_HELPER")

    image = choose_run_command_image(compute, compartment_id)
    log(
        "OFFLINE_REPAIR_HELPER_IMAGE_SELECTED",
        os=image.operating_system,
        version=image.operating_system_version,
        image_id=image.id,
    )
    helper = compute.launch_instance(
        oci.core.models.LaunchInstanceDetails(
            availability_domain=boot.availability_domain,
            compartment_id=compartment_id,
            display_name=HELPER_NAME,
            shape=SHAPE,
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image", image_id=image.id
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet.id,
                assign_public_ip=True,
                display_name=f"{HELPER_NAME}-vnic",
            ),
            agent_config=oci.core.models.LaunchInstanceAgentConfigDetails(
                is_management_disabled=False,
                are_all_plugins_disabled=False,
                plugins_config=[
                    oci.core.models.InstanceAgentPluginConfigDetails(
                        name=RUN_COMMAND_PLUGIN,
                        desired_state="ENABLED",
                    )
                ],
            ),
            metadata={"user_data": helper_cloud_init()},
            freeform_tags={
                "managed-by": "chatgpt",
                "purpose": "openclaw-offline-repair-helper-run-command",
            },
        )
    ).data
    helper = wait(compute.get_instance, helper.id, desired=("RUNNING",), timeout=1200)

    helper_ip = None
    for _ in range(36):
        helper_ip = instance_public_ip(compute, vnet, compartment_id, helper.id)
        if helper_ip:
            break
        time.sleep(5)
    if not helper_ip:
        raise RuntimeError("HELPER_OUTBOUND_PUBLIC_IP_NOT_ASSIGNED")
    log("OFFLINE_REPAIR_HELPER_RUNNING", helper_id=helper.id, transport="oci-run-command")

    attach = _attach_preserved_boot(compute, helper.id, boot_id, compartment_id)
    attach = wait_volume_attachment(compute, attach.id, {"ATTACHED"})
    log("OFFLINE_REPAIR_BOOT_ATTACHED_AS_DATA", attachment_id=attach.id)

    result = {
        "status": "prepared",
        "target_boot_id": boot_id,
        "target_availability_domain": boot.availability_domain,
        "helper_id": helper.id,
        "helper_ip": helper_ip,
        "helper_image_id": image.id,
        "helper_os": image.operating_system,
        "helper_os_version": image.operating_system_version,
        "attachment_id": attach.id,
        "subnet_id": subnet.id,
        "security_list_id": sl.id,
        "shape": SHAPE,
        "helper_transport": "oci-run-command",
    }
    Path(args.result_json).write_text(json.dumps(result))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()
    return prepare(args)


if __name__ == "__main__":
    raise SystemExit(main())
