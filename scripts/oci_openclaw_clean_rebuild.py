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

TARGET_NAME = "openclaw-e2-tailscale"
SHAPE = "VM.Standard.E2.1.Micro"
UBUNTU_VERSION = "24.04"
MIGRATION_ATTACHMENT_NAME = "openclaw-clean-cloudflared-source"
RUN_COMMAND_PLUGIN = "Compute Instance Run Command"
ROLLBACK_TAG = "clean-rebuild-rollback"
CREDENTIAL_SOURCE_TAG = "true"
LEGACY_RECOVERY_TAG = "authenticated-tailnet-recovery"
HELPER_PREFIXES = (
    "openclaw-e2-repair-helper",
    "openclaw-offline-repair-helper",
)


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
        raise RuntimeError("OPENCLAW_CLEAN_OLD_BOOT_ATTACHMENT_NOT_FOUND")
    rows.sort(key=lambda x: x.time_created, reverse=True)
    return rows[0].boot_volume_id


def find_preserved_boot(block, identity, compartment_id: str):
    candidates = []
    ads = identity.list_availability_domains(compartment_id=compartment_id).data
    for ad in ads:
        rows = block.list_boot_volumes(
            availability_domain=ad.name,
            compartment_id=compartment_id,
        ).data
        for row in rows:
            if row.lifecycle_state in {"TERMINATED", "TERMINATING", "FAULTY"}:
                continue
            tags = row.freeform_tags or {}
            if (
                tags.get("openclaw-cloudflared-source") == CREDENTIAL_SOURCE_TAG
                or tags.get("openclaw-clean-rollback") == ROLLBACK_TAG
                or tags.get("openclaw-recovery") == LEGACY_RECOVERY_TAG
            ):
                candidates.append(row)
    candidates.sort(
        key=lambda x: (
            (x.freeform_tags or {}).get("openclaw-cloudflared-source") == CREDENTIAL_SOURCE_TAG,
            x.time_created,
        ),
        reverse=True,
    )
    return candidates[0] if candidates else None


def mark_rollback(block, boot_volume_id: str, credential_source: bool = False):
    boot = block.get_boot_volume(boot_volume_id).data
    tags = dict(boot.freeform_tags or {})
    tags.update(
        {
            "managed-by": "chatgpt",
            "openclaw-clean-rollback": ROLLBACK_TAG,
            "do-not-delete": "openclaw-rollback",
        }
    )
    if credential_source:
        tags["openclaw-cloudflared-source"] = CREDENTIAL_SOURCE_TAG
    block.update_boot_volume(
        boot_volume_id,
        oci.core.models.UpdateBootVolumeDetails(freeform_tags=tags),
    )
    log("OPENCLAW_CLEAN_ROLLBACK_MARKED", boot_id=boot_volume_id)


def wait_terminated(compute, instance_id: str, timeout: int = 900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = compute.get_instance(instance_id).data
        if obj.lifecycle_state == "TERMINATED":
            return
        time.sleep(5)
    raise TimeoutError("OPENCLAW_CLEAN_OLD_INSTANCE_TERMINATION_TIMEOUT")


def wait_boot_available(block, boot_volume_id: str, timeout: int = 600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = block.get_boot_volume(boot_volume_id).data
        if obj.lifecycle_state == "AVAILABLE":
            return obj
        if obj.lifecycle_state in {"TERMINATED", "FAULTY"}:
            raise RuntimeError(f"OPENCLAW_CLEAN_OLD_BOOT_BAD_STATE_{obj.lifecycle_state}")
        time.sleep(5)
    raise TimeoutError("OPENCLAW_CLEAN_OLD_BOOT_AVAILABLE_TIMEOUT")


def wait_volume_attachment(compute, attachment_id: str, desired: str, timeout: int = 600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            obj = compute.get_volume_attachment(attachment_id).data
        except ServiceError as exc:
            if desired == "DETACHED" and exc.status == 404:
                return None
            raise
        if obj.lifecycle_state == desired:
            return obj
        if obj.lifecycle_state in {"FAILED", "DETACHED"} and desired != "DETACHED":
            raise RuntimeError(f"OPENCLAW_CLEAN_ATTACHMENT_BAD_STATE_{obj.lifecycle_state}")
        time.sleep(5)
    raise TimeoutError(f"OPENCLAW_CLEAN_ATTACHMENT_{desired}_TIMEOUT")


def instance_subnet_id(compute, vnet, compartment_id: str, instance_id: str):
    rows = compute.list_vnic_attachments(
        compartment_id=compartment_id,
        instance_id=instance_id,
    ).data
    rows = [x for x in rows if x.lifecycle_state not in {"DETACHED", "DETACHING"}]
    if not rows:
        raise RuntimeError("OPENCLAW_CLEAN_OLD_VNIC_NOT_FOUND")
    return vnet.get_vnic(rows[0].vnic_id).data.subnet_id


def choose_ubuntu_image(compute, compartment_id: str):
    rows = compute.list_images(
        compartment_id=compartment_id,
        shape=SHAPE,
        operating_system="Canonical Ubuntu",
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    rows = [
        x
        for x in rows
        if x.lifecycle_state == "AVAILABLE"
        and x.operating_system_version == UBUNTU_VERSION
        and "minimal" not in (x.display_name or "").lower()
        and (x.display_name or "").startswith("Canonical-Ubuntu-24.04-")
    ]
    if not rows:
        raise RuntimeError("OPENCLAW_CLEAN_NO_UBUNTU_E2_IMAGE")
    image = rows[0]
    log(
        "OPENCLAW_CLEAN_IMAGE_SELECTED",
        os=image.operating_system,
        version=image.operating_system_version,
        image_id=image.id,
    )
    return image


def cleanup_stale_helpers(compute, compartment_id: str):
    rows = compute.list_instances(compartment_id=compartment_id).data
    for row in rows:
        if row.lifecycle_state in {"TERMINATED", "TERMINATING"}:
            continue
        if not any((row.display_name or "").startswith(p) for p in HELPER_PREFIXES):
            continue
        log(
            "OPENCLAW_CLEAN_TERMINATING_STALE_HELPER",
            instance_id=row.id,
            name=row.display_name,
        )
        compute.terminate_instance(row.id, preserve_boot_volume=False)
        wait_terminated(compute, row.id)


def clean_cloud_init() -> str:
    script = r'''#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1
exec > >(tee -a /var/log/openclaw-clean-bootstrap.log /dev/console) 2>&1

echo OPENCLAW_CLEAN_BOOTSTRAP_START=true

if ! swapon --show=NAME --noheadings 2>/dev/null | grep -Fxq /swapfile; then
  (fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048)
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y curl ca-certificates git lvm2

curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh \
  | bash -s -- --no-prompt --no-onboard --verify

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
test -n "$B"
"$B" --version | tee /var/lib/openclaw-version.txt
ln -sfn "$B" /usr/local/bin/openclaw
touch /var/lib/openclaw-installed

cat >/etc/sudoers.d/101-oracle-cloud-agent-run-command <<'SUDO'
ocarun ALL=(ALL) NOPASSWD:ALL
SUDO
chmod 0440 /etc/sudoers.d/101-oracle-cloud-agent-run-command
visudo -cf /etc/sudoers.d/101-oracle-cloud-agent-run-command

echo OPENCLAW_CLEAN_BOOTSTRAP_COMPLETE=true
'''
    cloud_cfg = (
        "#cloud-config\n"
        "write_files:\n"
        "  - path: /usr/local/sbin/openclaw-clean-bootstrap.sh\n"
        "    permissions: '0700'\n"
        "    owner: root:root\n"
        "    encoding: b64\n"
        "    content: " + base64.b64encode(script.encode()).decode() + "\n"
        "runcmd:\n"
        "  - [ bash, /usr/local/sbin/openclaw-clean-bootstrap.sh ]\n"
    )
    return base64.b64encode(cloud_cfg.encode()).decode()


def prepare(args) -> int:
    cfg = load_config(args.config)
    compartment_id = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)
    vnet = oci.core.VirtualNetworkClient(cfg)
    block = oci.core.BlockstorageClient(cfg)
    identity = oci.identity.IdentityClient(cfg)

    # Reuse the existing VCN/subnet but temporarily allow SSH only from this
    # GitHub runner's public /32. The workflow always closes it in cleanup.
    _, managed_subnet, security_list = ensure_network(
        vnet, compartment_id, args.bootstrap_cidr
    )
    state = {
        "status": "network-ready",
        "security_list_id": security_list.id,
        "subnet_id": managed_subnet.id,
    }
    Path(args.state_json).write_text(json.dumps(state))

    old = live_named(compute, compartment_id, TARGET_NAME)
    if old and (old.freeform_tags or {}).get("purpose") == "openclaw-clean-rebuild":
        # A previous clean attempt is disposable. Keep the original credential
        # source boot instead of accidentally promoting this new boot to rollback.
        log("OPENCLAW_CLEAN_REMOVING_FAILED_CLEAN_ATTEMPT", instance_id=old.id)
        compute.terminate_instance(old.id, preserve_boot_volume=False)
        wait_terminated(compute, old.id)
        old = None

    if old:
        if old.shape != SHAPE:
            raise RuntimeError(f"OPENCLAW_CLEAN_UNEXPECTED_TARGET_SHAPE_{old.shape}")
        old_boot_id = boot_volume_for_instance(compute, compartment_id, old)
        old_ad = old.availability_domain
        old_subnet_id = instance_subnet_id(compute, vnet, compartment_id, old.id)
        mark_rollback(block, old_boot_id, credential_source=True)

        state.update({
            "status": "preserving-old",
            "old_instance_id": old.id,
            "old_boot_volume_id": old_boot_id,
            "availability_domain": old_ad,
            "old_subnet_id": old_subnet_id,
        })
        Path(args.state_json).write_text(json.dumps(state))
        log(
            "OPENCLAW_CLEAN_TERMINATING_OLD_PRESERVE_BOOT",
            instance_id=old.id,
            boot_id=old_boot_id,
        )
        compute.terminate_instance(old.id, preserve_boot_volume=True)
        wait_terminated(compute, old.id)
    else:
        boot = find_preserved_boot(block, identity, compartment_id)
        if not boot:
            raise RuntimeError("OPENCLAW_CLEAN_NO_EXISTING_TARGET_OR_ROLLBACK_BOOT")
        old_boot_id = boot.id
        old_ad = boot.availability_domain
        mark_rollback(block, old_boot_id, credential_source=True)
        state.update({
            "status": "using-preserved-old",
            "old_instance_id": None,
            "old_boot_volume_id": old_boot_id,
            "availability_domain": old_ad,
        })
        Path(args.state_json).write_text(json.dumps(state))
        log("OPENCLAW_CLEAN_USING_PRESERVED_OLD_BOOT", boot_id=old_boot_id)

    wait_boot_available(block, old_boot_id)

    cleanup_stale_helpers(compute, compartment_id)
    live_e2 = [
        x
        for x in compute.list_instances(compartment_id=compartment_id).data
        if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE
    ]
    log("OPENCLAW_CLEAN_LIVE_E2_BEFORE_NEW", count=len(live_e2))
    if len(live_e2) >= 2:
        names = ",".join(sorted((x.display_name or "?") for x in live_e2))
        raise RuntimeError("OPENCLAW_CLEAN_ALWAYS_FREE_E2_LIMIT_GUARD_" + names)

    image = choose_ubuntu_image(compute, compartment_id)
    ssh_key = Path(args.ssh_public_key_file).read_text().strip()

    details = oci.core.models.LaunchInstanceDetails(
        availability_domain=old_ad,
        compartment_id=compartment_id,
        display_name=TARGET_NAME,
        shape=SHAPE,
        source_details=oci.core.models.InstanceSourceViaImageDetails(
            source_type="image",
            image_id=image.id,
        ),
        create_vnic_details=oci.core.models.CreateVnicDetails(
            subnet_id=managed_subnet.id,
            assign_public_ip=True,
            display_name=f"{TARGET_NAME}-vnic-clean",
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
        metadata={
            "ssh_authorized_keys": ssh_key,
            "user_data": clean_cloud_init(),
        },
        freeform_tags={
            "managed-by": "chatgpt",
            "purpose": "openclaw-clean-rebuild",
            "source": "fresh-image",
        },
    )

    log(
        "OPENCLAW_CLEAN_NEW_LAUNCH_ATTEMPT",
        ad=old_ad,
        shape=SHAPE,
        image_id=image.id,
    )
    try:
        new = compute.launch_instance(details).data
    except ServiceError as exc:
        raise RuntimeError(
            f"OPENCLAW_CLEAN_NEW_LAUNCH_FAILED_{exc.status}_{exc.code}_{(exc.message or '')[:160]}"
        ) from exc
    new = wait(compute.get_instance, new.id, desired=("RUNNING",), timeout=1200)

    new_ip = None
    for _ in range(36):
        new_ip = instance_public_ip(compute, vnet, compartment_id, new.id)
        if new_ip:
            break
        time.sleep(5)
    if not new_ip:
        raise RuntimeError("OPENCLAW_CLEAN_NEW_PUBLIC_IP_NOT_ASSIGNED")

    attachment = compute.attach_volume(
        oci.core.models.AttachParavirtualizedVolumeDetails(
            instance_id=new.id,
            volume_id=old_boot_id,
            display_name=MIGRATION_ATTACHMENT_NAME,
            is_read_only=True,
        )
    ).data
    wait_volume_attachment(compute, attachment.id, "ATTACHED", timeout=600)

    state.update(
        {
            "status": "new-running-old-attached-readonly",
            "new_instance_id": new.id,
            "new_public_ip": new_ip,
            "new_image_id": image.id,
            "new_image_name": image.display_name,
            "old_boot_volume_id": old_boot_id,
            "old_boot_attachment_id": attachment.id,
            "old_boot_attachment_read_only": True,
            "security_list_id": security_list.id,
            "shape": SHAPE,
            "fresh_image": True,
        }
    )
    Path(args.state_json).write_text(json.dumps(state))
    print("OPENCLAW_CLEAN_NEW_VM_RUNNING=true", flush=True)
    print("OPENCLAW_CLEAN_FRESH_IMAGE=true", flush=True)
    print("OPENCLAW_CLEAN_OLD_BOOT_ATTACHED_READONLY=true", flush=True)
    return 0


def finish(args) -> int:
    cfg = load_config(args.config)
    compute = oci.core.ComputeClient(cfg)
    state = json.loads(Path(args.state_json).read_text())
    attachment_id = state.get("old_boot_attachment_id")
    if attachment_id:
        try:
            obj = compute.get_volume_attachment(attachment_id).data
            if obj.lifecycle_state not in {"DETACHED", "DETACHING"}:
                compute.detach_volume(attachment_id)
            wait_volume_attachment(compute, attachment_id, "DETACHED", timeout=600)
        except ServiceError as exc:
            if exc.status != 404:
                raise
    state["status"] = "complete"
    state["old_boot_detached"] = True
    Path(args.state_json).write_text(json.dumps(state))
    print("OPENCLAW_CLEAN_OLD_BOOT_DETACHED=true", flush=True)
    print("OPENCLAW_CLEAN_ROLLBACK_PRESERVED=true", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--config", required=True)
    p.add_argument("--ssh-public-key-file", required=True)
    p.add_argument("--bootstrap-cidr", required=True)
    p.add_argument("--state-json", required=True)

    f = sub.add_parser("finish")
    f.add_argument("--config", required=True)
    f.add_argument("--state-json", required=True)

    args = ap.parse_args()
    if args.command == "prepare":
        return prepare(args)
    return finish(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log(
            "OPENCLAW_CLEAN_REBUILD_FAILED",
            type=type(exc).__name__,
            message=json.dumps(str(exc)[:400]),
        )
        raise
