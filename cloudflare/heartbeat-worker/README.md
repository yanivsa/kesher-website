# Kesher Cloudflare Heartbeat Worker

Independent external watchdog running on Cloudflare Workers edge network.

## Purpose
During periods when GitHub Actions cron triggers stall or experience scheduling delays (such as during the 16.10.2026 Production Canary when GitHub crons stopped arriving for >55 minutes), this Worker runs on Cloudflare's independent edge Cron Trigger (every 5 minutes) to:
1. Probe live website health (`https://kesher.saharoni.com`).
2. Dispatch `kesher-content-controller.yml` (or `kesher-controller-liveness.yml`) on GitHub via authenticated REST API, which GitHub processes immediately without waiting for internal cron schedules.

## Configuration & Deployment
Deploy via Wrangler:
```bash
cd cloudflare/heartbeat-worker
npx wrangler deploy
```

Set GitHub Token secret for workflow dispatch:
```bash
npx wrangler secret put GITHUB_TOKEN
```
