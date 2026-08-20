#!/usr/bin/env bash
set -Eeuo pipefail

# Run the proven baseline patch first, but keep the helper alive so we can
# harden boot-time finalization before the authenticated boot disk is detached.
# The OCI Run Command helper receives this script as a standalone pinned file,
# so repository-relative sibling paths do not exist on the helper. Fetch the
# known-good baseline from the immutable merge commit that introduced this
# cold-boot hardening, then execute it locally.
export OPENCLAW_REPAIR_NO_POWEROFF=1
BASE_COMMIT=47eb2156451b1f445f6c9212cf972c6e3106dbf9
BASE_URL="https://raw.githubusercontent.com/yanivsa/kesher-website/${BASE_COMMIT}/scripts/openclaw_offline_mount_repair_base.sh"
BASE_TMP="$(mktemp)"
cleanup_base() { rm -f "$BASE_TMP"; }
trap cleanup_base EXIT
curl -fsSL --retry 5 --retry-delay 2 "$BASE_URL" -o "$BASE_TMP"
bash "$BASE_TMP" "$@"
rm -f "$BASE_TMP"
trap - EXIT

MNT=/mnt/openclaw-target
mkdir -p "$MNT"
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
[ -n "$target_disk" ] || { echo OFFLINE_REPAIR_BOOTFIX_DATA_DISK_NOT_FOUND=true; exit 1; }

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
  if mount -o rw "$part" "$MNT" 2>/dev/null; then
    if [ -f "$MNT/etc/os-release" ] && [ -x "$MNT/usr/local/sbin/openclaw-offline-finalize.sh" ]; then
      root_part="$part"
      break
    fi
    umount "$MNT"
  fi
done
[ -n "$root_part" ] || { echo OFFLINE_REPAIR_BOOTFIX_TARGET_ROOT_NOT_FOUND=true; exit 1; }

# Eliminate stale proof from previous boots and make this boot's result unambiguous.
rm -f "$MNT/var/lib/openclaw-ready.txt"
: > "$MNT/var/log/openclaw-offline-finalize.log"

# Give the real gateway and Serve endpoints substantially more time to become
# ready on an E2.1.Micro after cold boot.
sed -i 's/for i in $(seq 1 60); do/for i in $(seq 1 300); do/g' \
  "$MNT/usr/local/sbin/openclaw-offline-finalize.sh"

# Run finalization only after the network/tailscale service is wanted and ordered.
# Retry a failed oneshot instead of permanently leaving the boot in a failed state.
cat >"$MNT/etc/systemd/system/openclaw-offline-finalize.service" <<'UNIT'
[Unit]
Description=Finalize OpenClaw securely on the authenticated Tailscale tailnet
Wants=network-online.target tailscaled.service
After=local-fs.target network-online.target tailscaled.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/openclaw-offline-finalize.sh
RemainAfterExit=yes
TimeoutStartSec=1800
Restart=on-failure
RestartSec=30
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
UNIT
rm -f "$MNT/etc/systemd/system/basic.target.wants/openclaw-offline-finalize.service"
mkdir -p "$MNT/etc/systemd/system/multi-user.target.wants"
ln -sfn ../openclaw-offline-finalize.service \
  "$MNT/etc/systemd/system/multi-user.target.wants/openclaw-offline-finalize.service"

sync
umount "$MNT"
echo OFFLINE_REPAIR_BOOT_FINALIZER_HARDENED=true
echo OFFLINE_REPAIR_TARGET_SSH_KEY_REMOVED=true
echo OFFLINE_REPAIR_DISK_PATCHED=true
echo OFFLINE_REPAIR_RUN_COMMAND_COMPLETE=true
