# KESHER trusted cutover service — Linux/OCI deployment contract

This package installs the already-reviewed cutover application on an independent persistent Linux host. It does **not** activate Schema-6 production. Service startup performs no cutover step, no provider call, no workflow dispatch, and no state mutation.

## Security model

The HTTP process binds only `127.0.0.1:8789`. A separately administered TLS reverse proxy exposes the exact HTTPS origin used as `KESHER_CUTOVER_OIDC_AUDIENCE`. Do not place the Python service directly on a public interface and do not terminate trust solely at the reverse proxy: GitHub Actions OIDC is verified again inside the service.

The repository does not implement synthetic native exclusion for GitHub, Jules, NotebookLM, YouTube, Cloudflare, or the image provider. `KESHER_CUTOVER_NATIVE_FACTORY` must name an administrator-installed and independently reviewed `module:function` that supplies the exact native bundle described in `docs/superpowers/specs/2026-10-10-kesher-trusted-cutover-service-design.md`.

Until that native bundle exists and every resource can independently prove its predecessor retirement and canonical isolation, live cutover remains blocked. Never replace a missing native port with `PrerequisitePort`, a JSON receipt, an environment boolean, or a cached observation.

## Filesystem layout

Recommended layout:

```text
/opt/kesher-cutover/current/       reviewed repository checkout
/opt/kesher-cutover/venv/          pinned Python environment
/etc/kesher-cutover/               root-managed protected administrator configuration
/var/lib/kesher-cutover/           persistent service state owned by kesher-cutover
/var/lib/kesher-cutover/invocations.sqlite
```

Run the service as a dedicated unprivileged `kesher-cutover` user. Keep `/etc/kesher-cutover` root-managed and non-writable by the service. The systemd environment file may remain root-owned mode `0600` because systemd reads it before launching the process. The JSON files referenced by that environment must be readable by the service but not writable by it; a recommended layout is `root:kesher-cutover` ownership with mode `0640` (or an equivalent read-only ACL). Native provider credentials belong only to the native bundle's protected host custody; they must never be copied to GitHub Actions variables, request payloads, repository files, or logs.

## One-time denial-ledger initialization

Initialize the replay-denial ledger exactly once before enabling the systemd unit:

```sh
install -d -o kesher-cutover -g kesher-cutover -m 0700 /var/lib/kesher-cutover
sudo -u kesher-cutover /opt/kesher-cutover/venv/bin/python - <<'PY'
from scripts.kesher_runtime.cutover_service import InvocationJournal
InvocationJournal.initialize('/var/lib/kesher-cutover/invocations.sqlite')
PY
chmod 0600 /var/lib/kesher-cutover/invocations.sqlite
```

The service deliberately refuses a missing or malformed ledger. **Never recreate a lost ledger and retry an uncertain mutation.** Stop and reconcile the remote resource/state intent first.

## Configuration

Copy `kesher-cutover.env.example` to `/etc/kesher-cutover/kesher-cutover.env`, replace every placeholder, and keep the file protected. Install the referenced JSON files with the service-readable, non-writable permissions described above. Those JSON files contain reviewed bindings/material but no HTTP client can supply or override them.

The installed review must bind the exact current reviewed `main` SHA, executable digest, policy/definition digest, complete workflow-registration binding digest, migration-material digest, closed-evidence floor, six resource IDs, and NOTEBOOKLM sealing-key binding. `review_check` re-reads these files and current GitHub `main` before every accepted invocation.

The HTTPS audience must be the final exact gateway origin, for example `https://cutover.example.invalid` replaced with the real administrator-controlled origin. Do not include a path, query, wildcard, or alternate hostname. Configure the GitHub `kesher-cutover` environment and `KESHER_CUTOVER_GATEWAY_URL` only after independent deployment review.

## TLS ingress

Use a maintained TLS reverse proxy/load balancer that forwards only `POST /v1/cutover/step` to `127.0.0.1:8789`. Restrict request sizes and preserve the `Authorization` header. The service itself validates body size, exact request shape, OIDC issuer/audience/repository/workflow/main/run identity, and never returns exception details.

Do not add provider credentials or a generic mutation proxy to the ingress layer.

## Installation and startup

1. Install the exact reviewed repository revision under `/opt/kesher-cutover/current` and a pinned virtual environment under `/opt/kesher-cutover/venv`.
2. Install and independently review the native bundle named by `KESHER_CUTOVER_NATIVE_FACTORY`.
3. Install protected JSON configuration and the environment file using the permissions above.
4. Initialize the denial ledger once as described above.
5. Install `kesher-cutover.service` into `/etc/systemd/system/`.
6. Run `systemd-analyze verify /etc/systemd/system/kesher-cutover.service` where available.
7. Start/restart the service only for readiness review. Startup itself performs no cutover step.
8. Verify the listener is loopback-only. Expose it through the reviewed TLS origin only after the OIDC audience is fixed.

`Restart=on-failure` is safe because the durable journal is not recreated on restart and every live step re-observes reviewed configuration/main/native boundaries before mutation.

## Cutover remains separately authorized

Deployment of this service does not authorize a cutover. The controller retirement sentinel remains in place. After independent infrastructure review, follow the production cutover runbook one manually approved invocation at a time. Unknown/lost provider mutation responses are reconciled on a later invocation and are never blindly retried.

No recurring schedule or production controller activation belongs in this deployment package.
