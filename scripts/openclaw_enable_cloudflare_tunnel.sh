#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1

PUBLIC_HOSTNAME="${PUBLIC_HOSTNAME:-openclaw.saharoni.com}"
CLOUDFLARED_MIN_VERSION="2026.10.2"

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
test -n "$B"

# Preserve the secure origin posture: OpenClaw must remain loopback-only.
"$B" config set gateway.mode local >/dev/null
"$B" config set gateway.bind loopback >/dev/null
"$B" config validate >/dev/null

# Repair the live systemd unit with the executable that actually exists on this
# guest. This avoids the brittle offline boot-finalizer path while keeping the
# origin bound to loopback only.
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
Environment=OPENCLAW_SERVICE_REPAIR_POLICY=external
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
systemctl reset-failed openclaw-gateway.service >/dev/null 2>&1 || true
systemctl enable openclaw-gateway.service >/dev/null 2>&1 || true
if ! systemctl restart openclaw-gateway.service; then
  echo OPENCLAW_CLOUDFLARE_FAILED=GATEWAY_RESTART
  echo "OPENCLAW_GATEWAY_RESULT=$(systemctl show openclaw-gateway.service -p Result --value 2>/dev/null || true)"
  echo "OPENCLAW_GATEWAY_EXEC_MAIN_STATUS=$(systemctl show openclaw-gateway.service -p ExecMainStatus --value 2>/dev/null || true)"
  exit 44
fi
for i in $(seq 1 30); do
  systemctl is-active --quiet openclaw-gateway.service && break
  sleep 2
done
if ! systemctl is-active --quiet openclaw-gateway.service; then
  echo OPENCLAW_CLOUDFLARE_FAILED=GATEWAY_UNIT_NOT_ACTIVE
  echo "OPENCLAW_GATEWAY_RESULT=$(systemctl show openclaw-gateway.service -p Result --value 2>/dev/null || true)"
  echo "OPENCLAW_GATEWAY_EXEC_MAIN_STATUS=$(systemctl show openclaw-gateway.service -p ExecMainStatus --value 2>/dev/null || true)"
  exit 45
fi
echo OPENCLAW_LIVE_GATEWAY_REPAIR=true

for i in $(seq 1 30); do
  if "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1; then
    break
  fi
  sleep 2
done
if ! "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1; then
  echo OPENCLAW_CLOUDFLARE_FAILED=GATEWAY_RPC
  tail -40 /tmp/openclaw-gateway-status.txt 2>/dev/null | sed -E 's#https?://[^[:space:]]+#<REDACTED_URL>#g' || true
  exit 46
fi

PORT="$("$B" config get gateway.port 2>/dev/null | tr -cd '0-9' || true)"
[ -n "$PORT" ] || PORT=18789
if [ "$PORT" != "18789" ]; then
  echo "OPENCLAW_CLOUDFLARE_FAILED=UNEXPECTED_GATEWAY_PORT_${PORT}"
  exit 41
fi

# Fail closed if the gateway is ever exposed beyond loopback.
non_loopback_listener="$(ss -ltnH 2>/dev/null | awk '$4 ~ /:18789$/ {print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]|::1):18789$' || true)"
if [ -n "$non_loopback_listener" ]; then
  echo OPENCLAW_CLOUDFLARE_FAILED=PUBLIC_GATEWAY_LISTENER_DETECTED
  exit 43
fi

# Reuse the existing tunnel credentials, but upgrade the cloudflared binary
# before reconnecting. Cloudflare requires 2026.10.2+ for the October 2026
# eMudhra certificate incident.
if ! systemctl list-unit-files cloudflared.service --no-legend 2>/dev/null | grep -q '^cloudflared.service'; then
  echo OPENCLAW_CLOUDFLARE_FAILED=CLOUDFLARED_SERVICE_MISSING
  exit 47
fi
CLOUDFLARED_BIN="$(command -v cloudflared || true)"
if [ -z "$CLOUDFLARED_BIN" ]; then
  echo OPENCLAW_CLOUDFLARE_FAILED=CLOUDFLARED_BINARY_MISSING
  exit 50
fi

cloudflared_version() {
  "$CLOUDFLARED_BIN" --version 2>/dev/null | sed -nE 's/^cloudflared version ([0-9]+\.[0-9]+\.[0-9]+).*/\1/p' | head -1
}
version_at_least() {
  local have="$1" need="$2"
  [ -n "$have" ] || return 1
  if command -v dpkg >/dev/null 2>&1; then
    dpkg --compare-versions "$have" ge "$need"
  else
    [ "$(printf '%s\n%s\n' "$need" "$have" | sort -V | head -1)" = "$need" ]
  fi
}

before="$(cloudflared_version)"
echo "CLOUDFLARED_VERSION_BEFORE=${before:-unknown}"
if ! version_at_least "$before" "$CLOUDFLARED_MIN_VERSION"; then
  echo "CLOUDFLARED_SECURITY_UPGRADE_REQUIRED=true"
  if command -v apt-get >/dev/null 2>&1 && dpkg-query -W -f='${Status}' cloudflared 2>/dev/null | grep -q 'install ok installed'; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y --only-upgrade cloudflared
  elif command -v yum >/dev/null 2>&1 && rpm -q cloudflared >/dev/null 2>&1; then
    yum update -y cloudflared
  else
    "$CLOUDFLARED_BIN" update
  fi

  # Some package repositories can lag behind a security release. On Debian/
  # Ubuntu, fall back to Cloudflare's official latest .deb if still vulnerable.
  after_first="$(cloudflared_version)"
  if ! version_at_least "$after_first" "$CLOUDFLARED_MIN_VERSION" && command -v dpkg >/dev/null 2>&1; then
    arch="$(dpkg --print-architecture)"
    curl -fsSL --retry 3 --retry-delay 2 \
      -o /tmp/cloudflared.deb \
      "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}.deb"
    dpkg -i /tmp/cloudflared.deb
    rm -f /tmp/cloudflared.deb
  fi
fi

after="$(cloudflared_version)"
echo "CLOUDFLARED_VERSION_AFTER=${after:-unknown}"
if ! version_at_least "$after" "$CLOUDFLARED_MIN_VERSION"; then
  echo "OPENCLAW_CLOUDFLARE_FAILED=CLOUDFLARED_VERSION_TOO_OLD_${after:-unknown}"
  exit 51
fi
echo CLOUDFLARED_SECURITY_MINIMUM_OK=true

systemctl daemon-reload
systemctl reset-failed cloudflared.service >/dev/null 2>&1 || true
if ! systemctl restart cloudflared.service; then
  echo OPENCLAW_CLOUDFLARE_FAILED=CLOUDFLARED_RESTART
  echo "OPENCLAW_CLOUDFLARED_ACTIVE_STATE=$(systemctl show cloudflared.service -p ActiveState --value 2>/dev/null || true)"
  echo "OPENCLAW_CLOUDFLARED_RESULT=$(systemctl show cloudflared.service -p Result --value 2>/dev/null || true)"
  exit 48
fi
for i in $(seq 1 30); do
  systemctl is-active --quiet cloudflared.service && break
  sleep 2
done
if ! systemctl is-active --quiet cloudflared.service; then
  echo OPENCLAW_CLOUDFLARE_FAILED=CLOUDFLARED_NOT_ACTIVE
  echo "OPENCLAW_CLOUDFLARED_ACTIVE_STATE=$(systemctl show cloudflared.service -p ActiveState --value 2>/dev/null || true)"
  echo "OPENCLAW_CLOUDFLARED_RESULT=$(systemctl show cloudflared.service -p Result --value 2>/dev/null || true)"
  exit 49
fi

echo CLOUDFLARED_REUSED_EXISTING_SERVICE=true
echo OPENCLAW_GATEWAY_RPC_OK=true
echo OPENCLAW_GATEWAY_BIND=loopback
echo OPENCLAW_GATEWAY_PORT="$PORT"
echo CLOUDFLARED_SERVICE_ACTIVE=true
echo "OPENCLAW_PUBLIC_URL=https://${PUBLIC_HOSTNAME}/"
