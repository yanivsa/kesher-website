#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1

state="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", ""))')"
[ "$state" = Running ]
B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
test -n "$B"

"$B" config set gateway.mode local >/dev/null
"$B" config set gateway.bind loopback >/dev/null
"$B" config set gateway.tailscale.mode serve >/dev/null
"$B" config set gateway.auth.allowTailscale true --strict-json >/dev/null
"$B" config validate >/dev/null
systemctl disable --now openclaw-wait-tailnet.service >/dev/null 2>&1 || true
systemctl restart openclaw-gateway.service

for i in $(seq 1 60); do
  "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1 && break
  sleep 2
done
"$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1

tailscale serve --bg --yes http://127.0.0.1:18789 >/tmp/tailscale-serve.txt 2>&1 || true
for i in $(seq 1 60); do
  tailscale serve status 2>/dev/null | grep -q 'https://' && break
  sleep 2
done
SERVE="$(tailscale serve status 2>/dev/null)"
printf '%s\n' "$SERVE" | grep -q 'https://'

DNS="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("Self",{}).get("DNSName") or "").rstrip("."))')"
TSIP="$(tailscale ip -4 | head -1)"
test -n "$DNS"

printf 'OPENCLAW_TAILSCALE_FINALIZED=true\n'
printf 'TAILSCALE_BACKEND_STATE=%s\n' "$state"
printf 'OPENCLAW_TAILSCALE_DNS=%s\n' "$DNS"
printf 'OPENCLAW_TAILSCALE_IP=%s\n' "$TSIP"
printf 'OPENCLAW_READY_URL=https://%s/\n' "$DNS"
printf 'TAILSCALE_SERVE_STATUS_BEGIN\n%s\nTAILSCALE_SERVE_STATUS_END\n' "$SERVE"
