#!/usr/bin/env bash
set +e
printf 'OPENCLAW_READONLY_DIAG_BEGIN=true\n'
printf 'DIAG_DATE='; date -u +%FT%TZ
printf 'DIAG_OS='; . /etc/os-release 2>/dev/null; printf '%s %s\n' "${NAME:-unknown}" "${VERSION_ID:-unknown}"
printf 'DIAG_USER='; id
printf 'DIAG_OPENCLAW_CMD='; command -v openclaw || echo absent
printf 'DIAG_OPENCLAW_SEARCH_BEGIN\n'; find /root /usr/local /opt /usr/bin -type f -name openclaw -perm -111 -print 2>/dev/null | head -20 || true; printf 'DIAG_OPENCLAW_SEARCH_END\n'
printf 'DIAG_OPENCLAW_GATEWAY_SHOW_BEGIN\n'; systemctl show openclaw-gateway.service -p LoadState -p ActiveState -p SubState -p ExecStart -p FragmentPath 2>&1 || true; printf 'DIAG_OPENCLAW_GATEWAY_SHOW_END\n'
printf 'DIAG_PORT18789_BEGIN\n'; ss -lntp 2>&1 | grep -E '(^State|:18789[[:space:]])' || true; printf 'DIAG_PORT18789_END\n'
printf 'DIAG_CLOUDFLARED_CMD='; command -v cloudflared || echo absent
printf 'DIAG_CLOUDFLARED_VERSION='; cloudflared --version 2>&1 || true
printf 'DIAG_CLOUDFLARED_DPKG='; dpkg-query -W -f='${Status} ${Version}\n' cloudflared 2>&1 || true
printf 'DIAG_CLOUDFLARED_SHOW_BEGIN\n'; systemctl show cloudflared.service -p LoadState -p ActiveState -p SubState -p ExecStart -p FragmentPath 2>&1 || true; printf 'DIAG_CLOUDFLARED_SHOW_END\n'
printf 'DIAG_MARKER_FILE='; test -f /var/lib/openclaw-installed && echo present || echo absent
printf 'OPENCLAW_READONLY_DIAG_END=true\n'
exit 0
