# KESHER Native Fence v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five live `PrerequisitePort` refusals and incomplete GitHub exclusion boundary with native, independently readable enforcement; complete the trusted incident-bound repair boundary; preserve the finite generation-attempt contract; and safely admit the existing nine-phase KESHER production handover.

**Architecture:** Preserve `ExclusionFence`, `GitExclusionEpoch`, `GuardedGitHub`, OIDC-authenticated `/v1/cutover/step`, the SQLite invocation denial ledger, canonical state/CAS, and the existing handover state machine. Add a small proof-mode extension to distinguish actual credential revocation from equally strong resource-enforced denial, implement one focused native adapter per external resource, complete the 19 infrastructure separation proofs, wire the trusted factory, then complete the existing incident-bound Jules repair design before final candidate certification.

**Tech Stack:** Python 3.12+, stdlib HTTP/JSON/SQLite/crypto helpers already used by the repository, GitHub REST/GraphQL, Google Jules API, Google OAuth/YouTube Data API, Cloudflare API, existing NotebookLM client, existing provider/image transports, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-05-kesher-native-fence-v2-design.md`

## Global Constraints

- Work only on `codex/kesher-autonomous-stabilization-20260917`; do not create a new stabilization branch or goal.
- Preserve fail-closed behavior, exact epoch ownership, Git ref CAS, monotonic nine-phase handover, restart safety, and one-resource-effect-per-invocation.
- Preserve all CLOSED 5.2 evidence and the three quarantines unchanged.
- No production activation, live cutover, provider mutation, workflow retirement, credential revocation, or production state write occurs during implementation Tasks 1–10.
- Caller JSON, local files, workflow flags, empty run lists, and synthetic receipts never substitute for native readback.
- Secrets and credential values never enter repository content, evidence files, HTTP responses, logs, or chat output.
- Checkpoint identities (`15297dde...`, 114 registrations, 80 retirement targets) are evidence only; refresh them before final certification.
- The checkpoint-observed main drift from `1e009e1b...` to `880a3345...` is dated evidence; Task 1 must refresh current main again before any merge.
- Use TDD for each boundary change: failing test, observed failure, minimal implementation, passing focused test, commit.
- Do not weaken `_separated()`, registration completeness, evaluator independence, or generation-attempt limits to make gates pass.
- Do not rewrite the gateway as a Cloudflare Worker during stabilization.
- Jules may propose code changes; Jules-controlled code, tests, CI, or workflow definitions must never be the sole authority certifying that same repair.
- Global/legacy supervisor strike counts never become provider generation-attempt budgets.

## Review Focus

1. **Stale bearer still exists after “revocation”:** the protected resource must deny its effect when the provider cannot prove bearer destruction. Task 2 pins denial-mode semantics; Tasks 3–7 add provider-specific stale-authority tests.
2. **Lost mutation response:** restart adopts exact native readback and never repeats an uncertain effect. Tasks 3–7 each add lost-response/adoption tests.
3. **New/rebound GitHub writer appears after review:** admission fails before any resource effect. Task 3 retains full registration recertification and adds ruleset-actor drift coverage.
4. **Provider inventory is partial or scoped to the wrong account/resource:** `inspect()` fails closed. Tasks 4–7 test incomplete inventory and wrong binding explicitly.
5. **Infrastructure workflow inherits authority transitively:** all GH/CF/OCI/YT credential-service/resource mappings include child dispatch/host credentials. Task 8 adds transitive-chain regressions for the 19-proof matrix.
6. **Repair candidate influences its evaluator:** Task 10 runs trusted base guard checks outside candidate-controlled evaluator changes and rejects test/CI/guard weakening.
7. **Repair or restart resets generation budget:** Task 10 re-certifies exact `1 → 2 → 3`, no fourth attempt, no skipped attempt, and no budget reset from repair/supervisor strikes.

---

### Task 1: Refresh the implementation baseline without changing production

**Files:**
- Modify only as required by a semantic merge from current `main` into the existing stabilization branch.
- Verify: `docs/superpowers/specs/2026-10-05-kesher-native-fence-v2-design.md`
- Verify: `docs/forensics/2026-09-autonomous-stabilization/resume-registrations-20261005.json`

**Interfaces:**
- Consumes: current stabilization branch and current `origin/main`.
- Produces: one clean, current-main-derived implementation baseline with no unresolved conflicts and no changed 5.2 quarantine evidence.

- [ ] **Step 1: Fetch and record current heads.**

```bash
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git status --short
```
Expected: existing branch is clean; record both SHAs before any merge.

- [ ] **Step 2: Inspect the exact main drift before merging.**

```bash
git log --oneline --left-right HEAD...origin/main
git diff --stat HEAD...origin/main
```
Expected: every incoming file is classified as content/queue, runtime, workflow, policy, or infrastructure. Stop if incoming runtime/authority changes invalidate the approved spec.

- [ ] **Step 3: Semantically merge current main into the same branch.**

```bash
git merge --no-ff origin/main
```
Expected: no blind overwrite of stabilization runtime/policy; retain current-main content and unrelated production work.

- [ ] **Step 4: Run the current authority/cutover smoke gate.**

```bash
python3 -B -m unittest \
  tests.test_kesher_current_authority \
  tests.test_kesher_production_cutover \
  tests.test_kesher_external_exclusion -v
```
Expected: PASS. If registration counts drift, update only from fresh native inventory in Task 11; never guess IDs.

- [ ] **Step 5: Commit the reconciled baseline.**

```bash
git add -A
git commit -m "merge: reconcile Native Fence branch with current main"
```

---

### Task 2: Extend exclusion proof semantics for native revocation vs resource-enforced denial

**Files:**
- Modify: `scripts/kesher_runtime/exclusion.py`
- Modify: `tests/test_kesher_external_exclusion.py`
- Modify: `tests/test_kesher_production_cutover.py`

**Interfaces:**
- Consumes: existing `ExclusionFence._policy()`, `validate_external()`, `require_resource_command()`.
- Produces: protection dictionaries with exact fields `protection_method`, `predecessor_authority_denied`, `covered_credential_classes`, plus `credential_revocation_complete` only when native revocation is claimed.

- [ ] **Step 1: Write failing proof-mode tests.**

Add tests asserting:
- `native_revocation` requires `credential_revocation_complete is True` and exact credential-class coverage.
- `resource_enforced_denial` may omit/false `credential_revocation_complete` but requires `predecessor_authority_denied is True`, exact class coverage, exact resource binding, and native readback revision.
- unknown modes, partial class coverage, caller-selected resources, or `predecessor_authority_denied=False` fail closed.
- stale principals remain denied in both modes.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_external_exclusion tests.test_kesher_production_cutover -v
```
Expected: FAIL because the new proof fields/modes are not implemented.

- [ ] **Step 3: Implement the minimal schema change.**

Keep `CANONICAL_GATE` and `CONTROL_GATE` unchanged. Add the two accepted protection modes and update `_policy()`, `validate_external()` and proof construction so each port proves one exact mode and all credential classes. The adapter cannot choose its protected resource ID.

- [ ] **Step 4: Run GREEN.**

```bash
python3 -B -m unittest tests.test_kesher_external_exclusion tests.test_kesher_production_cutover -v
```
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add scripts/kesher_runtime/exclusion.py tests/test_kesher_external_exclusion.py tests/test_kesher_production_cutover.py
git commit -m "feat(cutover): support native revocation and resource denial proofs"
```

---

### Task 3: Add GitHub protected-ref ruleset enforcement and readback

**Files:**
- Create: `scripts/kesher_runtime/github_ruleset.py`
- Modify: `scripts/kesher_runtime/git_exclusion.py`
- Modify: `scripts/kesher_runtime/live_cutover.py`
- Create: `tests/test_kesher_github_ruleset.py`
- Modify: `tests/test_kesher_git_exclusion.py`
- Modify: `tests/test_kesher_current_authority.py`

**Interfaces:**
- Consumes: `GitHubResourceExclusion`, `GitExclusionEpoch`, exact repository ID, reviewed `main_sha`, canonical gateway App identity, fresh workflow registrations.
- Produces: `GitHubRulesetBoundary.inspect(repo) -> dict` and `GitHubRulesetBoundary.enforce(repo, observed_revision, policy) -> None`.

- [ ] **Step 1: Write failing ruleset tests.**

Cover both protected refs (`main`, `automation-state`), unknown human/App bypass, missing canonical App, changed ruleset revision, deleted rule, new writer registration, changed main, stale PAT/Jules actor, and lost mutation acknowledgment recovered only by matching native readback.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_github_ruleset tests.test_kesher_git_exclusion tests.test_kesher_current_authority -v
```
Expected: FAIL because `GitHubRulesetBoundary` does not exist.

- [ ] **Step 3: Implement `GitHubRulesetBoundary`.**

Use repository ruleset REST read/write endpoints through the injected admin-capable GitHub transport. Bind repository ID, protected ref patterns, canonical App identity, epoch metadata, and native ruleset revision. Actions workflow disablement is never the protected-ref fence.

- [ ] **Step 4: Compose ruleset readback into `GitHubResourceExclusion`.**

`inspect()` exposes protection only when epoch anchor, ruleset readback, predecessor direct-write denial, complete registration inventory, and every retirement drain proof agree.

- [ ] **Step 5: Run GREEN.**

```bash
python3 -B -m unittest tests.test_kesher_github_ruleset tests.test_kesher_git_exclusion tests.test_kesher_github_drain tests.test_kesher_current_authority -v
```
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add scripts/kesher_runtime/github_ruleset.py scripts/kesher_runtime/git_exclusion.py scripts/kesher_runtime/live_cutover.py tests/test_kesher_github_ruleset.py tests/test_kesher_git_exclusion.py tests/test_kesher_current_authority.py
git commit -m "feat(cutover): enforce GitHub protected-ref authority boundary"
```

---

### Task 4: Implement the Jules native exclusion port

**Files:**
- Modify: `scripts/kesher_runtime/jules.py`
- Create: `scripts/kesher_runtime/jules_exclusion.py`
- Create: `tests/test_kesher_jules_exclusion.py`
- Modify: `tests/test_kesher_production_cutover.py`

**Interfaces:**
- Consumes: `Jules.sessions()`, `Jules.get()`, repository source `sources/github/yanivsa/kesher-website`, injected predecessor-credential/grant administrator, GitHub protected-ref boundary.
- Produces: `JulesExclusionPort.inspect/exclude`; add `Jules.delete(name)` using the provider-supported DELETE session operation.

- [ ] **Step 1: Write failing transport and port tests.**

Cover DELETE method/path validation, repository-scoped pagination, every nonterminal/unknown state, wrong source context, partial inventory, delete/abort lost response, surviving session, rotated credential with stale session, and GitHub protected-ref denial of a surviving remote actor.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_jules_exclusion -v
```
Expected: FAIL because DELETE and the native port do not exist.

- [ ] **Step 3: Implement exact DELETE support.**

DELETE is effectful: no blind retry on uncertain transport response. Recovery uses subsequent exact session/inventory readback.

- [ ] **Step 4: Implement `JulesExclusionPort`.**

Inventory all repository-capable sessions visible to the administered grant; settle/delete nonterminal sessions; require predecessor credential/grant retirement readback; use `resource_enforced_denial` when stale Jules processes may survive but GitHub rules make protected writes impossible.

- [ ] **Step 5: Run GREEN plus article-quiescence regression.**

```bash
python3 -B -m unittest tests.test_kesher_jules_exclusion tests.test_kesher_article_worker tests.test_kesher_production_cutover -v
```
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add scripts/kesher_runtime/jules.py scripts/kesher_runtime/jules_exclusion.py tests/test_kesher_jules_exclusion.py tests/test_kesher_production_cutover.py
git commit -m "feat(cutover): add native Jules exclusion port"
```

---

### Task 5: Implement the YouTube OAuth/channel exclusion port

**Files:**
- Create: `scripts/kesher_runtime/youtube_exclusion.py`
- Modify only if needed for shared readback: `scripts/kesher_runtime/youtube.py`
- Create: `tests/test_kesher_youtube_exclusion.py`
- Modify: `tests/test_kesher_production_cutover.py`

**Interfaces:**
- Consumes: exact channel `UCx5fEFvdVf28HLAR2dFW64Q`, injected OAuth admin/revocation transport, YouTube Data API readback, known upload-session state.
- Produces: `YouTubeExclusionPort.inspect/exclude`.

- [ ] **Step 1: Write failing tests.**

Cover exact channel binding, wrong channel/project, predecessor OAuth accepted vs rejected, known in-flight upload, unknown/ambiguous upload state, lost revocation response, canonical credential separation, and resumable URI with invalid OAuth unable to mutate the channel.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_youtube_exclusion -v
```
Expected: FAIL because the port does not exist.

- [ ] **Step 3: Implement the adapter.**

Use native OAuth revocation/effective-access readback and exact channel identity. Do not require enumeration of every historical upload URI; require effective denial of predecessor mutation and settlement/refusal of every known accepted operation.

- [ ] **Step 4: Run GREEN plus media regressions.**

```bash
python3 -B -m unittest tests.test_kesher_youtube_exclusion tests.test_kesher_media_policy tests.test_kesher_production_cutover -v
```
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add scripts/kesher_runtime/youtube_exclusion.py scripts/kesher_runtime/youtube.py tests/test_kesher_youtube_exclusion.py tests/test_kesher_production_cutover.py
git commit -m "feat(cutover): add YouTube authority exclusion port"
```

---

### Task 6: Implement the Cloudflare account/Pages exclusion port

**Files:**
- Create: `scripts/kesher_runtime/cloudflare_exclusion.py`
- Modify: `scripts/kesher_runtime/cloudflare_pages.py`
- Create: `tests/test_kesher_cloudflare_exclusion.py`
- Modify: `tests/test_kesher_production_cutover.py`

**Interfaces:**
- Consumes: account `95ba6a62314a0682d0711050ba9c3445`, Pages project `kesher-website`, injected account-admin transport for member/token/integration inventory, existing Pages deployment reader.
- Produces: `CloudflareExclusionPort.inspect/exclude`.

- [ ] **Step 1: Write failing tests.**

Cover single/multiple account members, unknown integration, predecessor token with Pages edit authority, wrong account/project, incomplete pagination, active deployment, lost token-retirement response, scoped canonical credential, and infrastructure credential overlapping protected KESHER resource IDs.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_cloudflare_exclusion -v
```
Expected: FAIL because the port does not exist.

- [ ] **Step 3: Add complete admin inventory/readback helpers without exposing token values.**

Return only token IDs/names/status/effective permissions/resource bindings needed for proof; never return token secret values.

- [ ] **Step 4: Implement `CloudflareExclusionPort`.**

Settle KESHER deployment work, retire/deny predecessor account/project mutation authority, preserve only approved canonical authority, and derive native readback revision from provider-side policy/inventory state rather than a client counter.

- [ ] **Step 5: Run GREEN plus deployment reconciliation tests.**

```bash
python3 -B -m unittest tests.test_kesher_cloudflare_exclusion tests.test_kesher_article_deploy tests.test_kesher_production_cutover -v
```
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add scripts/kesher_runtime/cloudflare_exclusion.py scripts/kesher_runtime/cloudflare_pages.py tests/test_kesher_cloudflare_exclusion.py tests/test_kesher_production_cutover.py
git commit -m "feat(cutover): add Cloudflare account exclusion port"
```

---

### Task 7: Implement image-provider and NotebookLM legacy-authority ports

**Files:**
- Create: `scripts/kesher_runtime/image_provider_exclusion.py`
- Create: `scripts/kesher_runtime/notebooklm_exclusion.py`
- Modify: `scripts/kesher_runtime/provider.py`
- Modify: `scripts/kesher_runtime/article_images.py` only where provider classification metadata is required.
- Create: `tests/test_kesher_image_provider_exclusion.py`
- Create: `tests/test_kesher_notebooklm_exclusion.py`
- Modify: `tests/test_kesher_production_cutover.py`

**Interfaces:**
- Consumes: exact configured provider identities/credential classes, NotebookLM notebook `e101e7d7-5305-45b3-a611-21a5475ceb63`, injected credential/session administrators, known generation state.
- Produces: `ImageProviderExclusionPort.inspect/exclude`, `NotebookLMExclusionPort.inspect/exclude`.

- [ ] **Step 1: Write failing provider-classification tests.**

Assert public/read-only stock search is not falsely promoted to protected mutation authority; unknown provider/project or mutation-capable credential blocks; every active generation/job is settled or denied.

- [ ] **Step 2: Write failing NotebookLM tests.**

Cover exact notebook binding, known browser/session credential inventory, predecessor credential invalidation, nonterminal known generation, unknown session source, missing consumer-account readback, and explicit refusal to label proof as enterprise IAM.

- [ ] **Step 3: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_image_provider_exclusion tests.test_kesher_notebooklm_exclusion -v
```
Expected: FAIL because both ports do not exist.

- [ ] **Step 4: Implement `ImageProviderExclusionPort`.**

Require native revocation or resource denial only for providers capable of protected external mutable effects; keep exact provider/project binding and fail on unknown mutation-capable credentials.

- [ ] **Step 5: Implement `NotebookLMExclusionPort`.**

Use the short-term legacy-quarantine model: known credential/session/process retirement plus known-operation settlement and canonical command gating. Mark the protection method honestly; never claim unavailable provider IAM semantics.

- [ ] **Step 6: Run GREEN plus existing provider/media tests.**

```bash
python3 -B -m unittest tests.test_kesher_image_provider_exclusion tests.test_kesher_notebooklm_exclusion tests.test_kesher_media_policy tests.test_kesher_production_cutover -v
```
Expected: PASS.

- [ ] **Step 7: Commit.**

```bash
git add scripts/kesher_runtime/image_provider_exclusion.py scripts/kesher_runtime/notebooklm_exclusion.py scripts/kesher_runtime/provider.py scripts/kesher_runtime/article_images.py tests/test_kesher_image_provider_exclusion.py tests/test_kesher_notebooklm_exclusion.py tests/test_kesher_production_cutover.py
git commit -m "feat(cutover): add image and NotebookLM exclusion ports"
```

---

### Task 8: Complete the 19 infrastructure separation mappings

**Files:**
- Modify: `scripts/kesher_runtime/authority_policy.json`
- Modify: `scripts/kesher_runtime/authority_topology.py`
- Create or modify: `scripts/kesher_runtime/infrastructure_separation.py`
- Modify: `tests/test_kesher_authority_topology.py`
- Modify: `tests/test_kesher_current_authority.py`
- Modify: `tests/test_kesher_production_cutover.py`

**Interfaces:**
- Consumes: current 19 infrastructure workflow IDs/paths, exact workflow definition hashes, GH/CF/OCI/YT native credential/resource readbacks.
- Produces: `observe_infrastructure_separation() -> dict` matching the existing `_separated()` contract for every infrastructure workflow.

- [ ] **Step 1: Write failing tests for all 19 rows and transitive dispatch chains.**

At minimum cover the 16 OCI-bearing workflows, capacity-watch → provision, recovery-controller → offline-repair → tunnel, CI status authority, and YouTube OAuth diagnostic upload/metadata authority.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_authority_topology tests.test_kesher_current_authority tests.test_kesher_production_cutover -v
```
Expected: FAIL on incomplete service-to-credential/resource mappings.

- [ ] **Step 3: Correct policy mapping from actual workflow callchains and native credential classes.**

Do not invent OCI principals or credential IDs. Policy defines expected classes/resources; live observer supplies actual IDs/scopes from trusted administration.

- [ ] **Step 4: Implement/complete the trusted separation observer.**

Each proof binds exact workflow ID/path/definition/review/resource hashes and native readback; flattened credential IDs/classes match exactly. If a workflow can mutate a protected KESHER resource, classify it as retirement authority instead of fabricating separation.

- [ ] **Step 5: Run GREEN.**

```bash
python3 -B -m unittest tests.test_kesher_authority_topology tests.test_kesher_current_authority tests.test_kesher_production_cutover -v
```
Expected: PASS using fixtures modeling complete native mappings; missing OCI/CF/GH/YT data remains fail-closed.

- [ ] **Step 6: Commit.**

```bash
git add scripts/kesher_runtime/authority_policy.json scripts/kesher_runtime/authority_topology.py scripts/kesher_runtime/infrastructure_separation.py tests/test_kesher_authority_topology.py tests/test_kesher_current_authority.py tests/test_kesher_production_cutover.py
git commit -m "feat(cutover): complete infrastructure separation contract"
```

---

### Task 9: Wire the trusted factory and native ports without enabling production

**Files:**
- Create: `scripts/kesher_runtime/trusted_cutover_factory.py`
- Modify: `scripts/kesher_runtime/live_cutover.py`
- Modify: `scripts/kesher_runtime/production_ports.py`
- Modify: `scripts/kesher_runtime/cutover_service.py` only if factory/bootstrap validation needs an explicit hook.
- Create: `tests/test_kesher_trusted_cutover_factory.py`
- Modify: `tests/test_kesher_production_cutover.py`

**Interfaces:**
- Consumes: six exact resource adapters, approved resource bindings, policy/code/evidence/registration/migration hashes, `NOTEBOOKLM_STATE_KEY` binding, separation observer, persistent ledger path.
- Produces: `trusted_cutover_factory.build() -> CutoverApplication` suitable for administrator installation as `trusted_kesher_cutover:build` or equivalent reviewed module binding.

- [ ] **Step 1: Write failing composition tests.**

Reject missing adapter, prerequisite placeholder, wrong resource binding, missing admin client, wrong review digest, absent key binding, nonpersistent ledger, and caller-supplied provider material. Accept only all-six complete native composition.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_trusted_cutover_factory tests.test_kesher_production_cutover -v
```
Expected: FAIL because no trusted production factory exists.

- [ ] **Step 3: Implement the factory with dependency injection.**

Read credentials/config only from trusted service-side custody; construct five provider ports plus GitHub port; verify exact approved bindings/digests; construct `InvocationJournal` and `ActionsIdentity`; return `CutoverApplication`. No provider credential appears in the HTTP API.

- [ ] **Step 4: Replace `PrerequisitePort` only in the trusted live-factory path.**

Keep `PrerequisitePort` as fail-closed default/test sentinel. Ordinary repository imports must not instantiate live admin adapters.

- [ ] **Step 5: Run GREEN and service/auth regressions.**

```bash
python3 -B -m unittest \
  tests.test_kesher_trusted_cutover_factory \
  tests.test_kesher_production_cutover \
  tests.test_kesher_cutover_service \
  tests.test_kesher_cutover_auth -v
```
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add scripts/kesher_runtime/trusted_cutover_factory.py scripts/kesher_runtime/live_cutover.py scripts/kesher_runtime/production_ports.py scripts/kesher_runtime/cutover_service.py tests/test_kesher_trusted_cutover_factory.py tests/test_kesher_production_cutover.py
git commit -m "feat(cutover): compose trusted native exclusion gateway"
```

---

### Task 10: Complete trusted incident-bound repair (5.3) and re-certify finite attempts (5.4)

**Files:**
- Create: `scripts/kesher_runtime/recovery.py`
- Create: `.github/jules-templates/autonomous-repair.md`
- Modify: `.github/scripts/kesher_task_supervisor_runtime_v3.py`
- Modify only if durable incident linkage requires it: `scripts/kesher_runtime/policy.py`
- Create: `tests/test_kesher_repair_contract.py`
- Verify/extend: `tests/test_kesher_intervention_policy.py`
- Verify/extend: `tests/test_kesher_v6_intervention_isolation.py`
- Verify/extend: `tests/test_kesher_task_supervisor_runtime_v3.py`
- Verify/extend: `tests/test_kesher_generation_attempts.py`
- Verify/extend: `tests/test_kesher_three_strike_runtime.py`
- Verify/extend: `tests/test_kesher_final_attempt_fallback.py`

**Interfaces:**
- Preserve the previously reviewed 5.3 contract: `incident_key(identity, stage, failure_class)`, `repair_packet(incident, evidence)`, `reconcile_repair(...)`, `validate_repair(base, head, contract) -> fail-closed verdict`.
- Consume the existing V3 `SUPERVISOR_TAKEOVER_REQUIRED` / stable blocker fingerprint rather than creating another retry ladder.
- Jules is a repair proposer/continuation actor, never the trusted evaluator or final completion authority.

- [ ] **Step 1: Write failing repair-contract tests.**

Cover:
- timestamp-only Jules activity is not semantic progress;
- duplicate Jules session, branch, or PR creation is refused when an existing exact incident repair exists;
- changed HEAD de-escalation/adoption reuses the same incident rather than resetting it;
- candidate changes to trusted evaluator/guard/CI definitions are refused;
- test deletion, assertion weakening, blanket skip/xfail, or gate-threshold relaxation are refused;
- tracker/incident cannot close merely because Jules says Done or CI is green;
- failed/closed PR, terminal no-output session, merge race, uncertain Jules response, and external reauth remain explicit blocked/recovery states;
- obsolete-test migration requires a separate reviewed contract change, not autonomous repair discretion.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest \
  tests.test_kesher_repair_contract \
  tests.test_kesher_intervention_policy \
  tests.test_kesher_v6_intervention_isolation \
  tests.test_kesher_task_supervisor_runtime_v3 -v
```
Expected: new repair-contract tests FAIL because the trusted repair module is not implemented.

- [ ] **Step 3: Implement `recovery.py` as the incident-bound repair contract.**

Requirements:
- derive one stable incident key from exact target identity/stage/failure class;
- bind a repair packet to base SHA, incident evidence, permitted paths/operation, existing Jules session/branch/PR identity, and immutable trusted guard digest;
- adopt existing repair artifacts before creating anything new;
- circuit-break software exhaustion into one trusted takeover, never a fabricated `HUMAN_BLOCKER`;
- preserve persistent incident audit across restart;
- on uncertain Jules/merge transport response, inspect exact session/branch/PR/head before any retry.

- [ ] **Step 4: Implement trusted evaluator separation.**

`validate_repair(base, head, contract)` must execute from the trusted supervisor/base checkout, not from candidate-supplied validator code. It must compare base→head scope, reject guard/workflow/evaluator weakening, run immutable regression gates, require exact-head CI as an additional signal, and permit merge only when both trusted base guards and candidate CI agree. A candidate cannot authorize changing the tests that certify itself; such a change exits autonomous repair and starts a new reviewed contract cycle.

- [ ] **Step 5: Wire V3 takeover to the trusted repair contract without adding a second recovery ladder.**

When V3 reaches `SUPERVISOR_TAKEOVER_REQUIRED`, create/adopt one incident-bound repair packet and continue the same Issue/session/branch/PR where possible. Do not add a new production-mutating workflow registration merely for repair; reuse the trusted supervisor/controller authority path that will itself be covered by the final authority topology.

- [ ] **Step 6: Run repair GREEN.**

```bash
python3 -B -m unittest \
  tests.test_kesher_repair_contract \
  tests.test_kesher_intervention_policy \
  tests.test_kesher_v6_intervention_isolation \
  tests.test_kesher_task_supervisor_runtime_v3 -v
```
Expected: PASS.

- [ ] **Step 7: Re-certify the finite generation-attempt contract without changing its budget.**

Required invariants already represented by the existing tests:
- attempt 1 may advance to 2 only after exact definite provider rejection and required bounded delay/evidence;
- attempt 2 may advance to 3 only after exact definite rejection of 2;
- attempt 3 cannot be skipped into from 1 and no attempt 4 exists;
- uncertainty, unresolved provider intent, upload/archive intent, stale rejection digest, or inconsistent receipts block replacement generation;
- restart/repair/supervisor strike count cannot reset or replenish the media attempt budget;
- the final-attempt fallback may promote only a same-source usable prior artifact after attempt 3, never another source and never after a public upload exists.

Run:
```bash
python3 -B -m unittest \
  tests.test_kesher_generation_attempts \
  tests.test_kesher_three_strike_runtime \
  tests.test_kesher_final_attempt_fallback -v
```
Expected: PASS with no weakened assertions or increased budget.

- [ ] **Step 8: Add one cross-boundary regression: repair must not reset attempt history.**

A repaired code path resumes the exact incident/operation with canonical state and prior attempt snapshots intact. New code/head progress is not a new media target and does not create a fourth attempt.

Run the combined repair + attempt suites again and require PASS.

- [ ] **Step 9: Commit.**

```bash
git add scripts/kesher_runtime/recovery.py .github/jules-templates/autonomous-repair.md .github/scripts/kesher_task_supervisor_runtime_v3.py scripts/kesher_runtime/policy.py tests/test_kesher_repair_contract.py tests/test_kesher_intervention_policy.py tests/test_kesher_v6_intervention_isolation.py tests/test_kesher_task_supervisor_runtime_v3.py tests/test_kesher_generation_attempts.py tests/test_kesher_three_strike_runtime.py tests/test_kesher_final_attempt_fallback.py
git commit -m "feat(stabilization): complete trusted repair and finite-attempt gates"
```

---

### Task 11: Refresh native authority inventory and run complete candidate validation

**Files:**
- Modify only generated/current evidence under `docs/forensics/2026-09-autonomous-stabilization/` when produced by existing evidence tooling.
- Modify: `scripts/kesher_runtime/authority_policy.json` only if fresh native registration IDs require a reviewed rebinding.

**Interfaces:**
- Consumes: current GitHub/Cloudflare/provider read-only native inventories; implementation from Tasks 1–10.
- Produces: refreshed exact registration/resource/separation evidence and an immutable candidate head ready for independent review.

- [ ] **Step 1: Refresh current `main`, state ref, complete workflow registrations, ruleset actors, Pages identity, and all provider resource bindings read-only.**

Expected: any new/rebound/unknown writer blocks candidate certification until classified. Never assume the checkpoint’s 114/80 counts remain current.

- [ ] **Step 2: Recompute all review digests from the candidate head.**

Include policy+definition digest, executable digest, registration binding digest, closed-evidence digest, migration material digest, resource-binding digest, trusted repair guard digest, and saved validation input manifest.

- [ ] **Step 3: Run focused native/repair/attempt boundary tests.**

```bash
python3 -B -m unittest \
  tests.test_kesher_current_authority \
  tests.test_kesher_production_cutover \
  tests.test_kesher_external_exclusion \
  tests.test_kesher_git_exclusion \
  tests.test_kesher_github_drain \
  tests.test_kesher_github_ruleset \
  tests.test_kesher_jules_exclusion \
  tests.test_kesher_youtube_exclusion \
  tests.test_kesher_cloudflare_exclusion \
  tests.test_kesher_image_provider_exclusion \
  tests.test_kesher_notebooklm_exclusion \
  tests.test_kesher_authority_topology \
  tests.test_kesher_trusted_cutover_factory \
  tests.test_kesher_repair_contract \
  tests.test_kesher_intervention_policy \
  tests.test_kesher_v6_intervention_isolation \
  tests.test_kesher_generation_attempts \
  tests.test_kesher_three_strike_runtime \
  tests.test_kesher_final_attempt_fallback -v
```
Expected: PASS.

- [ ] **Step 4: Run the established complete repository gates.**

Run the same full Python, media-policy, controller, frontend/unit, generation/content/type/lint/build/distribution, browser, actionlint, compilation and diff gates used by checkpoint `15297dde...`.

Expected: no waived failure; regenerated outputs are exact or archived/justified deterministic generated deltas.

- [ ] **Step 5: Perform a local/read-only adversarial review before producing evidence.**

Check for: synthetic native proof, evaluator self-certification, new workflow writer unclassified, secrets in evidence, attempt-budget increase, quarantines changed, broad repair scope, and production side effects during validation. Any finding returns to the owning task.

- [ ] **Step 6: Commit refreshed evidence only after all candidate gates pass.**

```bash
git add docs/forensics/2026-09-autonomous-stabilization scripts/kesher_runtime/authority_policy.json
git commit -m "docs(stabilization): certify Native Fence v2 candidate"
```

---

### Task 12: Independent review, exact-head PR/merge, gateway provisioning, controlled cutover, and 5.6 proof

**Files:**
- No implementation edits permitted after exact-head approval except through a new reviewed cycle.
- Operational configuration: protected GitHub environment/variables, trusted gateway host, admin-side credentials, persistent SQLite ledger, TLS ingress.

**Interfaces:**
- Consumes: immutable candidate head from Task 11.
- Produces: merged exact head, independently provisioned gateway, native preflight proof, coordinated nine-phase handover, separately admitted runtime activation, and independent 5.6 public proof.

- [ ] **Step 1: Obtain independent read-only review of the complete candidate.**

Required result: 0 Critical / 0 Important. Any finding returns to the owning task and invalidates current approval digests.

- [ ] **Step 2: Create one PR for the exact candidate and require exact-head CI.**

Do not auto-merge a stale head. Verify CI/status identity and branch protection before merge.

- [ ] **Step 3: Merge only the certified head, then refresh exact merged `main` and recompute final installed digests.**

If merge changes the tree unexpectedly, stop and repeat Task 11 certification/review.

- [ ] **Step 4: Provision the trusted gateway outside the cutover runner.**

Install reviewed code/factory, TLS ingress, persistent ledger, isolated GitHub/provider admin and canonical credentials, exact resource bindings, final approval material, trusted repair guard material, and `NOTEBOOKLM_STATE_KEY` custody. Set `KESHER_CUTOVER_GATEWAY_URL` only after unauthenticated rejection and nonmutating native inspect/readbacks pass.

- [ ] **Step 5: Prove all six native boundaries and all 19 infrastructure separations before the first cutover effect.**

Expected: exact current inventory, no unknown actor, no uncontrolled provider job/session, GitHub protected-ref denial installed/read back, all separation proofs accepted, and the trusted repair evaluator isolated from repair candidates.

- [ ] **Step 6: Execute the existing manual-main cutover workflow one invocation at a time.**

```bash
gh workflow run kesher-production-cutover.yml \
  --repo yanivsa/kesher-website --ref main \
  -f epoch=ADMIN_APPROVED_EPOCH \
  -f reviewed_revision=EXACT_REVIEWED_CURRENT_MAIN_SHA
```
After each invocation, inspect exact native/Git journal state before another invocation. Never blindly retry an uncertain step.

- [ ] **Step 7: Complete nine-phase handover and verify Schema 6 authority.**

Expected: `VERIFIED`, owned epoch, all retirement drains/readbacks complete, trusted repair path available under canonical authority, finite attempt history preserved, production activation still separately admitted, and no inferred public completion.

- [ ] **Step 8: Perform separately admitted runtime activation and 5.6 independent public proof.**

Verify exact Article + Overview + Short source identity, publication/deployment/media lineage, public processing/metadata, and duplicate absence. Do not create new provider work merely to manufacture evidence. Preserve all three CLOSED 5.2 quarantines.

- [ ] **Step 9: Record final health evidence and retire temporary gateway exposure where safe.**

Keep durable audit/journal/evaluator evidence; do not automatically restore legacy mutation authority. Confirm no fourth generation path, no unresolved repair takeover, no unknown writer, no duplicate public product, and no synthetic completion claim.
