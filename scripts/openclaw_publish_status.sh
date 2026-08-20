#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_TOKEN:?GITHUB_TOKEN is required}"
: "${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}"

ISSUE_NUMBER="${OPENCLAW_STATUS_ISSUE_NUMBER:-465}"
STATUS_BRANCH="${OPENCLAW_STATUS_BRANCH:-ops/openclaw-status}"
STATUS_PATH="${OPENCLAW_STATUS_PATH:-openclaw-status.json}"
STATUS="${OPENCLAW_STATUS:-unknown}"
RUN_ID="${OPENCLAW_RUN_ID:-}"
RUN_URL="${OPENCLAW_RUN_URL:-}"
HEAD_SHA="${OPENCLAW_HEAD_SHA:-}"
READY_URL="${OPENCLAW_READY_URL_VALUE:-}"
FAILURE_HINT="${OPENCLAW_FAILURE_HINT:-}"
OFFLINE_COMPLETE="${OPENCLAW_OFFLINE_REPAIR_COMPLETE_VALUE:-unknown}"
RPC_OK="${OPENCLAW_GATEWAY_RPC_OK_VALUE:-unknown}"
SERVE_OK="${TAILSCALE_SERVE_ACTIVE_VALUE:-unknown}"
FINALIZE_OK="${OPENCLAW_OFFLINE_FINALIZE_SUCCESS_VALUE:-unknown}"
STRICT_MODE="${OPENCLAW_STATUS_STRICT:-0}"

bool_json() {
  case "$1" in
    true) printf 'true' ;;
    false) printf 'false' ;;
    *) printf 'null' ;;
  esac
}

strict_success=false
if [[ "$STATUS" == "success" && "$OFFLINE_COMPLETE" == "true" && "$RPC_OK" == "true" && "$SERVE_OK" == "true" && "$FINALIZE_OK" == "true" && "$READY_URL" == https://* ]]; then
  strict_success=true
fi

updated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
status_json="$(jq -n \
  --arg status "$STATUS" \
  --arg run_id "$RUN_ID" \
  --arg run_url "$RUN_URL" \
  --arg sha "$HEAD_SHA" \
  --arg ready_url "$READY_URL" \
  --arg failure_hint "${FAILURE_HINT//$'\n'/ }" \
  --arg updated_at "$updated_at" \
  --argjson strict_success "$strict_success" \
  --argjson offline_complete "$(bool_json "$OFFLINE_COMPLETE")" \
  --argjson rpc_ok "$(bool_json "$RPC_OK")" \
  --argjson serve_ok "$(bool_json "$SERVE_OK")" \
  --argjson finalize_ok "$(bool_json "$FINALIZE_OK")" \
  '{status:$status,run_id:(if $run_id=="" then null else ($run_id|tonumber) end),run_url:(if $run_url=="" then null else $run_url end),sha:(if $sha=="" then null else $sha end),strict_success:$strict_success,markers:{OPENCLAW_OFFLINE_REPAIR_COMPLETE:$offline_complete,OPENCLAW_GATEWAY_RPC_OK:$rpc_ok,TAILSCALE_SERVE_ACTIVE:$serve_ok,OPENCLAW_OFFLINE_FINALIZE_SUCCESS:$finalize_ok},ready_url:(if $ready_url=="" then null else $ready_url end),failure_hint:(if $failure_hint=="" then null else ($failure_hint[0:500]) end),updated_at:$updated_at}')"

issue_body="$(cat <<EOF_BODY
Managed status surface for the autonomous OpenClaw recovery controller.

This issue intentionally contains only safe operational metadata; no credentials or secrets.

STATUS=$STATUS
RUN_ID=$RUN_ID
RUN_URL=$RUN_URL
STRICT_SUCCESS=$strict_success
OPENCLAW_OFFLINE_REPAIR_COMPLETE=$OFFLINE_COMPLETE
OPENCLAW_GATEWAY_RPC_OK=$RPC_OK
TAILSCALE_SERVE_ACTIVE=$SERVE_OK
OPENCLAW_OFFLINE_FINALIZE_SUCCESS=$FINALIZE_OK
OPENCLAW_READY_URL=$READY_URL
FAILURE_HINT=${FAILURE_HINT//$'\n'/ }
UPDATED_AT=$updated_at
EOF_BODY
)"

errors=0
export GH_TOKEN="$GITHUB_TOKEN"

if ! gh api --method PATCH "repos/$GITHUB_REPOSITORY/issues/$ISSUE_NUMBER" -f body="$issue_body" >/dev/null; then
  echo "OPENCLAW_STATUS_ISSUE_UPDATE_FAILED=true" >&2
  errors=$((errors+1))
fi

existing_json=""
existing_sha=""
if response="$(gh api --method GET "repos/$GITHUB_REPOSITORY/contents/$STATUS_PATH" -f ref="$STATUS_BRANCH" 2>/dev/null)"; then
  existing_sha="$(jq -r '.sha // empty' <<<"$response")"
  existing_json="$(jq -r '.content // empty' <<<"$response" | tr -d '\n' | base64 -d 2>/dev/null || true)"
fi

semantic_same=false
if [[ -n "$existing_json" ]]; then
  if jq -e --argjson new "$status_json" 'del(.updated_at) == ($new|del(.updated_at))' <<<"$existing_json" >/dev/null 2>&1; then
    semantic_same=true
  fi
fi

if [[ "$semantic_same" != "true" ]]; then
  content_b64="$(printf '%s\n' "$status_json" | base64 -w0)"
  args=(--method PUT "repos/$GITHUB_REPOSITORY/contents/$STATUS_PATH" -f message="chore: update OpenClaw recovery status for run ${RUN_ID:-unknown}" -f content="$content_b64" -f branch="$STATUS_BRANCH")
  if [[ -n "$existing_sha" ]]; then
    args+=(-f sha="$existing_sha")
  fi
  if ! gh api "${args[@]}" >/dev/null; then
    echo "OPENCLAW_STATUS_BRANCH_UPDATE_FAILED=true" >&2
    errors=$((errors+1))
  fi
fi

commit_state=pending
case "$STATUS" in
  success) commit_state=success ;;
  failure) commit_state=failure ;;
  error) commit_state=error ;;
esac
if [[ -n "$HEAD_SHA" ]]; then
  description="OpenClaw recovery $STATUS"
  [[ "$strict_success" == "true" ]] && description="OpenClaw strict recovery verified"
  if ! gh api --method POST "repos/$GITHUB_REPOSITORY/statuses/$HEAD_SHA" \
      -f state="$commit_state" \
      -f target_url="$RUN_URL" \
      -f description="$description" \
      -f context="openclaw/recovery" >/dev/null; then
    echo "OPENCLAW_COMMIT_STATUS_UPDATE_FAILED=true" >&2
    errors=$((errors+1))
  fi
fi

echo "OPENCLAW_STATUS_SURFACE_UPDATED=true"
echo "OPENCLAW_STATUS_RUN_ID=$RUN_ID"
echo "OPENCLAW_STATUS_STATE=$STATUS"
if (( errors > 0 && STRICT_MODE == 1 )); then
  exit 1
fi
exit 0
