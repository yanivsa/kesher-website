# Kesher V5 Shared Video Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore regular YouTube video publication while ensuring one NotebookLM provider generation feeds both the long-form video and the Short for each article.

**Architecture:** Introduce a V5 controller state with separate `long_video` and `short` stages. Reuse the existing long-form workflow as the sole provider generator, add a Short `derive` path that adopts the exact long-form provider identity, and make controller completion require article + long-form + Short public verification.

**Tech Stack:** Python 3.12, GitHub Actions YAML, NotebookLM CLI, Remotion, GitHub Actions artifacts, YouTube OAuth/API.

**Spec:** `docs/superpowers/specs/2026-09-04-kesher-v5-shared-video-source-design.md`

## Global Constraints

- Exactly one provider generation identity per article (`slug` + `content_sha256`).
- Long-form owns NotebookLM generation; controller-owned Short production may only derive from that identity.
- Never duplicate an already verified public YouTube upload.
- Article publication is never rolled back by downstream video failure.
- V5 `complete` requires verified public article, long-form video, and Short.
- Revalidate durable state immediately before retry/rebuild/derive dispatch.

---

### Task 1: Add V5 controller contract tests

**Files:**
- Create: `tests/test_v5_shared_video_controller.py`
- Modify: `tests/test_v4_runtime_activation.py`

**Interfaces:**
- Consumes: existing V4/core controller test doubles.
- Produces: expected V5 state keys `long_video`, `short`; production ordering contract.

- [ ] **Step 1: Write failing tests** for: live article dispatches long-form first; verified long-form + missing Short dispatches Short derive; both public yields complete; existing verified Short + missing long-form preserves Short and dispatches only long-form; controller workflow listens to both child workflows.
- [ ] **Step 2: Run the targeted tests and verify RED** because V5 runtime/controller do not exist and V4 workflow excludes long-form.
- [ ] **Step 3: Commit RED tests only.**

### Task 2: Add shared-provider Short derivation

**Files:**
- Modify: `scripts/kesher_short_pipeline_v4.py`
- Modify: `scripts/kesher_video_reconcile.py`
- Modify: `.github/workflows/kesher-short-v4.yml`
- Modify: `tests/test_short_pipeline_v4.py`
- Modify: `tests/test_video_reconcile.py`

**Interfaces:**
- Produces: `derive` workflow operation that imports an exact provider identity (`source_id`, `task_id`, `artifact_id`, `source.slug`, `source.content_sha256`) from matching long-form durable state.
- Guarantees: derive path never calls NotebookLM `generate video`; absent/mismatched identity fails closed.

- [ ] **Step 1: Write failing derivation tests** proving exact identity adoption, slug/hash mismatch rejection, missing provider identity rejection, and no generation call.
- [ ] **Step 2: Run targeted tests and verify RED.**
- [ ] **Step 3: Implement minimal derivation/adoption helper** that seeds a Short state item from long-form state while preserving the current V4 creative/render/upload adapter.
- [ ] **Step 4: Add `derive` workflow input/step** that restores the newest trustworthy `kesher-video-state`, adopts the exact current article identity, then runs the Short adapter against that state.
- [ ] **Step 5: Run targeted Short/reconcile tests and verify GREEN.**
- [ ] **Step 6: Commit.**

### Task 3: Implement V5 controller state and orchestration

**Files:**
- Create: `scripts/kesher_content_controller_v5.py`
- Create: `scripts/kesher_content_controller_v5_runtime.py`
- Modify: `.github/workflows/kesher-content-controller.yml`
- Modify: `tests/test_v5_shared_video_controller.py`
- Modify: `tests/test_kesher_controller_queue.py`

**Interfaces:**
- State schema: `schema_version=5`, with independent `long_video` and `short` stages.
- Child workers: `kesher-daily-video.yml` for long-form; `kesher-short-v4.yml` with `operation=derive` for Short.

- [ ] **Step 1: Implement evidence-only V4→V5 migration**: adopt matching verified V4 Short; adopt matching verified long-form durable state; otherwise mark only the missing stage incomplete.
- [ ] **Step 2: Reuse the proven article/image flow**, then drive long-form to authoritative public verification before allowing Short derive dispatch.
- [ ] **Step 3: Implement independent active-run/retry/run-correlation fields** for `long_video` and `short`; do not share one `video` state slot.
- [ ] **Step 4: Implement terminal semantics**: `complete` only if all three outputs are verified; exhausted video stage remains blocked/incomplete, not `complete_without_short`.
- [ ] **Step 5: Update workflow event wiring** to wake on both `Kesher Daily NotebookLM Video Overview` and `Kesher Daily Article Short V4`, and execute `kesher_content_controller_v5_runtime.py`.
- [ ] **Step 6: Run V5 controller/queue tests and verify GREEN.**
- [ ] **Step 7: Commit.**

### Task 4: Add migration and duplicate-prevention regressions

**Files:**
- Modify: `tests/test_v5_shared_video_controller.py`
- Modify: `tests/test_v4_runtime_activation.py`

**Interfaces:**
- Validates current-production migration and stale-state behavior.

- [ ] **Step 1: Add tests** proving a verified current V4 Short is not re-uploaded, stale/mismatched long-form state is not adopted, active child runs are not duplicated, fast child completion maps to the correct stage, and stale derive inputs are revalidated.
- [ ] **Step 2: Run tests and verify RED where behavior is missing.**
- [ ] **Step 3: Add minimal V5 fixes until GREEN.**
- [ ] **Step 4: Commit.**

### Task 5: Full CI and rollout safety verification

**Files:**
- Modify only if verification exposes a defect.

- [ ] **Step 1: Run/verify targeted suites:** V5 controller, V4 runtime activation, Short V4, video reconcile, controller queue.
- [ ] **Step 2: Verify repository CI / stability / Short V4 checks on the PR.**
- [ ] **Step 3: Inspect the PR diff for unrelated files, accidental workflow permissions changes, or weakened safeguards.**
- [ ] **Step 4: Verify production semantics from code:** no controller-owned Short `full/generate` dispatch, exactly one provider generator, both workflow completion events wired, final completion requires both YouTube products.
- [ ] **Step 5: Merge only when all checks are green.**
- [ ] **Step 6: After merge, run one controlled production reconciliation for the current article. Expected: preserve existing verified Short; generate/publish only missing long-form.**
- [ ] **Step 7: Verify long-form is public + processing succeeded and no second Short/provider generation appeared. Only then declare ready for the next fresh-article end-to-end test.**
