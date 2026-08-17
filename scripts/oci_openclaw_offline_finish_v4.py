#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

from oci_openclaw_bootstrap import instance_public_ip, load_config, log, wait
from oci_openclaw_offline_repair_v2 import (
    SHAPE,
    TARGET_NAME,
    wait_boot_available,
    wait_terminated,
    wait_volume_attachment,
)


def target_cloud_init() -> str:
    payload = r'''#!/usr/bin/env bash
set -Eeuo pipefail
exec > >(tee -a /var/log/openclaw-target-cloud-init.log /dev/console) 2>&1

echo OPENCLAW_TARGET_CLOUD_INIT_START=true
for i in $(seq 1 120); do
  [ -x /usr/local/sbin/openclaw-offline-finalize.sh ] && break
  sleep 2
done
if [ ! -x /usr/local/sbin/openclaw-offline-finalize.sh ]; then
  echo OPENCLAW_TARGET_CLOUD_INIT_FAILED=FINALIZER_MISSING
  exit 31
fi

systemctl daemon-reload || true
set +e
systemctl start openclaw-offline-finalize.service
rc=$?
set -e
if [ "$rc" -ne 0 ]; then
  echo OPENCLAW_TARGET_CLOUD_INIT_SYSTEMD_FALLBACK=true
  /usr/local/sbin/openclaw-offline-finalize.sh
fi

echo OPENCLAW_TARGET_CLOUD_INIT_COMPLETE=true
'''
    encoded = base64.b64encode(payload.encode()).decode()
    if len(encoded.encode()) > 20_000:
        raise RuntimeError("TARGET_CLOUD_INIT_TOO_LARGE")
    return encoded


def finish(args) -> int:
    cfg = load_config(args.config)
    compartment_id = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)
    vnet = oci.core.VirtualNetworkClient(cfg)
    block = oci.core.BlockstorageClient(cfg)
    state = json.loads(Path(args.state_json).read_text())

    boot_id = state["target_boot_id"]
    attachment_id = state["attachment_id"]
    helper_id = state["helper_id"]
    subnet_id = state["subnet_id"]

    try:
        att = compute.get_volume_attachment(attachment_id).data
        if att.lifecycle_state not in {"DETACHED", "DETACHING"}:
            compute.detach_volume(attachment_id)
            wait_volume_attachment(compute, attachment_id, {"DETACHED"})
    except ServiceError as exc:
        if exc.status != 404:
            raise
    log("OFFLINE_REPAIR_BOOT_DETACHED_FROM_HELPER")

    helper = compute.get_instance(helper_id).data
    if helper.lifecycle_state not in {"TERMINATED", "TERMINATING"}:
        compute.terminate_instance(helper_id, preserve_boot_volume=False)
        wait_terminated(compute, helper_id)
    log("OFFLINE_REPAIR_HELPER_TERMINATED")

    boot = wait_boot_available(block, boot_id)
    live_e2 = [
        x for x in compute.list_instances(compartment_id=compartment_id).data
        if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE
    ]
    if len(live_e2) >= 2:
        raise RuntimeError("ALWAYS_FREE_E2_LIMIT_GUARD_BEFORE_TARGET_RELAUNCH")

    target = compute.launch_instance(
        oci.core.models.LaunchInstanceDetails(
            availability_domain=boot.availability_domain,
            compartment_id=compartment_id,
            display_name=TARGET_NAME,
            shape=SHAPE,
            source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(
                boot_volume_id=boot_id,
            ),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet_id,
                assign_public_ip=True,
                display_name=f"{TARGET_NAME}-vnic",
            ),
            metadata={"user_data": target_cloud_init()},
            freeform_tags={
                "managed-by": "chatgpt",
                "purpose": "openclaw-tailscale-always-free",
                "recovery": "offline-boot-volume-repair-target-cloud-init",
            },
        )
    ).data
    target = wait(compute.get_instance, target.id, desired=("RUNNING",), timeout=1200)

    target_ip = None
    for _ in range(36):
        target_ip = instance_public_ip(compute, vnet, compartment_id, target.id)
        if target_ip:
            break
        time.sleep(5)
    if not target_ip:
        raise RuntimeError("TARGET_PUBLIC_IP_NOT_ASSIGNED")

    state.update({
        "status": "relaunched",
        "target_id": target.id,
        "target_ip": target_ip,
        "target_lifecycle_state": target.lifecycle_state,
        "target_bootstrap": "cloud-init-finalizer",
    })
    Path(args.state_json).write_text(json.dumps(state))
    log(
        "OFFLINE_REPAIR_TARGET_RELAUNCHED",
        target_id=target.id,
        public_ip=target_ip,
        bootstrap="cloud-init-finalizer",
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--state-json", required=True)
    args = ap.parse_args()
    return finish(args)


if __name__ == "__main__":
    raise SystemExit(main())
