# Kesher Pipeline V4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make daily Kesher article publication self-healing and deterministic, then produce at most one downstream YouTube Short per article without allowing video failures to block the article.

**Architecture:** `kesher-content-controller` remains the sole orchestration owner. Jules owns article text and advisory video review only. GitHub Actions owns article normalization, generated publication files, image validation, CI recovery, merge/deploy, Short production, technical verification, retry budgets, and YouTube idempotency. Article success becomes durable at `article_live`; Short work is downstream and may end as `article_complete_without_short`.

**Tech Stack:** Python 3.12, GitHub Actions, GitHub REST API, Node 22, Vitest/unittest, NotebookLM CLI, ffmpeg/ffprobe, Remotion, YouTube Data API.

**Spec:** `docs/superpowers/specs/2026-09-03-kesher-article-short-pipeline-design.md` (design branch/PR #659 until merged).

## Global Constraints

- Production contract is canonical; runtime adapters may not contradict it.
- Jules writes/repairs article text only; deterministic repair is owned by GitHub Actions.
- Every article PR must pass the article contract even when full CI is selected.
- Article hero image is required and publication-blocking.
- Short failures never roll back or block a live article.
- One article identity (`slug + content SHA`) may produce at most one authoritative public YouTube Short.
- Short technical gate blocks upload; Jules review is advisory.
- Video/Short creation has a hard 5-attempt budget. If no usable Short exists after attempt 4 (the penultimate attempt), stop without attempt 5 and mark the article `article_complete_without_short`. Attempt 5 is reserved only for recovery of an already-created artifact/upload identity, never for a fresh semantic/video generation.
- No duplicate NotebookLM generation, Remotion final, upload session, or YouTube insert may be created when a persisted identity can be resumed.

---

### Task 1: Canonical article publication contract

**Files:**
- Create: `scripts/kesher_article_contract.py`
- Modify: `.github/scripts/select-ci-profile.py`
- Modify: `.github/scripts/validate-article-pr.py`
- Modify: `.github/scripts/article-pr-controller.py`
- Test: `tests/test_ci_profile.py`
- Create: `tests/test_kesher_article_contract.py`

**Interfaces:**
- Produces `ARTICLE_PUBLICATION_PATHS`, `ARTICLE_IMAGE_PREFIX`, `is_article_publication_path(path)`, `forbidden_article_paths(paths)`.
- All article selectors/controllers import the same definitions.

- [ ] Add failing tests proving `public/rss.xml` is an article publication path and unknown paths force full CI.
- [ ] Run `python -m unittest tests.test_ci_profile tests.test_kesher_article_contract -v` and confirm failure before implementation.
- [ ] Implement shared contract module and replace duplicated path lists.
- [ ] Re-run tests and confirm green.

### Task 2: Deterministic article normalizer before Jules repair

**Files:**
- Create: `scripts/kesher_article_normalizer.py`
- Modify: `.github/scripts/article-pr-controller-v3.py`
- Modify: `.github/workflows/auto-merge-article-prs.yml`
- Create: `tests/test_kesher_article_normalizer.py`

**Interfaces:**
- `extract_target_article(base_posts, head_posts, slot) -> dict`
- `normalized_posts(base_posts, article) -> list[dict]`
- `classify_normalization(base_posts, head_posts, slot, changed_paths) -> NormalizationDecision`

- [ ] Add failing tests for a #582-style branch: many unrelated changes plus one target article must normalize to current-main posts plus exactly that article.
- [ ] Add failing test proving existing main articles are byte/structure preserved and cannot be deleted by normalization.
- [ ] Run the normalizer tests and confirm expected failures.
- [ ] Implement pure normalization helpers.
- [ ] Integrate the PR controller so deterministic scope/generated-file/Git drift is repaired before any Jules semantic repair attempt.
- [ ] Keep the same PR/branch and never create a replacement PR.
- [ ] Re-run unit tests.

### Task 3: Always-on article contract gate and exact-head CI recovery

**Files:**
- Create: `.github/scripts/validate-article-contract-local.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/auto-merge-article-prs.yml`
- Create: `tests/test_article_contract_local.py`

**Interfaces:**
- Local gate consumes base SHA/head checkout/changed paths and validates exactly one new article and image identity.

- [ ] Add failing tests proving an article PR still runs article validation when general profile is `full`.
- [ ] Add failing tests proving stale verify success from an older SHA is rejected.
- [ ] Implement local article gate invocation in CI independent of profile selection.
- [ ] Preserve full `npm run check` for mixed/code changes.
- [ ] Keep explicit `workflow_dispatch` recovery for Actions-authored commits with no PR job; require fresh verify on exact head SHA.
- [ ] Run CI-profile and article-gate tests.

### Task 4: Image worker hard guarantee and collision-safe fallback

**Files:**
- Modify: `.github/scripts/article-image-worker-v4.py`
- Modify: `.github/workflows/kesher-article-image.yml`
- Modify: `scripts/kesher_content_controller_v3_best_effort.py`
- Modify: `config/kesher-production-contract.json`
- Test: existing image worker tests; add targeted fallback tests if absent.

**Interfaces:**
- Local fallback validates dimensions and SHA before returning a candidate.
- If all curated bytes collide, create a deterministic transformed variant with ffmpeg/Pillow-equivalent trusted tooling before commit.

- [ ] Add failing test where every topic-matching local candidate collides with an existing hero.
- [ ] Add failing test for undersized candidate.
- [ ] Implement deterministic transformed fallback and validate result before branch mutation.
- [ ] Remove best-effort semantics that allow image-less article merge; image terminal failure remains retryable/blocking for article only.
- [ ] Run image and contract tests.

### Task 5: Jules contract tightening

**Files:**
- Modify: `scripts/jules_article_runner_v3.py`
- Modify: `.github/scripts/article-pr-controller-v3.py`
- Modify: `.github/prompts/jules-remotion-video-upgrade.md`
- Test: `tests/test_production_contract_v3.py` (renamed/updated for v4 as needed), article runner tests.

**Interfaces:**
- Jules article prompts prohibit Git repair/generated-index/image/workflow work.
- Jules repair receives only semantic content errors after deterministic normalization.
- Video review remains advisory and may request rebuild of exact existing source only.

- [ ] Add failing prompt-contract tests for forbidden Jules responsibilities.
- [ ] Update prompts/runners to make ownership explicit.
- [ ] Ensure image/Git/CI failures never consume a Jules content-repair attempt.
- [ ] Run Jules contract tests.

### Task 6: Contract/state V4 and bounded Short lifecycle

**Files:**
- Modify: `config/kesher-production-contract.json`
- Modify: `scripts/kesher_automation_policy.py`
- Modify: `scripts/kesher_content_controller_v3_entry.py` or introduce the minimal v4 adapter
- Modify: `scripts/kesher_content_controller_v3_best_effort.py`
- Create/modify: controller state-machine tests.

**Interfaces:**
- Contract fields: `short.max_generation_attempts = 5`, `short.release_without_short_after_failed_attempt = 4`, `short.fifth_attempt_recovery_only = true`.
- State terminal: `article_complete_without_short`.

- [ ] Add failing state-machine test: article remains live after any Short failure.
- [ ] Add failing test: fresh Short generation is allowed for attempts 1-4 only.
- [ ] Add failing test: after failed attempt 4 with no usable artifact, controller marks `article_complete_without_short` and never dispatches attempt 5.
- [ ] Add failing test: attempt 5 may resume an existing NotebookLM task/upload session/YouTube ID, but may not start a new generation.
- [ ] Implement schema migration and the bounded lifecycle.
- [ ] Run controller/policy tests.

### Task 7: NotebookLM-derived 9:16 Short production

**Files:**
- Modify: `scripts/kesher_daily_pipeline.py`
- Modify: `scripts/kesher_video_reconcile.py`
- Modify: `src/remotion/ArticleShort.tsx`
- Modify: `src/remotion/Root.tsx`
- Modify: `.github/workflows/kesher-daily-video.yml`
- Add/modify: video pipeline and Remotion tests.

**Interfaces:**
- Persist `source_mode`: `direct-short` or `overview-segment`.
- Persist raw NotebookLM source identity and final Short SHA.
- Final Short target 1080x1920, 30-55 seconds, original NotebookLM audio.

- [ ] Add failing tests for direct-short capability selection/fallback.
- [ ] Add failing tests for 9:16 geometry, duration range, and audio preservation.
- [ ] Implement capability probe. Prefer direct short-form NotebookLM only when deterministically supported; otherwise use existing Overview as source.
- [ ] Implement contiguous 30-55 second semantic segment selection for long source.
- [ ] Convert `ArticleShort` from static card to source-video composition with minimal Hebrew branding/CTA and no generic subtitles.
- [ ] Ensure technical gate is the only publication blocker and Jules remains advisory.
- [ ] Run video tests.

### Task 8: YouTube idempotency and FIFO backlog

**Files:**
- Modify: `scripts/kesher_video_reconcile.py`
- Modify: `scripts/kesher_daily_pipeline.py`
- Modify: controller tests and upload guard tests.

**Interfaces:**
- Identity key is article slug + content SHA.
- Existing provider task/artifact/upload session/YouTube ID always resumes before any new operation.

- [ ] Add failing duplicate-insert test for interrupted verification.
- [ ] Add failing FIFO backlog test showing yesterday's Short can resume while today's article still publishes.
- [ ] Implement recovery-first upload/generation selection.
- [ ] Verify public+processed YouTube result before `short_public`.
- [ ] Mark `article_complete_without_short` terminal without requeue when generation budget ends at attempt 4.

### Task 9: Full verification and migration cleanup

**Files:**
- Modify tests only unless verification reveals defects.
- Update spec/plan if actual API capabilities require a documented fallback.

- [ ] Run Python unit suites for contract/controller/image/video.
- [ ] Run `npm run check`.
- [ ] Run Remotion/video hermetic tests.
- [ ] Confirm production contract tests enforce V4 and reject old best-effort/image-less semantics.
- [ ] Open implementation PR; require CI and Stability green.
- [ ] Merge only after exact-head checks pass.
- [ ] Leave old compatibility layers in place only where still required; do not combine unrelated controller cleanup with functional V4 rollout.
