#!/usr/bin/env bash
set -Eeuo pipefail

MNT=/mnt/openclaw-target
mkdir -p "$MNT"

cleanup() {
  mountpoint -q "$MNT" && umount "$MNT" || true
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

[ -n "$target_disk" ] || { echo OPENCLAW_OFFLINE_VERIFY_FAILED=DATA_DISK_NOT_FOUND; exit 31; }

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
  if mount -o ro "$part" "$MNT" 2>/dev/null; then
    if [ -f "$MNT/etc/os-release" ] && [ -d "$MNT/etc/systemd/system" ]; then
      root_part="$part"
      break
    fi
    umount "$MNT"
  fi
done

[ -n "$root_part" ] || { echo OPENCLAW_OFFLINE_VERIFY_FAILED=TARGET_ROOT_NOT_FOUND; exit 32; }
echo OPENCLAW_OFFLINE_VERIFY_TARGET_ROOT="$root_part"

safe_re='^(OPENCLAW_FINALIZE_START=|TAILSCALE_BACKEND_STATE=|OPENCLAW_GATEWAY_RPC_OK=|TAILSCALE_SERVE_ACTIVE=|OPENCLAW_TAILSCALE_DNS=|OPENCLAW_READY_URL=|OPENCLAW_OFFLINE_FINALIZE_SUCCESS=|OPENCLAW_FINALIZE_FAILED=)'

if [ -f "$MNT/var/log/openclaw-offline-finalize.log" ]; then
  grep -E "$safe_re" "$MNT/var/log/openclaw-offline-finalize.log" | tail -80 || true
else
  echo OPENCLAW_OFFLINE_VERIFY_FINALIZER_LOG_PRESENT=false
fi

if [ -f "$MNT/var/lib/openclaw-ready.txt" ]; then
  grep -E '^(OPENCLAW_TAILSCALE_FINALIZED=|TAILSCALE_BACKEND_STATE=|OPENCLAW_TAILSCALE_DNS=|OPENCLAW_TAILSCALE_IP=|OPENCLAW_READY_URL=)' "$MNT/var/lib/openclaw-ready.txt" || true
  echo OPENCLAW_OFFLINE_VERIFY_READY_FILE_PRESENT=true
else
  echo OPENCLAW_OFFLINE_VERIFY_READY_FILE_PRESENT=false
fi

log="$MNT/var/log/openclaw-offline-finalize.log"
ready="$MNT/var/lib/openclaw-ready.txt"
[ -f "$log" ] || exit 33
[ -f "$ready" ] || exit 34

grep -q '^OPENCLAW_GATEWAY_RPC_OK=true$' "$log" || exit 35
grep -q '^TAILSCALE_SERVE_ACTIVE=true$' "$log" || exit 36
grep -q '^OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true$' "$log" || exit 37
url="$(grep '^OPENCLAW_READY_URL=https://' "$ready" | tail -1 | cut -d= -f2-)"
[ -n "$url" ] || exit 38

echo OPENCLAW_OFFLINE_VERIFY_MARKERS_OK=true
echo OPENCLAW_READY_URL="$url"
