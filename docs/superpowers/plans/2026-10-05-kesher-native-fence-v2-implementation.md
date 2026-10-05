# KESHER Native Fence v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the five live `PrerequisitePort` refusals and incomplete GitHub exclusion boundary with native, independently readable enforcement that can safely admit the existing nine-phase KESHER production handover.

**Architecture:** Preserve `ExclusionFence`, `GitExclusionEpoch`, `GuardedGitHub`, OIDC-authenticated `/v1/cutover/step`, the SQLite invocation denial ledger, and the existing handover state machine. Add a small proof-mode extension to distinguish actual credential revocation from equally strong resource-enforced denial, then implement one focused native adapter per external resource and wire them through the trusted factory only after each adapter is independently testable.

**Tech Stack:** Python 3.12+, stdlib HTTP/JSON/SQLite/crypto helpers already used by the repository, GitHub REST/GraphQL, Google Jules API, Google OAuth/YouTube Data API, Cloudflare API, existing NotebookLM client, existing provider/image transports, `unittest`, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-05-kesher-native-fence-v2-design.md`

## Global Constraints

- Work only on `codex/kesher-autonomous-stabilization-20260917`; do not create a new stabilization branch or goal.
- Preserve fail-closed behavior, exact epoch ownership, Git ref CAS, monotonic nine-phase handover, restart safety, and one-resource-effect-per-invocation.
- Preserve all CLOSED 5.2 evidence and the three quarantines unchanged.
- No production activation, live cutover, provider mutation, workflow retirement, credential revocation, or state write occurs during implementation tasks 1–9.
- Caller JSON, local files, workflow flags, empty run lists, and synthetic receipts never substitute for native readback.
- Secrets and credential values never enter repository content, evidence files, HTTP responses, logs, or chat output.
- Current checkpoint identities (`15297dde...`, 114 registrations, 80 retirement targets) are evidence only; refresh them before final certification.
- The current main drift from `1e009e1b...` to `880a3345...` must be reconciled before final exact-head approval.
- Use TDD for each boundary change: failing test, observed failure, minimal implementation, passing focused test, commit.
- Do not weaken `_separated()` or registration completeness to make infrastructure proofs pass.
- Do not rewrite the gateway as a Cloudflare Worker during stabilization.

## Review Focus

1. **Stale bearer still exists after “revocation”:** the protected resource must still deny its effect when the provider cannot prove bearer destruction. Task 2 pins this with denial-mode validation tests; Tasks 3–7 add provider-specific stale-authority tests.
2. **Lost mutation response:** restart must adopt exact native readback and must not repeat the effect. Tasks 3–7 each add lost-response/adoption tests.
3. **New/rebound GitHub writer appears after review:** admission must fail before any resource effect. Task 3 retains full registration recertification and adds ruleset-actor drift coverage.
4. **Provider inventory is partial or scoped to the wrong account/resource:** `inspect()` must fail closed. Tasks 4–7 test incomplete inventory and wrong binding explicitly.
5. **Infrastructure workflow inherits authority transitively:** all GH/CF/OCI/YT credential-service/resource mappings must include child dispatch/host credentials; Task 8 adds transitive-chain regressions for the 19-proof matrix.

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

Run:
```bash
git fetch origin
git rev-parse HEAD
git rev-parse origin/main
git status --short
```
Expected: existing branch is clean; record both SHAs before any merge.

- [ ] **Step 2: Inspect the exact main drift before merging.**

Run:
```bash
git log --oneline --left-right HEAD...origin/main
git diff --stat HEAD...origin/main
```
Expected: every incoming file is classified as content/queue, runtime, workflow, policy, or infrastructure. Stop if incoming runtime/authority files invalidate the approved spec.

- [ ] **Step 3: Semantically merge current main into the same branch.**

Run:
```bash
git merge --no-ff origin/main
```
Expected: no blind overwrite of stabilization runtime/policy; retain current-main content and unrelated production work.

- [ ] **Step 4: Run the current authority and cutover smoke gate.**

Run:
```bash
python3 -B -m unittest \
  tests.test_kesher_current_authority \
  tests.test_kesher_production_cutover \
  tests.test_kesher_external_exclusion -v
```
Expected: PASS; if registration counts drift, update only from fresh native inventory in Task 9, not by guessing IDs.

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
- unknown proof modes, partial class coverage, caller-selected resources, or `predecessor_authority_denied=False` fail closed.
- stale principals remain denied in both modes.

- [ ] **Step 2: Run the focused tests and verify RED.**

```bash
python3 -B -m unittest tests.test_kesher_external_exclusion tests.test_kesher_production_cutover -v
```
Expected: FAIL because the new proof fields/modes are not implemented.

- [ ] **Step 3: Implement the minimal schema change in `exclusion.py`.**

Keep `CANONICAL_GATE` and `CONTROL_GATE` unchanged. Add constants for the two accepted modes and update `_policy()`, `validate_external()` and proof construction so a port must prove one exact mode and all credential classes. Do not let the adapter choose its protected resource ID.

- [ ] **Step 4: Run focused tests and verify GREEN.**

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
- Produces: `GitHubRulesetBoundary.inspect(repo) -> dict` and `GitHubRulesetBoundary.enforce(repo, observed_revision, policy) -> None`; the readback proves protected refs, allowed/bypass actors, destructive-update denial, and exact repository binding.

- [ ] **Step 1: Write failing ruleset tests.**

Cover:
- `main` and `automation-state` are both protected.
- unknown human/App bypass actor blocks admission.
- canonical App missing from the approved actor set blocks admission.
- changed ruleset revision, deleted rule, new writer registration, or changed main causes refusal.
- a stale PAT/Jules actor cannot update protected refs even if its bearer still exists.
- lost ruleset mutation acknowledgment is adopted only from matching native readback.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_github_ruleset tests.test_kesher_git_exclusion tests.test_kesher_current_authority -v
```
Expected: FAIL because `GitHubRulesetBoundary` does not exist.

- [ ] **Step 3: Implement `GitHubRulesetBoundary`.**

Use GitHub repository ruleset REST read/write endpoints through the injected admin-capable GitHub transport. Bind repository ID, exact protected ref patterns, canonical App identity, epoch metadata, and native ruleset revision. Never treat Actions workflow disablement as the protected-ref fence.

- [ ] **Step 4: Compose the ruleset readback into `GitHubResourceExclusion`.**

`GitHubResourceExclusion.inspect()` must expose protection only when: epoch anchor, ruleset readback, predecessor direct-write denial, full registration inventory, and all retirement drain proofs agree.

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
- Produces: `JulesExclusionPort.inspect(repo) -> dict`, `JulesExclusionPort.exclude(repo, observed_revision, policy) -> None`; add `Jules.delete(name: str) -> None` using the provider-supported DELETE session operation.

- [ ] **Step 1: Write failing transport and port tests.**

Cover DELETE method/path validation, repository-scoped pagination, every nonterminal state, unknown state, wrong source context, partial inventory, delete/abort lost response, surviving session, rotated credential with stale session, and GitHub protected-ref denial of a surviving remote actor.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_jules_exclusion -v
```
Expected: FAIL because DELETE and the native port do not exist.

- [ ] **Step 3: Extend `Jules.request()` to permit exact DELETE session operations and implement `Jules.delete()`.**

DELETE is effectful: no blind retry on uncertain transport response. Recovery is subsequent `get()`/inventory readback.

- [ ] **Step 4: Implement `JulesExclusionPort`.**

Inventory all repository-capable sessions visible to the administered grant; settle/delete nonterminal sessions; require predecessor credential/grant retirement readback; use `resource_enforced_denial` when stale Jules processes may survive but GitHub rules make protected writes impossible.

- [ ] **Step 5: Run GREEN plus article quiescence regression.**

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
- Produces: `YouTubeExclusionPort.inspect(repo) -> dict`, `YouTubeExclusionPort.exclude(repo, observed_revision, policy) -> None`.

- [ ] **Step 1: Write failing tests.**

Cover exact channel binding, wrong channel/project, predecessor OAuth token accepted vs rejected, known in-flight upload, unknown/ambiguous upload state, lost revocation response, canonical credential separation, and proof that a resumable URI without valid OAuth cannot mutate the channel.

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
- Produces: `CloudflareExclusionPort.inspect(repo) -> dict`, `CloudflareExclusionPort.exclude(repo, observed_revision, policy) -> None`.

- [ ] **Step 1: Write failing tests.**

Cover single/multiple account members, unknown integration, predecessor token with Pages edit authority, wrong account/project, incomplete pagination, active deployment, lost token-retirement response, scoped canonical credential, and infrastructure credential overlapping KESHER protected resource IDs.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_cloudflare_exclusion -v
```
Expected: FAIL because the port does not exist.

- [ ] **Step 3: Add complete admin inventory/readback helpers without exposing token values.**

Return only token IDs/names/status/effective permission/resource bindings needed for proof. Never return token secret values.

- [ ] **Step 4: Implement `CloudflareExclusionPort`.**

Settle KESHER deployment work, retire/deny predecessor account/project mutation authority, preserve only approved canonical authority, and generate native readback revision from the provider-side policy/inventory state rather than a client counter.

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

Assert public/read-only stock search is not falsely promoted to protected mutation authority; unknown provider/project or mutation-capable credential is blocking; every active generation/job is settled or denied.

- [ ] **Step 2: Write failing NotebookLM tests.**

Cover exact notebook binding, known browser/session credential inventory, predecessor credential invalidation, nonterminal known generation, unknown session source, missing consumer-account readback, and explicit refusal to label the proof as enterprise IAM.

- [ ] **Step 3: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_image_provider_exclusion tests.test_kesher_notebooklm_exclusion -v
```
Expected: FAIL because both ports do not exist.

- [ ] **Step 4: Implement `ImageProviderExclusionPort`.**

Require native revocation or resource denial only for providers that can cause protected external mutable effects; keep exact provider/project binding and fail on unknown mutation-capable credentials.

- [ ] **Step 5: Implement `NotebookLMExclusionPort`.**

Use the short-term legacy-quarantine model: known credential/session/process retirement plus known-operation settlement and canonical command gating. Mark the protection method honestly; do not claim unavailable provider IAM semantics.

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

- [ ] **Step 3: Correct the policy mapping from actual workflow callchains and native credential classes.**

Do not invent OCI principals or credential IDs. The policy defines expected classes/resources; the live observer supplies actual IDs and scopes from trusted administration.

- [ ] **Step 4: Implement/complete the trusted separation observer.**

Each proof must bind exact workflow ID/path/definition/review/resource hashes and native readback; flattened credential IDs/classes must match exactly. If a workflow can mutate a protected KESHER resource, classify it as retirement authority instead of fabricating separation.

- [ ] **Step 5: Run GREEN.**

```bash
python3 -B -m unittest tests.test_kesher_authority_topology tests.test_kesher_current_authority tests.test_kesher_production_cutover -v
```
Expected: PASS using fixtures that model complete native mappings; missing OCI/CF/GH/YT data remains fail-closed.

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
- Consumes: six exact resource adapters, approved resource bindings, final policy/code/evidence/registration/migration hashes, `NOTEBOOKLM_STATE_KEY` binding, separation observer, persistent ledger path.
- Produces: `trusted_cutover_factory.build() -> CutoverApplication` suitable for administrator installation as `trusted_kesher_cutover:build` or equivalent reviewed module binding.

- [ ] **Step 1: Write failing composition tests.**

Reject missing adapter, prerequisite placeholder, wrong resource binding, missing admin client, wrong review digest, absent key binding, nonpersistent ledger, and caller-supplied provider material. Accept only all-six complete native composition.

- [ ] **Step 2: Run RED.**

```bash
python3 -B -m unittest tests.test_kesher_trusted_cutover_factory tests.test_kesher_production_cutover -v
```
Expected: FAIL because no trusted production factory exists.

- [ ] **Step 3: Implement the factory with dependency injection.**

The factory reads credentials/configuration only from trusted service-side custody, constructs the five provider ports plus GitHub port, verifies exact approved bindings/digests, constructs `InvocationJournal` and `ActionsIdentity`, then returns `CutoverApplication`. No provider credential appears in the HTTP API.

- [ ] **Step 4: Replace `PrerequisitePort` only in the trusted live factory path.**

Keep `PrerequisitePort` available as the fail-closed default/test sentinel. Importing or running ordinary repository code must not instantiate live admin adapters.

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

### Task 10: Refresh native authority inventory and run complete candidate validation

**Files:**
- Modify only generated/current evidence under `docs/forensics/2026-09-autonomous-stabilization/` when produced by existing evidence tooling.
- Modify: `scripts/kesher_runtime/authority_policy.json` only if fresh native registration IDs require a reviewed rebinding.

**Interfaces:**
- Consumes: current GitHub/Cloudflare/provider read-only native inventories; implementation from Tasks 1–9.
- Produces: refreshed exact registration/resource/separation evidence and an immutable candidate head ready for independent review.

- [ ] **Step 1: Refresh `main`, state ref, 114+ workflow registrations, ruleset actors, Pages identity, and all provider resource bindings read-only.**

Expected: any new/rebound/unknown writer blocks candidate certification until classified.

- [ ] **Step 2: Recompute all review digests from the candidate head.**

Include policy+definition digest, executable digest, registration binding digest, closed-evidence digest, migration material digest, resource-binding digest, and saved validation input manifest.

- [ ] **Step 3: Run focused native-boundary tests.**

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
  tests.test_kesher_trusted_cutover_factory -v
```
Expected: PASS.

- [ ] **Step 4: Run the established complete repository gates.**

Run the same full Python, media-policy, controller, frontend/unit, generation/content/type/lint/build/distribution, browser, actionlint, compilation and diff gates used by checkpoint `15297dde...`.

Expected: no waived failure; regenerated outputs are either exact or archived/justified as deterministic generated deltas.

- [ ] **Step 5: Commit refreshed evidence only after all candidate gates pass.**

```bash
git add docs/forensics/2026-09-autonomous-stabilization scripts/kesher_runtime/authority_policy.json
git commit -m "docs(stabilization): certify Native Fence v2 candidate"
```

---

### Task 11: Independent review, exact-head PR/merge, gateway provisioning, and controlled cutover

**Files:**
- No implementation edits permitted after exact-head approval except a new reviewed cycle.
- Operational configuration: protected GitHub environment/variables, trusted gateway host, admin-side credentials, persistent SQLite ledger, TLS ingress.

**Interfaces:**
- Consumes: immutable candidate head from Task 10.
- Produces: merged exact head, independently provisioned gateway, native preflight proof, coordinated nine-phase handover, then separate 5.6 public proof.

- [ ] **Step 1: Obtain an independent read-only review of the complete candidate.**

Required result: 0 Critical / 0 Important; any finding returns to the owning task and invalidates the current approval digest.

- [ ] **Step 2: Create one PR for the exact candidate and require exact-head CI.**

Do not auto-merge a stale head. Verify CI/status identity and branch protection before merge.

- [ ] **Step 3: Merge only the certified head, then refresh exact merged `main` and recompute final installed digests.**

If merge changes the tree unexpectedly, stop and repeat Task 10 review/certification.

- [ ] **Step 4: Provision the trusted gateway outside the cutover runner.**

Install reviewed code/factory, TLS ingress, persistent ledger, isolated GitHub/provider admin and canonical credentials, exact resource bindings, final approval material and `NOTEBOOKLM_STATE_KEY` custody. Set `KESHER_CUTOVER_GATEWAY_URL` only after unauthenticated rejection and nonmutating native inspect/readbacks pass.

- [ ] **Step 5: Prove all six native boundaries and all 19 infrastructure separations before the first cutover effect.**

Expected: exact current inventory, no unknown actor, no uncontrolled provider job/session, GitHub protected-ref denial installed/read back, and every separation proof accepted by the existing validator.

- [ ] **Step 6: Execute the existing manual-main cutover workflow one invocation at a time.**

```bash
gh workflow run kesher-production-cutover.yml \
  --repo yanivsa/kesher-website --ref main \
  -f epoch=ADMIN_APPROVED_EPOCH \
  -f reviewed_revision=EXACT_REVIEWED_CURRENT_MAIN_SHA
```
After each invocation, inspect exact native/Git journal state before another invocation. Never blindly retry an uncertain step.

- [ ] **Step 7: Complete nine-phase handover and verify Schema 6 authority.**

Expected: `VERIFIED`, owned epoch, all retirement drains/readbacks complete, production activation still separately admitted, no inferred public completion.

- [ ] **Step 8: Finish remaining trusted incident-bound 5.3 and verify finite-attempt 5.4 in production authority.**

Do not reopen CLOSED 5.2 quarantines.

- [ ] **Step 9: Perform separately admitted runtime activation and 5.6 independent public proof.**

Verify exact Article + Overview + Short source identity, publication/deployment/media lineage, public processing/metadata, and duplicate absence. Do not create new provider work merely to manufacture evidence.

- [ ] **Step 10: Record final health evidence and retire temporary gateway exposure where safe.**

Keep durable audit/journal evidence; do not automatically restore legacy mutation authority.
