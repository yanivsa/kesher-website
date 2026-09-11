#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1
umask 077
exec > >(tee -a /var/log/openclaw-clean-finalize.log) 2>&1

PUBLIC_HOSTNAME="${PUBLIC_HOSTNAME:-openclaw.saharoni.com}"
TUNNEL_ID="${TUNNEL_ID:-58988d44-b0c4-4ad0-ba9d-c25b9914e773}"
MNT=/mnt/openclaw-rollback

cleanup_mount() {
  mountpoint -q "$MNT" && umount "$MNT" || true
}
trap cleanup_mount EXIT

echo OPENCLAW_CLEAN_FINALIZE_START=true
cloud-init status --wait
test -f /var/lib/openclaw-installed

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
[ -n "$B" ] || { echo OPENCLAW_CLEAN_FAILED=OPENCLAW_BINARY_MISSING; exit 61; }
"$B" --version >/var/lib/openclaw-version.txt
echo OPENCLAW_CLEAN_INSTALL_VERIFIED=true

# The legacy boot is attached read-only only to recover the tunnel's narrowly
# scoped runtime credential. No OpenClaw state, workspace, SSH keys, Tailscale
# state, or account certificate is copied.
mkdir -p "$MNT"
root_src="$(findmnt -n -o SOURCE /)"
root_disk="$(lsblk -srnpo NAME,TYPE "$root_src" 2>/dev/null | awk '$2=="disk" {print $1; exit}')"
[ -n "$root_disk" ] || root_disk="$root_src"

if command -v vgscan >/dev/null 2>&1; then
  udevadm settle 2>/dev/null || true
  pvscan --cache >/dev/null 2>&1 || true
  vgscan --mknodes >/dev/null 2>&1 || true
  vgchange -ay >/dev/null 2>&1 || true
fi

mapfile -t candidates < <(
  while read -r dev size typ; do
    case "$typ" in part|lvm) ;; *) continue ;; esac
    if ! lsblk -srnpo NAME "$dev" 2>/dev/null | grep -Fxq "$root_disk"; then
      printf '%s %s\n' "$dev" "$size"
    fi
  done < <(lsblk -brnpo NAME,SIZE,TYPE) | sort -k2,2nr | awk '{print $1}'
)

old_root=""
for part in "${candidates[@]}"; do
  cleanup_mount
  if mount -o ro "$part" "$MNT" 2>/dev/null; then
    if [ -f "$MNT/etc/os-release" ] && {
      [ -f "$MNT/etc/systemd/system/cloudflared.service" ] ||
      [ -d "$MNT/etc/cloudflared" ] ||
      [ -d "$MNT/root/.cloudflared" ] ||
      [ -d "$MNT/home/ubuntu/.cloudflared" ];
    }; then
      old_root="$part"
      break
    fi
    umount "$MNT"
  fi
done
[ -n "$old_root" ] || { echo OPENCLAW_CLEAN_FAILED=ROLLBACK_CLOUDFLARED_ROOT_NOT_FOUND; exit 62; }
echo OPENCLAW_CLEAN_ROLLBACK_MOUNTED_READONLY=true

mkdir -p /etc/cloudflared
chmod 700 /etc/cloudflared
rm -f /run/openclaw-migrated-tunnel-token /run/openclaw-migrated-credential.json

# Prefer the remote-tunnel token from the old systemd service. We never print it.
python3 - "$MNT" /run/openclaw-migrated-tunnel-token <<'PY'
from pathlib import Path
import re, shlex, sys

root = Path(sys.argv[1])
out = Path(sys.argv[2])
service_candidates = [
    root / "etc/systemd/system/cloudflared.service",
    root / "usr/lib/systemd/system/cloudflared.service",
    root / "lib/systemd/system/cloudflared.service",
]
texts = []
for p in service_candidates:
    if p.is_file():
        try:
            texts.append(p.read_text(errors="replace"))
        except Exception:
            pass

token = None
for text in texts:
    # Handles both --token VALUE and --token=VALUE.
    m = re.search(r"--token(?:=|\s+)(?:['\"])?([A-Za-z0-9._~-]+)", text)
    if m:
        token = m.group(1)
        break

if not token:
    # Support a unit which references a token file.
    for text in texts:
        m = re.search(r"--token-file(?:=|\s+)(?:['\"])?([^\s'\"]+)", text)
        if not m:
            continue
        token_path = m.group(1)
        p = root / token_path.lstrip("/")
        if p.is_file():
            value = p.read_text(errors="replace").strip()
            if value:
                token = value
                break

if not token:
    # Support Environment=TUNNEL_TOKEN=... or EnvironmentFile=...
    for text in texts:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("Environment=") and "TUNNEL_TOKEN=" in line:
                value = line.split("TUNNEL_TOKEN=", 1)[1].strip().strip("'\"")
                if value:
                    token = value
                    break
            if line.startswith("EnvironmentFile="):
                raw = line.split("=", 1)[1].strip().lstrip("-").strip("'\"")
                p = root / raw.lstrip("/")
                if p.is_file():
                    for env_line in p.read_text(errors="replace").splitlines():
                        if env_line.strip().startswith("TUNNEL_TOKEN="):
                            value = env_line.split("=", 1)[1].strip().strip("'\"")
                            if value:
                                token = value
                                break
            if token:
                break
        if token:
            break

if token:
    out.write_text(token + "\n")
    out.chmod(0o600)
PY

credential_mode=""
if [ -s /run/openclaw-migrated-tunnel-token ]; then
  install -m 600 /run/openclaw-migrated-tunnel-token /etc/cloudflared/tunnel-token
  credential_mode=token
else
  # Fallback for a locally-managed tunnel: copy only the tunnel-specific JSON.
  # Never copy cert.pem because that is an account-wide management credential.
  OLD_ROOT="$MNT" TUNNEL_ID="$TUNNEL_ID" python3 - <<'PY'
import json, os, shutil
from pathlib import Path

root = Path(os.environ["OLD_ROOT"])
tid = os.environ["TUNNEL_ID"]
roots = [
    root / "etc/cloudflared",
    root / "root/.cloudflared",
    root / "home/ubuntu/.cloudflared",
]
dest = Path("/run/openclaw-migrated-credential.json")
for d in roots:
    if not d.is_dir():
        continue
    for p in d.glob("*.json"):
        try:
            obj = json.loads(p.read_text(errors="replace"))
        except Exception:
            continue
        tunnel_id = str(obj.get("TunnelID") or obj.get("TunnelId") or "")
        if tunnel_id == tid or (
            obj.get("AccountTag") and obj.get("TunnelSecret") and tunnel_id
        ):
            shutil.copyfile(p, dest)
            dest.chmod(0o600)
            raise SystemExit(0)
raise SystemExit(1)
PY
  if [ -s /run/openclaw-migrated-credential.json ]; then
    install -m 600 /run/openclaw-migrated-credential.json "/etc/cloudflared/${TUNNEL_ID}.json"
    cat > /etc/cloudflared/config.yml <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: /etc/cloudflared/${TUNNEL_ID}.json
ingress:
  - hostname: ${PUBLIC_HOSTNAME}
    service: http://127.0.0.1:18789
  - service: http_status:404
EOF
    chmod 600 /etc/cloudflared/config.yml
    credential_mode=json
  fi
fi
rm -f /run/openclaw-migrated-tunnel-token /run/openclaw-migrated-credential.json

[ -n "$credential_mode" ] || {
  echo OPENCLAW_CLEAN_FAILED=CLOUDFLARED_TUNNEL_CREDENTIAL_NOT_FOUND
  exit 63
}
echo "OPENCLAW_CLEAN_CLOUDFLARED_CREDENTIAL_MODE=${credential_mode}"
echo OPENCLAW_CLEAN_ONLY_TUNNEL_CREDENTIAL_MIGRATED=true

# Install a fresh current cloudflared binary from Cloudflare's official release.
arch="$(uname -m)"
[ "$arch" = x86_64 ] || { echo "OPENCLAW_CLEAN_FAILED=UNSUPPORTED_CLOUDFLARED_ARCH_${arch}"; exit 64; }
curl -fL --retry 4 --retry-delay 3 --proto '=https' --tlsv1.2 \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 \
  -o /usr/local/bin/cloudflared
chmod 0755 /usr/local/bin/cloudflared
/usr/local/bin/cloudflared --version
echo OPENCLAW_CLEAN_CLOUDFLARED_FRESH_INSTALL=true

if [ "$credential_mode" = token ]; then
  cat >/etc/systemd/system/cloudflared.service <<'UNIT'
[Unit]
Description=Cloudflare Tunnel for OpenClaw
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/cloudflared --no-autoupdate tunnel run --token-file /etc/cloudflared/tunnel-token
Restart=on-failure
RestartSec=5s
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
else
  cat >/etc/systemd/system/cloudflared.service <<'UNIT'
[Unit]
Description=Cloudflare Tunnel for OpenClaw
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/cloudflared --no-autoupdate --config /etc/cloudflared/config.yml tunnel run
Restart=on-failure
RestartSec=5s
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
UNIT
fi

# Configure OpenClaw using its documented Cloudflare Access trusted-proxy topology.
"$B" config set gateway.mode local >/dev/null
"$B" config set gateway.bind loopback >/dev/null
"$B" config set gateway.port 18789 --strict-json >/dev/null
"$B" config set gateway.publicOrigin "https://${PUBLIC_HOSTNAME}" >/dev/null
"$B" config set gateway.trustedProxies '["127.0.0.1","::1"]' --strict-json >/dev/null
"$B" config set gateway.auth.mode trusted-proxy >/dev/null
"$B" config set gateway.auth.trustedProxy.userHeader cf-access-authenticated-user-email >/dev/null
"$B" config set gateway.auth.trustedProxy.requiredHeaders '["cf-access-jwt-assertion"]' --strict-json >/dev/null
"$B" config set gateway.auth.trustedProxy.allowLoopback true --strict-json >/dev/null
"$B" config set gateway.tailscale.mode off >/dev/null
"$B" config set agents.defaults.model.primary openai/gpt-5.6-sol >/dev/null
"$B" config validate >/dev/null
echo OPENCLAW_CLEAN_CONFIG_VALIDATED=true

cat >/etc/systemd/system/openclaw-gateway.service <<UNIT
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
ExecStart=$B gateway --port 18789
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

systemctl daemon-reload
systemctl enable openclaw-gateway.service cloudflared.service >/dev/null
systemctl reset-failed openclaw-gateway.service cloudflared.service >/dev/null 2>&1 || true
systemctl restart openclaw-gateway.service

gateway_ok=false
for i in $(seq 1 60); do
  if curl -fsS --max-time 5 http://127.0.0.1:18789/healthz >/tmp/openclaw-health.txt 2>&1; then
    gateway_ok=true
    break
  fi
  sleep 2
done
if [ "$gateway_ok" != true ]; then
  echo OPENCLAW_CLEAN_FAILED=GATEWAY_HEALTH
  systemctl status openclaw-gateway.service --no-pager -l || true
  journalctl -u openclaw-gateway.service -n 80 --no-pager || true
  exit 65
fi

if ! ss -ltnH | awk '$4 ~ /:18789$/ {print $4}' | grep -Eq '^(127\.0\.0\.1|\[::1\]|::1):18789$'; then
  echo OPENCLAW_CLEAN_FAILED=GATEWAY_LOOPBACK_LISTENER_MISSING
  exit 66
fi
non_loopback_listener="$(ss -ltnH | awk '$4 ~ /:18789$/ {print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]|::1):18789$' || true)"
if [ -n "$non_loopback_listener" ]; then
  echo OPENCLAW_CLEAN_FAILED=PUBLIC_GATEWAY_LISTENER_DETECTED
  exit 67
fi
echo OPENCLAW_CLEAN_GATEWAY_HEALTH_OK=true
echo OPENCLAW_CLEAN_GATEWAY_LOOPBACK_ONLY=true

systemctl restart cloudflared.service
tunnel_ok=false
for i in $(seq 1 45); do
  if systemctl is-active --quiet cloudflared.service; then
    tunnel_ok=true
    break
  fi
  sleep 2
done
if [ "$tunnel_ok" != true ]; then
  echo OPENCLAW_CLEAN_FAILED=CLOUDFLARED_NOT_ACTIVE
  systemctl status cloudflared.service --no-pager -l || true
  journalctl -u cloudflared.service -n 80 --no-pager \
    | sed -E 's/(token[ =:]+)[A-Za-z0-9._~-]+/\1<REDACTED>/Ig' || true
  exit 68
fi
echo CLOUDFLARED_SERVICE_ACTIVE=true

# Drop the old filesystem before success. OCI detaches the disk in the next step.
cleanup_mount
trap - EXIT

cat >/var/lib/openclaw-clean-ready.txt <<EOF
OPENCLAW_CLEAN_INSTALL_VERIFIED=true
OPENCLAW_CLEAN_GATEWAY_HEALTH_OK=true
OPENCLAW_CLEAN_GATEWAY_LOOPBACK_ONLY=true
CLOUDFLARED_SERVICE_ACTIVE=true
OPENCLAW_PUBLIC_URL=https://${PUBLIC_HOSTNAME}/
EOF
chmod 600 /var/lib/openclaw-clean-ready.txt
echo "OPENCLAW_PUBLIC_URL=https://${PUBLIC_HOSTNAME}/"
echo OPENCLAW_CLEAN_FINALIZE_SUCCESS=true
