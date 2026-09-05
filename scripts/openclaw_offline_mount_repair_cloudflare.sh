#!/usr/bin/env bash
set -Eeuo pipefail

# Reuse the proven preserved-disk recovery mechanics, then replace only the
# guest finalization/exposure contract. Tailscale is not required for success;
# the public lane is verified later by the Cloudflare Tunnel workflow.
export OPENCLAW_REPAIR_NO_POWEROFF=1
bash scripts/openclaw_offline_mount_repair_early.sh "$@"

MNT=/mnt/openclaw-target
mkdir -p "$MNT"
cleanup() {
  rc=$?
  mountpoint -q "$MNT" && umount "$MNT" || true
  exit "$rc"
}
trap cleanup EXIT

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
[ -n "$target_disk" ] || { echo OPENCLAW_CLOUDFLARE_REPAIR_FAILED=DATA_DISK_NOT_FOUND; exit 51; }

if command -v vgscan >/dev/null 2>&1; then
  udevadm settle 2>/dev/null || true
  pvscan --cache >/dev/null 2>&1 || true
  vgscan --mknodes >/dev/null 2>&1 || true
  vgchange -ay >/dev/null 2>&1 || true
  udevadm settle 2>/dev/null || true
fi

mapfile -t candidates < <(
  while read -r dev size typ; do
    case "$typ" in part|lvm) ;; *) continue ;; esac
    if lsblk -srnpo NAME "$dev" 2>/dev/null | grep -Fxq "$target_disk"; then
      printf '%s %s\n' "$dev" "$size"
    fi
  done < <(lsblk -brnpo NAME,SIZE,TYPE) | sort -k2,2nr | awk '{print $1}'
)
[ "${#candidates[@]}" -gt 0 ] || candidates=("$target_disk")

root_part=""
for part in "${candidates[@]}"; do
  mountpoint -q "$MNT" && umount "$MNT" || true
  if mount -o rw "$part" "$MNT" 2>/dev/null; then
    if [ -f "$MNT/etc/os-release" ] && [ -d "$MNT/usr" ]; then
      root_part="$part"
      break
    fi
    umount "$MNT"
  fi
done
[ -n "$root_part" ] || { echo OPENCLAW_CLOUDFLARE_REPAIR_FAILED=TARGET_ROOT_NOT_FOUND; exit 52; }

# Disable OpenClaw-managed Tailscale exposure on the preserved guest.
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
gateway.setdefault('tailscale', {})['mode'] = 'off'
gateway.setdefault('auth', {})['allowTailscale'] = False
agents = data.setdefault('agents', {})
defaults = agents.setdefault('defaults', {})
defaults.setdefault('model', {})['primary'] = 'openai/gpt-5.6-sol'

tmp = path.with_suffix('.json.tmp')
tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
tmp.replace(path)
PYCFG

# The gateway is system-owned, loopback-only, and independent of tailscaled.
cat >"$MNT/etc/systemd/system/openclaw-gateway.service" <<'UNIT'
[Unit]
Description=OpenClaw Gateway
After=network-online.target
Wants=network-online.target
StartLimitBurst=5
StartLimitIntervalSec=60

[Service]
Type=simple
Environment=HOME=/root
Environment=OPENCLAW_NO_PROMPT=1
Environment=OPENCLAW_SERVICE_REPAIR_POLICY=external
ExecStart=/usr/local/bin/openclaw gateway --port 18789
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

# Finalization proves only the local gateway. Public availability is a separate
# Cloudflare proof, so a Tailscale outage/login state cannot block boot.
cat >"$MNT/usr/local/sbin/openclaw-offline-finalize.sh" <<'TARGET'
#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1
exec > >(tee -a /var/log/openclaw-offline-finalize.log) 2>&1

echo "OPENCLAW_FINALIZE_START=$(date -Is)"
echo OPENCLAW_TAILSCALE_REQUIRED=false

if ! swapon --show=NAME --noheadings 2>/dev/null | grep -Fxq /swapfile; then
  swapon /swapfile >/dev/null 2>&1 || true
fi

B="$(command -v openclaw 2>/dev/null || true)"
if [ -z "$B" ]; then
  for candidate in /usr/local/bin/openclaw /usr/bin/openclaw /root/.local/bin/openclaw /root/.npm-global/bin/openclaw; do
    if [ -x "$candidate" ]; then B="$candidate"; break; fi
  done
fi
[ -n "$B" ] || { echo OPENCLAW_FINALIZE_FAILED=OPENCLAW_BINARY_MISSING; exit 21; }

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
gateway.setdefault('tailscale', {})['mode'] = 'off'
gateway.setdefault('auth', {})['allowTailscale'] = False
agents = data.setdefault('agents', {})
defaults = agents.setdefault('defaults', {})
defaults.setdefault('model', {})['primary'] = 'openai/gpt-5.6-sol'

tmp = path.with_suffix('.json.tmp')
tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
tmp.replace(path)
PYCFG

python3 - <<'PYVERIFY'
import json
from pathlib import Path

data = json.loads(Path('/root/.openclaw/openclaw.json').read_text())
gateway = data.get('gateway', {})
checks = {
    'gateway.mode': gateway.get('mode') == 'local',
    'gateway.bind': gateway.get('bind') == 'loopback',
    'gateway.tailscale.mode': gateway.get('tailscale', {}).get('mode') == 'off',
    'gateway.auth.allowTailscale': gateway.get('auth', {}).get('allowTailscale') is False,
}
missing = [key for key, ok in checks.items() if not ok]
if missing:
    raise SystemExit('OPENCLAW_CONFIG_VERIFY_FAILED=' + ','.join(missing))
PYVERIFY
echo OPENCLAW_CONFIG_VALIDATED=true

timeout 30 systemctl daemon-reload || {
  echo OPENCLAW_FINALIZE_FAILED=SYSTEMD_DAEMON_RELOAD
  exit 22
}

# Do not rely on parallel multi-user.target ordering. The finalizer owns the
# responsibility for starting the loopback-only gateway before probing RPC.
timeout 30 systemctl enable openclaw-gateway.service >/dev/null 2>&1 || true
if ! timeout 45 systemctl restart openclaw-gateway.service; then
  echo OPENCLAW_FINALIZE_FAILED=GATEWAY_SERVICE_START
  systemctl status openclaw-gateway.service --no-pager -l 2>/dev/null || true
  exit 22
fi
for i in $(seq 1 30); do
  [ "$(systemctl is-active openclaw-gateway.service 2>/dev/null || true)" = active ] && break
  sleep 1
done
gateway_unit_state="$(systemctl is-active openclaw-gateway.service 2>/dev/null || true)"
echo OPENCLAW_GATEWAY_UNIT_ACTIVE="$gateway_unit_state"
if [ "$gateway_unit_state" != active ]; then
  echo OPENCLAW_FINALIZE_FAILED=GATEWAY_UNIT_NOT_ACTIVE
  echo "OPENCLAW_GATEWAY_RESULT=$(systemctl show openclaw-gateway.service -p Result --value 2>/dev/null || true)"
  echo "OPENCLAW_GATEWAY_EXEC_MAIN_CODE=$(systemctl show openclaw-gateway.service -p ExecMainCode --value 2>/dev/null || true)"
  echo "OPENCLAW_GATEWAY_EXEC_MAIN_STATUS=$(systemctl show openclaw-gateway.service -p ExecMainStatus --value 2>/dev/null || true)"
  echo "OPENCLAW_GATEWAY_DISCOVERED_BINARY=$B"
  if [ -x /usr/local/bin/openclaw ]; then
    echo OPENCLAW_GATEWAY_UNIT_BINARY_PRESENT=true
  else
    echo OPENCLAW_GATEWAY_UNIT_BINARY_PRESENT=false
  fi
  echo OPENCLAW_GATEWAY_JOURNAL_BEGIN=true
  systemctl status openclaw-gateway.service --no-pager -l 2>/dev/null || true
  journalctl -u openclaw-gateway.service -n 160 --no-pager 2>/dev/null || true
  journalctl -u openclaw-gateway.service -n 80 --no-pager -o cat > /tmp/openclaw-gateway-journal.txt 2>/dev/null || true
  python3 - <<'PYDIAG'
import re
from pathlib import Path

path = Path('/tmp/openclaw-gateway-journal.txt')
if path.exists():
    interesting = re.compile(
        r"(?i)(error|failed|failure|invalid|cannot|can't|not found|no such|enoent|eacces|permission|exited|status=|config|unsupported|unknown|exception)"
    )
    url = re.compile(r"https?://\S+", re.I)
    secret = re.compile(
        r"(?i)\b(authorization|bearer|token|secret|password|api[_-]?key)\b\s*[:=]\s*(\"[^\"]*\"|'[^']*'|\S+)"
    )
    for raw in path.read_text(errors='replace').splitlines()[-80:]:
        if not interesting.search(raw):
            continue
        line = url.sub('<REDACTED_URL>', raw)
        line = secret.sub(lambda m: f"{m.group(1)}=<REDACTED>", line)
        line = ' '.join(line.split())[:600]
        if line:
            print(f"OPENCLAW_GATEWAY_JOURNAL_LINE={line}")
PYDIAG
  echo OPENCLAW_GATEWAY_JOURNAL_END=true
  exit 22
fi

rpc_ok=false
rpc_source=""
for i in $(seq 1 40); do
  if timeout 8 "$B" gateway status --require-rpc --timeout 3000 >/tmp/openclaw-gateway-status.txt 2>&1; then
    rpc_ok=true
    rpc_source=gateway-status
    break
  fi
  health_rc=0
  rm -f /tmp/openclaw-gateway-health.json
  timeout 8 "$B" gateway health --timeout 3000 --json >/tmp/openclaw-gateway-health.json 2>&1 || health_rc=$?
  if [ "$health_rc" -eq 0 ] || python3 -c 'import json; d=json.load(open("/tmp/openclaw-gateway-health.json")); assert isinstance(d, dict) and d' 2>/dev/null; then
    rpc_ok=true
    rpc_source=gateway-health
    break
  fi
  sleep 2
done
if [ "$rpc_ok" != true ]; then
  echo OPENCLAW_FINALIZE_FAILED=GATEWAY_RPC
  echo OPENCLAW_GATEWAY_UNIT_ACTIVE="$(systemctl is-active openclaw-gateway.service 2>/dev/null || true)"
  systemctl status openclaw-gateway.service --no-pager -l 2>/dev/null || true
  tail -80 /tmp/openclaw-gateway-status.txt 2>/dev/null || true
  tail -80 /tmp/openclaw-gateway-health.json 2>/dev/null || true
  exit 22
fi

echo OPENCLAW_GATEWAY_RPC_SOURCE="$rpc_source"
echo OPENCLAW_GATEWAY_RPC_OK=true
mkdir -p /var/lib
cat >/var/lib/openclaw-ready.txt <<'EOF'
OPENCLAW_LOCAL_FINALIZED=true
OPENCLAW_GATEWAY_BIND=loopback
OPENCLAW_GATEWAY_PORT=18789
OPENCLAW_LOCAL_READY=true
OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true
EOF
echo OPENCLAW_LOCAL_READY=true
echo OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true
TARGET
chmod 0755 "$MNT/usr/local/sbin/openclaw-offline-finalize.sh"

cat >"$MNT/etc/systemd/system/openclaw-offline-finalize.service" <<'UNIT'
[Unit]
Description=Finalize OpenClaw local gateway for Cloudflare Tunnel
Wants=network-online.target swap.target
After=local-fs.target swap.target network-online.target
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

mkdir -p "$MNT/etc/systemd/system/multi-user.target.wants"
ln -sfn ../openclaw-gateway.service "$MNT/etc/systemd/system/multi-user.target.wants/openclaw-gateway.service"
ln -sfn ../openclaw-offline-finalize.service "$MNT/etc/systemd/system/multi-user.target.wants/openclaw-offline-finalize.service"
rm -f "$MNT/etc/systemd/system/basic.target.wants/openclaw-offline-finalize.service"

rm -f "$MNT/var/lib/openclaw-ready.txt"
: >"$MNT/var/log/openclaw-offline-finalize.log"
sync
umount "$MNT"
trap - EXIT

echo OPENCLAW_TAILSCALE_REQUIRED=false
echo OFFLINE_REPAIR_CLOUDFLARE_PRIMARY=true
echo OFFLINE_REPAIR_DISK_PATCHED=true
