# Kesher Cloudflare Heartbeat Worker

Independent external watchdog running on Cloudflare Workers edge network.

## Purpose
During periods when GitHub Actions internal cron triggers stall or experience scheduling delays, this Worker runs on Cloudflare's independent edge Cron Trigger (every 5 minutes) to:
1. Probe live website health (`https://kesher.saharoni.com`).
2. Dispatch `kesher-content-controller.yml` on GitHub via authenticated REST API, which GitHub processes immediately without waiting for internal cron schedules.
3. Idempotently protect against duplicate dispatches by querying GitHub Actions for active controller runs before triggering.

## Security & Architecture
- **Read-Only Health Probes (`GET /`, `GET /health`, `GET /ping`)**:
  Probes production site health and reports configuration status. Never mutates state and never calls GitHub Actions dispatch.
- **Authenticated Manual Dispatch (`POST /dispatch`, `POST /trigger`)**:
  Protected by Bearer token authentication matching secret `HEARTBEAT_SECRET`. Unauthenticated requests receive HTTP 401 Unauthorized.
- **Scheduled Edge Cron (`*/5 * * * *`)**:
  Automatically invokes the heartbeat dispatch routine with active-run idempotency checks.

## Configuration & Deployment
Deploy via Wrangler:
```bash
cd cloudflare/heartbeat-worker
npx wrangler deploy
```

Configure secrets:
```bash
# GitHub Token with repo and workflow scopes:
gh auth token | tr -d '\n' | npx wrangler secret put GITHUB_TOKEN

# Shared secret for manual POST /dispatch:
npx wrangler secret put HEARTBEAT_SECRET
```
