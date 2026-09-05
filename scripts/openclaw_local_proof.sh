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
[ -n "$target_disk" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=DATA_DISK_NOT_FOUND; exit 61; }

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
[ -n "$root_part" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=TARGET_ROOT_NOT_FOUND; exit 62; }

echo OPENCLAW_LOCAL_PROOF_ROOT="$root_part"
READY="$MNT/var/lib/openclaw-ready.txt"
LOG="$MNT/var/log/openclaw-offline-finalize.log"

if [ ! -s "$READY" ]; then
  echo OPENCLAW_LOCAL_PROOF_FAILED=READY_FILE_MISSING
  echo OPENCLAW_LOCAL_PROOF_FINALIZER_LOG_BEGIN=true
  tail -160 "$LOG" 2>/dev/null || true
  echo OPENCLAW_LOCAL_PROOF_FINALIZER_LOG_END=true
  echo OPENCLAW_LOCAL_PROOF_GATEWAY_UNIT_BEGIN=true
  sed -n '1,120p' "$MNT/etc/systemd/system/openclaw-gateway.service" 2>/dev/null || true
  echo OPENCLAW_LOCAL_PROOF_GATEWAY_UNIT_END=true
  echo OPENCLAW_LOCAL_PROOF_GATEWAY_JOURNAL_BEGIN=true
  if [ -d "$MNT/var/log/journal" ]; then
    journalctl --directory="$MNT/var/log/journal" -u openclaw-gateway.service -n 160 --no-pager 2>/dev/null || true
  else
    echo OPENCLAW_GATEWAY_JOURNAL_PERSISTENT_MISSING=true
  fi
  echo OPENCLAW_LOCAL_PROOF_GATEWAY_JOURNAL_END=true
  exit 63
fi
[ -s "$LOG" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=FINALIZER_LOG_MISSING; exit 64; }

grep -E '^(OPENCLAW_LOCAL_FINALIZED|OPENCLAW_GATEWAY_BIND|OPENCLAW_GATEWAY_PORT|OPENCLAW_LOCAL_READY|OPENCLAW_OFFLINE_FINALIZE_SUCCESS)=' "$READY" || true
grep -E '^(OPENCLAW_GATEWAY_RPC_OK|OPENCLAW_LOCAL_READY|OPENCLAW_OFFLINE_FINALIZE_SUCCESS|OPENCLAW_FINALIZE_FAILED)=' "$LOG" | tail -40 || true

local_finalized="$(grep -Fx 'OPENCLAW_LOCAL_FINALIZED=true' "$READY" || true)"
bind="$(grep -Fx 'OPENCLAW_GATEWAY_BIND=loopback' "$READY" || true)"
port="$(grep -Fx 'OPENCLAW_GATEWAY_PORT=18789' "$READY" || true)"
local_ready="$(grep -Fx 'OPENCLAW_LOCAL_READY=true' "$READY" || true)"
rpc="$(grep -Fx 'OPENCLAW_GATEWAY_RPC_OK=true' "$LOG" 2>/dev/null || true)"
finalize="$(grep -Fx 'OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true' "$LOG" 2>/dev/null || true)"

[ -n "$local_finalized" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=FINALIZED_FLAG_MISSING; exit 65; }
[ -n "$bind" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=LOOPBACK_BIND_MISSING; exit 66; }
[ -n "$port" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=GATEWAY_PORT_MISSING; exit 67; }
[ -n "$local_ready" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=LOCAL_READY_MISSING; exit 68; }
[ -n "$rpc" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=RPC_PROOF_MISSING; exit 69; }
[ -n "$finalize" ] || { echo OPENCLAW_LOCAL_PROOF_FAILED=FINALIZE_PROOF_MISSING; exit 70; }

echo OPENCLAW_GATEWAY_RPC_OK=true
echo OPENCLAW_LOCAL_READY=true
echo OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true
echo OPENCLAW_OFFLINE_REPAIR_COMPLETE=true
echo OPENCLAW_OFFLINE_PROOF_COMPLETE=true
