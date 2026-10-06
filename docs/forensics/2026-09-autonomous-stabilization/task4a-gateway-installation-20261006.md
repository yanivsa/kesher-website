# Task 4A gateway installation contract

Repository implementation is ready for independent provisioning; the live service is **not provisioned or certified**. `task4a-installation-template-20261006.json` is deliberately incomplete. Its supervisor task ID is the expected identity, not live suspension/tool-authority proof. The dated Task 3.5 readback template remains untouched and unresolved.

Use the existing Python service. No Cloudflare Worker, alternate authority store, shared static API key or attestation-file fallback is introduced. The SQLite invocation table is a **deny ledger**, not canonical state or proof of provider exclusion. Its persistent storage, nonrollback custody and backups remain a host-administrator responsibility; a filesystem path or successful SQLite open cannot prove durability across loss of the host.

## Independently installed service factory

An administrator must install one top-level `trusted_kesher_cutover.py` module outside the repository checkout, in a protected directory such as `/etc/kesher-cutover/factory`. Review its exact SHA-256 and all imported dependencies independently; the factory cannot approve itself or obtain approval from the Actions client. Runtime code, factory, approval metadata and trusted observers must be read-only to the service identity. Credentials and sealing keys remain service-side.

The factory's `build()` must:

1. Load a complete, independently approved installation specification with the exact repository numeric/node IDs, reviewed **current main** SHA, epoch/owner, six native resource bindings, HTTPS origin and persistent ledger path. `supervisor_task_id` must equal `6aa71096e1788191ae791be184322d69`.
2. Compose the existing `live_cutover.build_runtime` using the actual GitHub ruleset/credential guard and five native provider ports, independently installed fresh `ControlPlaneConvergence` observer, all 19 service separation observers, immutable approved migration/closed-5.2 material and sealing custody. Unsupported `PrerequisitePort` observers refuse. No fake production factory is provided.
3. Construct `ActionsIdentity` with `repo='yanivsa/kesher-website'`, `repository_id=1239881973`, exact reviewed main and HTTPS audience. The existing verifier checks GitHub's signed OIDC and the live exact run/attempt/workflow/main. There is no static API key option.
4. Return `CutoverApplication(runtime=runtime, identity=identity, journal=InvocationJournal(spec['ledger_path']), epoch=spec['epoch'], reviewed_revision=spec['reviewed_revision'], review_check=independent_installed_byte_review, installation=spec)`.

`validate_installation(application)` is the read-only local configuration/storage check. It rejects missing/wrong task identity, mismatched native resource bindings, incomplete keys, wrong OIDC audience, non-HTTPS origin, malformed or missing database, relative/symlink ledger path and permissive ledger file permissions. It does not initialize, repair, claim an invocation or mutate a resource. The service additionally runs the independent byte review and native `runtime.preflight()` before listening. Preflight reads all six resources, infrastructure and control planes before any effect. Thus an active/unobserved predecessor or missing native adapter prevents a successful full preflight, even with valid local configuration.

The loader accepts only a top-level `module:function`, an absolute external root without symlink substitution, and an independently supplied exact factory SHA-256. It executes the verified bytes, without stale pyc reuse. These are installation checks, not a Python sandbox; factory administrators and dependency review remain trusted.

## Durable host and TLS

Use a dedicated Linux service identity, persistent `/var/lib/kesher-cutover` (0700), ledger 0600, and root-owned read-only code/factory/configuration. Initialize the ledger **once**, as the service user during separately authorized provisioning:

```sh
python3 -B -c 'from scripts.kesher_runtime.cutover_service import InvocationJournal; InvocationJournal.initialize("/var/lib/kesher-cutover/invocations.sqlite")'
```

Initialization uses exclusive creation and refuses replacement. Never put it in ExecStart, a temporary directory, Actions workspace or an ephemeral container layer. Never delete/reinitialize it following an uncertain response. Recover the protected volume and reconcile exact remote intents. Keep both gateway invocation and native-ruleset effect claims in protected durable custody across restart.

Install reviewed runtime dependencies, including `cryptography`, in a dedicated venv. Run from the immutable reviewed checkout. After substituting the independently approved factory digest (not a repository-generated approval):

```sh
/opt/kesher-cutover/venv/bin/python -B -m scripts.kesher_runtime.cutover_service \
  --factory trusted_kesher_cutover:build \
  --factory-root /etc/kesher-cutover/factory \
  --factory-sha256 "$KESHER_FACTORY_SHA256" --check-only
```

This command does not invoke `step`, start HTTP or initialize the ledger. It does call independently installed read-only native observers. A production factory must not perform effects at import/construction. With current absent native prerequisites it must fail. In Task 4B the full convergence preflight can succeed only after the freshly observed predecessor is safely suspended/restricted within the coordinated cutover window. Local installation readiness may be validated earlier without claiming live convergence.

For the durable service use the same command without `--check-only`, `WorkingDirectory=/opt/kesher-cutover/reviewed`, `User=kesher-cutover`, `UMask=0077`, `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=true`, `PrivateTmp=true`, `ReadWritePaths=/var/lib/kesher-cutover`, and a persistent volume. Configure the exact factory digest through administrator-owned startup configuration. Allow no externally writable Python import paths. Do not start/install the service as part of Task 4A.

The server binds only `127.0.0.1:8789`. Terminate HTTPS at an independently managed reverse proxy; forward `/v1/cutover/step`, preserve Authorization, do not log credentials or request bodies, enforce request-size/time limits, and firewall direct port access. TLS certificate, DNS, ingress route and OIDC audience must all match the exact approved HTTPS origin. No guessed origin is provided.

GitHub environment `kesher-cutover` must restrict to exact main plus independent approval. Current `protected_branches=true` is insufficient evidence of exact main-only deployment (current readback has no rulesets). Use native environment branch policy and independently read it back before configuring `KESHER_CUTOVER_GATEWAY_URL`. No provider credentials are sent to Actions by this cutover path.

## Task 4B choreography, not executed

1. Complete every native adapter, credential separation, canonical App, host/TLS, exact current-main/registration review and migration sealing prerequisite. Ruleset has exactly one reviewed canonical Integration bypass, never an empty or legacy/admin/user bypass list, and pins literal main + automation-state refs.
2. Freshly observe the exact external supervisor/account and all repo-capable Jules sessions/grants. Enter the coordinated cutover window; suspend the legacy Master Active Supervisor and verify no running continuation can mutate. Keep it active throughout Task 4A.
3. Complete predecessor denial at each native resource and prove all 19 infrastructure separations, including OCI. Run full gateway preflight and the existing one-effect-per-invocation nine-phase handover with exact CAS and uncertain-response reconciliation. Never use an empty Actions list as fencing proof.
4. Only after separately certified successful cutover may Schema-6 canonical activation occur and the external task become OBSERVER-ONLY. No activation is performed by Task 4A or inferred from a gateway response. Never restore broad old authority to clear an error.

Cloudflare Pages tokens are account-scoped: isolate a minimum Pages credential from OCI/OpenClaw and bind its use at the trusted gateway to account `95ba6a62314a0682d0711050ba9c3445`, project `kesher-website`, project ID `41773648-4870-407a-b868-5f05f2a2da57`. No per-project native token scope is assumed. YouTube tokens are not Google environment-scoped; repository/workflow restrictions and protected canonical credential custody provide that isolation, together with native predecessor revocation and complete outstanding-upload readback.
