#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
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
TAILSCALE_NAME = "openclaw-e2-tailscale"
SHAPE = "VM.Standard.E2.1.Micro"
AUTH_URL_PUBLIC_KEY = '-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA7y7wGpe6lqrEAeicJPhj\nEqKpc6zdHzDchmjmfU3tUcpZUgJbIEOqlgvWOacBXbH2JYXpritU/OtmqNg7Pq6Z\njklbDbo4VAK/hxnhvF66P2mWkqzX1sUl9HOP7IoXvFz3Qd+BPOxWOU2qim/E57gq\njwHMfAUzIn04h7ub2DCm91rB4FmKUriyfFYeprDD99K2zzS0C0oyBY8GuCHGyPt3\ny3B45cTnDUAcIldA+L35tnhCh9q3+F7r2sJHxJeb6XNzPequV3I0dT5m8bFAulCZ\nVxJ5lC5IeU5xEn2lsoEGNJrREG0Jd47f1DQGS7E3zhk3uR863NR4g/fWNtCfm0Qm\niQIDAQAB\n-----END PUBLIC KEY-----'


def existing_instance(compute, compartment_id, name=NAME):
    rows = compute.list_instances(compartment_id=compartment_id, display_name=name).data
    live = [x for x in rows if x.lifecycle_state not in {"TERMINATED", "TERMINATING"}]
    if not live:
        return None
    live.sort(key=lambda x: x.time_created, reverse=True)
    return live[0]


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


def replacement_cloud_init():
    script = r'''#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1

echo "OPENCLAW_TAILSCALE_BOOTSTRAP_START=true" >/dev/console

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
"$B" --version | tee /var/lib/openclaw-version.txt /dev/console

"$B" config set gateway.mode local
"$B" config set gateway.bind loopback
"$B" config set gateway.tailscale.mode serve
"$B" config set gateway.auth.allowTailscale true --strict-json
"$B" config set agents.defaults.model.primary openai/gpt-5.6-sol
"$B" config validate

cat >/etc/systemd/system/openclaw-gateway.service <<EOF
[Unit]
Description=OpenClaw Gateway
After=network-online.target tailscaled.service
Wants=network-online.target tailscaled.service

[Service]
Type=simple
Environment=HOME=/root
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/root/.local/bin
ExecStart=$B gateway --port 18789
Restart=always
RestartSec=10
RestartPreventExitStatus=78
TimeoutStopSec=30
TimeoutStartSec=30
SuccessExitStatus=0 143
OOMPolicy=continue
KillMode=control-group
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable openclaw-gateway.service

curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled

echo "TAILSCALE_AUTH_BEGIN=true" >/dev/console
set +e
tailscale up --hostname=openclaw 2>&1 | tee /var/log/tailscale-up.log /dev/console
TS_RC=${PIPESTATUS[0]}
set -e
if [ "$TS_RC" -ne 0 ]; then
  echo "TAILSCALE_UP_FAILED=$TS_RC" >/dev/console
  exit "$TS_RC"
fi

echo "TAILSCALE_AUTH_COMPLETE=true" >/dev/console
systemctl start openclaw-gateway.service

for i in $(seq 1 180); do
  if "$B" gateway status --require-rpc --timeout 5 >/var/log/openclaw-gateway-status.log 2>&1; then
    DNS="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("Self",{}).get("DNSName") or "").rstrip("."))')"
    TSIP="$(tailscale ip -4 | head -1)"
    if [ -n "$DNS" ]; then
      echo "OPENCLAW_READY_URL=https://$DNS/" | tee /var/lib/openclaw-ready.txt /dev/console
    fi
    echo "OPENCLAW_TAILSCALE_IP=$TSIP" | tee -a /var/lib/openclaw-ready.txt /dev/console
    echo "OPENCLAW_TAILSCALE_READY=true" | tee -a /var/lib/openclaw-ready.txt /dev/console
    exit 0
  fi
  sleep 10
done

echo "OPENCLAW_GATEWAY_WAIT_TIMEOUT=true" >/dev/console
exit 1
'''
    cloud_cfg = (
        "#cloud-config\n"
        "write_files:\n"
        "  - path: /usr/local/sbin/bootstrap-openclaw-tailscale.sh\n"
        "    permissions: '0700'\n"
        "    owner: root:root\n"
        "    encoding: b64\n"
        "    content: " + base64.b64encode(script.encode()).decode() + "\n"
        "runcmd:\n"
        "  - [ bash, /usr/local/sbin/bootstrap-openclaw-tailscale.sh ]\n"
    )
    return base64.b64encode(cloud_cfg.encode()).decode()


def instance_subnet_id(compute, vnet, compartment_id, instance_id):
    atts = compute.list_vnic_attachments(compartment_id=compartment_id, instance_id=instance_id).data
    if not atts:
        raise RuntimeError("OPENCLAW_VNIC_NOT_FOUND")
    return vnet.get_vnic(atts[0].vnic_id).data.subnet_id


def encrypt_for_chat(value: str) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    key = serialization.load_pem_public_key(AUTH_URL_PUBLIC_KEY.encode())
    encrypted = key.encrypt(
        value.encode(),
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )
    return base64.b64encode(encrypted).decode()


def ensure_console_connection(compute, compartment_id, instance_id, public_key_file):
    rows = compute.list_instance_console_connections(
        compartment_id=compartment_id,
        instance_id=instance_id,
    ).data
    active = [x for x in rows if x.lifecycle_state in {"ACTIVE", "CREATING"}]
    if active:
        conn = active[0]
    else:
        public_key = Path(public_key_file).read_text().strip()
        conn = compute.create_instance_console_connection(
            oci.core.models.CreateInstanceConsoleConnectionDetails(
                instance_id=instance_id,
                public_key=public_key,
                freeform_tags={"managed-by": "chatgpt", "purpose": "openclaw-bootstrap-console"},
            )
        ).data
    deadline = time.time() + 180
    while time.time() < deadline:
        conn = compute.get_instance_console_connection(conn.id).data
        if conn.lifecycle_state == "ACTIVE":
            return conn
        if conn.lifecycle_state == "FAILED":
            raise RuntimeError("INSTANCE_CONSOLE_CONNECTION_FAILED")
        time.sleep(5)
    raise TimeoutError("INSTANCE_CONSOLE_CONNECTION_TIMEOUT")


def capture_console(compute, instance_id):
    history = compute.capture_console_history(
        oci.core.models.CaptureConsoleHistoryDetails(
            instance_id=instance_id,
            display_name="openclaw-tailscale-bootstrap",
        )
    ).data
    deadline = time.time() + 180
    while time.time() < deadline:
        history = compute.get_console_history(history.id).data
        if history.state == "SUCCEEDED":
            response = compute.get_console_history_content(history.id)
            data = response.data
            if hasattr(data, "content"):
                data = data.content
            if hasattr(data, "read"):
                data = data.read()
            if isinstance(data, bytes):
                return data.decode("utf-8", "replace")
            return str(data)
        if history.state == "FAILED":
            raise RuntimeError("CONSOLE_HISTORY_FAILED")
        time.sleep(5)
    raise TimeoutError("CONSOLE_HISTORY_TIMEOUT")


def report_console_state(text: str, result: dict):
    ready = re.findall(r"OPENCLAW_READY_URL=(https://[^\s]+)", text)
    if ready:
        url = ready[-1].strip()
        log("OPENCLAW_TAILSCALE_READY", url=url)
        result["status"] = "tailscale_ready"
        result["ready_url"] = url
        return True

    urls = re.findall(r"https://login\.tailscale\.com/[^\s<>'\"]+", text)
    auth_urls = [u.rstrip(".,)") for u in urls if "/a/" in u]
    other_urls = [u.rstrip(".,)") for u in urls if "/a/" not in u]
    if auth_urls:
        cipher = encrypt_for_chat(auth_urls[-1])
        print("TAILSCALE_AUTH_URL_ENCRYPTED=" + cipher, flush=True)
        result["status"] = "tailscale_auth_pending"
        return True
    if other_urls:
        cipher = encrypt_for_chat(other_urls[-1])
        print("TAILSCALE_CONSENT_URL_ENCRYPTED=" + cipher, flush=True)
        result["status"] = "tailscale_consent_pending"
        return True

    if "TAILSCALE_AUTH_COMPLETE=true" in text:
        result["status"] = "tailscale_authenticated_gateway_starting"
        return True
    if "OPENCLAW_TAILSCALE_BOOTSTRAP_START=true" in text:
        result["status"] = "tailscale_bootstrapping"
        return True
    return False


def inspect_replacement(compute, compartment_id, instance, public_key_file):
    ensure_console_connection(compute, compartment_id, instance.id, public_key_file)
    text = capture_console(compute, instance.id)
    result = {
        "instance_id": instance.id,
        "shape": instance.shape,
        "lifecycle_state": instance.lifecycle_state,
    }
    if not report_console_state(text, result):
        result["status"] = "tailscale_console_pending"
    return result


def launch_replacement(config, compute, vnet, identity, compartment_id, old_instance, public_key_file):
    live_e2 = [
        x for x in compute.list_instances(compartment_id=compartment_id).data
        if x.lifecycle_state not in {"TERMINATED", "TERMINATING"} and x.shape == SHAPE
    ]
    log("LIVE_E2_COUNT", count=len(live_e2))
    if len(live_e2) >= 2:
        raise RuntimeError("ALWAYS_FREE_E2_LIMIT_GUARD")

    subnet_id = instance_subnet_id(compute, vnet, compartment_id, old_instance.id)
    os_name, image = choose_image(compute, compartment_id)
    ads = identity.list_availability_domains(compartment_id=compartment_id).data
    errors = []
    for ad in ads:
        log("TAILSCALE_REPLACEMENT_LAUNCH_ATTEMPT", ad=ad.name, shape=SHAPE)
        try:
            details = oci.core.models.LaunchInstanceDetails(
                availability_domain=ad.name,
                compartment_id=compartment_id,
                display_name=TAILSCALE_NAME,
                shape=SHAPE,
                source_details=oci.core.models.InstanceSourceViaImageDetails(
                    source_type="image",
                    image_id=image.id,
                ),
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=subnet_id,
                    assign_public_ip=True,
                    display_name=f"{TAILSCALE_NAME}-vnic",
                ),
                metadata={"user_data": replacement_cloud_init()},
                freeform_tags={
                    "managed-by": "chatgpt",
                    "purpose": "openclaw-tailscale-always-free",
                    "replacement-for": NAME,
                },
            )
            instance = compute.launch_instance(details).data
            instance = wait(compute.get_instance, instance.id, desired=("RUNNING",), timeout=1200)
            ip = instance_public_ip(compute, vnet, compartment_id, instance.id)
            log("TAILSCALE_REPLACEMENT_CREATED", ad=ad.name, state=instance.lifecycle_state, public_ip=ip)
            time.sleep(45)
            result = inspect_replacement(compute, compartment_id, instance, public_key_file)
            result.update({
                "availability_domain": ad.name,
                "public_ip": ip,
                "os": os_name,
                "plan": "TAILSCALE_REPLACEMENT",
            })
            return result
        except ServiceError as exc:
            err = {
                "status": exc.status,
                "code": exc.code,
                "message": (exc.message or "")[:240],
                "ad": ad.name,
            }
            errors.append(err)
            log("TAILSCALE_REPLACEMENT_LAUNCH_FAILED", **err)
            text = f"{exc.code or ''} {exc.message or ''}".lower()
            if exc.status == 404 or "capacity" in text or "shape" in text:
                continue
            raise
    return {"status": "replacement_blocked_after_all_ads", "errors": errors, "shape": SHAPE}


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

    replacement = existing_instance(compute, compartment_id, TAILSCALE_NAME)
    if replacement:
        result = inspect_replacement(compute, compartment_id, replacement, args.ssh_public_key_file)
        result["public_ip"] = instance_public_ip(compute, vnet, compartment_id, replacement.id)
        result["plan"] = "TAILSCALE_REPLACEMENT"
        Path(args.result_json).write_text(json.dumps(result))
        print("OCI_RESULT_STATUS=" + result["status"], flush=True)
        return 0

    existing = existing_instance(compute, compartment_id, NAME)
    if existing:
        ip = instance_public_ip(compute, vnet, compartment_id, existing.id)
        log("OPENCLAW_PLAN_B_EXISTS", state=existing.lifecycle_state, shape=existing.shape, public_ip=ip)
        result = launch_replacement(
            config, compute, vnet, identity, compartment_id, existing, args.ssh_public_key_file
        )
        Path(args.result_json).write_text(json.dumps(result))
        print("OCI_RESULT_STATUS=" + str(result.get("status")), flush=True)
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
