# Kesher Master Supervisor + Hybrid Chaos — Implementation Plan

Date: 2026-09-16
Design: `docs/superpowers/specs/2026-09-16-kesher-master-supervisor-hybrid-chaos-design.md`
Branch for planning only: `plan/master-supervisor-chaos-20260916`
Production controller: V5 only

## Objective

Implement an autonomous supervisory layer that turns a blocked/stalled Kesher production cycle into a closed-loop recovery process:

`Detect -> Diagnose -> Decide -> Act -> Verify -> Continue`

The Master Supervisor must finish safe recoveries without waiting for Yaniv or ChatGPT. V5 remains the only production-state writer. Jules is invoked only for code repair after deterministic recovery is insufficient.

## Delivery strategy

Do not implement this as one large PR. Use small gated PRs so production remains stable. Every implementation PR follows TDD: add failing tests first, make the minimum code change, run focused tests, then run the existing stability/contract suite.

Recommended implementation sequence:

1. land/close the current narrow #829 incident repair independently;
2. add supervisor schemas and contract in shadow-only mode;
3. build evidence + incident engine offline;
4. add separate supervisor state ledger;
5. add deterministic recipe engine;
6. add typed recovery-command boundary into V5;
7. wire Master Supervisor workflow in shadow mode;
8. add Jules repair broker;
9. add autonomous PR/CI repair loop;
10. add self-liveness watchdog;
11. build Hybrid Chaos harness and pass offline/shadow gates;
12. progressively enable S1, S2, then S3.

---

## Task 0 — Establish a clean baseline and preserve current incident work

**Purpose:** do not mix the architectural work with the current rejected-Overview repair.

**Existing work:** PR #829 (`Route rejected Video Overview to Remotion rebuild`) remains a narrow incident repair and should be verified/merged on its own merits before production rollout of the Master Supervisor.

### Steps

1. Verify #829 required checks and exact diff scope.
2. If green, merge #829 without adding Master Supervisor code to it.
3. Capture its incident as the first deterministic recovery recipe fixture:
   - exact item rejected;
   - `signature_fullscreen != true`;
   - correct action: exact Remotion `rebuild`;
   - never regenerate NotebookLM content.
4. Rebase future implementation branches on the post-#829 main branch.

### Acceptance

- no architecture changes in #829;
- its behavior has a regression test;
- the same failure is represented later in chaos fixtures.

---

## Task 1 — Extend the production contract with Master Supervisor invariants

**Modify:**
- `config/kesher-production-contract.json`
- `tests/test_production_contract_v3.py`

### Test first

Add assertions for a new `supervision` section containing at least:

- `owner: kesher-master-supervisor`;
- `production_state_writer: kesher-content-controller`;
- `supervisor_state_ref: automation-supervisor-state`;
- `heartbeat_minutes` (recommend 10; faster event triggers remain allowed);
- `actionable_safe_work_must_execute: true`;
- `report_only_when_action_available: false`;
- `direct_takeover_requires_action_before_report: true`;
- fingerprint fields including `pipeline_id`, `cycle`, `slug`, `content_sha256`, `stage`, `failure_signature`;
- `external_running_heartbeat_max_minutes: 90`;
- escalation S1/S2/S3 definitions;
- human-blocker allowlist;
- duplicate prevention and single-writer invariants;
- shadow/live rollout mode.

Add invariant tests:
- Master may not write production state;
- only V5 may dispatch production state transitions;
- one active Jules repair identity per incident;
- stale commands must no-op;
- no provider regeneration when an exact reusable task/artifact exists.

### Run

```bash
python -m unittest tests.test_production_contract_v3 -v
```

Then run the existing V5 stability/contract subset used by CI.

### Commit

`contract: define autonomous Master Supervisor ownership`

### Acceptance

The contract can answer, machine-readably: who owns production state, who owns incident decisions, when Jules may be called, and what requires a human.

---

## Task 2 — Introduce typed supervisor domain models

**Create:**
- `scripts/kesher_master_supervisor_models.py`
- `tests/test_master_supervisor_models.py`

### Models

Implement small immutable/dataclass-style structures for:

1. `EvidenceSnapshot`
2. `IncidentIdentity`
3. `Incident`
4. `RecoveryCommand`
5. `SupervisorDecision`
6. `VerificationResult`
7. `HumanBlocker`

### Required behavior

`IncidentIdentity` must normalize and produce the canonical fingerprint:

`pipeline_id|cycle|slug|content_sha256|stage|failure_signature`

`RecoveryCommand` must include:
- `command_id`;
- incident fingerprint;
- source identity;
- stage/action;
- optional exact IDs;
- evidence hash;
- issue time.

No secrets or raw credentials may be accepted in the command schema.

### Tests

Write tests proving:
- same semantic failure with different run IDs/timestamps yields same fingerprint;
- changed stage produces a different incident;
- changed semantic failure produces a different incident;
- missing source identity is rejected;
- a recovery command cannot be constructed without incident/evidence binding;
- serialization is stable and deterministic.

### Run

```bash
python -m unittest tests.test_master_supervisor_models -v
```

### Commit

`supervisor: add canonical incident and recovery models`

---

## Task 3 — Build the canonical evidence collector

**Refactor/modify:**
- `scripts/kesher_cloud_supervisor.py`

**Create:**
- `scripts/kesher_master_supervisor_evidence.py`
- `tests/test_master_supervisor_evidence.py`
- `tests/fixtures/kesher-supervisor/` fixture directory

### Design

Turn `kesher_cloud_supervisor.py` into a thin CLI/orchestrator. Put evidence extraction in a testable module with injected GitHub/public-verification adapters.

### Evidence sources

Collect, without writes:
- `automation-state` V5 state;
- authoritative `src/data/posts.json` on `main`;
- latest valid `kesher-video-state` artifacts;
- latest valid Short durable state;
- active/recent controller/worker workflow runs;
- failed job/step logs only when needed;
- article PR and repair PR state;
- Jules session/task evidence already available in repository/runtime;
- public article HTTP/title verification;
- exact YouTube verification for Overview/Short;
- media dimensions/signature/technical flags;
- current `direct_takeover_required` signal from V5.

### Important correction to current Cloud Supervisor

Do not mark Overview/Short false merely because the artifact contains only an ID reference. Parse the durable state and independently verify public delivery before deciding the three-link contract.

### Failure normalization

Create a function that:
1. prefers structured controller/provider errors;
2. falls back to the failing workflow step/log excerpt;
3. strips timestamps, run IDs, temp paths, request IDs and volatile line references;
4. emits a short semantic `failure_signature` plus hash.

### Tests

Fixtures must cover:
- complete delivery;
- article live, Overview missing;
- provider generating with exact source IDs;
- stale item from older slug;
- exact rejected Overview missing signature;
- YouTube uploaded but V5 unreconciled;
- Short invalid portrait;
- corrupt newest state artifact with valid older retained artifact;
- CI failure;
- unknown exception.

Test that poll-only changes do not count as progress.

### Run

```bash
python -m unittest tests.test_master_supervisor_evidence -v
```

### Commit

`supervisor: build canonical read-only evidence snapshot`

---

## Task 4 — Add a separate durable supervisor incident ledger

**Create:**
- `scripts/kesher_master_supervisor_state.py`
- `tests/test_master_supervisor_state.py`

**Do not modify:** V5 `automation-state` ownership.

### State location

Use:
- ref/branch: `automation-supervisor-state`;
- path: `.kesher-supervisor/state.json`.

### Ledger record

Per incident store:
- fingerprint;
- classification;
- strike;
- first/last seen;
- last evidence hash;
- last durable progress fingerprint;
- issued command IDs/action keys;
- active Jules session/task/PR;
- PR head SHA/CI state;
- cooldown/next eligible action;
- resolution evidence;
- human blocker details when applicable.

### Concurrency

Use optimistic writes/retries similar to the V5 state store but on the separate ref. Two concurrent Supervisor runs receiving the same evidence must converge on one ledger action.

### Tests

- first observation creates one incident;
- same evidence does not duplicate an action;
- durable progress resets strike/escalation;
- semantic failure change creates new incident;
- concurrent simulated writes converge/retry;
- resolved incident is not reopened unless new evidence/failure appears;
- supervisor state never writes `automation-state`.

### Run

```bash
python -m unittest tests.test_master_supervisor_state -v
```

### Commit

`supervisor: persist incidents on an isolated state ref`

---

## Task 5 — Build the deterministic recovery recipe engine

**Create:**
- `config/kesher-recovery-recipes.json`
- `scripts/kesher_master_supervisor_recipes.py`
- `tests/test_master_supervisor_recipes.py`

### Recipe contract

Each recipe contains:
- `id`;
- stage/class match;
- structured match predicates;
- required evidence;
- exact recovery action;
- duplicate guard;
- expected verification predicate;
- max attempts/cooldown;
- escalation on failure.

Keep code responsible for validation and complex predicates; keep stable mappings/config in JSON.

### Initial recipes

Implement and test at least:

1. `article_pending_trusted_image -> dispatch_trusted_image_same_pr`
2. `article_image_guard_failed -> recover_trusted_image_same_pr`
3. `article_ci_failed -> continue_same_pr_repair`
4. `public_article_not_visible_after_deploy -> verify_then_redeploy_if_needed`
5. `stale_provider_binding -> rebind_exact_current_source`
6. `exact_provider_generating_ids_lost -> resume_exact_provider_task`
7. `overview_rejected_missing_signature -> rebuild_exact_overview`
8. `overview_verified_not_uploaded -> retry_exact_upload`
9. `youtube_public_but_state_unreconciled -> reconcile_public_youtube`
10. `youtube_processing_running -> external_running_heartbeat`
11. `youtube_processing_failed -> retry_exact_upload_or_escalate`
12. `overview_public_short_missing -> continue_exact_short`
13. `short_wrong_aspect -> rebuild_exact_short`
14. `newest_state_corrupt -> use_newest_valid_retained_state`
15. `worker_died_exact_artifact_exists -> resume_from_exact_artifact`
16. `attempt_budget_exhausted_bookkeeping -> bounded_exact_recovery`
17. `repair_pr_conflict -> safe_rebase_same_pr`
18. `repair_ci_failed -> feed_failure_to_same_jules_session`

### Critical tests

For every recipe include a negative twin proving it refuses to act when exact identity/evidence is missing.

### Run

```bash
python -m unittest tests.test_master_supervisor_recipes -v
```

### Commit

`supervisor: add deterministic recovery recipe engine`

---

## Task 6 — Add the typed RecoveryCommand entry point to V5

**Modify:**
- `.github/workflows/kesher-content-controller.yml`
- `scripts/kesher_content_controller_stabilized.py`
- possibly the V5 runtime adapter only where required

**Create:**
- `tests/test_v5_recovery_commands.py`

### Workflow input

Add an optional `workflow_dispatch` recovery input carrying a compact JSON command or equivalent scalar fields. It contains no secrets.

Normal scheduled/event V5 behavior must remain unchanged when no command is present.

### V5 command validation

Before executing:
1. load current canonical V5 state and current exact provider state;
2. recompute authoritative source identity;
3. verify incident source/stage still matches;
4. verify referenced item/task/artifact exists and matches source;
5. verify no equivalent production worker is active;
6. verify command/action is allowlisted;
7. verify command has not already been consumed for the same evidence;
8. execute through existing V5 dispatch/recovery primitives;
9. record the production action in V5 history/state;
10. return a structured result.

If any identity has become stale, return `stale_recovery_command_noop` and do nothing.

### Tests

- valid exact rejected Overview command dispatches `rebuild` exact item;
- stale slug/hash command no-ops;
- wrong item ID no-ops/fails closed;
- duplicate command ID does not dispatch twice;
- active equivalent worker prevents duplicate dispatch;
- normal heartbeat path is unchanged;
- command cannot bypass attempt/safety rules except explicitly allowlisted bounded bookkeeping recovery;
- no V6 production dispatch.

### Run

```bash
python -m unittest tests.test_v5_recovery_commands -v
python -m unittest tests.test_v5_video_source_binding -v
python -m unittest tests.test_production_contract_v3 -v
```

### Commit

`controller: accept validated idempotent recovery commands`

---

## Task 7 — Implement the Master Supervisor decision loop in shadow mode

**Modify:**
- `scripts/kesher_cloud_supervisor.py`

**Create:**
- `scripts/kesher_master_supervisor_runtime.py`
- `tests/test_master_supervisor_runtime.py`
- `.github/workflows/kesher-master-supervisor.yml`

### Runtime algorithm

One audit performs:

1. `collect_evidence()`
2. `verify_delivery_contract()`
3. if complete -> close matching incidents and return Done
4. derive incident/failure fingerprint
5. compare to incident ledger and durable progress fingerprint
6. classify incident
7. if healthy/external-running -> record observation only
8. if known recoverable -> select deterministic recipe
9. if novel recoverable -> prepare S2 path when strike rules allow
10. if human blocker -> persist minimal blocker
11. in shadow mode -> log intended action only
12. in live mode -> execute exactly one safe action per audit
13. verify the action result on the next evidence read/audit; do not infer success from dispatch success

### Workflow triggers

Use:
- schedule heartbeat, recommended every 10 minutes;
- `workflow_run` completion events for V5/article/image/video/short/deploy/repair CI;
- manual `workflow_dispatch` with `mode=shadow|live` for controlled testing.

Use its own concurrency group, e.g. `kesher-master-supervisor`, `cancel-in-progress:false`.

### Permissions

Start minimal/read-mostly permissions. Add only the write permissions needed for supervisor-state branch and workflow dispatch when live S1 is enabled. Do not grant secret-management/admin permissions.

### Tests

- shadow never dispatches or changes production;
- same incident twice in same evidence state produces no duplicate intended action;
- external-running heartbeat respects 90-minute ceiling;
- changed durable progress resets escalation;
- `direct_takeover_required` becomes a machine-owned action path, not a report-only terminal;
- one safe action maximum per audit.

### Run

```bash
python -m unittest tests.test_master_supervisor_runtime -v
```

### Commit

`supervisor: run autonomous decision loop in shadow mode`

---

## Task 8 — Make S1 deterministic recovery live

**Modify:**
- `scripts/kesher_master_supervisor_runtime.py`
- `.github/workflows/kesher-master-supervisor.yml`
- supervisor contract/config as needed

### Behavior

When `mode=live-s1` and the incident is `known_recoverable`:
- issue exactly one validated RecoveryCommand to V5;
- store command ID/action key in supervisor ledger before/atomically with dispatch intent;
- observe the resulting V5/worker run;
- verify durable progress independently;
- continue automatically on subsequent audits;
- if same failure persists to S2 threshold, do not repeat unlimited S1 actions.

### Tests

- dispatch failure can be retried without double production action;
- GitHub returns success but V5 no-ops stale command -> Supervisor reclassifies from fresh evidence;
- command consumed + workflow died -> exact recovery resumes without duplicate generation;
- #829 fixture completes through rebuild -> upload -> short continuation path.

### Gate

Do not enable S2 automatically yet. Run S1 with shadow comparison until the chaos/offline tests for deterministic recipes are clean.

### Commit

`supervisor: enable live deterministic S1 recovery`

---

## Task 9 — Build a Jules repair broker for S2

**Reuse/refactor where possible:**
- existing Jules article runner/session utilities;
- `scripts/jules_article_diagnostics.py` patterns;
- existing GitHub/Jules credentials and session persistence.

**Create:**
- `scripts/kesher_master_supervisor_jules.py`
- `tests/test_master_supervisor_jules.py`
- `.github/prompts/jules-kesher-incident-repair.md` if a dedicated reusable repair prompt is needed.

### Incident package

Produce a deterministic package with:
- incident fingerprint/strike;
- authoritative source identity;
- failing stage/workflow/job/step;
- concise normalized log evidence;
- relevant state excerpt;
- previous recovery actions;
- suspected scope, if known;
- exact Definition of Done;
- required test commands;
- immutable constraints: same incident/session/PR, no duplicate content/provider generation, no security weakening.

### Session rules

- one active Jules session per incident fingerprint;
- persist session/task/PR identity in supervisor ledger;
- continue the same session with new CI evidence;
- do not open a second repair PR while the first is active;
- configurable hard budget, initially conservative (for example one active session and bounded retries within it).

### Tests

- first S2 creates one session/package;
- repeated audit reuses it;
- changed failure signature can start a new incident;
- CI failure feeds back to same session;
- Jules timeout/API error does not create duplicates;
- missing exact source evidence blocks Jules content-generation instructions.

### Run

```bash
python -m unittest tests.test_master_supervisor_jules -v
```

### Commit

`supervisor: broker one Jules repair session per incident`

---

## Task 10 — Implement autonomous repair PR + CI loop for S3

**Create/refactor:**
- `scripts/kesher_master_supervisor_repair.py`
- `tests/test_master_supervisor_repair.py`

**Modify:**
- Master runtime/Jules broker as needed.

### S3 loop

When same failure reaches S3 with no durable progress:

1. locate the existing incident repair branch/PR;
2. inspect changed files and diff scope;
3. obtain CI/check conclusions;
4. if CI failed, extract only relevant failed-step evidence and feed it to the same Jules session;
5. if PR has a safe merge conflict, rebase/update the same repair branch using repository-safe mechanics;
6. rerun required tests/checks;
7. enforce scope allowlist/denylist;
8. merge only when all required gates are green and current main has not invalidated the fix;
9. return to V5 production via validated recovery/normal heartbeat;
10. verify public Article + Overview + Short;
11. mark incident resolved only after delivery verification.

### Allowlist/denylist

Initial autonomous merge scope should be narrow:
- allow: `scripts/kesher_*`, targeted workflow/config/tests associated with the incident;
- deny by default: secrets, auth credential storage, billing, unrelated site content, broad dependency upgrades, security controls.

Any denied-scope change becomes a human blocker or requires a narrower Jules revision; it is not auto-merged.

### Tests

- green safe-scope PR -> merge action selected;
- failing CI -> no merge, same Jules session gets evidence;
- unrelated/broad diff -> no auto-merge;
- stale PR head after main changes -> re-evaluate before merge;
- conflict that can be safely rebased -> same PR continues;
- conflict with semantic ambiguity -> human blocker, no guessing;
- after merge, Supervisor resumes original incident instead of stopping at “merged.”

### Run

```bash
python -m unittest tests.test_master_supervisor_repair -v
```

### Commit

`supervisor: close the S3 repair and resume loop`

---

## Task 11 — Add Master Supervisor liveness watchdog without recursion

**Create:**
- `.github/workflows/kesher-master-supervisor-watchdog.yml`
- `scripts/kesher_master_supervisor_watchdog.py`
- `tests/test_master_supervisor_watchdog.py`

### Scope

The liveness watchdog may only:
- inspect the latest successful Master audit;
- rerun the Master once if stale;
- persist/update one supervisor-health incident after repeated misses;
- leave V5 heartbeat running.

It may not:
- diagnose content incidents;
- dispatch article/video/short production directly;
- call Jules;
- write V5 production state.

### Tests

- fresh supervisor -> no action;
- stale supervisor -> one rerun;
- repeated checks do not dispatch multiple simultaneous Master runs;
- repeated supervisor failure produces one health incident;
- watchdog never becomes a third recovery controller.

### Commit

`supervisor: add bounded liveness circuit breaker`

---

## Task 12 — Build the offline Hybrid Chaos harness

**Create:**
- `scripts/kesher_master_supervisor_chaos.py`
- `tests/test_master_supervisor_chaos.py`
- `tests/fixtures/kesher-supervisor/scenarios/*.json`

### Harness modes

`--mode offline`:
- all GitHub/provider/public services mocked;
- safe in CI;
- deterministic.

`--mode replay`:
- consumes captured/historical evidence snapshots;
- no writes/dispatches;
- validates decisions.

`--mode controlled-live`:
- disabled by default;
- requires explicit workflow input/environment flag;
- may operate only on allowlisted test/replay incidents and existing exact identities;
- no intentional duplicate publication/generation.

### Scenario matrix

Implement at least these 17 scenarios:

| ID | Fault | Expected autonomous outcome |
|---|---|---|
| C01 | exact NotebookLM task running but V5 lost IDs | recover/bind exact IDs; no regeneration |
| C02 | stale provider item from old slug is newest | ignore stale item; bind current source only |
| C03 | exact Overview rejected: full-screen signature missing | exact Remotion rebuild |
| C04 | YouTube upload succeeded but V5 state missed it | reconcile exact public upload |
| C05 | YouTube processing genuinely running <90m | heartbeat/wait; no strike inflation |
| C06 | YouTube processing failed | retry exact safe upload or escalate |
| C07 | Short exists but wrong aspect ratio | exact Short rebuild to verified 9:16 |
| C08 | trusted article image missing | same-PR trusted image recovery |
| C09 | article PR CI failure | same-PR repair; Jules only after S1 |
| C10 | active repair PR conflicts with main | safe same-PR rebase or fail closed |
| C11 | Jules API/session transient failure | reuse same incident/session identity; bounded retry |
| C12 | Jules fix lands but CI fails | send failed checks to same Jules session |
| C13 | production worker is killed mid-action | resume exact persisted task/artifact |
| C14 | two Master audits run concurrently | exactly one action issued |
| C15 | newest video-state artifact is corrupt | use newest trustworthy retained artifact; no fresh generation |
| C16 | attempts exhausted due bookkeeping bug but exact recovery exists | bounded one-time exact recovery |
| C17 | unknown new failure signature | collect package -> S2 Jules -> CI -> S3 completion |

Add compound tests:
- C02 + C03 together;
- C13 + concurrent C14;
- C17 followed by a new distinct failure signature to prove incident reset.

### Required assertion for every scenario

`Detect -> Diagnose -> Decide -> Act -> Verify -> Continue`

Also assert:
- duplicate task/artifact/upload count = 0;
- unsafe action count = 0;
- authoritative source remains stable;
- incident closes only after independent verification.

### Run

```bash
python -m unittest tests.test_master_supervisor_chaos -v
```

### Commit

`test: add autonomous recovery chaos matrix`

---

## Task 13 — Add historical replay corpus and decision-parity gate

**Create:**
- `tests/fixtures/kesher-supervisor/replay/`
- `scripts/kesher_supervisor_capture_evidence.py` or a safe redacted capture utility
- replay tests in `tests/test_master_supervisor_replay.py`

### Corpus

Capture/redact representative historical incidents already seen in production, including:
- stale source binding;
- image guard failure;
- provider exhaustion;
- rejected Overview signature;
- upload reconciliation issues;
- article/Jules stalls;
- successful healthy cycle.

Never store credentials/tokens/cookies in fixtures.

### Gate

Require:
- zero unsafe decisions;
- zero duplicate-generation recommendations;
- correct source identity selection for every replay;
- expected recovery action/classification for known incidents;
- unknown incidents route to evidence/Jules, not guessed production actions.

### Commit

`test: replay historical Kesher incidents against Master Supervisor`

---

## Task 14 — Add observability that reports outcomes, not requests for help

**Modify/Create:**
- Master workflow summary output;
- optionally one durable JSON audit artifact per run with bounded retention.

### Required report fields

For each audit:
- cycle/slug;
- Article URL/status;
- Overview URL/status;
- Short URL/status;
- incident fingerprint if any;
- classification/strike;
- action actually executed;
- verification result;
- Jules session/PR only when active;
- next deterministic action;
- human blocker only when genuine.

Use the user-facing structure already established:

```text
סטטוס דיווח — <date/slug>
מאמר — ...
וידאו — ...
שורט — ...

זיהיתי תקלה — ...
ביצעתי — ...
נלמד — ...
עודכן ב-Controller/Jules — ...
דייקתי למניעת הישנות — ...
הצעד הבא — ... | Done
```

The Master must not output “direct takeover required” as the final action when safe work is available; it must perform the takeover first.

### Tests

Snapshot/test rendering for healthy, recovered, Jules-active and human-blocker states.

### Commit

`supervisor: report verified outcomes and next deterministic action`

---

## Task 15 — Progressive rollout gates

Rollout is evidence-based, not time-estimate-based.

### Gate A — offline

Required:
- all new unit tests green;
- all 17 chaos scenarios green;
- all existing V5/contract/watchdog/source-binding suites green;
- no changes to production behavior yet.

Recommended command bundle:

```bash
python -m unittest \
  tests.test_production_contract_v3 \
  tests.test_v5_video_source_binding \
  tests.test_v5_recovery_commands \
  tests.test_master_supervisor_models \
  tests.test_master_supervisor_evidence \
  tests.test_master_supervisor_state \
  tests.test_master_supervisor_recipes \
  tests.test_master_supervisor_runtime \
  tests.test_master_supervisor_jules \
  tests.test_master_supervisor_repair \
  tests.test_master_supervisor_watchdog \
  tests.test_master_supervisor_chaos \
  tests.test_master_supervisor_replay -v
```

Also run repository CI/build tests required by the changed files.

### Gate B — shadow production

Master runs on real evidence but cannot dispatch recovery or Jules.

Exit criteria:
- decisions recorded for multiple real/historical cycles;
- zero unsafe/ambiguous actions proposed as executable;
- no mismatch between Master authoritative source and V5 authoritative source;
- no false duplicate-generation recommendation.

### Gate C — live S1 only

Enable deterministic recipes/RecoveryCommand only.

Exit criteria:
- known incidents recover through V5 without human/ChatGPT intervention;
- duplicate counts remain zero;
- stale commands no-op correctly;
- normal healthy pipeline behavior remains unchanged.

### Gate D — live S2

Enable automatic Jules repair session creation/continuation.

Exit criteria:
- one Jules identity per incident;
- CI failures return to same session;
- no repeated credit-consuming sessions from heartbeat polls;
- fixed code returns automatically to V5 recovery.

### Gate E — live S3

Enable safe-scope repair PR completion/merge/recovery.

Exit criteria:
- safe repair incidents reach public delivery without manual continuation;
- broad/security-sensitive diffs fail closed;
- merge is impossible unless gates are green;
- post-merge chain resumes automatically.

### Gate F — default autonomous mode

Switch Master default from shadow to autonomous safe mode. Keep a one-switch rollback to shadow that does not disable V5.

---

## Task 16 — Simplify legacy intervention logic only after proof

**Do not do this early.** The current Three-Strike and watchdog mechanisms remain as compatibility/signal producers while the Master proves itself.

After Gate E/F success, review:
- `scripts/kesher_three_strike_runtime.py`
- `scripts/kesher_intervention_policy.py`
- `scripts/kesher_content_watchdog.py`
- `scripts/kesher_cloud_supervisor.py`

### Goal

Remove duplicated decision ownership while preserving fast local V5 recovery. Preferred final split:
- V5 watchdog: short-horizon stage recovery;
- Master: cross-stage incident diagnosis/escalation/repair;
- liveness watchdog: Master heartbeat only.

Add migration tests before deleting any old state field or behavior.

### Commit

`refactor: consolidate Kesher recovery ownership after Master rollout`

---

# Cross-cutting invariants to enforce in every PR

1. V5 is the only production state writer.
2. V6 is shadow only.
3. Master writes only supervisor ledger and dispatches validated commands.
4. One incident fingerprint -> at most one active recovery action/Jules session/repair PR at a time.
5. Exact reusable provider task/artifact beats regeneration.
6. Upload uses exact verified item identity.
7. Article/image repair reuses the same PR when possible.
8. A successful dispatch is not success; independent evidence verification is required.
9. Poll/log freshness is not durable progress.
10. NotebookLM/YouTube externally running exception is bounded to 90 minutes with evidence.
11. No security-gate bypass, no secret exposure, no payment, no irreversible external action without explicit approval.
12. “Blocked” is actionable unless a genuine human blocker is proven.

# Cost/credit controls

The architecture minimizes AI/provider spending by design:

- Master heartbeat/evidence/recipe logic is deterministic Python/GitHub logic.
- Jules is called only after S1 cannot resolve the same incident.
- one Jules session per fingerprint, reused for CI feedback;
- provider generation is forbidden when an exact reusable task/artifact exists;
- NotebookLM generation budget is identity-bound;
- YouTube uploads are exactly-once/reconciled before retry;
- healthy audits perform no AI call.

Add counters to supervisor reports so actual usage can be measured rather than guessed:
- Jules sessions/tasks per incident;
- provider generations per source hash;
- uploads per item;
- supervisor audits/actions;
- deterministic recoveries versus AI repairs.

# Definition of Done for the entire project

The project is complete only when all of the following are demonstrated:

- the Master Supervisor can run continuously without editing V5 production state directly;
- all chaos scenarios pass the full Detect/Diagnose/Decide/Act/Verify/Continue chain;
- known incidents are recovered deterministically;
- a novel code defect can progress automatically through Jules -> PR -> CI -> merge -> V5 resume -> verified delivery within allowed scope;
- concurrent runs cannot create duplicate content, provider generations, Jules sessions, PRs or uploads;
- Master failure has a bounded liveness recovery path without an infinite hierarchy of controllers;
- Article + Overview + Short completion remains the only final Done state;
- normal operation requires no Yaniv/ChatGPT intervention;
- Yaniv is contacted only when the system can name a concrete true human blocker and the minimum action required.

# Execution order / PR slicing

Recommended PR sequence:

1. **Contract + models**
2. **Evidence collector + supervisor ledger**
3. **Recipe engine**
4. **V5 RecoveryCommand boundary**
5. **Master shadow workflow/runtime**
6. **Live S1 deterministic recovery**
7. **S2 Jules broker**
8. **S3 repair/CI/merge loop**
9. **Liveness watchdog**
10. **Chaos/replay corpus + rollout switches**
11. **Legacy simplification after production proof**

Each PR must be independently reversible and must not require the next PR to keep existing V5 production working.
