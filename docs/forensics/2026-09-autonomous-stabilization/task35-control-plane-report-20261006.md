# Task 3.5 — control-plane convergence (repository implementation)

Starting HEAD: `1bf7bd8e486aed70c0619b39f32eef774d565d33`.
Worktree: `/Users/ninja/Documents/Kesher-worktrees/autonomous-stabilization-20260917`.
Branch: `codex/kesher-autonomous-stabilization-20260917`.
The ending implementation commit is the commit containing this report; its exact
SHA and independently verified remote SHA are returned after normal push.

The six protected resources remain github, jules, notebooklm, youtube,
cloudflare and image_provider. No ChatGPT resource, controller, mutation proxy,
repair dispatcher, credential or schedule was added. No production effect was
performed. The native Task 3 ruleset implementation and Git-ref exclusion code
are byte-for-byte unchanged. Existing workflow roles, capabilities, resource
scopes, credentials, dispatches and registration bindings remain unchanged.
The policy adds an explicit actor manifest and recertifies/adds affected reviewed
call-chain inputs. Unknown actor policy cannot pass installed-code inventory.

## Audit and exact control paths

`task35-control-plane-inventory-20261006.json` records all 74 reviewed workflow
rows, their triggers/capabilities/dispatch edges/full reviewed call chains,
retained registration identities (including dynamic authority), and 187 source
references with exact path/function/line. The reference scanner is a supporting
index, never an authority classifier or proof that no external actor exists.
Explicit native resource fences remain required for old revisions and external
scripts/tools. No live registrations, task account or Jules sessions were read.

Controller V5 writers converge on
`scripts/kesher_content_controller.py:GitHubClient.save_controller_state`:

- `scripts/kesher_content_controller_v5.py:V5Controller.tick`;
- `scripts/kesher_content_controller_v5_runtime_base.py:RuntimeV5Controller.tick`
  and `_media_watchdog_preflight`;
- `scripts/kesher_content_controller_v5_runtime.py:RuntimeV5Controller.tick`;
- `scripts/kesher_content_controller_stabilized.py:StabilizedRuntimeV5Controller`
  quality/rejected-media/targeted recovery paths and `tick`;
- `scripts/kesher_three_strike_runtime.py:ThreeStrikeMediaInterventionMixin`
  `_direct_takeover` and `_media_watchdog_preflight`;
- inherited core/V3/V4 controllers and
  `scripts/kesher_content_controller_entry.py` child-adoption helpers.

The read/load/save guards and V5 state reconstruction guard reject Schema 6,
any handover key, and any Git exclusion key before reconstruction or mutation.
The resource-side legacy CAS/write guard protects against stale old-code callers;
local code cannot revoke a process's already-held credential.

The only canonical controller writer is
`scripts/kesher_runtime/controller_entry.py:execute_tick` → `authority.require_live`
→ `handover.require_authority` → `GitHubStateStore.save` (exact state CAS).
`controller.run_tick` is a lower-level reducer/store helper, not a separate
production admission route. Canonical worker writes enter through
`worker_entry`/`WorkerContext` exact claim/ownership and resource command gates.
The resource control guard restricts `controller_cas` to
`kesher-canonical-controller`; predecessor principals cannot impersonate it.
`scripts/kesher_content_controller_v6_runtime.py` is a shadow/manual diagnostic
using an isolated in-memory intervention state; it has no production writer.
The canonical workflow remains inert; no activation was performed.

Jules creation/continuation/acceptance paths found:

- canonical `scripts/kesher_runtime/article_worker.py:run_article` →
  `jules.acquire_session` → `Jules.create` (durable exact creation intent);
  `article_quiescence.assert_article_quiescent` rereads exact predecessor/output
  sessions before normalization/image/validation/merge effects;
- legacy `scripts/jules_article_runner_core.py:create_session`, `acquire_session`,
  `send_message`, `poll` (including `approvePlan`); runner/V3/V4 wrappers invoke it;
- `scripts/kesher_content_controller_v5.py:GitHubClient.nudge_article_session`;
- `scripts/jules_video_reviewer.py:create_session`/`wait_for_message`, plus V3 wrapper;
- `scripts/kesher_master_supervisor_live.py:JulesRecoveryClient.acquire_or_continue`
  (existing-session sendMessage versus new session POST are separate branches);
- `.github/scripts/kesher_task_supervisor.py:create_session`/`send_to_session`/
  `ensure_session`, runtime/V2/V3 deduplicated recovery continuations;
- `.github/scripts/article-pr-controller.py:send_jules_repair` and V3 equivalent;
- inline Jules daily/weekly/nightly workflow creators and
  `.github/scripts/watch-jules-session.py` continuation/approval;
- legacy article PR controllers, task supervisor `process_pr`, inline
  `auto-merge-jules-audit-prs.yml`, and master supervisor
  `try_finalize_recovery_pr` can accept/merge or cause CI/deployment dispatch.
  Their workflow fences/retirement are preserved. Candidate-controlled legacy
  verification is not promoted to canonical certification.

The inventory also records PR/workflow_run/repository_dispatch/workflow_dispatch
chains, queued/rerun paths, targeted-media dispatcher, emergency bridges and
infrastructure dispatch edges. Workflow labels do not establish safe authority.
The GitHub master workflow is retired by its impossible sentinel. The external
ChatGPT **Master Active Supervisor** is a distinct predecessor actor with
GitHub/Jules mutation paths, not that workflow and not a seventh resource.

Observed origin/main: `db31dfdbc6f5539bc0b743db88990b4d7186a60b`.
Six relevant source/workflow drift paths were recorded: preexisting Native Fence
v2/Task 3 deltas absent on main. No reconciliation, merge or main integration was
performed; this audit does not claim live workflow/provider exclusivity.

## Why hourly rescue can repeat, and the durable prevention layer

The supplied external task still describes independent V5 → Jules → Direct
escalation while V6 is shadow. Repository retirement does not revoke its tools,
old checkouts or already-running sessions. Legacy escalation budgets are scoped
to their incident/session/controller cycle, so an hourly supervisor can encounter
new symptoms and create a new rescue context. A finite provider-generation budget
alone does not constrain a separate external control plane.

A reproduced canonical defect also permitted a new failure label to open another
recovery operation after an exact target/stage had already exhausted its budget.
The new terminal circuit consumes the existing durable incident ledger: an
unresolved incident prevents further recovery commands for that exact
identity/stage even after restart or changing symptoms. Independent media targets
remain eligible; fresh public verification remains observable. There is no
budget reset, receipt deletion, global generation halt or new repair pipeline.
A trusted reviewed repair must explicitly resolve the terminal incident before
that target/stage resumes. A new exact deployment revision retains its own budget
when the prior incident has a proved input binding; unbound historical incidents
remain fail-closed. Healthy publication can still establish completion.

The machine inventory contains the required 12-class failure matrix, including
owner, deterministic/restart/finite handling, prevention and regression suites.
Existing 3 generation attempts, single uncertain mutation intent, exact session
adoption, finite poll deadlines, worker acceptance watchdogs, exact-head merge,
public identity proof and duplicate suppression are preserved. Terminal repairs
belong in the owning controller/worker/workflow/prompt/test under independent
review, never in an hourly unadmitted Direct Takeover.

This is a structural diagnosis supported by code and regressions. The repeated
hourly stalls were supplied by the user; current external task execution logs and
production/provider state were intentionally not queried. No exact diagnosis of
an individual live stall or claim of restored production health is made.

## External operator and native prerequisite — deliberately not satisfied here

`ControlPlaneConvergence` is an administrator-installed trusted dependency, not
client JSON or an environment flag. `live_cutover.build_runtime` requires it.
Every cutover invocation checks all six resources and the fresh control-plane
readback before its first effect. Final exclusion and each trusted live authority
observation also require it. Stable actor/task/resource/admission identity is included in the existing
handover authority basis. Full lifecycle/session facts are independently validated
on every read, with their own receipt digest. Fresh poll timestamps, suspended-to-
observer conversion and removal of already denied sessions do not falsely
invalidate authority; renewed legacy mutation or unknown sessions still refuse.

The administrator must independently identify the exact task/account ID and
ALL KESHER external scheduler/actor paths, then choose one enforceable state:

1. **Suspended:** suspend the exact external Master Active Supervisor and its
   legacy rescue paths before cutover; independently read back the suspension.
2. **Observer:** convert it to read-only Schema-6 observation/escalation, remove
   V5/Jules/Direct mutations and verify the effective tool/account restriction.
3. **Resource restricted:** retain the external actor only when BOTH actual
   GitHub and Jules native boundaries already enforce this same exact
   repo/resource/epoch/owner policy. Suspension/prompt edits alone do not establish
   native exclusion. Without both fences this state refuses even bootstrap.

In every case direct takeover is disabled and GitHub/Jules access is bound to
canonical admission. After handover, a later observer can report exact canonical
incidents/public evidence but cannot create/continue Jules work, dispatch/rerun
mutating workflows, change state or merge outside the admitted command boundary.

The independent observer must read current service/operator state on EVERY call,
within 60 seconds, for the independently installed task ID; incomplete/unknown
actors refuse. It must distinguish complete predecessor Jules grants/sessions
from future canonical command-bound creation, and prove BOTH continuation and
repository access denied for every predecessor session before exclusivity.
A completed Actions run, an empty list from one API key, a completed Jules session,
or a changed task prompt is not this proof. Unknown or unresolved Jules authority
blocks admission. No unsupported cancel API is invented.

`task35-operator-readback-template-20261006.json` intentionally contains UNRESOLVED
identities, incomplete inventories and unknown permissions. It is a fail-closed
schema example, NEVER live evidence. Filling a file cannot implement the trusted
observer. The repository has no ability to edit that ChatGPT task.

Task 4 still requires actual administrator-controlled observers/native enforcement
for Jules and the other four provider resources, exact complete credentials/grants/
sessions/in-flight exclusion, infrastructure separation, independently approved
current-main/registration/review bindings and capability-sealing custody. The
existing production cutover runbook remains the operational base; this report adds
the control-plane prerequisite and does not execute that runbook. The prior
resume also records that incident-bound Jules repair is unconnected: the runtime
emits durable repair_required incidents, not an installed trusted repair executor.
This task does not fabricate that executor or route incidents to legacy Jules;
its later integration must obey the same canonical admission/trusted evaluator
boundary. The original stabilization Goal remains unfinished.

## Validation and preserved evidence

Independent review identified two Important edge cases: a prior terminal
deployment incident blocked a new exact main revision, and lifecycle facts
incorrectly froze permitted later observer conversion. Both received observed
RED regressions and GREEN fixes. Complete/focused/broader validation was rerun
after those source changes. The two minor audit observations were resolved by
adding transitive policy/Jules dependency pins and verifying the completed
12-class machine matrix. No finding is deferred; no second review was claimed.

RED before implementation: missing operator prerequisite did not block the first
resource effect; exhausted exact media incident could open a new recovery command
under a new failure label. Both failures were observed. A third RED demonstrated
undeclared supervisor authority fields being accepted; strict readback shape now
refuses them before any effect.

- New convergence regressions: 13 tests, OK.
- Focused convergence/ruleset/Git exclusion/drain/controller/Jules/attempt/legacy
  suites: 133 tests, OK (final rerun recorded in checkpoint).
- Broader authority topology/exclusion/cutover/current authority/handover/Git
  handover/authority digest suites: 141 tests, OK.
- Complete Python discovery: 1239 tests, OK, no skips.
- Call-chain mismatches: 0; definition mismatches: 0; `git diff --check`: PASS.
- Existing authority metadata and native Task 3 runtime bytes: unchanged.

Python 3.14 emits existing InvocationJournal SQLite ResourceWarnings. The complete
suite also intentionally creates a duplicate ZIP member to test fail-closed
archive handling. Neither warning was suppressed or turned into a weakened gate.
No frontend/workflow/provider implementation changed, so build/browser/production
validation was not performed or inferred.

Closed 5.2 remains unchanged: Overview `OPwpR3ReV0k` exact archive contradicts the
claimed source/kind; Short `TKAwQMzvP6U` lacks exact producer lineage; historical
upload capability `5QW2YCqMG6Q` stays quarantined until trusted coordinated sealing.
No historical evidence file, migration logic or quarantine was replaced.

`production_state_written=false`, `production_activated=false`,
`public_completion_inferred=false`. No live ruleset/workflow/run/session/provider/
credential/production mutation, no PR, no merge and no Task 4 work.
