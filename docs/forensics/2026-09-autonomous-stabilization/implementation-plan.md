# KESHER autonomous stabilization implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Keep one stabilization branch and one PR. The user has authorized investigation through implementation, safe merge and reconciliation; do not add a second planning approval cycle.

**Goal:** Make daily Article → deployment → Overview + native Short → independent public verification deterministic, durable and recoverable without ChatGPT.

**Architecture:** One controller also owns escalation. An exact-command ledger and CAS state protect all worker boundaries. Existing proven media/image functions remain workers; obsolete orchestrators and independent repair mutators are retired after migration and replacement regression proof.

**Tech stack:** Python standard library for orchestration/state, existing GitHub Actions, existing Node/Remotion and NotebookLM/YouTube workers.

**Spec:** [target-architecture.md](target-architecture.md)

## Global constraints

- No new provider jobs merely to test recovery; use offline mocks/replays and GET-only observation.
- No secret material in state, reports, logs or commits.
- All source-bound operations require full immutable source identity and explicit media kind.
- One canonical operational state: `automation-state:.kesher-controller/state.json`, schema 6, revision CAS.
- Current contract: complete independent native Short first; approved bounded independent fallback; in-content signature without extended duration; bounded voice preference; optional visual enrichment.
- Never weaken an evaluator to make a repair pass. Explain and prove intentional obsolete-contract migration.
- Existing main snapshot is `55563f42`; later main changes must be reviewed and integrated before final CI.

## 1. Canonical identity, CAS and crash-safe commands

**Files:** create `scripts/kesher_runtime/__init__.py`, `identity.py`, `state.py`, `github.py`; create `tests/test_kesher_canonical_state.py`.

**Interfaces:** `SourceIdentity(slot, slug, content_sha256)`; `MediaIdentity(source, kind)`; `new_state()`; `LoadedState(state, blob_sha)`; `GitHubStateStore.load()` and `.save(loaded, proposed)`; `plan_command(state, target, operation, ordinal, inputs)`; `claim_command(state, command_id, worker_run_id, expected_target)`.

- [ ] Add failing state/identity tests. Core cases:

```python
source = SourceIdentity('2026-09-17', 'article', 'a' * 64)
assert MediaIdentity(source, 'overview').key != MediaIdentity(source, 'short').key
with self.assertRaises(ValueError):
    SourceIdentity('2026-09-17', 'article', '')
first = store.load()
second = store.load()
store.save(first, advance(first.state))
with self.assertRaises(CasConflict):
    store.save(second, advance(second.state))
```

- [ ] Run `python3 -m unittest tests.test_kesher_canonical_state -v` and preserve expected failures.
- [ ] Implement strict dataclass validation, deterministic IDs, immutable target fields and copy-on-write ledger transitions. GET retries are bounded; POST/PUT ambiguity is never blindly retried. Save uses the originally observed SHA and increments revision exactly once.
- [ ] Test duplicate claims, stale source/kind, rejected partial identity, two schedulers and crash after intent before dispatch. Add local HTTP fault coverage for accepted mutation followed by lost response.
- [ ] Run the focused suite, record red/green evidence, commit explicit files.

## 2. Exact worker handoff and durable checkpoints

**Files:** create `scripts/kesher_runtime/worker.py`; modify canonical article/image/normalizer/media workflows and worker state I/O; test `tests/test_kesher_worker_commands.py`.

**Interfaces:** `WorkerContext.claim(command_id, workflow_run_id)`; `.checkpoint(receipt)`; `.finish(result)`; exact target projection into existing media worker state; controller-only command creation.

- [ ] Add failing tests proving two workflow invocations claim only once, old command cannot switch to current source, and a worker receipt cannot mutate another identity.

```python
first = context.claim(command_id, 'run-1')
duplicate = context.claim(command_id, 'run-2')
assert first.execute is True
assert duplicate.execute is False
```

- [ ] Add expected command ID/source/code revision inputs and run-name correlation. Checkout trusted current main for production; PR validation remains hermetic. Claim before exposing provider credentials to execution steps.
- [ ] Replace mutable artifact restoration with canonical exact-item projection and immutable evidence retrieval. Persist provider/upload checkpoints through CAS. Preserve fresh-secret precedence.
- [ ] Exercise crash before and after provider ID/upload-session checkpoints, output download failure and uncertain responses. Run worker/pipeline/auth regression suites and commit.

## 3. Single controller and fair recovery

**Files:** create `scripts/kesher_runtime/controller.py`, `policy.py`, `observe.py`; replace `kesher-content-controller.yml` production entrypoint; test `tests/test_kesher_autonomous_controller.py`.

**Interfaces:** `observe()` returns typed immutable observations; `reconcile(state, observations, now)` returns proposed state and zero/one planned command; `run_tick()` commits intent before dispatch and never dispatches after CAS conflict.

- [ ] Reproduce exact backlog identity loss, generate-without-upload, stale same-slug SHA, global external-run waiting, false timestamp progress and current/backlog starvation.
- [ ] Implement explicit stage lifecycle and classified budgets. Adopt exact existing PR, provider, upload and command receipts first. Bind retry counters to target and action; consume no generation attempts for auth preflight or normal pending polls.
- [ ] Implement current priority with eligible historical work during current pending/backoff. No global FIFO override of an exact target. Integrate article/image/normalization/merge/deploy transitions using current-head proof.
- [ ] Test all event/heartbeat orderings, duplicate events, day rollover, two publications same day, crash/restart and twelve-hour provider unavailability. Commit after focused controller/worker suites.

## 4. Public contract, media provenance and article gates

**Files:** create `scripts/kesher_runtime/verification.py`; repair existing media validators/cache/metadata code, image provider consumers, article path contract and deploy verification; tests `test_kesher_public_delivery.py` plus historical suites.

**Interfaces:** `verify_article(source, deploy, response)` and `verify_media(identity, local_evidence, remote_metadata)` return explicit evidence or classified failure. `delivery_complete(run)` requires all three matching public receipts.

- [ ] Convert captured #804 image/RSS, Short/Overview shared-provider, stale render hashes, old outro and wrong remote URL/title examples into failing regressions.
- [ ] Consolidate trusted image/path contract consumers, bind proof to current PR head/source/image bytes, and make normalization idempotent.
- [ ] Bind render cache to raw/source/kind/props/motion-plan/signature/engine hashes; preserve timeline/audio. Enforce independent native origin and only authorized bounded fallback.
- [ ] Fetch YouTube snippet/status/processing/channel remotely, compare complete expected metadata and exact links, reconcile existing ID/session before upload, and recover metadata without another upload.
- [ ] Verify article deploy SHA, canonical route, content marker, hero and metadata, including Hebrew Unicode URLs. Test 200-at-wrong-route and 404-after-green-deploy. Run focused suites and commit.

## 5. Incident-bound Jules and trusted repair gates

**Files:** create `scripts/kesher_runtime/recovery.py`, `.github/jules-templates/autonomous-repair.md`, trusted guard-integrity script/workflow; update repository instructions; test `tests/test_kesher_repair_contract.py`.

**Interfaces:** `incident_key(identity, stage, failure_class)`; `repair_packet(incident, evidence)`; `reconcile_repair(...)`; `validate_repair(base, head, contract)` returns a fail-closed verdict.

- [ ] Tests fail for timestamp-only Jules activity, duplicate sessions/PRs, CI evaluator changes, test deletion/assertion weakening and premature tracker closure.
- [ ] Implement semantic stall deadlines, existing-session/branch/PR adoption, bounded continuations and persistent incident audit. Software exhaustion is circuit-broken repair, not a fabricated interactive-auth blocker.
- [ ] Run trusted base guard checks and immutable regression gates against repair code. Require exact-head complete CI and permitted scope before automatic merge. Require authorized historical contract evidence for obsolete-test migration.
- [ ] Resume the interrupted source/operation after repair; public verification resolves the incident. Test failed/closed PR, terminal no-output session, merge race and external reauth recovery. Commit.

## 6. Migration, retirement and canonical observability

**Files:** create `scripts/kesher_runtime/migration.py`, migration report/status renderer; remove retired mutating workflows/controller entrypoints after invariant replacement; tests `tests/test_kesher_runtime_migration.py` and topology tests.

- [ ] Replay captured V5, supervisor and media snapshots. Duplicate uploads/provider conflicts and missing provenance must quarantine, not pick newest. Preserve every previous identifier/budget/audit link.
- [ ] Prove interrupted old workers cannot overwrite new schema/state, and retired entrypoints cannot mutate. Add complete workflow authority allowlist and static dispatch graph validation.
- [ ] Consolidate controller/escalation state, remove independent supervisor schedule and one-off mutators, and retain only useful read-only diagnostics.
- [ ] Emit one canonical per-slot status with identities, stage/verification receipts, incident/action/Jules/PR and next action. Commit migration plus retirement together once replay/topology tests pass.

## 7. Historical matrix, chaos and adversarial review

**Files:** forensic timeline/diagnosis/root-cause graph/recovery matrix/regression matrix; `tests/test_kesher_autonomous_chaos.py`.

- [ ] Complete adjudication of every significant indexed family and account explicitly for unavailable history/log evidence. Distinguish scan coverage from proven root cause.
- [ ] Map every user-listed regression and failure family to a meaningful test or technical reason deterministic coverage is impossible.
- [ ] Fault-inject 401/403/429/500, timeout/network, forever-pending provider, duplicate scheduler, CAS conflict, crashes, stale auth/source/kind/cache/upload and failed GitHub API. Assert no duplication, false completion, state corruption or unbounded active retry.
- [ ] Run Python discovery, canonical targeted suites and `npm run check`; review all bypasses/duplicate entrypoints. Address findings and rerun affected gates.

## 8. One PR and actual deployment proof

- [ ] Integrate current main without disturbing unrelated work, review complete diff and push one stabilization branch/PR.
- [ ] Require complete exact-head GitHub CI, trusted guard checks and review. Merge only if policy and evidence permit.
- [ ] Reconcile actual state and disable registered obsolete mutators as part of the verified cutover. Keep migration backups.
- [ ] Run read-only shadow/reconciliation and remote A+B+C checks. Any bounded real canary must have exact identity/idempotency proof before dispatch.
- [ ] Audit every original requirement/deliverable against current evidence. Mark the goal complete only when this audit passes; green CI alone is insufficient.
