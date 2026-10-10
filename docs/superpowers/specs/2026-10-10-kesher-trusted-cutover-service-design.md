# KESHER trusted external cutover service design

## Status and scope

This design packages the already-reviewed Schema-6 cutover service for a persistent Linux/OCI host. It does **not** activate production, dispatch a workflow, mutate automation-state, change provider state, or remove the canonical controller retirement sentinel.

The repository already implements the cutover state machine, GitHub Actions OIDC verification, exact-main/code/policy bindings, guarded GitHub mutation path, external exclusion contracts, and a durable SQLite replay-denial journal. The missing production layer is administrator-owned composition and host packaging.

## Security boundary

The service must fail closed unless all administrator-controlled inputs are present and all six resource boundaries are supplied by a separately installed native bundle. The repository must never fabricate service evidence for GitHub, Jules, NotebookLM, YouTube, Cloudflare, or the image provider.

Five external services do not expose enough public API surface to prove the repository's complete exclusion contract by themselves. Therefore this implementation intentionally does **not** create synthetic provider adapters. A service-local native bundle remains a deployment prerequisite and must implement real `inspect()`/`exclude()` operations plus infrastructure-separation readback under administrator custody.

## Composition

A new reviewed module `trusted_kesher_cutover.py` exposes `build()` for `scripts.kesher_runtime.cutover_service`.

`build()`:

1. Loads immutable review/configuration material from administrator-owned JSON files whose paths are provided by environment variables.
2. Imports a service-local native factory selected by `KESHER_CUTOVER_NATIVE_FACTORY` (`module:function`).
3. Requires the native factory to return the GitHub transport, GitHub boundary, all five non-GitHub native ports, a fresh separation observer, and a sealing-key callable. Missing or structurally incomplete native material is a refusal.
4. Verifies repository identity, exact reviewed main SHA, policy/code/registration/migration-material digests through the existing `live_cutover.build_runtime` contract.
5. Constructs `ActionsIdentity` against the exact repository ID, reviewed main SHA and configured HTTPS audience.
6. Opens the pre-initialized persistent `InvocationJournal`; it never initializes or recreates a missing ledger.
7. Returns the existing `CutoverApplication` with a `review_check` that re-reads administrator review/config files and current repository bytes before every invocation.

No caller controls ports, review evidence, resource bindings, migration material, credentials, sealing key, or closure evidence.

## Administrator files and environment

Required environment variables contain paths/identifiers only, never evidence payloads or secrets:

- `KESHER_CUTOVER_REVIEW_FILE`
- `KESHER_CUTOVER_MATERIAL_FILE`
- `KESHER_CUTOVER_CLOSURE_FILE`
- `KESHER_CUTOVER_BINDINGS_FILE`
- `KESHER_CUTOVER_REGISTRATIONS_FILE`
- `KESHER_CUTOVER_KEY_BINDING_FILE`
- `KESHER_CUTOVER_NATIVE_FACTORY`
- `KESHER_CUTOVER_OIDC_AUDIENCE`
- `KESHER_CUTOVER_JOURNAL`
- `KESHER_CUTOVER_EPOCH`
- `KESHER_CUTOVER_OWNER`
- `KESHER_GITHUB_REPOSITORY`
- `KESHER_GITHUB_REPOSITORY_ID`
- `KESHER_CUTOVER_ROOT` (optional; defaults to installed repository root)

The review/config JSON files are service-side protected custody and are not committed with live values.

## Native bundle contract

The service-local native factory receives no HTTP-client material. It returns a mapping containing:

- `github`: GitHub API transport used by guarded cutover code;
- `github_boundary`: real predecessor/canonical GitHub grant boundary;
- `external_ports`: exactly `jules`, `notebooklm`, `youtube`, `cloudflare`, `image_provider`;
- `separation_observer`: callable returning fresh independently enforced infrastructure separation;
- `key`: callable returning the sealing key from protected custody.

Every external port must be a real implementation, not `PrerequisitePort`. The trusted factory rejects unsupported/synthetic prerequisite ports before constructing the runtime.

## Persistent service packaging

The service runs as an unprivileged dedicated user, binds only `127.0.0.1:8789`, uses `/var/lib/kesher-cutover/invocations.sqlite` for the denial ledger, and is exposed only through administrator-managed TLS reverse proxy. The OIDC audience must equal the exact final HTTPS gateway origin.

A systemd unit and environment-file template are provided. Startup never initializes the ledger and never performs cutover or provider mutations. An administrator initializes the ledger once with mode `0600` before first service start.

## Acceptance and blocker semantics

Repository CI can prove composition and fail-closed behavior with fixtures, but it cannot prove the external provider boundaries. The implementation is therefore reviewable while live deployment remains blocked until a real native bundle and protected service-side configuration are installed and independently audited.

The expected implementation verdict before those external prerequisites exist is:

`BLOCKED_BY_NATIVE_PROVIDER_CAPABILITY:jules,notebooklm,youtube,cloudflare,image_provider`
