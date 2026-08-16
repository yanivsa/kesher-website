#!/usr/bin/env bash
set -Eeuo pipefail
export HOME=/root
export OPENCLAW_NO_PROMPT=1

systemctl start openclaw-offline-finalize.service >/dev/null 2>&1 || true
for i in $(seq 1 90); do
  if [ -s /var/lib/openclaw-ready.txt ] && grep -q '^OPENCLAW_TAILSCALE_FINALIZED=true$' /var/lib/openclaw-ready.txt; then
    break
  fi
  sleep 2
done

state="$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", ""))' 2>/dev/null || true)"
echo TAILSCALE_BACKEND_STATE="$state"
[ "$state" = Running ] || {
  echo OPENCLAW_VERIFY_TAILSCALE_FAILED=true
  tail -80 /var/log/openclaw-offline-finalize.log 2>/dev/null | sed -E 's#https?://[^[:space:]]+#<REDACTED_URL>#g' || true
  exit 30
}

B="$(command -v openclaw || find /root -type f -name openclaw -perm -111 2>/dev/null | head -1)"
[ -n "$B" ]
"$B" gateway status --require-rpc --timeout 5 >/tmp/openclaw-verify-rpc.txt 2>&1 || {
  echo OPENCLAW_VERIFY_RPC_FAILED=true
  tail -80 /tmp/openclaw-verify-rpc.txt || true
  tail -80 /var/log/openclaw-offline-finalize.log 2>/dev/null | sed -E 's#https?://[^[:space:]]+#<REDACTED_URL>#g' || true
  exit 31
}
echo OPENCLAW_GATEWAY_RPC_OK=true

serve="$(tailscale serve status 2>/dev/null || true)"
printf '%s\n' "$serve" | grep -q 'https://' || {
  echo OPENCLAW_VERIFY_SERVE_FAILED=true
  tail -80 /var/log/openclaw-offline-finalize.log 2>/dev/null | sed -E 's#https?://[^[:space:]]+#<REDACTED_URL>#g' || true
  exit 32
}
echo TAILSCALE_SERVE_ACTIVE=true

DNS="$(tailscale status --json | python3 -c 'import json,sys; d=json.load(sys.stdin); print((d.get("Self",{}).get("DNSName") or "").rstrip("."))')"
[ -n "$DNS" ]
READY="https://$DNS/"
printf 'OPENCLAW_READY_URL=%s\n' "$READY"

sed -i '/ openclaw-offline-recovery$/d' /home/ubuntu/.ssh/authorized_keys 2>/dev/null || true
echo OPENCLAW_RECOVERY_KEY_REMOVED=true
echo OPENCLAW_VERIFY_OK=true
