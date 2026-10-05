# KESHER Native Fence v2 — Design

Date: 2026-10-05
Repository: `yanivsa/kesher-website`
Branch: `codex/kesher-autonomous-stabilization-20260917`
Baseline checkpoint: `15297dde7acf8ee9a4507f2c87435a050900ba71`

## 1. Purpose

Complete the blocked production authority handover without weakening the existing fail-closed, epoch, CAS, identity, restart, and nine-phase handover invariants.

The current implementation is intentionally blocked because the live five external provider ports are `PrerequisitePort` refusals and the GitHub boundary still requires native predecessor-authority exclusion. The goal of Native Fence v2 is to replace impossible or obsolete provider assumptions with native, independently verifiable controls that the providers actually expose, while preserving the existing security model wherever it is implementable.

This design does not activate production, perform cutover, or infer public completion. It defines the trusted boundary that must exist before those actions are admitted.

## 2. Non-negotiable invariants

The following existing properties remain unchanged:

- Production authority is fail-closed.
- `automation-state` remains the canonical journal/state authority.
- Git ownership is anchored with exact ref CAS and the reviewed main SHA.
- A cutover epoch has a single accepted owner.
- The nine handover phases remain restart-safe and monotonic.
- Uncertain external effects are observed before any retry; they are never blindly repeated.
- Provider/publication effects require an accepted, current canonical command.
- The cutover runner cannot submit evidence, provider credentials, or mutable resource selections.
- Independent code/policy/evidence approval remains outside candidate-controlled assertions.
- Closed 5.2 evidence and the three quarantines remain unchanged.
- Missing or contradictory native proof blocks admission.

## 3. Scope

Native Fence v2 covers six protected resources:

1. `github`
2. `jules`
3. `notebooklm`
4. `youtube`
5. `cloudflare`
6. `image_provider`

It also covers the 19 infrastructure separation proofs required by the current authority topology.

It does not redesign the content controller, media workers, publication identity model, 5.2 evidence findings, finite-attempt state machine, or post-cutover public verification.

## 4. Architectural decision

Keep the existing `ExclusionFence`, `GitExclusionEpoch`, `GuardedGitHub`, OIDC-authenticated `POST /v1/cutover/step`, durable invocation denial ledger, and nine-phase coordinator.

Replace only the provider-specific assumptions that currently make live exclusion impossible:

- Implement real native adapters where a provider exposes sufficient inventory, revocation/retirement, settlement, and readback semantics.
- Where a provider does not expose a complete historical authority inventory, use a narrower resource-enforced boundary that is independently verifiable and prevents predecessor authority from producing protected effects.
- Never represent a missing provider capability as successful proof.
- Never accept JSON receipts, local flags, or workflow disablement as substitutes for native enforcement.

## 5. GitHub boundary

### 5.1 Existing controls retained

Retain:

- GraphQL multi-ref CAS on `main` and `automation-state`.
- Durable workflow disable/cancel/drain intents and readbacks.
- Exact registration reconciliation.
- Unknown/rebound registration fail-closed behavior.
- Exact run-attempt terminal proof.
- GitHub gateway operations restricted by `CONTROL_GATE`.

### 5.2 Resource-enforced direct-write denial

Add an independently administered repository ruleset protecting at least:

- `refs/heads/main`
- `refs/heads/automation-state`

The ruleset must restrict updates and destructive ref operations. Only the canonical trusted GitHub App/gateway principal may receive the minimum bypass required for the reviewed guarded operations. Human/admin bypass must not silently invalidate the proof; any remaining bypass principal is part of the actor inventory and must be explicitly approved or removed for the cutover epoch.

The GitHub exclusion adapter must read back the effective ruleset/actor configuration and bind that readback to the epoch, reviewed main, repository ID, and canonical App identity.

### 5.3 Retirement targets

The current 114-registration inventory is authoritative only for the checkpoint and must be refreshed before cutover. The current policy contains 80 retirement targets. Every target requires:

- durable disable intent;
- native `disabled_manually` readback where applicable;
- cancellation of active attempts;
- terminal exact-attempt proof;
- two fresh complete inventories showing no active target attempt;
- rejection if the workflow is re-enabled or a new/rebound registration appears.

### 5.4 Credentials

Workflow disablement is not credential revocation. The final GitHub proof must account for effective write authority from installed Apps, deploy keys, relevant PAT/OAuth/SSH paths that can mutate protected refs, and the canonical gateway principal.

The design may use server-side repository rules to deny protected-ref mutation instead of attempting to enumerate every copied historical bearer token, provided the denial is native, persistent, independently readable, and applies regardless of the bearer used.

## 6. Jules boundary

### 6.1 Protected capabilities

Protect:

- session creation;
- session continuation;
- repository access for `sources/github/yanivsa/kesher-website`.

### 6.2 Native adapter requirements

The Jules adapter must:

- enumerate all repository-capable sessions visible to the administered Jules account/grant;
- inspect exact session source/repository context;
- classify nonterminal states as blocking;
- terminate/delete sessions using the provider-supported operation when available;
- verify subsequent native readback showing no surviving repository-capable nonterminal session;
- rotate or retire predecessor Jules API credentials/grants where supported;
- verify at the GitHub boundary that the retired Jules principal cannot mutate protected refs even if a remote Jules process survives.

Session deletion alone is insufficient if repository write authority remains. The GitHub ruleset therefore acts as the final protected-effect boundary for stale Jules actors.

## 7. YouTube boundary

### 7.1 Updated capability model

Do not treat a resumable-upload session URI as permanently independent of OAuth authority if subsequent upload requests still require OAuth bearer authorization.

The adapter must bind the exact channel and OAuth project, then:

- enumerate known canonical/legacy grants available through the administered OAuth account/project;
- revoke predecessor OAuth authorization;
- verify predecessor credentials can no longer perform channel mutation;
- inspect known in-flight/resumable operations and wait for or reject ambiguous provider state;
- provision a distinct canonical credential behind `require_resource_command`;
- independently read the exact target channel identity before and after retirement.

The proof requirement is effective inability of predecessor authority to mutate the protected channel, not enumeration of every upload URI ever issued when the provider does not expose such an inventory.

## 8. Cloudflare boundary

The reviewed account is `95ba6a62314a0682d0711050ba9c3445`; Pages project is `kesher-website`.

Current account readback shows one accepted account member with Super Administrator authority. Before cutover this fact must be refreshed.

The Cloudflare adapter must:

- enumerate effective account members and integrations relevant to Pages/Workers/config mutation;
- enumerate account-owned tokens where the administrative API permits it;
- settle active KESHER deployment work;
- retire predecessor credentials/integrations that can mutate `kesher-website`;
- isolate the canonical credential to the exact required KESHER resources and operations;
- read back effective permissions and denied/non-target resources;
- prove that infrastructure workflows using Cloudflare credentials are disjoint from protected KESHER resource IDs, or classify them as retirement targets.

Sensitive token values never leave trusted service custody and never enter evidence or chat output.

## 9. Image-provider boundary

Separate read-only acquisition providers from mutation-capable generation providers.

For each provider that can create protected generated assets or otherwise cause external mutable effects:

- identify the exact provider/project/account;
- inventory active canonical and predecessor credentials that are administratively visible;
- rotate/retire predecessor credentials;
- settle provider jobs where job APIs exist;
- require canonical commands for new generation;
- verify effective denial of predecessor authority on the protected provider/project.

Read-only public stock-search credentials do not need to be modeled as protected mutation authority unless they can create or alter protected external state. They remain subject to normal secret hygiene and dependency review.

## 10. NotebookLM boundary

NotebookLM consumer access is the hardest resource because the existing workflow uses consumer-account/browser-style credentials and does not currently have a complete provider IAM/administrative API matching the exclusion contract.

### 10.1 Short-term cutover design

Treat legacy NotebookLM consumer access as quarantined legacy authority:

- enumerate every known locally stored/browser/runtime credential source used by KESHER;
- stop and retire all known legacy processes/runners that can use those credentials;
- rotate/invalidate the available consumer authentication material;
- require no nonterminal known generation operation;
- enforce at the canonical KESHER state/gateway boundary that no new NotebookLM operation is admitted until the handover is VERIFIED and a canonical command is claimed;
- fail closed if credential invalidation or known-operation settlement cannot be independently confirmed.

This is not represented as provider IAM proof.

### 10.2 Long-term migration option

Evaluate migration of canonical notebook generation to a provider edition exposing administrable API/IAM boundaries, such as Gemini/Notebook enterprise capability, as a separate post-stabilization project. This is not required to complete the immediate stabilization unless the short-term consumer credential boundary cannot be proven safely.

## 11. Infrastructure separation proofs

Retain the existing 19-proof matrix and validator structure. Do not weaken `_separated()` merely to make proofs pass.

For the 16 OCI-bearing workflows, complete the credential-to-service/resource mapping from actual OCI principal/policy/host credentials. Each proof must bind exact workflow ID/path/definition hash and independently demonstrate disjoint effective resource IDs from the six protected KESHER resource IDs.

Where actual native readback shows a workflow can mutate a protected KESHER resource, classify it as retirement authority instead of infrastructure.

## 12. Gateway hosting

Do not rewrite the trusted gateway as a Cloudflare Worker during stabilization.

Keep the existing Python service contract:

- loopback-bound trusted service;
- TLS ingress in front of it;
- GitHub Actions OIDC verification performed by the service itself;
- persistent atomic SQLite invocation ledger;
- administrator-installed `trusted_kesher_cutover:build` factory;
- native provider credentials held only by the service/admin layer.

A Cloudflare Worker may later serve as ingress/proxy, but it must not become a second authority store and is not required for cutover.

## 13. Data flow

For each authenticated cutover invocation:

1. Validate exact epoch and reviewed revision.
2. Re-run independent installed review checks.
3. Verify GitHub Actions OIDC and native live run/main identity.
4. Claim the invocation in the durable denial ledger before any effect.
5. Refresh all six resource inventories.
6. Refresh all 19 infrastructure separation proofs.
7. Refuse competing or incomplete protection.
8. Perform at most one resource exclusion/bootstrap effect or one coordinator phase transition.
9. On the next authenticated invocation, read back the prior effect before advancing.
10. Never activate production merely because all HTTP calls returned success; the canonical journal and native readbacks decide admission.

## 14. Main drift and certification

The checkpoint reviewed main `1e009e1b990dc4a63b791e6060aa9718beae6781`. Current main has advanced and must be refreshed before certification.

Any new main commit must be semantically reconciled before final approval. Content-only drift does not automatically invalidate the architecture, but exact code/policy/registration/resource digests must be recomputed and independently approved for the final merged head.

No cutover invocation may use the dated reviewed revision after main drift.

## 15. Testing strategy

Implementation must follow test-driven development around provider adapters and boundary revisions.

Required test layers:

- existing full cutover/handover/exclusion suites unchanged unless contract semantics are intentionally revised;
- focused unit tests for every native adapter;
- negative tests for missing inventory, wrong resource binding, stale revision, competing epoch, unknown actor, surviving session/job, and unavailable admin readback;
- lost-response/restart tests proving no duplicate effect;
- GitHub ruleset/direct-write denial tests using readback and disposable/ref-safe probes where possible;
- separation proof tests for all 19 infrastructure definitions and all mapped credential classes;
- final full Python/controller/media/frontend/browser/build/actionlint/diff gates on the exact candidate head;
- independent read-only review before merge;
- post-merge exact-head CI;
- live cutover only after native preflight succeeds;
- independent 5.6 Article/Overview/Short verification after cutover.

## 16. Rollout and rollback posture

Native exclusion is intentionally one-way for the cutover epoch. There is no automatic `release()` that re-enables retired legacy authority.

If a step fails or produces uncertain transport state:

- stop advancing;
- preserve the journal and invocation ledger;
- inspect the native resource and Git anchor;
- adopt only an exact matching readback;
- otherwise remain blocked.

Do not restore legacy mutation authority merely to make progress. Recovery is forward through verified state or explicit administrator intervention.

## 17. Acceptance criteria

Native Fence v2 is ready for production handover only when all of the following are true on the final current-main-derived candidate:

- all six ports have real production adapters or an explicitly reviewed effective-denial boundary matching this design;
- GitHub protected-ref direct-write denial is independently read back and bound to the canonical principal/epoch;
- all retirement targets are disabled/drained with exact attempt proof;
- Jules has no surviving uncontrolled repository-capable session/effective protected-ref authority;
- predecessor YouTube authority cannot mutate the exact protected channel;
- predecessor Cloudflare authority cannot mutate the exact KESHER Pages/config resources;
- mutation-capable image providers are canonical-only or effectively denied to predecessors;
- NotebookLM legacy credentials/processes are retired and no unverified consumer IAM claim is made;
- all 19 infrastructure separation proofs pass using complete current native mappings;
- the trusted gateway factory, OIDC auth, TLS ingress, persistent ledger, resource bindings, review digests and key custody are installed;
- all focused and full validation gates pass on the exact final head;
- no unresolved Critical/Important review finding remains;
- the coordinated nine-phase handover can proceed without any synthetic receipt or inferred completion.

## 18. Deferred work

The following are explicitly outside this stabilization implementation unless they become necessary to satisfy the acceptance criteria:

- migrating the Python gateway to Cloudflare Workers/D1;
- replacing consumer NotebookLM with an enterprise notebook product;
- unrelated workflow cleanup;
- broader historical forensic reconciliation;
- UI/content/SEO changes unrelated to the authority cutover.
