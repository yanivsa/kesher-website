#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

NAME = "openclaw-a1"
VCN_NAME = "openclaw-vcn"
SUBNET_NAME = "openclaw-subnet"
SECURITY_LIST_NAME = "openclaw-bootstrap-security"
IGW_NAME = "openclaw-igw"
SHAPE = "VM.Standard.A1.Flex"
OCPUS = 1.0
MEMORY_GB = 6.0


def log(event: str, **fields):
    safe = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"{event}" + (f" {safe}" if safe else ""), flush=True)


def wait(getter, resource_id, desired=("AVAILABLE", "RUNNING"), timeout=900):
    deadline = time.time() + timeout
    while time.time() < deadline:
        obj = getter(resource_id).data
        state = getattr(obj, "lifecycle_state", None)
        if state in desired:
            return obj
        if state in {"TERMINATED", "FAILED"}:
            raise RuntimeError(f"resource entered terminal state {state}")
        time.sleep(5)
    raise TimeoutError(f"timed out waiting for {resource_id}")


def load_config(path: str):
    config = oci.config.from_file(path, "DEFAULT")
    oci.config.validate_config(config)
    return config


def existing_instance(compute, compartment_id):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=NAME).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    if not live:
        return None
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0]


def capacity_domains(identity, compute, compartment_id):
    ads = identity.list_availability_domains(compartment_id=compartment_id).data
    available = []
    statuses = []
    for ad in ads:
        try:
            report = compute.create_compute_capacity_report(
                oci.core.models.CreateComputeCapacityReportDetails(
                    compartment_id=compartment_id,
                    availability_domain=ad.name,
                    shape_availabilities=[
                        oci.core.models.CreateCapacityReportShapeAvailabilityDetails(
                            instance_shape=SHAPE,
                            instance_shape_config=oci.core.models.CapacityReportInstanceShapeConfig(
                                ocpus=OCPUS,
                                memory_in_gbs=MEMORY_GB,
                            ),
                        )
                    ],
                )
            ).data
            shape_rows = report.shape_availabilities or []
            status = shape_rows[0].availability_status if shape_rows else "UNKNOWN"
            count = shape_rows[0].available_count if shape_rows else None
            statuses.append((ad.name, status, count))
            log("A1_CAPACITY", ad=ad.name, status=status, available_count=count)
            if status == "AVAILABLE":
                available.append(ad.name)
        except ServiceError as exc:
            statuses.append((ad.name, f"REPORT_ERROR_{exc.status}", None))
            log("A1_CAPACITY_REPORT_ERROR", ad=ad.name, status=exc.status, code=exc.code)
    return [ad.name for ad in ads], available, statuses


def ensure_network(vnet, compartment_id, bootstrap_cidr):
    vcns = [x for x in vnet.list_vcns(compartment_id=compartment_id).data if x.lifecycle_state != "TERMINATED"]
    ours = [x for x in vcns if x.display_name == VCN_NAME]
    if ours:
        vcn = ours[0]
    else:
        if len(vcns) >= 2:
            raise RuntimeError("FREE_TIER_VCN_LIMIT_REACHED")
        vcn = vnet.create_vcn(
            oci.core.models.CreateVcnDetails(
                compartment_id=compartment_id,
                cidr_block="10.77.0.0/16",
                display_name=VCN_NAME,
                dns_label="openclawvcn",
            )
        ).data
        vcn = wait(vnet.get_vcn, vcn.id)
        log("VCN_CREATED", id=vcn.id)

    igws = [x for x in vnet.list_internet_gateways(compartment_id=compartment_id, vcn_id=vcn.id).data
            if x.lifecycle_state != "TERMINATED"]
    ours_igw = [x for x in igws if x.display_name == IGW_NAME]
    if ours_igw:
        igw = ours_igw[0]
    else:
        igw = vnet.create_internet_gateway(
            oci.core.models.CreateInternetGatewayDetails(
                compartment_id=compartment_id,
                vcn_id=vcn.id,
                is_enabled=True,
                display_name=IGW_NAME,
            )
        ).data
        igw = wait(vnet.get_internet_gateway, igw.id)
        log("IGW_CREATED", id=igw.id)

    rt = vnet.get_route_table(vcn.default_route_table_id).data
    existing_rules = list(rt.route_rules or [])
    if not any(r.destination == "0.0.0.0/0" and r.network_entity_id == igw.id for r in existing_rules):
        existing_rules = [r for r in existing_rules if r.destination != "0.0.0.0/0"]
        existing_rules.append(
            oci.core.models.RouteRule(
                network_entity_id=igw.id,
                destination="0.0.0.0/0",
                destination_type="CIDR_BLOCK",
            )
        )
        vnet.update_route_table(
            rt.id,
            oci.core.models.UpdateRouteTableDetails(route_rules=existing_rules),
        )
        log("ROUTE_READY", route_table=rt.id)

    sls = [x for x in vnet.list_security_lists(compartment_id=compartment_id, vcn_id=vcn.id).data
           if x.lifecycle_state != "TERMINATED" and x.display_name == SECURITY_LIST_NAME]
    ingress = [
        oci.core.models.IngressSecurityRule(
            protocol="6",
            source=bootstrap_cidr,
            source_type="CIDR_BLOCK",
            tcp_options=oci.core.models.TcpOptions(
                destination_port_range=oci.core.models.PortRange(min=22, max=22)
            ),
            description="Temporary bootstrap SSH from current GitHub runner only",
        )
    ]
    egress = [
        oci.core.models.EgressSecurityRule(
            protocol="all",
            destination="0.0.0.0/0",
            destination_type="CIDR_BLOCK",
            description="Outbound bootstrap traffic",
        )
    ]
    if sls:
        sl = sls[0]
        vnet.update_security_list(
            sl.id,
            oci.core.models.UpdateSecurityListDetails(
                display_name=SECURITY_LIST_NAME,
                ingress_security_rules=ingress,
                egress_security_rules=egress,
            ),
        )
    else:
        sl = vnet.create_security_list(
            oci.core.models.CreateSecurityListDetails(
                compartment_id=compartment_id,
                vcn_id=vcn.id,
                display_name=SECURITY_LIST_NAME,
                ingress_security_rules=ingress,
                egress_security_rules=egress,
            )
        ).data
        sl = wait(vnet.get_security_list, sl.id)
        log("SECURITY_LIST_CREATED", id=sl.id)

    subnets = [x for x in vnet.list_subnets(compartment_id=compartment_id, vcn_id=vcn.id).data
               if x.lifecycle_state != "TERMINATED" and x.display_name == SUBNET_NAME]
    if subnets:
        subnet = subnets[0]
    else:
        subnet = vnet.create_subnet(
            oci.core.models.CreateSubnetDetails(
                compartment_id=compartment_id,
                vcn_id=vcn.id,
                cidr_block="10.77.1.0/24",
                display_name=SUBNET_NAME,
                dns_label="openclaw",
                route_table_id=vcn.default_route_table_id,
                security_list_ids=[sl.id],
                prohibit_public_ip_on_vnic=False,
            )
        ).data
        subnet = wait(vnet.get_subnet, subnet.id)
        log("SUBNET_CREATED", id=subnet.id)
    return vcn, subnet, sl


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
            log("IMAGE_SELECTED", os=os_name, image_id=image.id, display_name=json.dumps(image.display_name))
            return os_name, image
    raise RuntimeError("NO_ALWAYS_FREE_COMPATIBLE_ARM_IMAGE_FOUND")


def cloud_init():
    text = r'''#cloud-config
package_update: true
packages:
  - curl
  - ca-certificates
  - git
runcmd:
  - [ bash, -lc, "export HOME=/root; export OPENCLAW_NO_PROMPT=1; curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --no-prompt --no-onboard >>/var/log/openclaw-install.log 2>&1" ]
  - [ bash, -lc, "OPENCLAW_BIN=$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1); test -n \"$OPENCLAW_BIN\"; \"$OPENCLAW_BIN\" --version >/var/lib/openclaw-version.txt 2>&1; touch /var/lib/openclaw-installed" ]
'''
    return base64.b64encode(text.encode()).decode()


def instance_public_ip(compute, vnet, compartment_id, instance_id):
    attachments = compute.list_vnic_attachments(
        compartment_id=compartment_id,
        instance_id=instance_id,
    ).data
    if not attachments:
        return None
    vnic = vnet.get_vnic(attachments[0].vnic_id).data
    return vnic.public_ip


def close_bootstrap_ssh(vnet, security_list_id):
    sl = vnet.get_security_list(security_list_id).data
    vnet.update_security_list(
        security_list_id,
        oci.core.models.UpdateSecurityListDetails(
            display_name=sl.display_name,
            ingress_security_rules=[],
            egress_security_rules=list(sl.egress_security_rules or []),
        )
    )
    log("BOOTSTRAP_SSH_CLOSED", security_list=security_list_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--ssh-public-key-file")
    ap.add_argument("--bootstrap-cidr")
    ap.add_argument("--result-json")
    ap.add_argument("--close-ssh", action="store_true")
    ap.add_argument("--security-list-id")
    args = ap.parse_args()

    config = load_config(args.config)
    compartment_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    vnet = oci.core.VirtualNetworkClient(config)
    identity = oci.identity.IdentityClient(config)

    if args.close_ssh:
        if not args.security_list_id:
            raise RuntimeError("--security-list-id required with --close-ssh")
        close_bootstrap_ssh(vnet, args.security_list_id)
        return 0

    if not args.ssh_public_key_file or not args.bootstrap_cidr or not args.result_json:
        raise RuntimeError("bootstrap mode requires SSH key, CIDR and result path")

    existing = existing_instance(compute, compartment_id)
    if existing:
        ip = instance_public_ip(compute, vnet, compartment_id, existing.id)
        result = {
            "status": "existing",
            "instance_id": existing.id,
            "lifecycle_state": existing.lifecycle_state,
            "shape": existing.shape,
            "public_ip": ip,
        }
        Path(args.result_json).write_text(json.dumps(result))
        log("OPENCLAW_INSTANCE_EXISTS", state=existing.lifecycle_state, shape=existing.shape, public_ip=ip)
        return 0

    all_ads, available_ads, statuses = capacity_domains(identity, compute, compartment_id)
    report_definitive = statuses and all(
        s[1] in {"OUT_OF_HOST_CAPACITY", "HARDWARE_NOT_SUPPORTED"} for s in statuses
    )
    if not available_ads and report_definitive:
        result = {"status": "no_capacity", "capacity": statuses}
        Path(args.result_json).write_text(json.dumps(result))
        log("A1_CAPACITY_UNAVAILABLE")
        return 0

    candidate_ads = available_ads or all_ads
    _, subnet, sl = ensure_network(vnet, compartment_id, args.bootstrap_cidr)
    os_name, image = choose_image(compute, compartment_id)
    ssh_key = Path(args.ssh_public_key_file).read_text().strip()

    last_error = None
    for ad in candidate_ads:
        log("INSTANCE_LAUNCH_ATTEMPT", ad=ad, shape=SHAPE, ocpus=OCPUS, memory_gb=MEMORY_GB)
        try:
            details = oci.core.models.LaunchInstanceDetails(
                availability_domain=ad,
                compartment_id=compartment_id,
                display_name=NAME,
                shape=SHAPE,
                shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                    ocpus=OCPUS,
                    memory_in_gbs=MEMORY_GB,
                ),
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
                freeform_tags={"managed-by": "chatgpt", "purpose": "openclaw-free"},
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
                "availability_domain": ad,
                "lifecycle_state": instance.lifecycle_state,
                "shape": instance.shape,
                "ocpus": OCPUS,
                "memory_gb": MEMORY_GB,
                "public_ip": ip,
                "os": os_name,
                "security_list_id": sl.id,
            }
            Path(args.result_json).write_text(json.dumps(result))
            log("OPENCLAW_INSTANCE_CREATED", ad=ad, state=instance.lifecycle_state, public_ip=ip)
            return 0
        except ServiceError as exc:
            last_error = {"status": exc.status, "code": exc.code, "message": exc.message[:200], "ad": ad}
            log(
                "INSTANCE_LAUNCH_FAILED",
                ad=ad,
                status=exc.status,
                code=exc.code,
                message=json.dumps(exc.message[:160]),
            )
            msg = (exc.message or "").lower()
            if "out of host capacity" in msg or "outofhostcapacity" in (exc.code or "").lower():
                continue
            raise

    result = {"status": "no_capacity_after_launch", "last_error": last_error, "capacity": statuses}
    Path(args.result_json).write_text(json.dumps(result))
    log("A1_CAPACITY_UNAVAILABLE_AFTER_LAUNCH")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log("OCI_BOOTSTRAP_FAILED", type=type(exc).__name__, message=json.dumps(str(exc)[:300]))
        raise
