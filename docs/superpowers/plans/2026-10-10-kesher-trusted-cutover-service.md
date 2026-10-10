# Trusted external cutover service implementation plan

Spec: `docs/superpowers/specs/2026-10-10-kesher-trusted-cutover-service-design.md`

Base: `715a5c037ce38fa20cebf89e06fd2e9a7d82080e`

Global constraints: no production activation, no workflow dispatch, no automation-state/provider mutation, no sentinel removal, no synthetic native evidence, no merge/deploy.

## Task 1 — Define and test the trusted composition boundary

Files:
- add `tests/test_kesher_trusted_cutover_service.py`
- add `trusted_kesher_cutover.py`

RED: tests import `trusted_kesher_cutover` and require refusal for missing config, missing ledger, missing native factory, incomplete external port map, `PrerequisitePort`, invalid factory return type, and review/main mismatch.

GREEN: implement strict config loading, JSON duplicate-field rejection, service-local native factory import, port validation, pre-existing ledger validation, runtime composition through `live_cutover.build_runtime`, `ActionsIdentity`, and `CutoverApplication`.

Expected: configuration cannot create/initialize durable state or fabricate any native resource proof.

## Task 2 — Bind fresh installed review on every invocation

Files:
- update `tests/test_kesher_trusted_cutover_service.py`
- update `trusted_kesher_cutover.py`

RED: mutate an administrator review/config file after application construction and prove `review_check` refuses before runtime mutation.

GREEN: re-read protected review/config material, recompute executable/policy/registration/material/closure bindings using existing repository contracts, and require exact equality with the application’s installed binding.

Expected: stale reviewed main/code/policy/evidence/configuration cannot be used after installed bytes or files drift.

## Task 3 — Linux/OCI packaging

Files:
- add `ops/kesher-cutover/kesher-cutover.service`
- add `ops/kesher-cutover/kesher-cutover.env.example`
- add `ops/kesher-cutover/README.md`
- update tests with packaging assertions

RED: packaging tests require loopback-only service, dedicated persistent state directory, no secret values, no automatic ledger initialization, restart-safe service settings, and explicit TLS/OIDC-audience instructions.

GREEN: add systemd/env/docs templates matching those constraints.

Expected: service startup performs no cutover automatically and cannot silently recreate a lost ledger.

## Task 4 — Governance and final verification

Files:
- update `scripts/kesher_runtime/authority_policy.json` only via canonical synchronizer if governed call-chain hashes require it.

Verify:
- trusted service tests;
- `tests.test_kesher_production_cutover`;
- authority/handover/cutover related suites;
- Stability regression command used by repository CI;
- `python3 scripts/kesher_runtime/sync_authority_policy.py --check`;
- `python3 scripts/kesher_runtime/workflow_governance.py`;
- YAML/actionlint where applicable;
- `git diff --check`.

Open PR `feat(kesher): implement trusted external cutover service` and do not merge.

Final review focus: no native provider evidence is synthesized; no secret-bearing values are committed; native factory cannot be selected by an HTTP caller; journal is fail-closed and pre-existing; review is fresh; controller remains retired; no production mutation or workflow dispatch is introduced.
