#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

from oci_openclaw_bootstrap import ensure_network, instance_public_ip, load_config, log, wait

OLD_NAME = "openclaw-e2-plan-b"
NAME = "openclaw-e2-tailscale"
SHAPE = "VM.Standard.E2.1.Micro"
MANAGED_TAG = "ssh-recovery-v2"


def live_named(compute, compartment_id, name):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=name).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0] if live else None


def wait_terminated(compute, instance_id, timeout=900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = compute.get_instance(instance_id).data
        if obj.lifecycle_state == "TERMINATED":
            return
        time.sleep(5)
    raise TimeoutError("REPLACEMENT_TERMINATION_TIMEOUT")


def choose_image(compute, compartment_id):
    rows = compute.list_images(
        compartment_id=compartment_id,
        shape=SHAPE,
        operating_system="Canonical Ubuntu",
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    rows = [x for x in rows if x.lifecycle_state == "AVAILABLE"]
    if not rows:
        raise RuntimeError("NO_E2_UBUNTU_IMAGE")
    return rows[0]


def main():
    # The workflow later imports scripts.oci_openclaw_plan_b_e2 from the repo root.
    # That module historically imports oci_openclaw_bootstrap as a top-level module.
    # Create a runner-local compatibility shim so the encryption helper can load.
    shim = Path(__file__).resolve().parent.parent / "oci_openclaw_bootstrap.py"
    shim.write_text("from scripts.oci_openclaw_bootstrap import *\n")

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
    identity = oci.identity.IdentityClient(cfg)

    # Any live replacement reaching this workflow is incomplete: a successful
    # setup ends with SSH closed and does not need this rebuild workflow again.
    # Recycling it also breaks any older stuck SSH session before a fresh key
    # is generated. We wait for TERMINATED before reopening the shared SSH rule.
    replacement = live_named(compute, compartment_id, NAME)
    if replacement:
        log("TERMINATING_INCOMPLETE_TAILSCALE_REPLACEMENT", instance_id=replacement.id)
        compute.terminate_instance(replacement.id, preserve_boot_volume=False)
        wait_terminated(compute, replacement.id)
        log("INCOMPLETE_TAILSCALE_REPLACEMENT_TERMINATED")

    old = live_named(compute, compartment_id, OLD_NAME)
    if not old:
        raise RuntimeError("OLD_OPENCLAW_FALLBACK_NOT_FOUND")

    live_e2 = [x for x in compute.list_instances(compartment_id=compartment_id).data
               if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE]
    log("LIVE_E2_BEFORE_REBUILD", count=len(live_e2))
    if len(live_e2) >= 2:
        raise RuntimeError("ALWAYS_FREE_E2_LIMIT_GUARD")

    _, subnet, sl = ensure_network(vnet, compartment_id, args.bootstrap_cidr)
    image = choose_image(compute, compartment_id)
    ssh_key = Path(args.ssh_public_key_file).read_text().strip()
    ads = identity.list_availability_domains(compartment_id=compartment_id).data
    errors = []
    for ad in ads:
        try:
            log("TAILSCALE_SSH_LAUNCH_ATTEMPT", ad=ad.name)
            inst = compute.launch_instance(
                oci.core.models.LaunchInstanceDetails(
                    availability_domain=ad.name,
                    compartment_id=compartment_id,
                    display_name=NAME,
                    shape=SHAPE,
                    source_details=oci.core.models.InstanceSourceViaImageDetails(
                        source_type="image", image_id=image.id
                    ),
                    create_vnic_details=oci.core.models.CreateVnicDetails(
                        subnet_id=subnet.id,
                        assign_public_ip=True,
                        display_name=f"{NAME}-vnic",
                    ),
                    metadata={"ssh_authorized_keys": ssh_key},
                    freeform_tags={
                        "managed-by": "chatgpt",
                        "purpose": "openclaw-tailscale-always-free",
                        "bootstrap-mode": MANAGED_TAG,
                    },
                )
            ).data
            inst = wait(compute.get_instance, inst.id, desired=("RUNNING",), timeout=1200)
            ip = None
            for _ in range(24):
                ip = instance_public_ip(compute, vnet, compartment_id, inst.id)
                if ip:
                    break
                time.sleep(5)
            result = {
                "status": "created",
                "instance_id": inst.id,
                "shape": inst.shape,
                "availability_domain": ad.name,
                "lifecycle_state": inst.lifecycle_state,
                "public_ip": ip,
                "os": "Canonical Ubuntu",
                "security_list_id": sl.id,
            }
            Path(args.result_json).write_text(json.dumps(result))
            log("TAILSCALE_SSH_REPLACEMENT_CREATED", ad=ad.name, public_ip=ip)
            return 0
        except ServiceError as exc:
            err = {"ad": ad.name, "status": exc.status, "code": exc.code, "message": (exc.message or "")[:200]}
            errors.append(err)
            log("TAILSCALE_SSH_LAUNCH_FAILED", **err)
            text = f"{exc.code or ''} {exc.message or ''}".lower()
            if exc.status == 404 or "capacity" in text or "shape" in text:
                continue
            raise

    Path(args.result_json).write_text(json.dumps({"status":"blocked_after_all_ads","errors":errors}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
