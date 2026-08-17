#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

from oci_openclaw_bootstrap import ensure_network, instance_public_ip, load_config, log, wait

TARGET_NAME = "openclaw-e2-tailscale"
FALLBACK_NAME = "openclaw-e2-plan-b"
HELPER_NAME = "openclaw-e2-repair-helper"
SHAPE = "VM.Standard.E2.1.Micro"
RECOVERY_TAG = "authenticated-tailnet-recovery"
RECOVERY_DISPLAY_NAME = "openclaw-authenticated-tailnet-recovery"
ATTACH_NAME = "openclaw-authenticated-boot-repair"
HELPER_SUCCESS = "OFFLINE_REPAIR_DISK_PATCHED=true"
HELPER_REQUIRED = {
    "OFFLINE_REPAIR_TARGET_SSH_KEY_REMOVED=true",
    HELPER_SUCCESS,
}
HELPER_FAILURE_PREFIXES = (
    "OFFLINE_REPAIR_SCRIPT_FAILED_RC=",
    "OFFLINE_REPAIR_DATA_DISK_NOT_FOUND=true",
    "OFFLINE_REPAIR_TARGET_ROOT_NOT_FOUND=true",
)
NO_SSH_CIDR = "192.0.2.1/32"


def live_named(compute, compartment_id: str, name: str):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=name).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0] if live else None


def wait_terminated(compute, instance_id: str, timeout: int = 900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = compute.get_instance(instance_id).data
        if obj.lifecycle_state == "TERMINATED":
            return
        time.sleep(5)
    raise TimeoutError("INSTANCE_TERMINATION_TIMEOUT")


def wait_boot_available(block, boot_id: str, timeout: int = 600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = block.get_boot_volume(boot_id).data
        if obj.lifecycle_state == "AVAILABLE":
            return obj
        if obj.lifecycle_state in {"TERMINATED", "FAULTY"}:
            raise RuntimeError(f"BOOT_VOLUME_BAD_STATE_{obj.lifecycle_state}")
        time.sleep(5)
    raise TimeoutError("BOOT_VOLUME_AVAILABLE_TIMEOUT")


def wait_volume_attachment(compute, attachment_id: str, desired: set[str], timeout: int = 600):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            obj = compute.get_volume_attachment(attachment_id).data
        except ServiceError as exc:
            if exc.status == 404 and "DETACHED" in desired:
                return None
            raise
        if obj.lifecycle_state in desired:
            return obj
        time.sleep(5)
    raise TimeoutError("VOLUME_ATTACHMENT_TIMEOUT")


def boot_for_instance(compute, compartment_id: str, inst):
    rows = compute.list_boot_volume_attachments(
        availability_domain=inst.availability_domain,
        compartment_id=compartment_id,
        instance_id=inst.id,
    ).data
    rows = [x for x in rows if x.lifecycle_state not in {"DETACHED", "DETACHING"}]
    if not rows:
        raise RuntimeError("TARGET_BOOT_VOLUME_NOT_FOUND")
    rows.sort(key=lambda x: x.time_created, reverse=True)
    return rows[0].boot_volume_id


def tagged_boot(block, compartment_id: str):
    rows = block.list_boot_volumes(compartment_id=compartment_id).data
    rows = [
        x for x in rows
        if x.lifecycle_state != "TERMINATED"
        and (
            x.display_name == RECOVERY_DISPLAY_NAME
            or (x.freeform_tags or {}).get("openclaw-recovery") == RECOVERY_TAG
        )
    ]
    rows.sort(key=lambda x: x.time_created, reverse=True)
    return rows[0] if rows else None


def mark_boot(block, boot_id: str):
    block.update_boot_volume(
        boot_id,
        oci.core.models.UpdateBootVolumeDetails(display_name=RECOVERY_DISPLAY_NAME),
    )
    log("OFFLINE_REPAIR_BOOT_MARKED", boot_id=boot_id, display_name=RECOVERY_DISPLAY_NAME)


def choose_image(compute, compartment_id: str):
    rows = compute.list_images(
        compartment_id=compartment_id,
        shape=SHAPE,
        operating_system="Canonical Ubuntu",
        sort_by="TIMECREATED",
        sort_order="DESC",
    ).data
    rows = [x for x in rows if x.lifecycle_state == "AVAILABLE"]
    if not rows:
        raise RuntimeError("NO_UBUNTU_E2_IMAGE")
    return rows[0]


def current_target_boot(compute, block, compartment_id: str):
    target = live_named(compute, compartment_id, TARGET_NAME)
    if target:
        boot_id = boot_for_instance(compute, compartment_id, target)
        mark_boot(block, boot_id)
        return target, boot_id
    boot = tagged_boot(block, compartment_id)
    if not boot:
        raise RuntimeError("NO_LIVE_TARGET_OR_TAGGED_RECOVERY_BOOT")
    return None, boot.id


def cleanup_existing_helper(compute, compartment_id: str, boot_id: str):
    helper = live_named(compute, compartment_id, HELPER_NAME)
    if not helper:
        return
    log("OFFLINE_REPAIR_CLEANING_EXISTING_HELPER", helper_id=helper.id)
    atts = compute.list_volume_attachments(
        compartment_id=compartment_id,
        instance_id=helper.id,
    ).data
    for att in atts:
        if getattr(att, "volume_id", None) == boot_id and att.lifecycle_state not in {"DETACHED", "DETACHING"}:
            compute.detach_volume(att.id)
            wait_volume_attachment(compute, att.id, {"DETACHED"})
    compute.terminate_instance(helper.id, preserve_boot_volume=False)
    wait_terminated(compute, helper.id)
    log("OFFLINE_REPAIR_OLD_HELPER_TERMINATED")


def helper_cloud_init(repair_script_file: str) -> str:
    repair = Path(repair_script_file).read_text()
    payload = (
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        "exec > >(tee -a /var/log/openclaw-helper-repair.log /dev/console) 2>&1\n"
        "echo OFFLINE_REPAIR_HELPER_CLOUD_INIT_START=true\n"
        + repair
        + "\n"
    )
    encoded = base64.b64encode(payload.encode()).decode()
    if len(encoded.encode()) > 28_000:
        raise RuntimeError("HELPER_CLOUD_INIT_TOO_LARGE")
    return encoded


def target_cloud_init() -> str:
    payload = (
        "#!/usr/bin/env bash\n"
        "set -Eeuo pipefail\n"
        "exec > >(tee -a /var/log/openclaw-target-relaunch.log /dev/console) 2>&1\n"
        "echo OPENCLAW_TARGET_CLOUD_INIT_START=true\n"
        "/usr/local/sbin/openclaw-offline-finalize.sh\n"
    )
    return base64.b64encode(payload.encode()).decode()


def capture_console_text(compute, instance_id: str) -> str:
    hist = compute.capture_console_history(
        oci.core.models.CaptureConsoleHistoryDetails(
            instance_id=instance_id,
            display_name="openclaw-helper-repair-verification",
        )
    ).data
    for _ in range(60):
        obj = compute.get_console_history(hist.id).data
        if obj.lifecycle_state == "SUCCEEDED":
            break
        if obj.lifecycle_state == "FAILED":
            raise RuntimeError("HELPER_CONSOLE_CAPTURE_FAILED")
        time.sleep(2)
    else:
        raise TimeoutError("HELPER_CONSOLE_CAPTURE_TIMEOUT")

    data = compute.get_console_history_content(hist.id).data
    if hasattr(data, "content"):
        data = data.content
    if hasattr(data, "read"):
        data = data.read()
    if isinstance(data, bytes):
        return data.decode("utf-8", "replace")
    return str(data)


def helper_markers(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("OFFLINE_REPAIR_"):
            out.append(line[-500:])
    return out[-80:]


def prepare(args) -> int:
    cfg = load_config(args.config)
    compartment_id = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)
    vnet = oci.core.VirtualNetworkClient(cfg)
    block = oci.core.BlockstorageClient(cfg)

    target, boot_id = current_target_boot(compute, block, compartment_id)
    log("OFFLINE_REPAIR_BOOT_IDENTIFIED", boot_id=boot_id)

    _, subnet, sl = ensure_network(vnet, compartment_id, NO_SSH_CIDR)
    cleanup_existing_helper(compute, compartment_id, boot_id)

    if target:
        log("OFFLINE_REPAIR_TERMINATING_TARGET_PRESERVE_BOOT", target_id=target.id)
        compute.terminate_instance(target.id, preserve_boot_volume=True)
        wait_terminated(compute, target.id)

    boot = wait_boot_available(block, boot_id)

    live_e2 = [x for x in compute.list_instances(compartment_id=compartment_id).data
               if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE]
    log("OFFLINE_REPAIR_LIVE_E2_BEFORE_HELPER", count=len(live_e2))
    if len(live_e2) >= 2:
        raise RuntimeError("ALWAYS_FREE_E2_LIMIT_GUARD_BEFORE_HELPER")

    image = choose_image(compute, compartment_id)
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
                assign_public_ip=False,
                display_name=f"{HELPER_NAME}-vnic",
            ),
            metadata={"user_data": helper_cloud_init(args.repair_script_file)},
            freeform_tags={
                "managed-by": "chatgpt",
                "purpose": "openclaw-offline-repair-helper-cloud-init",
            },
        )
    ).data
    helper = wait(compute.get_instance, helper.id, desired=("RUNNING",), timeout=1200)
    log("OFFLINE_REPAIR_HELPER_RUNNING", helper_id=helper.id, transport="cloud-init-console")

    attach = compute.attach_volume(
        oci.core.models.AttachParavirtualizedVolumeDetails(
            instance_id=helper.id,
            volume_id=boot_id,
            display_name=ATTACH_NAME,
            is_read_only=False,
        )
    ).data
    attach = wait_volume_attachment(compute, attach.id, {"ATTACHED"})
    log("OFFLINE_REPAIR_BOOT_ATTACHED_AS_DATA", attachment_id=attach.id)

    result = {
        "status": "prepared",
        "target_boot_id": boot_id,
        "target_availability_domain": boot.availability_domain,
        "helper_id": helper.id,
        "helper_ip": None,
        "attachment_id": attach.id,
        "subnet_id": subnet.id,
        "security_list_id": sl.id,
        "shape": SHAPE,
        "helper_transport": "cloud-init-console",
    }
    Path(args.result_json).write_text(json.dumps(result))
    return 0


def wait_helper(args) -> int:
    cfg = load_config(args.config)
    compute = oci.core.ComputeClient(cfg)
    state = json.loads(Path(args.state_json).read_text())
    helper_id = state["helper_id"]
    deadline = time.time() + args.timeout
    last_markers: list[str] = []

    while time.time() < deadline:
        helper = compute.get_instance(helper_id).data
        if helper.lifecycle_state in {"TERMINATED", "TERMINATING"}:
            raise RuntimeError("HELPER_TERMINATED_BEFORE_REPAIR_COMPLETED")
        text = capture_console_text(compute, helper_id)
        markers = helper_markers(text)
        if markers != last_markers:
            for line in markers:
                print(line, flush=True)
            last_markers = markers

        for line in markers:
            if line.startswith(HELPER_FAILURE_PREFIXES):
                raise RuntimeError(line)

        if HELPER_SUCCESS in markers:
            missing = HELPER_REQUIRED.difference(set(markers))
            if missing:
                raise RuntimeError("HELPER_SUCCESS_MISSING_REQUIRED_MARKERS_" + "_".join(sorted(missing)))
            state["helper_repair_verified"] = True
            Path(args.state_json).write_text(json.dumps(state))
            print("OFFLINE_REPAIR_HELPER_CONSOLE_OK=true", flush=True)
            return 0
        time.sleep(10)

    if last_markers:
        print("OFFLINE_REPAIR_HELPER_LAST_MARKERS_BEGIN", flush=True)
        for line in last_markers:
            print(line, flush=True)
        print("OFFLINE_REPAIR_HELPER_LAST_MARKERS_END", flush=True)
    raise TimeoutError("HELPER_REPAIR_CONSOLE_TIMEOUT")


def finish(args) -> int:
    cfg = load_config(args.config)
    compartment_id = cfg["tenancy"]
    compute = oci.core.ComputeClient(cfg)
    vnet = oci.core.VirtualNetworkClient(cfg)
    block = oci.core.BlockstorageClient(cfg)
    state = json.loads(Path(args.state_json).read_text())

    if not state.get("helper_repair_verified"):
        raise RuntimeError("HELPER_REPAIR_NOT_VERIFIED")

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
    live_e2 = [x for x in compute.list_instances(compartment_id=compartment_id).data
               if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE]
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
                "recovery": "offline-boot-volume-repair-cloud-init",
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
    })
    Path(args.state_json).write_text(json.dumps(state))
    log("OFFLINE_REPAIR_TARGET_RELAUNCHED", target_id=target.id, public_ip=target_ip)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("prepare")
    p.add_argument("--config", required=True)
    p.add_argument("--repair-script-file", required=True)
    p.add_argument("--result-json", required=True)
    p.set_defaults(func=prepare)

    w = sub.add_parser("wait-helper")
    w.add_argument("--config", required=True)
    w.add_argument("--state-json", required=True)
    w.add_argument("--timeout", type=int, default=600)
    w.set_defaults(func=wait_helper)

    f = sub.add_parser("finish")
    f.add_argument("--config", required=True)
    f.add_argument("--state-json", required=True)
    f.set_defaults(func=finish)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
