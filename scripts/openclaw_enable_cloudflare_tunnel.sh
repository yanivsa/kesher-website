#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1

: "${CLOUDFLARE_TUNNEL_TOKEN_B64:?missing tunnel token}"
PUBLIC_HOSTNAME="${PUBLIC_HOSTNAME:-openclaw.saharoni.com}"
TOKEN="$(printf '%s' "$CLOUDFLARE_TUNNEL_TOKEN_B64" | base64 -d)"
unset CLOUDFLARE_TUNNEL_TOKEN_B64

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
test -n "$B"

# Preserve the secure origin posture: OpenClaw must remain loopback-only.
"$B" config set gateway.mode local >/dev/null
"$B" config set gateway.bind loopback >/dev/null
"$B" config validate >/dev/null
systemctl restart openclaw-gateway.service

for i in $(seq 1 30); do
  if "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1; then
    break
  fi
  sleep 2
done
"$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1

# OpenClaw's local gateway port used by this deployment.
PORT="$("$B" config get gateway.port 2>/dev/null | tr -cd '0-9' || true)"
[ -n "$PORT" ] || PORT=18789
if [ "$PORT" != "18789" ]; then
  echo "OPENCLAW_CLOUDFLARE_FAILED=UNEXPECTED_GATEWAY_PORT_${PORT}"
  exit 41
fi

# Fail closed if the gateway is ever exposed beyond loopback before starting the tunnel.
non_loopback_listener="$(ss -ltnH 2>/dev/null | awk '$4 ~ /:18789$/ {print $4}' | grep -Ev '^(127\.0\.0\.1|\[::1\]|::1):18789$' || true)"
if [ -n "$non_loopback_listener" ]; then
  echo "OPENCLAW_CLOUDFLARE_FAILED=PUBLIC_GATEWAY_LISTENER_DETECTED"
  exit 43
fi

arch="$(uname -m)"
case "$arch" in
  aarch64|arm64) asset=cloudflared-linux-arm64 ;;
  x86_64|amd64) asset=cloudflared-linux-amd64 ;;
  *) echo "OPENCLAW_CLOUDFLARE_FAILED=UNSUPPORTED_ARCH_${arch}"; exit 42 ;;
esac

curl -fsSL --proto '=https' --tlsv1.2 \
  "https://github.com/cloudflare/cloudflared/releases/latest/download/${asset}" \
  -o /usr/local/bin/cloudflared
chmod 0755 /usr/local/bin/cloudflared
/usr/local/bin/cloudflared --version

# Replace any previous cloudflared service cleanly; token is never printed.
systemctl disable --now cloudflared.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/cloudflared.service
systemctl daemon-reload
/usr/local/bin/cloudflared service install "$TOKEN" >/dev/null
unset TOKEN
systemctl enable --now cloudflared.service >/dev/null

for i in $(seq 1 30); do
  if systemctl is-active --quiet cloudflared.service; then
    break
  fi
  sleep 2
done
systemctl is-active --quiet cloudflared.service

echo OPENCLAW_GATEWAY_RPC_OK=true
echo OPENCLAW_GATEWAY_BIND=loopback
echo OPENCLAW_GATEWAY_PORT="$PORT"
echo CLOUDFLARED_SERVICE_ACTIVE=true
echo "OPENCLAW_PUBLIC_URL=https://${PUBLIC_HOSTNAME}/"
