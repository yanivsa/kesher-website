#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"
export GH_TOKEN="$GITHUB_TOKEN"

workflow="openclaw-offline-boot-repair.yml"
runs="$(gh api --method GET "repos/$GITHUB_REPOSITORY/actions/workflows/$workflow/runs" -f branch=main -f per_page=20)"
run="$(jq -c '[.workflow_runs[] | select(.event=="push" or .event=="workflow_dispatch")][0] // empty' <<<"$runs")"

if [[ -z "$run" ]]; then
  gh api --method POST "repos/$GITHUB_REPOSITORY/actions/workflows/$workflow/dispatches" -f ref=main >/dev/null
  OPENCLAW_STATUS=queued \
  OPENCLAW_FAILURE_HINT=controller_dispatched_missing_run \
  OPENCLAW_HEAD_SHA="${GITHUB_SHA:-}" \
  OPENCLAW_STATUS_STRICT=1 \
    bash scripts/openclaw_publish_status.sh
  echo "OPENCLAW_CONTROLLER_DISPATCHED=true"
  exit 0
fi

run_id="$(jq -r '.id' <<<"$run")"
status="$(jq -r '.status' <<<"$run")"
conclusion="$(jq -r '.conclusion // ""' <<<"$run")"
run_url="$(jq -r '.html_url' <<<"$run")"
head_sha="$(jq -r '.head_sha // ""' <<<"$run")"

if [[ "$status" != "completed" ]]; then
  mapped="$status"
  [[ "$mapped" != "queued" ]] && mapped=in_progress
  OPENCLAW_STATUS="$mapped" \
  OPENCLAW_RUN_ID="$run_id" \
  OPENCLAW_RUN_URL="$run_url" \
  OPENCLAW_HEAD_SHA="$head_sha" \
  OPENCLAW_FAILURE_HINT="github_status=$status" \
  OPENCLAW_STATUS_STRICT=1 \
    bash scripts/openclaw_publish_status.sh
  echo "OPENCLAW_CONTROLLER_TRACKING_RUN=$run_id"
  exit 0
fi

logs="$(gh run view "$run_id" --repo "$GITHUB_REPOSITORY" --log 2>&1 || true)"
# gh run view prefixes real log records with job/step/timestamp fields. Require the
# proof token to terminate the record so echoed shell/Python source such as
# print('OPENCLAW_...=true') cannot masquerade as execution proof.
check_marker() {
  local escaped
  escaped="$(printf '%s' "$1" | sed 's/[][\\.^$*+?{}|()]/\\&/g')"
  grep -Eq "(^|[[:space:]])${escaped}[[:space:]]*$" <<<"$logs" && printf true || printf false
}
offline="$(check_marker 'OPENCLAW_OFFLINE_REPAIR_COMPLETE=true')"
rpc="$(check_marker 'OPENCLAW_GATEWAY_RPC_OK=true')"
serve="$(check_marker 'TAILSCALE_SERVE_ACTIVE=true')"
finalize="$(check_marker 'OPENCLAW_OFFLINE_FINALIZE_SUCCESS=true')"
ready_url="$(bash scripts/openclaw_extract_ready_url.sh <<<"$logs" || true)"

if [[ "$conclusion" == "success" && "$offline" == true && "$rpc" == true && "$serve" == true && "$finalize" == true && "$ready_url" == https://* ]]; then
  OPENCLAW_STATUS=success \
  OPENCLAW_RUN_ID="$run_id" \
  OPENCLAW_RUN_URL="$run_url" \
  OPENCLAW_HEAD_SHA="$head_sha" \
  OPENCLAW_READY_URL_VALUE="$ready_url" \
  OPENCLAW_OFFLINE_REPAIR_COMPLETE_VALUE=true \
  OPENCLAW_GATEWAY_RPC_OK_VALUE=true \
  TAILSCALE_SERVE_ACTIVE_VALUE=true \
  OPENCLAW_OFFLINE_FINALIZE_SUCCESS_VALUE=true \
  OPENCLAW_STATUS_STRICT=1 \
    bash scripts/openclaw_publish_status.sh
  echo "OPENCLAW_CONTROLLER_STRICT_SUCCESS=true"
  echo "OPENCLAW_CONTROLLER_RUN_ID=$run_id"
  echo "OPENCLAW_CONTROLLER_READY_URL=$ready_url"
  exit 0
fi

missing=()
[[ "$offline" == true ]] || missing+=(OPENCLAW_OFFLINE_REPAIR_COMPLETE)
[[ "$rpc" == true ]] || missing+=(OPENCLAW_GATEWAY_RPC_OK)
[[ "$serve" == true ]] || missing+=(TAILSCALE_SERVE_ACTIVE)
[[ "$finalize" == true ]] || missing+=(OPENCLAW_OFFLINE_FINALIZE_SUCCESS)
[[ "$ready_url" == https://* ]] || missing+=(OPENCLAW_READY_URL)
missing_csv="$(IFS=,; echo "${missing[*]:-none}")"
OPENCLAW_STATUS=failure \
OPENCLAW_RUN_ID="$run_id" \
OPENCLAW_RUN_URL="$run_url" \
OPENCLAW_HEAD_SHA="$head_sha" \
OPENCLAW_READY_URL_VALUE="$ready_url" \
OPENCLAW_FAILURE_HINT="conclusion=${conclusion:-unknown}; missing=$missing_csv" \
OPENCLAW_OFFLINE_REPAIR_COMPLETE_VALUE="$offline" \
OPENCLAW_GATEWAY_RPC_OK_VALUE="$rpc" \
TAILSCALE_SERVE_ACTIVE_VALUE="$serve" \
OPENCLAW_OFFLINE_FINALIZE_SUCCESS_VALUE="$finalize" \
OPENCLAW_STATUS_STRICT=1 \
  bash scripts/openclaw_publish_status.sh

echo "OPENCLAW_CONTROLLER_STRICT_SUCCESS=false"
echo "OPENCLAW_CONTROLLER_RUN_ID=$run_id"
echo "OPENCLAW_CONTROLLER_FAILURE_HINT=conclusion=${conclusion:-unknown}; missing=$missing_csv"
