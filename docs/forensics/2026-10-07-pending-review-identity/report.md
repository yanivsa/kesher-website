# Exact Video Overview item binding — recovered 2026-10-07

Recovered worktree: `/Users/ninja/.codex/worktrees/pending-review-exact-item-20261007/Kesher`.
Branch: `fix/pending-review-exact-item-binding-20261007`.
Starting HEAD/main: `ac9eac28f4d7d6e4f89fca5e16bfa50014a7c84f`.
The five modified implementation files and original untracked 17-test regression file survived the power loss. No reset, discard, replacement worktree, branch recreation or stabilization-branch edit occurred.

## Root cause and contract

The initiating artifact ID was discarded between generation, pending detection, evidence preparation, review and upload. Each stage independently searched state: the first same-source active item, a global pending list, an oldest unresolved item, or a newest-date upload candidate. A missing requested ID could become `None` and permit a fresh generation.

Existing generated-artifact operations now resolve the exact ID uniquely using existing canonical `id`, source slug/content SHA, `type`, and `fresh_generation_attempt`. The canonical adapter also retains its command source/kind and immutable item/attempt checks. There is no new stored identity format. Missing/duplicated IDs, wrong source/kind/attempt and ambiguous existing artifacts refuse explicitly. Neither list order nor timestamps resolve artifact ambiguity.

Generation can establish an initial binding only from a unique active artifact or its own newly created item. Unknown active kinds fail closed. Explicit missing/terminal IDs never fall through into replacement generation. Requested content is checked before new provider work. The selected ID/content/attempt is exported for later workflow steps.

Review decisions are revalidated against the exact current immutable evidence before recording. Jules remains advisory; the independent technical and public-delivery gates remain in force. Existing YouTube IDs and resumable receipts are recovered on the same item; no second insertion is introduced.

## Caller audit

| Caller | Authoritative identity and behavior |
| --- | --- |
| `kesher-daily-video.yml` generate/full | Dispatch identity when provided; otherwise the exact creation/resume result exported by the pipeline. Pending detection resolves that ID. |
| Daily Overview rebuild | Explicit rebuild ID plus requested source fields; exact rebuilt item exported for subsequent steps. |
| `prepare_jules_video_evidence.py` | Required CLI item ID from the pending step; copies only that item's hashed evidence. |
| `jules_video_reviewer_v3.py` → legacy reviewer | Required CLI item ID from the same pending step. The adapter delegates to the stricter selector. Prompt, decision and returned hashes remain bound to that ID. |
| Reviewer → official pipeline review recording | The exact reviewed ID, source/content/attempt and revalidated hashes; no global error fallback. |
| Overview upload reconciliation → upload | Dispatch or creation/resume ID plus source/content. Overview uploads require an exact binding even outside the workflow's media-mode setting. |
| `kesher-targeted-media-recovery-dispatch.yml` | An explicit `target_item_id` on the recovery request, verified source SHA and exact upload operation. Missing Overview binding refuses instead of invoking full generation. Short dispatch remains unchanged. |
| `kesher_exact_video_target.py` / backlog handoff | Unique exact source/content artifact or its own creation result; multiple exact artifacts refuse. Selected ID exported into the child dispatch. The backlog workflow remains retired. |
| Stabilized V5 controller | Previously known exact snapshot item; duplicate unresolved same-source items require an initiating ID. Existing generating/rejected/pending items retain their binding in dispatch. |
| V5 backlog runtime | Previously selected unique exact unresolved item; forwards ID/source/content instead of rediscovering from FIFO. |
| Canonical `media_worker.py` | Already passes its canonical item's ID and source to upload; the new resolver also checks its bound command and attempt. No attempt-transition or provider logic changed. |
| Short pipeline/workflow | Native type and exact exported creation/resume identity are retained; existing Short policy, source/audio, provider receipts and attempt-transition tests remain green. |
| Retired final-attempt/gifted/current-gifted/live-E2E recovery paths | Existing sentinel job guards remain unchanged. Source-only calls cannot use the stricter existing-artifact upload boundary. No retirement is undone and no voice-fallback algorithm is absorbed. |
| Exact marshmallow resume/upload and evidence-repair workflows | Already supply explicit item/source identity into the daily bridge or use an exact repair ID; downstream propagation retains it. Their retired guards remain unchanged. |

## Tests and review

Original RED: 17 tests, 17 assertion failures, zero errors, before production edits. After recovery the original regression file was unchanged. The same failures were reproduced against an isolated archive of base main; the partial implementation already passed those 17 tests.

Additional RED/GREEN cycles exercised the workflow's actual pending-selection script, locally captured recovery dispatch arguments, controller handoff, attempt export, changed returned-review evidence, mode-independent Overview refusal, requested source SHA, and unknown-kind duplicate prevention. External calls in tests use isolated fixtures or fakes, never production APIs.

Current checks: 28 exact identity/caller tests pass; repository `npm run test:video-policy` passes 245 tests; focused media/controller safety passes 84. Actionlint 1.7.12 and `git diff --check` pass. No content, generated media, assets, provider credentials, workflow permissions, production state or live session changed.

Self-review found and fixed mode-independent CLI fallback, missing source-hash admission before new generation, loss of the generation attempt, current-evidence drift before recording a returned decision, and an unclassified active artifact being ignored. Same-source fixtures contain multiple items; both the historical hug slug and a generic slug use the same invariant. GitHub run attempts are never media-generation identity. `UNPROVEN_MEDIA_ATTEMPT_TRANSITION` remains in force.

The broad Python gate ran 1,206 tests, with zero skips and the repository's eight explicitly retired compatibility-contract tests excluded as declared in `tests/kesher_daily_pipeline_suite.py`. It is blocked by existing main authority/B-roll failures; exact failing test IDs are recorded in `validation.json`. The clean-main reproduction below records the exact authority failures, including the earlier unclassified-definition refusal.

## Authority and baseline limitation

Only hash leaves for intentionally changed task files were recertified. Workflow roles, registrations, dispatch inputs/scopes, resource/capability assignments, credentials and authority code were preserved. All task-file pins match their actual bytes. Five stale pins already on unchanged main were left untouched:

- `tests/test_kesher_optional_video_enrichment.py`: two call-chain pins.
- `.github/kesher-media-recovery-request.json`: one call-chain pin.
- `.github/workflows/kesher-short-v4.yml`: two child dispatch-definition pins.

Both unchanged main B-roll workflows declare `KESHER_BROLL_ENABLED: "false"`. PR #1073 merged at `8df5219f3ce60c70487927721e7a43caec8eced5` intentionally changed the Overview and Short flags from true to false and added a regression requiring false. The old production-contract assertion at `tests/test_production_contract_v3.py:77` still expects true. This task preserves that assertion and all B-roll behavior. PR #1081 covers nine baseline hash leaves but misses the targeted dispatcher self call-chain pin and does not resolve the B-roll assertion or unclassified one-off workflow. It was inspected read-only, not absorbed, updated or merged.

## PR #1071

Its generic exact-upload routing is superseded by this fix. The concrete historical request binding to `video-20261006-132152-043ca12425` is an outcome action; this fix intentionally does not add that ID to the recovery request or execute recovery. Therefore the entire PR is **not automatically redundant**. Its one-asset binding can be considered separately after the root fix; no timestamps or new artifacts should substitute for that identity. PR #1071 was neither modified, closed nor merged.

The user authorized publishing the root fix after baseline reproduction and focused GREEN revalidation. The final commit/remote identity is recorded by the branch and draft PR. Full authority certification remains blocked by the documented main baseline; no full-gate GREEN, merge readiness or production activation is claimed.

## Clean-main baseline proof and publication boundary

A separate clean managed worktree at `/Users/ninja/.codex/worktrees/pending-review-baseline-ac9eac28/Kesher` was created at exact `origin/main`, `ac9eac28f4d7d6e4f89fca5e16bfa50014a7c84f`. HEAD and origin/main matched; status was empty before and after the checks. No baseline file was edited.

The five exact policy-leaf checks plus the unchanged B-roll test ran as six tests: six expected assertion failures, zero errors, zero skips. Every selected recorded policy leaf and referenced file is byte-identical between pristine main and the pending-review worktree. The B-roll test method is byte-identical too (SHA-256 `cf68b8a5f4b7edb7777e4cf2c21959f6ceace6fd4b99c2641327169eed0404d8`). These six blockers are BASELINE.

All five locations below are under `scripts/kesher_runtime/authority_policy.json`, `workflows[workflow]`:

| Workflow | Exact review leaf | Recorded SHA-256 | Actual SHA-256 |
| --- | --- | --- | --- |
| `.github/workflows/ci.yml` | `review.call_chain["tests/test_kesher_optional_video_enrichment.py"]` | `0f7ab8acf5b6853102955875698d0bff794fb0153da7188b80d53d2bfb1fb270` | `b3441e378fb45123fc584557ced7d1b31b0a0a70bc1af3804196bca36425cca8` |
| `.github/workflows/kesher-content-controller-v6.yml` | `review.call_chain["tests/test_kesher_optional_video_enrichment.py"]` | `0f7ab8acf5b6853102955875698d0bff794fb0153da7188b80d53d2bfb1fb270` | `b3441e378fb45123fc584557ced7d1b31b0a0a70bc1af3804196bca36425cca8` |
| `.github/workflows/kesher-targeted-media-recovery-dispatch.yml` | `review.call_chain[".github/kesher-media-recovery-request.json"]` | `3287651fefef6a0a5e919ac9a8b1540884709f034ddce963b9832c118d96ecd9` | `a27033e1a08ac82a14d86bac3e2e0b6e4760c02adb9fc8b777668228c233b540` |
| `.github/workflows/kesher-goal-dispatch.yml` | `review.dispatch_bindings[".github/workflows/kesher-short-v4.yml"]` | `f21516f2123a9b37a152513c25153364dcfd7bf5d94e8ba850a274d2705fba26` | `8101ca37c4c733ba7d7c5c8155cba23e13dcd94c4f3d4eb6fb4b8e2c9da8f58b` |
| `.github/workflows/kesher-targeted-media-recovery-dispatch.yml` | `review.dispatch_bindings[".github/workflows/kesher-short-v4.yml"]` | `f21516f2123a9b37a152513c25153364dcfd7bf5d94e8ba850a274d2705fba26` | `8101ca37c4c733ba7d7c5c8155cba23e13dcd94c4f3d4eb6fb4b8e2c9da8f58b` |

The exact stale B-roll assertion is `self.assertIn('KESHER_BROLL_ENABLED: "true"', workflow)` in `ProductionContractV3Tests.test_free_stock_secrets_are_scoped_to_render_steps`, line 77. The method checks Overview then Short; it fails on Overview first. Both workflows contain false at the job and render-step levels. The intentionally disabled behavior is proven by PR #1073's actual merge diff, rather than inferred from timestamps.

Only the 12 exact test methods responsible for the previous broad-gate failure/error entries were additionally run. Pristine main produced seven failure entries and fourteen error entries; the pending branch produced seven failure entries and ten error entries. All seventeen pending entries have the same test/subtest IDs and exact terminal exception signatures on pristine main. The B-roll assertion signature omits the surrounding whole-workflow dump because the pending identity propagation intentionally changes other workflow bytes; the assertion method itself is exactly identical.

Main also has five other stale hash leaves: four daily-video child dispatch pins and the targeted-dispatcher's self call-chain pin. This task changes those workflow files, so their task-specific resulting hashes were already recertified as part of the existing 136 hash-only updates. The unrelated five selected stale leaves remain unchanged. Pristine main additionally contains `.github/workflows/kesher-exact-short-metadata-recovery-20261006.yml`, introduced by `ac9eac28`, absent from the policy's workflow set. Its bytes and policy absence are identical on both branches, and `AUTHORITY_UNCLASSIFIED_DEFINITION` remains fail-closed. This masks later pin failures in aggregate checks and is documented as an additional baseline blocker, not hidden behind a six-only claim.

After reproduction, the root branch was revalidated: 28 exact identity/caller tests, 245 video-policy tests, and 84 media/controller safety tests passed. Actionlint and `git diff --check` passed. No full expensive matrix was repeated and no tests/assertions were weakened. The evidence is in `baseline-reproduction.json`; `reproduce-baseline.py <clean-main-worktree> <pending-worktree> <outside-output.json>` repeats only the selected pin/B-roll checks and exact affected consumers. It requires clean exact main before and after.

## Proposed separate baseline-fix scope — not implemented here

For the six specified remaining blockers, the minimum separate commit changes only `scripts/kesher_runtime/authority_policy.json` and `tests/test_production_contract_v3.py`: refresh the five selected existing review hash leaves to their actual reviewed bytes, change only the stale enabled-B-roll assertion to require false while retaining credential scope and budget assertions, and recertify every existing call-chain pin for the changed test file. Do not enable stock B-roll or change credentials, dispatches, workflows, providers, roles or capabilities for these six corrections.

For that separate PR to make pristine current main's complete authority inventory green, it must also address the independently proven additional baseline: refresh the other five stale current-main hash leaves and independently review the one-off Short metadata workflow's real mutation authority. That workflow cannot be silently allowlisted; its metadata writer and credential use require an explicit policy/retirement decision with regression coverage. PR #1081 already covers nine of main's ten stale leaves and can avoid a competing hash-only PR if its owner extends/reconciles it. No change to that PR or workflow is made here. Recompute hashes against the eventual combined exact tree, preserving this task's new workflow bytes.

Validate the separate change with the exact stale B-roll method, the PR #1073 disabled-B-roll regression, authority-topology/three-dispatcher/production-cutover suites, complete call-chain/definition/dispatch hash enumeration, and `git diff --check`. The broader required gate remains a merge prerequisite after baseline repair.

INTERRUPTED LOCAL WORK WAS PRESERVED; NO MEDIA GENERATION/UPLOAD; NO JULES/MASTER-SUPERVISOR/PRODUCTION/CUTOVER MUTATION; PR NOT MERGED.
