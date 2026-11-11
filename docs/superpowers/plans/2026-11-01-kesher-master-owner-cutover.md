# KESHER Master Owner Cutover Implementation Plan

**Goal:** Make Master Active Supervisor the sole KESHER decision owner while preserving one canonical Schema-6 state and deterministic GitHub workers.

**Architecture:** Keep the registered `kesher-content-controller.yml` workflow identity through handover, but add an explicit Master-intent live path. Pre-cutover legacy execution remains bridge-gated to Schema 5; after verified Schema-6 migration that path fails closed. The Master path accepts only request ID plus provider-neutral target/operation JSON, derives exact worker inputs from fresh observation, persists the immutable command through CAS, and dispatches only the canonical worker route.

**Safety:** No live Master write before verified handover. No caller-supplied worker/provider identities. Same pending exact command is resumed, not duplicated. Existing outbox remains the only dispatch mechanism.

## Tasks
1. RED: add regression tests for same-command resume and live Master workflow contract.
2. GREEN: implement idempotent same-command resume in `master_intent.py`.
3. GREEN: add `live` execution to `master_intent_entry.py` with authority checks, CAS save-before-dispatch, and trusted workflow identity.
4. Extend the existing registered controller workflow with a Master-only dispatch path while retaining Schema-5 bridge behavior until cutover.
5. Re-certify authority policy hashes and add Master intent files to the controller reviewed call chain.
6. Run focused tests, authority/cutover tests, then full quality gate.
7. Merge only when all gates are green.
8. Execute production cutover repeatedly with one epoch until `VERIFIED`; verify Schema 6 and exclusive authority.
9. Update Master Active Supervisor prompt to use the live Master intent path and never delegate next-action selection to Jules/Controller.
10. Run canary and three clean Master cycles; verify Article + Video + Short public links for one immutable SourceIdentity.
