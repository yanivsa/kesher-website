#!/usr/bin/env bash
set -Eeuo pipefail
MNT=/mnt/openclaw-proof
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
for _ in $(seq 1 120); do
  while read -r dev typ; do
    [ "$typ" = disk ] || continue
    [ "$dev" = "$root_disk" ] && continue
    target_disk="$dev"
    break
  done < <(lsblk -dnpo NAME,TYPE)
  [ -n "$target_disk" ] && break
  sleep 2
done
[ -n "$target_disk" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=DATA_DISK_NOT_FOUND; exit 31; }

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
    [ "$dev" = "$root_src" ] && continue
    if lsblk -srnpo NAME "$dev" 2>/dev/null | grep -Fxq "$target_disk"; then
      printf '%s %s\n' "$dev" "$size"
    fi
  done < <(lsblk -brnpo NAME,SIZE,TYPE) | sort -k2,2nr | awk '{print $1}'
)
[ "${#candidates[@]}" -gt 0 ] || candidates=("$target_disk")

root_part=""
for part in "${candidates[@]}"; do
  mountpoint -q "$MNT" && umount "$MNT" || true
  if mount -o ro "$part" "$MNT" 2>/dev/null; then
    if [ -f "$MNT/etc/os-release" ] && [ -d "$MNT/usr" ]; then
      root_part="$part"
      break
    fi
    umount "$MNT"
  fi
done
[ -n "$root_part" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=TARGET_ROOT_NOT_FOUND; exit 32; }
echo OPENCLAW_OFFLINE_PROOF_ROOT="$root_part"

READY="$MNT/var/lib/openclaw-ready.txt"
LOG="$MNT/var/log/openclaw-offline-finalize.log"

if [ ! -s "$READY" ]; then
  echo OPENCLAW_OFFLINE_PROOF_FAILED=READY_FILE_MISSING
  if [ -s "$LOG" ]; then
    grep -E '^(OPENCLAW_|TAILSCALE_)' "$LOG" | tail -80 || true
  fi
  exit 33
fi

# Emit only safe proof markers from the durable guest state.
grep -E '^(OPENCLAW_TAILSCALE_FINALIZED|TAILSCALE_BACKEND_STATE|OPENCLAW_TAILSCALE_DNS|OPENCLAW_READY_URL)=' "$READY" || true
if [ -s "$LOG" ]; then
  grep -E '^(OPENCLAW_GATEWAY_RPC_OK|TAILSCALE_SERVE_ACTIVE|OPENCLAW_OFFLINE_FINALIZE_SUCCESS|OPENCLAW_FINALIZE_FAILED)=' "$LOG" | tail -40 || true
fi

ready_finalized="$(grep -Fx 'OPENCLAW_TAILSCALE_FINALIZED=true' "$READY" || true)"
backend="$(grep -Fx 'TAILSCALE_BACKEND_STATE=Running' "$READY" || true)"
url="$(grep -E '^OPENCLAW_READY_URL=https://[A-Za-z0-9._-]+/?$' "$READY" | tail -1 || true)"
rpc="$(grep -Fx 'OPENCLAW_GATEWAY_RPC_OK=true' "$LOG" 2>/dev/null || true)"
serve="$(grep -Fx 'TAILSCALE_SERVE_ACTIVE=true' "$LOG" 2>/dev/null || true)"
finalize="$(grep -Fx 'OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true' "$LOG" 2>/dev/null || true)"

[ -n "$ready_finalized" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=FINALIZED_FLAG_MISSING; exit 34; }
[ -n "$backend" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=TAILSCALE_NOT_RUNNING; exit 35; }
[ -n "$url" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=READY_URL_MISSING; exit 36; }
[ -n "$rpc" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=RPC_PROOF_MISSING; exit 37; }
[ -n "$serve" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=SERVE_PROOF_MISSING; exit 38; }
[ -n "$finalize" ] || { echo OPENCLAW_OFFLINE_PROOF_FAILED=FINALIZE_PROOF_MISSING; exit 39; }

echo OPENCLAW_GATEWAY_RPC_OK=true
echo TAILSCALE_SERVE_ACTIVE=true
echo OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true
echo OPENCLAW_OFFLINE_REPAIR_COMPLETE=true
echo "$url"
echo OPENCLAW_OFFLINE_PROOF_COMPLETE=true
