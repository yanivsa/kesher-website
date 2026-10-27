#!/usr/bin/env bash
set +e
printf 'OPENCLAW_READONLY_DIAG_BEGIN=true\n'
printf 'DIAG_DATE='; date -u +%FT%TZ
printf 'DIAG_KERNEL='; uname -a
printf 'DIAG_OS='; . /etc/os-release 2>/dev/null; printf '%s %s\n' "${NAME:-unknown}" "${VERSION_ID:-unknown}"
printf 'DIAG_USER='; id
printf 'DIAG_SYSTEM_STATE='; systemctl is-system-running 2>&1 || true
printf 'DIAG_SSH_ACTIVE='; systemctl is-active ssh 2>&1 || systemctl is-active sshd 2>&1 || true
printf 'DIAG_SSH_ENABLED='; systemctl is-enabled ssh 2>&1 || systemctl is-enabled sshd 2>&1 || true
printf 'DIAG_PORT22_BEGIN\n'; ss -lnt 2>&1 | grep -E '(^State|:22[[:space:]])' || true; printf 'DIAG_PORT22_END\n'
printf 'DIAG_CLOUD_INIT_BEGIN\n'; cloud-init status --long 2>&1 || true; printf 'DIAG_CLOUD_INIT_END\n'
printf 'DIAG_BOOTSTRAP_FILE='; test -f /var/log/openclaw-clean-bootstrap.log && echo present || echo absent
printf 'DIAG_OPENCLAW_CMD='; command -v openclaw || echo absent
printf 'DIAG_OPENCLAW_SEARCH_BEGIN\n'; find /root /usr/local /opt -type f -name openclaw -perm -111 -print 2>/dev/null | head -20 || true; printf 'DIAG_OPENCLAW_SEARCH_END\n'
printf 'DIAG_OPENCLAW_GATEWAY_UNIT_BEGIN\n'; systemctl cat openclaw-gateway.service 2>&1 || true; systemctl show openclaw-gateway.service -p LoadState -p ActiveState -p SubState -p ExecStart -p FragmentPath 2>&1 || true; printf 'DIAG_OPENCLAW_GATEWAY_UNIT_END\n'
printf 'DIAG_CLOUDFLARED_CMD='; command -v cloudflared || echo absent
printf 'DIAG_CLOUDFLARED_VERSION='; cloudflared --version 2>&1 || true
printf 'DIAG_CLOUDFLARED_UNIT_BEGIN\n'; systemctl cat cloudflared.service 2>&1 || true; systemctl show cloudflared.service -p LoadState -p ActiveState -p SubState -p ExecStart -p FragmentPath 2>&1 || true; printf 'DIAG_CLOUDFLARED_UNIT_END\n'
printf 'DIAG_MARKER_FILE='; test -f /var/lib/openclaw-installed && echo present || echo absent
printf 'DIAG_NETWORK_BEGIN\n'; ip -brief address 2>&1 || true; ip route 2>&1 || true; printf 'DIAG_NETWORK_END\n'
printf 'DIAG_SUDO_N='; sudo -n true >/dev/null 2>&1 && echo yes || echo no
if sudo -n true >/dev/null 2>&1; then
  printf 'DIAG_SSH_JOURNAL_BEGIN\n'
  sudo -n journalctl -u ssh -u sshd --no-pager -n 60 2>&1 | grep -Eai 'ssh|listen|error|fail|start|stop' | tail -60 || true
  printf 'DIAG_SSH_JOURNAL_END\n'
  printf 'DIAG_CLOUD_LOG_BEGIN\n'
  sudo -n grep -Eai 'OPENCLAW_CLEAN_BOOTSTRAP|cloud-init|cloud-final|ssh|error|failed|failure' /var/log/cloud-init-output.log /var/log/openclaw-clean-bootstrap.log 2>/dev/null | tail -100 || true
  printf 'DIAG_CLOUD_LOG_END\n'
fi
printf 'OPENCLAW_READONLY_DIAG_END=true\n'
exit 0
