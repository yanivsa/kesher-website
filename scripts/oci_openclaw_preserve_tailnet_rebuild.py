#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import oci

from oci_openclaw_bootstrap import ensure_network, instance_public_ip, load_config, log, wait

NAME = "openclaw-e2-tailscale"
SHAPE = "VM.Standard.E2.1.Micro"
RECOVERY_TAG = "authenticated-tailnet-recovery"


def live_named(compute, compartment_id: str, name: str):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=name).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0] if live else None


def boot_volume_for_instance(compute, compartment_id: str, inst):
    rows = compute.list_boot_volume_attachments(
        availability_domain=inst.availability_domain,
        compartment_id=compartment_id,
        instance_id=inst.id,
    ).data
    rows = [x for x in rows if x.lifecycle_state not in {"DETACHED", "DETACHING"}]
    if not rows:
        raise RuntimeError("OPENCLAW_BOOT_VOLUME_ATTACHMENT_NOT_FOUND")
    rows.sort(key=lambda x: x.time_created, reverse=True)
    return rows[0].boot_volume_id


def tagged_recovery_boot_volume(block, compartment_id: str):
    rows = block.list_boot_volumes(compartment_id=compartment_id).data
    rows = [x for x in rows
            if x.lifecycle_state != "TERMINATED"
            and (x.freeform_tags or {}).get("openclaw-recovery") == RECOVERY_TAG]
    rows.sort(key=lambda x: x.time_created, reverse=True)
    return rows[0] if rows else None


def mark_recovery_boot_volume(block, boot_volume_id: str):
    boot = block.get_boot_volume(boot_volume_id).data
    tags = dict(boot.freeform_tags or {})
    tags["managed-by"] = "chatgpt"
    tags["openclaw-recovery"] = RECOVERY_TAG
    block.update_boot_volume(
        boot_volume_id,
        oci.core.models.UpdateBootVolumeDetails(freeform_tags=tags),
    )


def wait_terminated(compute, instance_id: str, timeout: int = 900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = compute.get_instance(instance_id).data
        if obj.lifecycle_state == "TERMINATED":
            return
        time.sleep(5)
    raise TimeoutError("OPENCLAW_OLD_INSTANCE_TERMINATION_TIMEOUT")


def wait_boot_available(block, boot_volume_id: str, timeout: int = 600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = block.get_boot_volume(boot_volume_id).data
        if obj.lifecycle_state == "AVAILABLE":
            return obj
        if obj.lifecycle_state in {"TERMINATED", "FAULTY"}:
            raise RuntimeError(f"BOOT_VOLUME_BAD_STATE_{obj.lifecycle_state}")
        time.sleep(5)
    raise TimeoutError("BOOT_VOLUME_AVAILABLE_TIMEOUT")


def recovery_cloud_init() -> str:
    script = r'''#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1
exec > >(tee -a /var/log/openclaw-tailnet-recovery.log /dev/console) 2>&1

echo OPENCLAW_TAILNET_RECOVERY_START=true
for i in $(seq 1 120); do
  state="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", ""))' 2>/dev/null || true)"
  [ "$state" = Running ] && break
  sleep 2
done
state="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", ""))')"
[ "$state" = Running ]

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
test -n "$B"
"$B" config set gateway.mode local >/dev/null
"$B" config set gateway.bind loopback >/dev/null
"$B" config set gateway.tailscale.mode serve >/dev/null
"$B" config set gateway.auth.allowTailscale true --strict-json >/dev/null
"$B" config validate >/dev/null
systemctl disable --now openclaw-wait-tailnet.service >/dev/null 2>&1 || true
systemctl restart openclaw-gateway.service

for i in $(seq 1 60); do
  "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1 && break
  sleep 2
done
"$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1

tailscale serve --bg --yes http://127.0.0.1:18789 >/tmp/tailscale-serve.txt 2>&1 || true
for i in $(seq 1 60); do
  tailscale serve status 2>/dev/null | grep -q 'https://' && break
  sleep 2
done
tailscale serve status 2>/dev/null | grep -q 'https://'

DNS="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("Self",{}).get("DNSName") or "").rstrip("."))')"
TSIP="$(tailscale ip -4 | head -1)"
test -n "$DNS"
{
  echo OPENCLAW_TAILSCALE_FINALIZED=true
  echo TAILSCALE_BACKEND_STATE="$state"
  echo OPENCLAW_TAILSCALE_DNS="$DNS"
  echo OPENCLAW_TAILSCALE_IP="$TSIP"
  echo OPENCLAW_READY_URL="https://$DNS/"
} | tee /var/lib/openclaw-ready.txt

echo OPENCLAW_TAILNET_RECOVERY_DONE=true
'''
    cloud_cfg = (
        "#cloud-config\n"
        "write_files:\n"
        "  - path: /usr/local/sbin/openclaw-tailnet-recovery.sh\n"
        "    permissions: '0700'\n"
        "    owner: root:root\n"
        "    encoding: b64\n"
        "    content: " + base64.b64encode(script.encode()).decode() + "\n"
        "runcmd:\n"
        "  - [ bash, /usr/local/sbin/openclaw-tailnet-recovery.sh ]\n"
    )
    return base64.b64encode(cloud_cfg.encode()).decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ssh-public-key-file", required=True)
    ap.add_argument("--bootstrap-cidr", required=True)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()

    cfg = load_config(args.config)
    compartment_id = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)
    vnet = oci.core.VirtualNetworkClient(cfg)
    block = oci.core.BlockstorageClient(cfg)

    live_e2 = [x for x in compute.list_instances(compartment_id=compartment_id).data
               if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE]
    if len(live_e2) > 2:
        raise RuntimeError("ALWAYS_FREE_E2_LIMIT_ALREADY_EXCEEDED")

    inst = live_named(compute, compartment_id, NAME)
    if inst:
        if inst.shape != SHAPE:
            raise RuntimeError(f"UNEXPECTED_OPENCLAW_SHAPE_{inst.shape}")
        boot_volume_id = boot_volume_for_instance(compute, compartment_id, inst)
        mark_recovery_boot_volume(block, boot_volume_id)
        log("PRESERVING_AUTHENTICATED_BOOT_VOLUME", boot_volume_id=boot_volume_id)
    else:
        tagged = tagged_recovery_boot_volume(block, compartment_id)
        if not tagged:
            raise RuntimeError("OPENCLAW_TAILSCALE_INSTANCE_AND_RECOVERY_BOOT_NOT_FOUND")
        boot_volume_id = tagged.id
        log("RESUMING_FROM_PRESERVED_BOOT_VOLUME", boot_volume_id=boot_volume_id)

    _, subnet, sl = ensure_network(vnet, compartment_id, args.bootstrap_cidr)
    result = {
        "status": "starting",
        "old_instance_id": inst.id if inst else None,
        "boot_volume_id": boot_volume_id,
        "security_list_id": sl.id,
        "shape": SHAPE,
    }
    Path(args.result_json).write_text(json.dumps(result))

    if inst:
        compute.terminate_instance(inst.id, preserve_boot_volume=True)
        wait_terminated(compute, inst.id)
        log("AUTHENTICATED_VM_TERMINATED_BOOT_PRESERVED", instance_id=inst.id)

    boot = wait_boot_available(block, boot_volume_id)
    ssh_key = Path(args.ssh_public_key_file).read_text().strip()

    details = oci.core.models.LaunchInstanceDetails(
        availability_domain=boot.availability_domain,
        compartment_id=compartment_id,
        display_name=NAME,
        shape=SHAPE,
        source_details=oci.core.models.InstanceSourceViaBootVolumeDetails(
            boot_volume_id=boot_volume_id,
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=subnet.id,
            assign_public_ip=True,
            display_name=f"{NAME}-vnic",
        ),
        metadata={
            "ssh_authorized_keys": ssh_key,
            "user_data": recovery_cloud_init(),
        },
        freeform_tags={
            "managed-by": "chatgpt",
            "purpose": "openclaw-tailscale-always-free",
            "recovery": "preserved-authenticated-boot-volume",
        },
    )
    new_inst = compute.launch_instance(details).data
    new_inst = wait(compute.get_instance, new_inst.id, desired=("RUNNING",), timeout=1200)

    ip = None
    for _ in range(36):
        ip = instance_public_ip(compute, vnet, compartment_id, new_inst.id)
        if ip:
            break
        time.sleep(5)
    if not ip:
        raise RuntimeError("RECOVERED_OPENCLAW_PUBLIC_IP_NOT_ASSIGNED")

    result.update({
        "status": "created",
        "instance_id": new_inst.id,
        "lifecycle_state": new_inst.lifecycle_state,
        "availability_domain": new_inst.availability_domain,
        "public_ip": ip,
    })
    Path(args.result_json).write_text(json.dumps(result))
    log("OPENCLAW_PRESERVED_BOOT_RELAUNCHED", instance_id=new_inst.id, public_ip=ip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
