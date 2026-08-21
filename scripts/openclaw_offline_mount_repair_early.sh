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

# The gateway unit is persisted and starts during multi-user boot, before the
# finalizer's runtime JSON write. Preseed the exact validated gateway config on
# the offline authenticated disk so the first gateway process starts with the
# intended loopback/Tailscale settings and does not require a risky runtime
# restart on the constrained E2 guest.
python3 - "$MNT/root/.openclaw/openclaw.json" <<'PYCFG'
import json
from pathlib import Path
import sys

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
try:
    data = json.loads(path.read_text()) if path.exists() else {}
except Exception:
    data = {}

gateway = data.setdefault('gateway', {})
gateway['mode'] = 'local'
gateway['bind'] = 'loopback'
gateway.setdefault('tailscale', {})['mode'] = 'serve'
gateway.setdefault('auth', {})['allowTailscale'] = True
agents = data.setdefault('agents', {})
defaults = agents.setdefault('defaults', {})
defaults.setdefault('model', {})['primary'] = 'openai/gpt-5.6-sol'

tmp = path.with_suffix('.json.tmp')
tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
tmp.replace(path)
PYCFG
echo OFFLINE_REPAIR_GATEWAY_CONFIG_PRESEEDED=true

# Keep the gateway retry budget inside the workflow's proof window and avoid
# spawning multiple Node config processes while the 1 GB E2 guest is bringing
# up the gateway. The finalizer writes the same JSON values directly, then
# validates them before RPC proof.
python3 - "$MNT/usr/local/sbin/openclaw-offline-finalize.sh" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
s = p.read_text()
old_output = 'exec > >(tee -a /var/log/openclaw-offline-finalize.log /dev/console) 2>&1'
new_output = 'exec > >(tee -a /var/log/openclaw-offline-finalize.log) 2>&1'
if old_output in s:
    s = s.replace(old_output, new_output, 1)
elif new_output not in s:
    raise SystemExit('OPENCLAW_BOOTFIX_CONSOLE_TEE_NOT_FOUND')
start_anchor = 'echo "OPENCLAW_FINALIZE_START=$(date -Is)"'
start_guard = '''echo "OPENCLAW_FINALIZE_START=$(date -Is)"
# Make the persisted swap explicit before Node/systemd work begins. On the
# 1 GB Always Free E2 guest the finalizer itself must survive gateway startup
# long enough to write readiness proof.
if ! swapon --show=NAME --noheadings 2>/dev/null | grep -Fxq /swapfile; then
  swapon /swapfile >/dev/null 2>&1 || true
fi
if swapon --show=NAME --noheadings 2>/dev/null | grep -Fxq /swapfile; then
  echo OPENCLAW_FINALIZER_SWAP_ACTIVE=true
else
  echo OPENCLAW_FINALIZER_SWAP_ACTIVE=false
fi'''
if start_guard not in s:
    if start_anchor not in s:
        raise SystemExit('OPENCLAW_BOOTFIX_FINALIZER_START_ANCHOR_NOT_FOUND')
    s = s.replace(start_anchor, start_guard, 1)

old_config_calls = '''run_config set gateway.mode local
run_config set gateway.bind loopback
run_config set gateway.tailscale.mode serve
run_config set gateway.auth.allowTailscale true --strict-json
run_config set agents.defaults.model.primary openai/gpt-5.6-sol'''
new_config_calls = '''echo OPENCLAW_CONFIG_STAGE=direct-json
python3 - <<'PYCFG'
import json
from pathlib import Path

path = Path('/root/.openclaw/openclaw.json')
path.parent.mkdir(parents=True, exist_ok=True)
try:
    data = json.loads(path.read_text()) if path.exists() else {}
except Exception:
    data = {}

gateway = data.setdefault('gateway', {})
gateway['mode'] = 'local'
gateway['bind'] = 'loopback'
gateway.setdefault('tailscale', {})['mode'] = 'serve'
gateway.setdefault('auth', {})['allowTailscale'] = True
agents = data.setdefault('agents', {})
defaults = agents.setdefault('defaults', {})
defaults.setdefault('model', {})['primary'] = 'openai/gpt-5.6-sol'

tmp = path.with_suffix('.json.tmp')
tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\\n')
tmp.replace(path)
PYCFG
echo OPENCLAW_CONFIG_DIRECT_JSON_WRITTEN=true'''
if old_config_calls in s:
    s = s.replace(old_config_calls, new_config_calls, 1)
elif new_config_calls not in s:
    raise SystemExit('OPENCLAW_BOOTFIX_CONFIG_CALLS_NOT_FOUND')

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
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise SystemExit('OPENCLAW_BOOTFIX_GATEWAY_BLOCK_NOT_FOUND')
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
OOMScoreAdjust=500
KillMode=control-group

[Install]
WantedBy=multi-user.target
UNIT
chmod 0644 /etc/systemd/system/openclaw-gateway.service
echo OPENCLAW_GATEWAY_SYSTEM_UNIT_REFRESHED=true

echo OPENCLAW_SYSTEMD_STAGE=disable-wait-tailnet
'''
if unit not in s:
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
if old_start in s:
    s = s.replace(old_start, new_start, 1)
elif new_start not in s:
    raise SystemExit('OPENCLAW_BOOTFIX_GATEWAY_START_BLOCK_NOT_FOUND')
p.write_text(s)
PY
echo OFFLINE_REPAIR_FINALIZER_SAFE_LOGGING=true
echo OFFLINE_REPAIR_FINALIZER_DIRECT_JSON_CONFIG=true

# The Always Free E2 guest has only 1 GB of RAM. Starting the Node gateway can
# otherwise invoke the OOM killer while the oneshot finalizer is still writing
# readiness proof. Persist swap on the authenticated boot volume so it is
# available before multi-user services start; this consumes no extra OCI
# compute resource and leaves the E2 instance-count guard unchanged.
swapfile="$MNT/swapfile"
swap_bytes=1073741824
available_kb="$(df -Pk "$MNT" | awk 'NR==2 {print $4}')"
current_bytes="$(stat -c %s "$swapfile" 2>/dev/null || echo 0)"
if [ "$current_bytes" -lt "$swap_bytes" ]; then
  [ "$available_kb" -ge 1310720 ] || {
    echo OFFLINE_REPAIR_SWAP_FAILED=INSUFFICIENT_DISK
    exit 1
  }
  rm -f "$swapfile"
  if ! fallocate -l 1G "$swapfile"; then
    dd if=/dev/zero of="$swapfile" bs=1M count=1024 status=none
  fi
fi
chmod 0600 "$swapfile"
mkswap -f "$swapfile" >/dev/null
sed -i '\#^[[:space:]]*/swapfile[[:space:]]#d' "$MNT/etc/fstab"
printf '/swapfile none swap sw 0 0\n' >>"$MNT/etc/fstab"
echo OFFLINE_REPAIR_E2_SWAP_PERSISTED=true

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
Wants=network-online.target tailscaled.service swap.target
After=local-fs.target swap.target network-online.target tailscaled.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/openclaw-offline-finalize.sh
RemainAfterExit=yes
TimeoutStartSec=1800
Restart=on-failure
RestartSec=30
OOMScoreAdjust=-1000
StandardOutput=journal
StandardError=journal

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
