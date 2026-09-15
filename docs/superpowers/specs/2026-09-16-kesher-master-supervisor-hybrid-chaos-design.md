# Kesher Master Supervisor + Hybrid Chaos Design

Date: 2026-09-16
Status: Design approved for detailed planning; implementation not started
Production controller: V5 only
V6 role: shadow only, never production

## Goal

Turn the Kesher content system into a continuously operating, self-healing production pipeline that does not stop at “problem detected.” When a recoverable incident occurs, the system must detect it, diagnose it, select a safe next action, execute that action, verify the result, and continue the original delivery chain without waiting for Yaniv or ChatGPT.

Human intervention is reserved for true human blockers: new secrets or 2FA, payment/purchase, new permissions, security weakening, or an irreversible external action that cannot be safely automated.

Success is defined by delivery, not workflow color: every intended content cycle reaches a verified public Article + Video Overview + Short, all bound to the same authoritative source identity.

## Existing foundation

The repository already contains several pieces of the desired architecture:

- `kesher-content-controller.yml` runs V5 frequently and keeps a single controller concurrency group.
- `kesher_content_controller.py` is the durable production state owner and already enforces retry/idempotency behavior.
- `kesher_content_watchdog.py` detects stale work and can nudge/restart within a bounded recovery budget.
- `kesher_intervention_policy.py` tracks durable progress and implements a three-check escalation policy.
- `kesher_three_strike_runtime.py` records `direct_takeover_required` after repeated non-progress.
- `kesher_cloud_supervisor.py` audits current production state and can trigger the Controller.
- article/image/video/short workflows already preserve exact identities and have several fail-closed guards.

The architectural gap is after bounded recovery is exhausted. Today the system can raise `direct_takeover_required`, but the final diagnosis and repair loop still depends on an external operator. The existing Cloud Supervisor also does not yet build a canonical evidence snapshot, derive a failure signature, own an incident ledger, execute targeted recovery recipes, or drive a Jules repair through CI and back into the original pipeline.

## Target architecture

### 1. V5 Production Controller — single production writer

V5 remains the only component allowed to write the canonical production state on `automation-state`.

Responsibilities:
- own stage transitions, attempts, exact source identity and public delivery state;
- dispatch production workers;
- validate and execute typed recovery commands;
- reject stale/mismatched recovery commands;
- preserve existing idempotency and duplicate-prevention rules.

The Master Supervisor must never directly edit V5 production state.

### 2. Master Supervisor — read-mostly autonomous orchestrator

Evolve `scripts/kesher_cloud_supervisor.py` into the authoritative supervisor rather than creating a second production controller.

Responsibilities:
1. collect evidence from V5 state, workflow runs/jobs, durable video/short state, PR/Jules state, public article and YouTube delivery;
2. identify the authoritative current work identity;
3. derive a stable incident fingerprint;
4. classify the incident;
5. select the next action from deterministic recovery recipes;
6. send a typed recovery command to V5 when production action is needed;
7. escalate to Jules only when deterministic recovery cannot resolve the incident;
8. inspect Jules repair PR/branch and CI, feed failures back to the same Jules session, and merge only after required gates pass;
9. after repair, re-enter the original production chain and verify Article + Overview + Short;
10. persist its own incident ledger separately from V5 state.

The Master Supervisor owns orchestration, not production state.

### 3. Supervisor incident ledger — separate state

Use a separate durable branch/ref, e.g. `automation-supervisor-state`, with `.kesher-supervisor/state.json`.

The ledger stores only supervisory information:
- incident fingerprint and first/last observation;
- current strike and classification;
- normalized failure signature;
- evidence hash;
- actions already issued and their idempotency keys;
- active V5 recovery command ID;
- Jules session/task/PR identity;
- current repair head SHA and CI state;
- cooldown / next eligible action time;
- resolution status and verified completion evidence.

This separation prevents two components from racing over the same production state.

### 4. Canonical evidence snapshot

Each supervisor audit produces an immutable logical snapshot containing at minimum:

- `pipeline_id`, `cycle`, `slug`, `content_sha256`;
- authoritative article title/URL and live verification;
- current stage and V5 controller status;
- exact item/task/source/artifact IDs for Overview and Short when present;
- durable provider state;
- workflow run/job IDs and conclusions;
- relevant failed step and normalized error lines;
- PR number/head SHA/mergeability/checks when a repair PR exists;
- Jules session identity and last durable output fingerprint;
- YouTube ID/URL/public/processing state;
- media dimensions, portrait/signature/technical verification flags;
- evidence timestamps and evidence hash.

Poll timestamps alone are never considered progress. Progress means a durable change in identity, artifact, state, URL, verified field, PR head, or other explicit delivery evidence.

### 5. Incident identity and failure signature

Use the user-approved identity model, extended with cycle where useful:

`pipeline_id | cycle | slug | content_sha256 | stage | failure_signature`

`failure_signature` is normalized from structured state first and logs second. Volatile values such as timestamps, run IDs, temporary paths, line numbers that change without semantic meaning, and request IDs are stripped before hashing.

A changed stage or changed semantic error creates a new incident. The same error with no durable progress advances the existing incident.

### 6. Incident classification

Every audit returns exactly one class:

- `complete` — Article + Overview + Short are independently verified public and source-consistent.
- `healthy_progress` — durable progress occurred or an expected child worker is running inside its normal window.
- `external_running_heartbeat` — NotebookLM generation or YouTube processing is genuinely running; heartbeat exception is allowed up to 90 minutes with evidence.
- `known_recoverable` — a deterministic recipe exists.
- `novel_recoverable` — no recipe exists but sufficient evidence exists for a Jules repair.
- `human_blocker` — requires 2FA/secret/payment/new permission/security weakening/irreversible external approval.
- `unsafe_or_ambiguous` — exact identity cannot be proven; fail closed and gather evidence rather than create duplicate work.

“Blocked” is not a final state unless it is a real human blocker.

## Recovery command boundary

The Master Supervisor does not mutate V5 state. It sends V5 a typed `RecoveryCommand` through `workflow_dispatch` or an equivalent explicit controller entry point.

Required fields:
- `command_id` / idempotency key;
- `incident_fingerprint`;
- `pipeline_id`, `cycle`, `slug`, `content_sha256`, `stage`;
- `action`;
- exact optional `item_id`, `task_id`, `artifact_id`, `source_id`, `pr_number`;
- `evidence_hash`;
- `issued_at`.

V5 must re-read current canonical state and validate that the command still matches before acting. A stale command becomes a recorded no-op, never a best-guess action.

Initial actions should be allowlisted, for example:
- `resume_exact_provider_task`;
- `rebuild_exact_overview`;
- `retry_exact_upload`;
- `dispatch_trusted_image_same_pr`;
- `continue_exact_short`;
- `reconcile_public_youtube`;
- `rerun_failed_ci_same_head`;
- `rebase_repair_pr` where repository policy permits.

## Deterministic recovery recipes

Recipes are data-driven or small deterministic functions, not AI prompts. Each recipe defines:
- match conditions;
- required evidence;
- exact safe action;
- duplicate-prevention guard;
- verification condition;
- maximum attempts / cooldown;
- escalation target if unresolved.

Initial recipe set must cover at least:
1. article pending trusted image;
2. article image guard failure;
3. article CI failure with same PR;
4. deploy succeeded but public article not yet verified;
5. stale provider binding to a previous slug/source;
6. exact provider task already generating but controller lost/badly persisted IDs;
7. exact Overview rejected for missing full-screen signature -> Remotion rebuild of exact item;
8. exact technically verified Overview not uploaded;
9. YouTube upload exists but V5 state missed reconciliation;
10. YouTube processing still running under the bounded heartbeat window;
11. YouTube processing failed;
12. Short missing for an already verified Overview;
13. Short exists but is not valid 9:16;
14. corrupt newest durable video-state artifact -> fall back to newest valid retained artifact;
15. worker died mid-action but exact provider/artifact identity exists;
16. retry budget exhausted because of controller bookkeeping while a safe exact recovery still exists;
17. PR conflict for the active repair PR;
18. repair CI failure after Jules change.

## Escalation model

Preserve the S1/S2/S3 semantics but make all three machine-executable:

### S1 — Controller recovery

On first observation of the same incident, use a deterministic recovery recipe through V5 if safe. No new provider generation when an exact reusable task/artifact exists.

### S2 — Jules repair

On the next supervisor audit with the same failure fingerprint and no durable progress, create or continue exactly one Jules repair session for that incident.

The incident package includes:
- exact source identity;
- failure fingerprint and strike;
- failing stage and workflow/job/step IDs;
- minimal relevant logs;
- current state excerpt;
- prior recovery actions and results;
- exact file scope where known;
- Definition of Done;
- commands/tests that must pass;
- explicit no-duplicate/no-security-weakening constraints.

A new supervisor run continues the same Jules session rather than opening another one.

### S3 — Direct autonomous repair loop

On the third observation with the same failure and no progress, the supervisor owns completion of the repair loop:
- continue the existing repair PR/session;
- if a safe deterministic repository repair is possible, apply it on the same repair branch/PR;
- run required tests/checks;
- inspect diff scope;
- resolve safe rebase/conflict cases;
- merge only when all required gates are green;
- trigger/resume V5;
- verify public delivery;
- close the incident only after delivery is complete.

S3 must not mean “tell a human to take over.”

## Jules budget and role

Jules is a repair agent, not a heartbeat service.

Rules:
- no Jules call on healthy audits;
- one active Jules session per incident fingerprint;
- reuse the same session for CI feedback;
- configurable maximum session/task count per incident;
- never ask Jules to regenerate public content as a substitute for reconciliation;
- deterministic recovery is always preferred before Jules.

This limits credits and reduces nondeterministic behavior.

## Safety and duplicate prevention

Before every action the supervisor must prove:
- authoritative source identity is exact;
- no equivalent child workflow/action is already active;
- no equivalent command/action idempotency key was already issued for the same evidence hash;
- no reusable exact provider task/artifact already exists before generation;
- upload action is bound to an exact verified item;
- repair action targets the existing PR/session when one exists.

Never autonomously:
- expose or rotate secrets;
- weaken CI/security gates;
- perform purchase/payment;
- bypass 2FA;
- request new external permissions on the user's behalf;
- perform irreversible external cleanup/deletion without explicit approval.

## Master Supervisor self-healing

Avoid an infinite chain of supervisors supervising supervisors.

Use one minimal liveness watchdog, implemented as a deterministic GitHub workflow, whose only responsibilities are:
- verify that a successful Master Supervisor audit has occurred within the configured liveness window;
- rerun the Master Supervisor once when stale;
- if repeated liveness checks fail, preserve a single supervisor-health incident and keep the existing V5 heartbeat running;
- never diagnose content incidents itself;
- never create Jules tasks or production artifacts.

The watchdog is a circuit breaker, not a third controller.

## Hybrid Chaos test strategy

Use three progressively stronger modes.

### Mode A — offline deterministic simulation

Fixture states and mocked GitHub/provider responses. No external writes. Used for fast TDD and exhaustive fault matrix tests.

### Mode B — shadow replay

Feed the Master Supervisor historical real controller/video/short states and workflow evidence, but disable all writes/dispatches. Compare its decisions to known expected recoveries.

### Mode C — controlled live recovery

Use real workflows and real existing identities only after Modes A/B pass. Inject only reversible/contained faults or replay existing failed incidents. Never intentionally create duplicate public content, duplicate NotebookLM generation, or destructive production changes.

## Chaos acceptance contract

Every injected incident must demonstrate the entire loop:

`Detect -> Diagnose -> Decide -> Act -> Verify -> Continue`

Passing a scenario requires:
- exact incident fingerprint produced;
- correct classification;
- expected action selected;
- no duplicate action/artifact/task;
- result independently verified;
- original chain resumes;
- final delivery becomes complete or a true human blocker is proven;
- incident ledger closes only after verification.

## Rollout gates

No calendar-duration promises are required. Promotion is evidence-based:

1. **Offline gate:** full unit/integration chaos matrix green, including concurrency/idempotency tests.
2. **Shadow gate:** replay a sufficiently broad historical evidence set with zero unsafe actions and expected classification/action parity.
3. **Live S1 gate:** enable deterministic Master actions only; Jules remains observation-only.
4. **Live S2 gate:** enable automatic Jules repair package/session continuation.
5. **Live S3 gate:** enable autonomous repair-PR/CI/recovery completion for explicitly allowlisted repository scopes.
6. **Full autonomy:** the system runs all safe layers without human confirmation and escalates to Yaniv only for a true human blocker.

A rollback switch must be available at every gate to return the Master Supervisor to shadow/read-only mode without disabling V5 production.

## Success metrics

Primary:
- manual interventions per content cycle: target 0;
- duplicate article/provider generation/video/upload: 0;
- stale source cross-binding: 0;
- unsafe automated action: 0;
- delivery contract completion: Article + Overview + Short verified for every intended cycle.

Operational:
- incidents resolved without human action;
- audits required from first detection to verified recovery;
- deterministic recovery rate versus Jules escalation rate;
- Jules sessions per incident;
- NotebookLM generations per source identity;
- stale-command no-op count;
- supervisor liveness failures.

## Non-goals

- replacing V5 with V6;
- using an LLM on every heartbeat;
- creating a second component that directly edits production state;
- weakening existing publication gates for availability;
- intentionally breaking production for chaos testing before isolated/shadow gates pass.

## Final architectural invariant

At any moment there is exactly one production-state writer (V5), exactly one supervisory decision owner (Master Supervisor), and at most one active repair identity per incident. The system should report results to the user, not wait for the user to invent the next action.
