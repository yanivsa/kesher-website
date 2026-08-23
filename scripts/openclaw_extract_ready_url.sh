#!/usr/bin/env bash
set -euo pipefail

grep -Eo '(^|[[:space:]])OPENCLAW_READY_URL=https://[A-Za-z0-9._-]+/?[[:space:]]*$' \
  | sed -E 's/^.*OPENCLAW_READY_URL=//' \
  | sed -E 's/[[:space:]]+$//' \
  | tail -1
