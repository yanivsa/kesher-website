#!/usr/bin/env bash
set -Eeuo pipefail

PUB_B64="${1:?public key b64 required}"
MNT=/mnt/openclaw-target
mkdir -p "$MNT"

root_src="$(findmnt -n -o SOURCE /)"
root_parent="$(lsblk -no PKNAME "$root_src" 2>/dev/null | head -1 || true)"
if [ -n "$root_parent" ]; then
  root_disk="/dev/$root_parent"
else
  root_disk="$root_src"
fi
printf 'OFFLINE_REPAIR_HELPER_ROOT_DISK=%s\n' "$root_disk"

target_disk=""
for i in $(seq 1 120); do
  while read -r dev typ; do
    [ "$typ" = disk ] || continue
    [ "$dev" = "$root_disk" ] && continue
    target_disk="$dev"
    break
  done < <(lsblk -dnpo NAME,TYPE)
  [ -n "$target_disk" ] && break
  sleep 2
done
[ -n "$target_disk" ] || {
  echo OFFLINE_REPAIR_DATA_DISK_NOT_FOUND=true
  lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS || true
  exit 1
}
echo OFFLINE_REPAIR_DATA_DISK="$target_disk"

# Do not depend on lsblk/udev having populated FSTYPE for a newly attached OCI
# boot volume. Try every partition on the non-helper disk, largest first; if
# there are no partitions, try the whole disk. mount(8) will auto-detect the
# filesystem and harmlessly reject EFI/swap/non-filesystem candidates.
mapfile -t candidates < <(
  lsblk -brnpo NAME,SIZE,TYPE "$target_disk" \
    | awk '$3=="part" {print $1, $2}' \
    | sort -k2,2nr | awk '{print $1}'
)
if [ "${#candidates[@]}" -eq 0 ]; then
  candidates=("$target_disk")
fi
printf 'OFFLINE_REPAIR_CANDIDATE_COUNT=%s\n' "${#candidates[@]}"

root_part=""
for part in "${candidates[@]}"; do
  printf 'OFFLINE_REPAIR_TRY_PART=%s\n' "$part"
  mountpoint -q "$MNT" && umount "$MNT" || true
  if mount -o rw "$part" "$MNT" 2>/tmp/openclaw-mount.err; then
    if [ -f "$MNT/etc/os-release" ] && [ -d "$MNT/var/lib/tailscale" ]; then
      root_part="$part"
      break
    fi
    umount "$MNT"
  fi
done
[ -n "$root_part" ] || {
  echo OFFLINE_REPAIR_TARGET_ROOT_NOT_FOUND=true
  lsblk -o NAME,SIZE,TYPE,FSTYPE,PARTLABEL,PARTUUID,MOUNTPOINTS || true
  blkid || true
  sed -E 's#https?://[^[:space:]]+#<REDACTED_URL>#g' /tmp/openclaw-mount.err 2>/dev/null || true
  exit 1
}
echo OFFLINE_REPAIR_TARGET_ROOT="$root_part"

cleanup() {
  sync || true
  mountpoint -q "$MNT" && umount "$MNT" || true
}
trap cleanup EXIT

install -d -m 755 "$MNT/usr/local/sbin"
cat >"$MNT/usr/local/sbin/openclaw-offline-finalize.sh" <<'TARGET'
#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1
exec >>/var/log/openclaw-offline-finalize.log 2>&1

echo "FINALIZE_START=$(date -Is)"
systemctl enable --now tailscaled.service
for i in $(seq 1 120); do
  state="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", ""))' 2>/dev/null || true)"
  [ "$state" = Running ] && break
  sleep 2
done
state="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", ""))' 2>/dev/null || true)"
[ "$state" = Running ] || { echo "TAILSCALE_NOT_RUNNING=$state"; exit 20; }

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
[ -n "$B" ] || { echo OPENCLAW_BINARY_MISSING=true; exit 21; }
"$B" config set gateway.mode local >/dev/null
"$B" config set gateway.bind loopback >/dev/null
"$B" config set gateway.tailscale.mode serve >/dev/null
"$B" config set gateway.auth.allowTailscale true --strict-json >/dev/null
"$B" config set agents.defaults.model.primary openai/gpt-5.6-sol >/dev/null
"$B" config validate >/dev/null

systemctl disable --now openclaw-wait-tailnet.service >/dev/null 2>&1 || true
systemctl daemon-reload
systemctl enable openclaw-gateway.service >/dev/null
systemctl restart openclaw-gateway.service

for i in $(seq 1 60); do
  if "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1; then
    break
  fi
  sleep 2
done
"$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1 || {
  echo OPENCLAW_GATEWAY_RPC_FAILED=true
  tail -80 /tmp/openclaw-gateway-status.txt || true
  exit 22
}

if ! tailscale serve status 2>/dev/null | grep -q 'https://'; then
  set +e
  serve_out="$(tailscale serve --bg --yes http://127.0.0.1:18789 2>&1)"
  serve_rc=$?
  set -e
  printf '%s\n' "$serve_out" | sed -E 's#https?://[^[:space:]]+#<REDACTED_URL>#g'
  if [ "$serve_rc" -ne 0 ]; then
    echo TAILSCALE_SERVE_COMMAND_FAILED=true
    exit 23
  fi
fi
for i in $(seq 1 60); do
  tailscale serve status 2>/dev/null | grep -q 'https://' && break
  sleep 2
done
SERVE="$(tailscale serve status 2>/dev/null || true)"
printf '%s\n' "$SERVE" | grep -q 'https://' || { echo TAILSCALE_SERVE_NOT_READY=true; exit 24; }

DNS="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("Self",{}).get("DNSName") or "").rstrip("."))')"
TSIP="$(tailscale ip -4 | head -1)"
[ -n "$DNS" ] || { echo TAILSCALE_DNS_MISSING=true; exit 25; }
mkdir -p /var/lib
cat >/var/lib/openclaw-ready.txt <<EOF
OPENCLAW_TAILSCALE_FINALIZED=true
TAILSCALE_BACKEND_STATE=$state
OPENCLAW_TAILSCALE_DNS=$DNS
OPENCLAW_TAILSCALE_IP=$TSIP
OPENCLAW_READY_URL=https://$DNS/
EOF
echo OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true
TARGET
chmod 755 "$MNT/usr/local/sbin/openclaw-offline-finalize.sh"

cat >"$MNT/etc/systemd/system/openclaw-offline-finalize.service" <<'UNIT'
[Unit]
Description=Finalize OpenClaw securely on the authenticated Tailscale tailnet
After=network-online.target tailscaled.service
Wants=network-online.target
Requires=tailscaled.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/openclaw-offline-finalize.sh
RemainAfterExit=yes
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
UNIT
mkdir -p "$MNT/etc/systemd/system/multi-user.target.wants"
ln -sfn ../openclaw-offline-finalize.service "$MNT/etc/systemd/system/multi-user.target.wants/openclaw-offline-finalize.service"

pub="$(printf '%s' "$PUB_B64" | base64 -d)"
read -r keytype keydata _ <<<"$pub"
[ -n "$keytype" ] && [ -n "$keydata" ]
install -d -m 700 "$MNT/home/ubuntu/.ssh"
touch "$MNT/home/ubuntu/.ssh/authorized_keys"
sed -i '/ openclaw-offline-recovery$/d' "$MNT/home/ubuntu/.ssh/authorized_keys"
printf '%s %s openclaw-offline-recovery\n' "$keytype" "$keydata" >>"$MNT/home/ubuntu/.ssh/authorized_keys"
chmod 600 "$MNT/home/ubuntu/.ssh/authorized_keys"
chown -R 1000:1000 "$MNT/home/ubuntu/.ssh"

sync
echo OFFLINE_REPAIR_DISK_PATCHED=true
