#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
test -n "$B"

state="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", ""))')"
[ "$state" = "Running" ]

"$B" config set gateway.mode local >/dev/null
"$B" config set gateway.bind loopback >/dev/null
"$B" config set gateway.tailscale.mode serve >/dev/null
"$B" config set gateway.auth.allowTailscale true --strict-json >/dev/null
"$B" config validate >/dev/null

systemctl disable --now openclaw-wait-tailnet.service >/dev/null 2>&1 || true
systemctl restart openclaw-gateway.service

for i in $(seq 1 30); do
  if "$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1; then
    break
  fi
  sleep 2
done
"$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-gateway-status.txt 2>&1

for i in $(seq 1 30); do
  if tailscale serve status 2>/dev/null | grep -q 'https://'; then
    break
  fi
  sleep 2
done

DNS="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("Self",{}).get("DNSName") or "").rstrip("."))')"
TSIP="$(tailscale ip -4 | head -1)"
SERVE="$(tailscale serve status 2>/dev/null || true)"

test -n "$DNS"
printf 'OPENCLAW_TAILSCALE_FINALIZED=true\n'
printf 'TAILSCALE_BACKEND_STATE=%s\n' "$state"
printf 'OPENCLAW_TAILSCALE_DNS=%s\n' "$DNS"
printf 'OPENCLAW_TAILSCALE_IP=%s\n' "$TSIP"
printf 'OPENCLAW_READY_URL=https://%s/\n' "$DNS"
printf 'TAILSCALE_SERVE_STATUS_BEGIN\n%s\nTAILSCALE_SERVE_STATUS_END\n' "$SERVE"
