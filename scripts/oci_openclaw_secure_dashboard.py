#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import shlex
import time
from pathlib import Path

import oci
from oci.exceptions import ServiceError

from oci_openclaw_bootstrap import load_config, log, wait

NAME = "openclaw-e2-dashboard"
SHAPE = "VM.Standard.E2.1.Micro"
VCN_NAME = "openclaw-vcn"
SUBNET_NAME = "openclaw-subnet"
SECURITY_LIST_NAME = "openclaw-bootstrap-security"


def live_instances(compute, compartment_id):
    rows = compute.list_instances(compartment_id=compartment_id).data
    return [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]


def existing_instance(compute, compartment_id):
    rows = [x for x in live_instances(compute, compartment_id) if x.display_name == NAME]
    rows.sort(key=lambda x: x.time_created, reverse=True)
    return rows[0] if rows else None


def get_network(vnet, compartment_id):
    vcns = [x for x in vnet.list_vcns(compartment_id=compartment_id).data
            if x.lifecycle_state != "TERMINATED" and x.display_name == VCN_NAME]
    if not vcns:
        raise RuntimeError("OPENCLAW_VCN_NOT_FOUND")
    vcn = vcns[0]
    subnets = [x for x in vnet.list_subnets(compartment_id=compartment_id, vcn_id=vcn.id).data
               if x.lifecycle_state != "TERMINATED" and x.display_name == SUBNET_NAME]
    if not subnets:
        raise RuntimeError("OPENCLAW_SUBNET_NOT_FOUND")
    sls = [x for x in vnet.list_security_lists(compartment_id=compartment_id, vcn_id=vcn.id).data
           if x.lifecycle_state != "TERMINATED" and x.display_name == SECURITY_LIST_NAME]
    if not sls:
        raise RuntimeError("OPENCLAW_SECURITY_LIST_NOT_FOUND")
    sl = sls[0]

    # The dashboard is reachable only through outbound Cloudflare Tunnel.
    # Keep every direct inbound rule closed, including SSH and port 18789.
    vnet.update_security_list(
        sl.id,
        oci.core.models.UpdateSecurityListDetails(
            display_name=sl.display_name,
            ingress_security_rules=[],
            egress_security_rules=list(sl.egress_security_rules or []),
        ),
    )
    log("DASHBOARD_DIRECT_INGRESS_CLOSED", security_list=sl.id)
    return subnets[0], sl


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
            return os_name, rows[0]
    raise RuntimeError("NO_E2_IMAGE_FOUND")


def instance_public_ip(compute, vnet, compartment_id, instance_id):
    atts = compute.list_vnic_attachments(compartment_id=compartment_id, instance_id=instance_id).data
    if not atts:
        return None
    return vnet.get_vnic(atts[0].vnic_id).data.public_ip


def cloud_init(tunnel_token: str, hostname: str, allowed_email: str):
    token = shlex.quote(tunnel_token)
    host = shlex.quote(hostname)
    email = shlex.quote(allowed_email)
    script = f'''#!/usr/bin/env bash
set -euo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1
HOSTNAME={host}
ALLOWED_EMAIL={email}

# 1 GB E2 Micro needs swap headroom for Node/OpenClaw.
if ! swapon --show | grep -q /swapfile; then
  (fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048)
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y curl ca-certificates git

curl -fsSL --proto '=https' --tlsv1.2 https://openclaw.ai/install.sh | bash -s -- --no-prompt --no-onboard >>/var/log/openclaw-install.log 2>&1
B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
test -n "$B"
"$B" --version | tee /var/lib/openclaw-version.txt

"$B" config set gateway.mode local
"$B" config set gateway.bind loopback
"$B" config set gateway.port 18789 --strict-json
"$B" config set gateway.trustedProxies '["127.0.0.1","::1"]' --strict-json
"$B" config set gateway.auth.mode trusted-proxy
"$B" config set gateway.auth.trustedProxy.userHeader cf-access-authenticated-user-email
"$B" config set gateway.auth.trustedProxy.requiredHeaders '["cf-access-jwt-assertion","x-forwarded-proto"]' --strict-json
"$B" config set gateway.auth.trustedProxy.allowUsers "[\"$ALLOWED_EMAIL\"]" --strict-json
"$B" config set gateway.auth.trustedProxy.allowLoopback true --strict-json
"$B" config set gateway.auth.trustedProxy.deviceAutoApprove.enabled true --strict-json
"$B" config set gateway.auth.trustedProxy.deviceAutoApprove.scopes '["operator.read","operator.write","operator.approvals"]' --strict-json
"$B" config set gateway.controlUi.allowedOrigins "[\"https://$HOSTNAME\"]" --strict-json
"$B" config set agents.defaults.model.primary openai/gpt-5.6-sol
"$B" config validate

cat >/etc/systemd/system/openclaw-gateway.service <<EOF
[Unit]
Description=OpenClaw Gateway
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
Environment=HOME=/root
ExecStart=$B gateway --port 18789
Restart=always
RestartSec=5
RestartPreventExitStatus=78
TimeoutStopSec=30
TimeoutStartSec=30
SuccessExitStatus=0 143
OOMPolicy=continue
KillMode=control-group

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now openclaw-gateway.service

ready=false
for i in $(seq 1 90); do
  if curl -fsS --max-time 5 http://127.0.0.1:18789/ >/dev/null; then ready=true; break; fi
  sleep 5
done
[ "$ready" = true ]

mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" >/etc/apt/sources.list.d/cloudflared.list
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y cloudflared
printf '%s' {token} >/root/.openclaw-tunnel-token
chmod 600 /root/.openclaw-tunnel-token
cloudflared service install "$(cat /root/.openclaw-tunnel-token)"
rm -f /root/.openclaw-tunnel-token
systemctl enable --now cloudflared.service

touch /var/lib/openclaw-dashboard-ready
printf 'OPENCLAW_DASHBOARD_READY=true\\n' >/dev/console
'''
    cloud_cfg = "#cloud-config\nwrite_files:\n  - path: /usr/local/sbin/bootstrap-openclaw-dashboard.sh\n    permissions: '0700'\n    owner: root:root\n    encoding: b64\n    content: " + base64.b64encode(script.encode()).decode() + "\nruncmd:\n  - [ bash, /usr/local/sbin/bootstrap-openclaw-dashboard.sh ]\n"
    return base64.b64encode(cloud_cfg.encode()).decode()


def launch(compute, identity, vnet, compartment_id, subnet, image, os_name, user_data):
    ads = identity.list_availability_domains(compartment_id=compartment_id).data
    errors = []
    for ad in ads:
        try:
            log("DASHBOARD_LAUNCH_ATTEMPT", ad=ad.name, shape=SHAPE)
            details = oci.core.models.LaunchInstanceDetails(
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
                metadata={"user_data": user_data},
                freeform_tags={
                    "managed-by": "chatgpt",
                    "purpose": "openclaw-secure-dashboard-always-free",
                },
            )
            instance = compute.launch_instance(details).data
            instance = wait(compute.get_instance, instance.id, desired=("RUNNING",), timeout=1200)
            ip = None
            for _ in range(24):
                ip = instance_public_ip(compute, vnet, compartment_id, instance.id)
                if ip:
                    break
                time.sleep(5)
            return instance, ad.name, ip, errors
        except ServiceError as exc:
            err = {"ad": ad.name, "status": exc.status, "code": exc.code, "message": (exc.message or "")[:200]}
            errors.append(err)
            log("DASHBOARD_LAUNCH_FAILED", **err)
            # E2 Micro is commonly placed in only one AD. Keep trying other ADs
            # for authorization/not-found and capacity placement failures only.
            text = f"{exc.code or ''} {exc.message or ''}".lower()
            if exc.status == 404 or "capacity" in text or "shape" in text:
                continue
            raise
    return None, None, None, errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--tunnel-token-file", required=True)
    ap.add_argument("--hostname", required=True)
    ap.add_argument("--allowed-email", required=True)
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args()

    config = load_config(args.config)
    compartment_id = config["tenancy"]
    compute = oci.core.ComputeClient(config)
    vnet = oci.core.VirtualNetworkClient(config)
    identity = oci.identity.IdentityClient(config)

    existing = existing_instance(compute, compartment_id)
    if existing:
        result = {
            "status": "existing",
            "instance_id": existing.id,
            "shape": existing.shape,
            "lifecycle_state": existing.lifecycle_state,
            "public_ip": instance_public_ip(compute, vnet, compartment_id, existing.id),
        }
        Path(args.result_json).write_text(json.dumps(result))
        log("DASHBOARD_INSTANCE_EXISTS", shape=existing.shape, state=existing.lifecycle_state)
        return 0

    # Hard zero-cost guardrail: Oracle Always Free includes at most two E2 Micro
    # instances. Never attempt a third live E2 Micro instance.
    live_e2 = [x for x in live_instances(compute, compartment_id) if x.shape == SHAPE]
    log("LIVE_E2_COUNT", count=len(live_e2))
    if len(live_e2) >= 2:
        result = {"status": "blocked_free_tier_limit", "live_e2_count": len(live_e2)}
        Path(args.result_json).write_text(json.dumps(result))
        return 0

    subnet, sl = get_network(vnet, compartment_id)
    os_name, image = choose_image(compute, compartment_id)
    token = Path(args.tunnel_token_file).read_text().strip()
    if len(token) < 50:
        raise RuntimeError("INVALID_TUNNEL_TOKEN")
    user_data = cloud_init(token, args.hostname, args.allowed_email)

    instance, ad, ip, errors = launch(
        compute, identity, vnet, compartment_id, subnet, image, os_name, user_data
    )
    if not instance:
        result = {"status": "no_capacity_or_placement", "shape": SHAPE, "errors": errors}
        Path(args.result_json).write_text(json.dumps(result))
        return 0

    result = {
        "status": "created",
        "instance_id": instance.id,
        "availability_domain": ad,
        "lifecycle_state": instance.lifecycle_state,
        "shape": instance.shape,
        "public_ip": ip,
        "os": os_name,
        "security_list_id": sl.id,
        "hostname": args.hostname,
    }
    Path(args.result_json).write_text(json.dumps(result))
    log("DASHBOARD_INSTANCE_CREATED", ad=ad, state=instance.lifecycle_state, public_ip=ip)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        log("DASHBOARD_PROVISION_FAILED", type=type(exc).__name__, message=json.dumps(str(exc)[:400]))
        raise
