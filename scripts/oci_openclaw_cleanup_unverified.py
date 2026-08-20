#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

import oci_openclaw_offline_repair_v2 as r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--state-json", required=True)
    args = ap.parse_args()

    state_path = Path(args.state_json)
    if not state_path.exists():
        print("OPENCLAW_UNVERIFIED_CLEANUP_NO_STATE=true", flush=True)
        return 0

    state = json.loads(state_path.read_text())
    cfg = r.load_config(args.config)
    compartment_id = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)
    vnet = oci.core.VirtualNetworkClient(cfg)
    block = oci.core.BlockstorageClient(cfg)

    boot_id = state["target_boot_id"]
    attachment_id = state.get("attachment_id")
    helper_id = state.get("helper_id")
    subnet_id = state["subnet_id"]

    if attachment_id:
        try:
            att = compute.get_volume_attachment(attachment_id).data
            if att.lifecycle_state not in {"DETACHED", "DETACHING"}:
                compute.detach_volume(attachment_id)
                r.wait_volume_attachment(compute, attachment_id, {"DETACHED"})
        except ServiceError as exc:
            if exc.status != 404:
                raise
        r.log("OPENCLAW_UNVERIFIED_BOOT_DETACHED")

    if helper_id:
        try:
            helper = compute.get_instance(helper_id).data
            if helper.lifecycle_state not in {"TERMINATED", "TERMINATING"}:
                compute.terminate_instance(helper_id, preserve_boot_volume=False)
                r.wait_terminated(compute, helper_id)
        except ServiceError as exc:
            if exc.status != 404:
                raise
        r.log("OPENCLAW_UNVERIFIED_HELPER_TERMINATED")

    existing = r.live_named(compute, compartment_id, r.TARGET_NAME)
    if existing:
        state.update({
            "status": "relaunched-unverified",
            "target_id": existing.id,
            "target_lifecycle_state": existing.lifecycle_state,
            "unverified_cleanup": True,
        })
        state_path.write_text(json.dumps(state))
        print("OPENCLAW_UNVERIFIED_TARGET_ALREADY_LIVE=true", flush=True)
        return 0

    boot = r.wait_boot_available(block, boot_id)
    live_e2 = [
        x for x in compute.list_instances(compartment_id=compartment_id).data
        if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == r.SHAPE
    ]
    if len(live_e2) >= 2:
        raise RuntimeError("ALWAYS_FREE_E2_LIMIT_GUARD_UNVERIFIED_RELAUNCH")

    target = compute.launch_instance(
        oci.core.models.LaunchInstanceDetails(
            availability_domain=boot.availability_domain,
            compartment_id=compartment_id,
            display_name=r.TARGET_NAME,
            shape=r.SHAPE,
            source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(
                boot_volume_id=boot_id,
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet_id,
                assign_public_ip=True,
                display_name=f"{r.TARGET_NAME}-vnic",
            ),
            metadata={"user_data": r.target_cloud_init()},
            freeform_tags={
                "managed-by": "chatgpt",
                "purpose": "openclaw-tailscale-always-free",
                "recovery": "unverified-helper-cleanup-relaunch",
            },
        )
    ).data
    target = r.wait(compute.get_instance, target.id, desired=("RUNNING",), timeout=1200)

    target_ip = None
    for _ in range(36):
        target_ip = r.instance_public_ip(compute, vnet, compartment_id, target.id)
        if target_ip:
            break
        time.sleep(5)
    if not target_ip:
        raise RuntimeError("UNVERIFIED_TARGET_PUBLIC_IP_NOT_ASSIGNED")

    state.update({
        "status": "relaunched-unverified",
        "target_id": target.id,
        "target_ip": target_ip,
        "target_lifecycle_state": target.lifecycle_state,
        "unverified_cleanup": True,
    })
    state_path.write_text(json.dumps(state))
    r.log("OPENCLAW_UNVERIFIED_TARGET_RELAUNCHED", target_id=target.id, public_ip=target_ip)
    print("OPENCLAW_UNVERIFIED_CLEANUP_COMPLETE=true", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
