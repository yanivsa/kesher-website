# Kesher Supervision Stability V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Kesher incidents converge through Controller → Jules → Direct escalation with durable exact identity, idempotent repair, fixed supervision SLAs, and read-only V6 shadow learning.

**Architecture:** Extend the existing V5 durable controller state and intervention ledger rather than adding a second state store. The shared intervention policy becomes the single source for incident identity and hourly strike ownership; a focused Jules repair adapter performs S2 handoff; V6 consumes the same durable evidence read-only.

**Tech Stack:** Python 3, GitHub Actions, Jules v1alpha REST API, JSON production contract, unittest.

**Spec:** `docs/superpowers/specs/2026-09-14-kesher-supervision-stability-design.md`

## Global Constraints

- V5 remains the only production controller.
- V6 remains read-only/shadow with production/article/provider/upload dispatch disabled.
- Exact incident identity is `pipeline_id + slug + content_sha256 + stage + failure_signature`.
- Hourly escalation is S1 Controller → S2 Jules → S3 Direct.
- No duplicate article, PR, Jules repair session, provider generation, video, or upload.
- Existing exact `source_id`, `task_id`, `artifact_id`, provider identity, and public evidence must be preserved.
- A+B+C public verification remains the only Done contract.

---

### Task 1: Lock the new intervention contract with failing tests

**Files:**
- Modify: `tests/test_kesher_intervention_policy.py`
- Modify: `tests/test_kesher_v6_intervention_isolation.py`
- Create: `tests/test_kesher_jules_incident_repair.py`
- Create: `tests/test_kesher_supervision_contract.py`

**Interfaces:**
- Produces expected `ESCALATE_JULES`, failure-signature incident identity and deterministic idempotency-key behavior used by later tasks.

- [ ] Update intervention tests to assert h1/h2/h3 = Controller/Jules/Direct.
- [ ] Add tests proving a controller action does not suppress S2 Jules on the next distinct hourly check.
- [ ] Add tests proving a changed `failure_signature` starts a new S1 incident.
- [ ] Add tests proving the same exact incident derives the same idempotency key and a different failure signature derives a different key.
- [ ] Add Jules repair tests for deterministic session title, exact identity prompt, duplicate prevention and active-session reuse.
- [ ] Add supervision-contract tests for 60-minute strikes, 90-minute external timeout, SLA table and prompt versions.
- [ ] Update V6 isolation tests to expect Controller/Jules/Direct while preserving all dispatch flags false.
- [ ] Run `python3 -m unittest tests.test_kesher_intervention_policy tests.test_kesher_jules_incident_repair tests.test_kesher_supervision_contract tests.test_kesher_v6_intervention_isolation` and verify expected RED failures are missing new behavior, not syntax/import accidents.
- [ ] Commit the red tests.

### Task 2: Implement supervision contract and exact incident identity

**Files:**
- Modify: `config/kesher-production-contract.json`
- Modify: `scripts/kesher_automation_policy.py`
- Modify: `scripts/kesher_intervention_policy.py`

**Interfaces:**
- Produces `supervision_policy()`, `ESCALATE_JULES`, `incident_key(..., failure_signature=...)`, `incident_idempotency_key(...)`, and persisted owner/failure/idempotency metadata.

- [ ] Add the validated `supervision` section to the production contract.
- [ ] Add supervision validation/helper to `kesher_automation_policy.py` without changing unrelated production values.
- [ ] Extend incident identity with required `failure_signature`.
- [ ] Add deterministic SHA-256 idempotency key for exact incident identity.
- [ ] Change second distinct hourly check to `ESCALATE_JULES`; keep same-token dedup and durable-progress reset.
- [ ] Persist owner, failure signature and idempotency key in the existing `interventions` ledger.
- [ ] Run Task 1 tests and verify GREEN for contract/intervention tests.
- [ ] Commit.

### Task 3: Add idempotent Jules incident repair adapter

**Files:**
- Create: `scripts/kesher_jules_incident_repair.py`
- Modify: `scripts/kesher_content_controller_v5.py`

**Interfaces:**
- Consumes exact incident identity + idempotency key.
- Produces/reuses one Jules repair session and returns its stable session identity without polling or duplicate creation.

- [ ] Implement prompt version 1 and deterministic title from incident idempotency key.
- [ ] Implement active exact-title session listing/reuse with fail-closed duplicate detection.
- [ ] Implement one-attempt session creation and uncertain-response reconciliation by title.
- [ ] Make the prompt explicitly forbid new article/provider generation/video/upload identities and require preservation of existing IDs.
- [ ] Add `V5GitHubClient.escalate_incident_to_jules(...)` using `JULES_API_KEY` and the repair adapter.
- [ ] Run Jules repair tests and relevant article-runner tests.
- [ ] Commit.

### Task 4: Wire S2 Jules and persistent source metadata into V5

**Files:**
- Modify: `scripts/kesher_three_strike_runtime.py`
- Modify: `scripts/kesher_content_controller_stabilized.py`
- Modify/add relevant runtime tests if present.

**Interfaces:**
- Consumes S2 `ESCALATE_JULES` decision.
- Persists Jules repair session metadata and current exact V5 source identity.

- [ ] Derive stable failure signatures from the exact stage/error condition.
- [ ] Pass failure signature to every article/media incident observation.
- [ ] On S2 call exactly one idempotent Jules repair handoff and persist session/idempotency metadata.
- [ ] Keep fast V5 watchdog recovery enabled between hourly supervisor checks; do not create a duplicate provider identity.
- [ ] On S3 preserve current `direct_takeover_required` behavior with the richer incident identity.
- [ ] Persist `pipeline_id: v5`, `source`, and supervision contract version whenever authoritative article identity exists.
- [ ] Run intervention/runtime/controller tests.
- [ ] Commit.

### Task 5: Make V6 an hourly read-only incident learner

**Files:**
- Modify: `scripts/kesher_content_controller_v6_runtime.py`
- Modify: `.github/workflows/kesher-content-controller-v6.yml`
- Modify: `tests/test_kesher_v6_intervention_isolation.py`

**Interfaces:**
- Consumes a V5 durable state snapshot.
- Produces a read-only shadow recommendation/parity report; never dispatches or uploads.

- [ ] Add a V5-state incident retrospective helper that reports current identity, strike, owner/action recommendation and A+B+C parity.
- [ ] Add CLI support to analyze a provided V5 state JSON file.
- [ ] Assert all V6 mutation flags remain false in output and tests.
- [ ] Add an hourly staggered schedule to the V6 workflow; fetch `automation-state` read-only and write only a job summary.
- [ ] Run V6 tests and self-check.
- [ ] Commit.

### Task 6: Full verification and PR

**Files:**
- No new production files unless verification reveals a scoped defect.

**Interfaces:**
- Produces one reviewable stabilization PR.

- [ ] Run targeted Python unit tests for intervention, Jules repair, V6 and controller stability.
- [ ] Run repository Kesher stability/CI commands used by `.github/workflows/kesher-stability-pr.yml` and `ci.yml` where available.
- [ ] Review diff for no provider/upload weakening, no new secret exposure and no V6 production permissions.
- [ ] Open PR `Stabilize Kesher supervision: Controller → Jules → Direct`.
- [ ] Wait for GitHub CI/Stability/V6 shadow checks; inspect failures and repair only the failing scope.
- [ ] Merge only after required gates are green.