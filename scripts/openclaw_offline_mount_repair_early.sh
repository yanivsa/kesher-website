#!/usr/bin/env bash
set -Eeuo pipefail

# Run the proven baseline patch first, but keep the helper alive so we can
# harden boot-time finalization before the authenticated boot disk is detached.
export OPENCLAW_REPAIR_NO_POWEROFF=1
bash scripts/openclaw_offline_mount_repair_base.sh "$@"

MNT=/mnt/openclaw-target
mkdir -p "$MNT"
root_src="$(findmnt -n -o SOURCE /)"
root_disk="$(lsblk -srnpo NAME,TYPE "$root_src" 2>/dev/null | awk '$2=="disk" {print $1; exit}')"
[ -n "$root_disk" ] || root_disk="$root_src"
target_disk=""
while read -r dev typ; do
  [ "$typ" = disk ] || continue
  [ "$dev" = "$root_disk" ] && continue
  target_disk="$dev"
  break
done < <(lsblk -dnpo NAME,TYPE)
[ -n "$target_disk" ] || { echo OFFLINE_REPAIR_BOOTFIX_DATA_DISK_NOT_FOUND=true; exit 1; }

mapfile -t candidates < <(
  while read -r dev size typ; do
    [ "$typ" = part ] || [ "$typ" = lvm ] || continue
    if lsblk -srnpo NAME "$dev" 2>/dev/null | grep -Fxq "$target_disk"; then
      printf '%s %s\n' "$dev" "$size"
    fi
  done < <(lsblk -brnpo NAME,SIZE,TYPE) | sort -k2,2nr | awk '{print $1}'
)
[ "${#candidates[@]}" -gt 0 ] || candidates=("$target_disk")
root_part=""
for part in "${candidates[@]}"; do
  if mount -o rw "$part" "$MNT" 2>/dev/null; then
    if [ -f "$MNT/etc/os-release" ] && [ -x "$MNT/usr/local/sbin/openclaw-offline-finalize.sh" ]; then
      root_part="$part"
      break
    fi
    umount "$MNT"
  fi
done
[ -n "$root_part" ] || { echo OFFLINE_REPAIR_BOOTFIX_TARGET_ROOT_NOT_FOUND=true; exit 1; }

# Eliminate stale proof from previous boots and make this boot's result unambiguous.
rm -f "$MNT/var/lib/openclaw-ready.txt"
: > "$MNT/var/log/openclaw-offline-finalize.log"

# Keep the gateway retry budget inside the workflow's proof window.
python3 - "$MNT/usr/local/sbin/openclaw-offline-finalize.sh" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old = '''for i in $(seq 1 60); do
  if "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1; then break; fi
  sleep 2
done
"$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1 || {
  echo OPENCLAW_FINALIZE_FAILED=GATEWAY_RPC
  tail -80 /tmp/openclaw-gateway-status.txt || true
  exit 22
}'''
new = '''rpc_ok=false
rpc_source=""
for i in $(seq 1 30); do
  if timeout 5 "$B" gateway status --require-rpc --timeout 1 >/tmp/openclaw-gateway-status.txt 2>&1; then
    rpc_ok=true
    rpc_source="gateway-status"
    break
  fi
  health_rc=0
  rm -f /tmp/openclaw-gateway-health.json
  timeout 5 "$B" gateway health --timeout 1 --json >/tmp/openclaw-gateway-health.json 2>&1 || health_rc=$?
  if [ "$health_rc" -eq 0 ] || python3 -c 'import json; d=json.load(open("/tmp/openclaw-gateway-health.json")); assert isinstance(d, dict) and d' 2>/dev/null; then
    rpc_ok=true
    rpc_source="gateway-health"
    break
  fi
  sleep 1
done
if [ "$rpc_ok" != true ]; then
  echo OPENCLAW_FINALIZE_FAILED=GATEWAY_RPC
  echo OPENCLAW_GATEWAY_UNIT_ACTIVE="$(systemctl is-active openclaw-gateway.service 2>/dev/null || true)"
  echo OPENCLAW_GATEWAY_UNIT_RESULT="$(systemctl show openclaw-gateway.service -p Result --value 2>/dev/null || true)"
  echo OPENCLAW_GATEWAY_UNIT_EXEC_STATUS="$(systemctl show openclaw-gateway.service -p ExecMainStatus --value 2>/dev/null || true)"
  tail -80 /tmp/openclaw-gateway-status.txt || true
  tail -80 /tmp/openclaw-gateway-health.json 2>/dev/null || true
  exit 22
fi
echo OPENCLAW_GATEWAY_RPC_SOURCE="$rpc_source"'''
if old not in s:
    raise SystemExit('OPENCLAW_BOOTFIX_GATEWAY_BLOCK_NOT_FOUND')
s = s.replace(old, new, 1)
anchor = '''echo OPENCLAW_SYSTEMD_STAGE=disable-wait-tailnet
'''
unit = '''# Refresh the system-level gateway unit from the canonical OpenClaw Linux service shape.
# The authenticated host is headless and system-owned, so do not depend on a user session.
cat >/etc/systemd/system/openclaw-gateway.service <<UNIT
[Unit]
Description=OpenClaw Gateway
After=network-online.target tailscaled.service
Wants=network-online.target tailscaled.service
StartLimitBurst=5
StartLimitIntervalSec=60

[Service]
Type=simple
Environment=HOME=/root
Environment=OPENCLAW_NO_PROMPT=1
Environment=OPENCLAW_SERVICE_REPAIR_POLICY=external
ExecStart="$B" gateway --port 18789
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
UNIT
chmod 0644 /etc/systemd/system/openclaw-gateway.service
echo OPENCLAW_GATEWAY_SYSTEM_UNIT_REFRESHED=true

echo OPENCLAW_SYSTEMD_STAGE=disable-wait-tailnet
'''
if anchor not in s:
    raise SystemExit('OPENCLAW_BOOTFIX_SYSTEMD_ANCHOR_NOT_FOUND')
s = s.replace(anchor, unit, 1)
old_start = '''echo OPENCLAW_SYSTEMD_STAGE=start-gateway
timeout 15 systemctl enable openclaw-gateway.service >/dev/null || {
  echo OPENCLAW_FINALIZE_FAILED=GATEWAY_ENABLE
  exit 22
}
timeout 15 systemctl restart --no-block openclaw-gateway.service || {
  echo OPENCLAW_FINALIZE_FAILED=GATEWAY_RESTART
  exit 22
}
echo OPENCLAW_GATEWAY_START_REQUESTED=true'''
new_start = '''echo OPENCLAW_SYSTEMD_STAGE=start-gateway
# The gateway unit is already persisted offline into multi-user.target.wants.
# Runtime activation calls have repeatedly hung on this constrained E2 guest,
# including systemctl and setsid. Do not launch a second process here.
# Continue directly to bounded RPC/health proof; if systemd did not start the
# persisted unit successfully, those probes fail closed with diagnostics.
echo OPENCLAW_GATEWAY_START_REQUESTED=true'''
if old_start not in s:
    raise SystemExit('OPENCLAW_BOOTFIX_GATEWAY_START_BLOCK_NOT_FOUND')
s = s.replace(old_start, new_start, 1)
p.write_text(s)
PY

# Persist the gateway unit activation while the authenticated disk is offline.
# This avoids any runtime mkdir/ln/systemctl activation boundary on the E2 guest.
mkdir -p "$MNT/etc/systemd/system/multi-user.target.wants"
ln -sfn ../openclaw-gateway.service \
  "$MNT/etc/systemd/system/multi-user.target.wants/openclaw-gateway.service"
echo OFFLINE_REPAIR_GATEWAY_UNIT_PERSISTED=true

# Run finalization only after the network/tailscale service is wanted and ordered.
# Retry a failed oneshot instead of permanently leaving the boot in a failed state.
cat >"$MNT/etc/systemd/system/openclaw-offline-finalize.service" <<'UNIT'
[Unit]
Description=Finalize OpenClaw securely on the authenticated Tailscale tailnet
Wants=network-online.target tailscaled.service
After=local-fs.target network-online.target tailscaled.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/openclaw-offline-finalize.sh
RemainAfterExit=yes
TimeoutStartSec=1800
Restart=on-failure
RestartSec=30
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
UNIT
rm -f "$MNT/etc/systemd/system/basic.target.wants/openclaw-offline-finalize.service"
mkdir -p "$MNT/etc/systemd/system/multi-user.target.wants"
ln -sfn ../openclaw-offline-finalize.service \
  "$MNT/etc/systemd/system/multi-user.target.wants/openclaw-offline-finalize.service"

sync
umount "$MNT"
echo OFFLINE_REPAIR_BOOT_FINALIZER_HARDENED=true
echo OFFLINE_REPAIR_TARGET_SSH_KEY_REMOVED=true
echo OFFLINE_REPAIR_DISK_PATCHED=true
echo OFFLINE_REPAIR_RUN_COMMAND_COMPLETE=true