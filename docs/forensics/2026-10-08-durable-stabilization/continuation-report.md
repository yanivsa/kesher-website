# KESHER durable stabilization — refreshed completion evidence

## 1. RECONCILIATION

Current main: `ac9eac28f4d7d6e4f89fca5e16bfa50014a7c84f`. Same worktree and branch: `codex/kesher-autonomous-stabilization-20260917`. Initial local and remote head: `38bae366d2388eec3f6c0648dcd1602558258279`, clean. Exact historical checkpoint `15297dde7acf8ee9a4507f2c87435a050900ba71` exists. Main remains the merge base; initial divergence was main0/branch51 commits. The repeated request is byte-identical to the October7 attachment.

The existing completed implementation and semantic main reconciliation were reused, including Native Fence/control-plane work and exact-item review binding. No reset, rebase, replacement implementation, new branch or new main integration was needed. All683 prior certified inputs matched before editing. Current129 GitHub registrations have identical ID/path/state tuples to the prior inventory. Relevant open automation PRs include1085,1084,1082,1081,1074,1071 and1056; exact heads are recorded in `github-readback.json`. PR1083 is now closed/unmerged; its owner explicitly declared1085 the replacement.

Fresh live evidence exposed a bounded V6 defect: closed PR failures still became current approval blockers. Only `scripts/kesher_v6_production_shadow.py`, `tests/test_v6_production_shadow.py` and six SHA leaves in `scripts/kesher_runtime/authority_policy.json` changed. All non-hash authority semantics are unchanged. Implementation commit: `930d41a4aa8428320a98bf64c9e7fc73275a1b1b`. An evidence-only checkpoint follows; its exact final branch/remote SHA is read back after push in the operator report.

## 2. ROOT CAUSES FIXED

Existing fixes were preserved and freshly regression-tested:

- `IMAGE_CATALOG_EXHAUSTED`: `.github/scripts/article-image-worker-v4.py` uses the third existing supported generation slot for a fresh owned/context-specific hero after provider/catalog exhaustion. Dimensions, type, unique pixels/hash, semantic rules, deterministic naming, cooldown/lifetime rules and total three-generation budget remain. Regression: `tests/test_image_catalog_replenishment.py` (automatic validated replenishment; duplicate and semantic refusals).
- `VOICE_PITCH_REJECTION_LOOP`: `scripts/kesher_daily_pipeline.py` persists item-local attempts and refuses stale counter/receipt regression; `scripts/kesher_video_reconcile.py` derives replacement attempts from durable receipts and revalidates the same usable final-attempt artifact under the existing male-fallback policy. First two pitch rejections remain strict; no fourth voice regeneration or counter leakage. Regression: `tests/test_voice_attempt_durability.py`. Unrelated generic technical retry budgets were not redesigned.
- `UNBOUND_JULES_REVIEW_SELECTION`: `scripts/jules_video_reviewer.py` and `.github/workflows/kesher-daily-video.yml` require slug+content SHA before selection/API use; reused exact item/source/kind/attempt binding protects lookup, result reuse and resume. Regression: `tests/test_jules_dual_identity.py`, with existing exact-item suites retained.
- `AUTHORITY_SHA_DESYNC`: `scripts/kesher_runtime/sync_authority_policy.py` supplies deterministic offline atomic update and write-free verification; `.github/workflows/ci.yml` checks stale pins without recertifying production. `scripts/kesher_runtime/authority_policy.json` remains pinned and denied where live separation is unproven. Regression: `tests/test_authority_policy_sync.py` (matching/stale/update/idempotence/unsafe inputs).

Additional V6 regression: `test_closed_unmerged_pr_is_stale_not_an_approval_blocker` and `test_merged_pr_historical_failure_does_not_block_current_delivery`. Both failed on the previous implementation before correction. Closed/unmerged exact-target PRs now report `stale_pr`; closed checks remain historical evidence; only open exact-head failures create a current check blocker. Open approval gates and exact source/head checks remain intact.

## 3. WORKFLOWS RETIRED

The existing four verified sentinel deletions remain: `kesher-exact-marshmallow-video-resume.yml`, `kesher-exact-marshmallow-video-upload-recovery.yml`, `kesher-repair-exact-video-state.yml`, `kesher-video-evidence-repair.yml`. Exact source archives and registration evidence are retained in the October7 evidence directory. No workflow definition changed in this continuation.

Canonical media/recovery/V6 workflows remain. The active current-main `kesher-exact-short-metadata-recovery-20261006.yml` and three historical dated OCI workflows retain exact-hash governance exceptions; exceptions grant no authority. All58 retained missing-definition identities, including the four observed owner registrations, remain unresolved/denied. Deleting source has not remotely disabled or fenced these actors. No live registration/credential mutation occurred.

`scripts/kesher_runtime/workflow_governance.py` and `config/kesher-workflow-governance.json` continue rejecting new date/slug/PR-specific rescue definitions. Fresh governance and action lint pass.

## 4. MASTER SUPERVISOR CHANGES

Existing `config/kesher-production-contract.json` and `scripts/kesher_master_supervisor_live.py` are unchanged in this continuation. Stable fingerprint: component+failure_class+state_stage. One persisted rescue, seven-day recurrence escalation to generic component-owner correction+deterministic regression, no third symptom rescue. Delivery leaves the defect awaiting a merged generic correction. Legacy S3 merge/executor paths refuse; V6/V5 recommendations are compared. No duplicate spec, scheduler activation or master-supervisor production mutation. Fresh focused/full tests cover this contract.

## 5. V6 SHADOW

The observer reads exact current-main catalogs/Git blobs, the automation-state ref, exact PR/head checks/runs, retained canonical media archives, the expected public article route and optional authorized YouTube metadata/geometry. It diagnoses missing public assets, state lag, orphaned state, stale PRs, current blocked checks and upstream-complete/downstream-waiting drift. It preserves exact source identities and never substitutes timestamp-nearest evidence.

Actual post-correction observation made20 external GET requests. Article source absent from exact main; route HTTP404; Overview/Short exact identities remain unproven. V5 state remains schema5/October4/article_image_running, target-unbound. PR1083 is closed/unmerged. Drift: `orphaned_state`, `stale_pr`; recommendation: `reconcile_authoritative_state`, replacing the obsolete approval recommendation. See `live-v6-shadow.json`; the pre-correction observation is retained separately.

Transport rejects non-GET methods and unauthorized repository/credential hosts; signed archives do not receive GitHub authorization headers. Existing workflow permissions remain read-only and checkout credentials are not persisted. Mutation-refusal/input-immutability/exact-identity tests pass. `production_dispatch_enabled=false`, `production_state_written=false`, `provider_dispatch_enabled=false`, `upload_enabled=false`, `public_completion_inferred=false`. Both media observations retain `producer_lineage_proven=false`. No generation/upload/OAuth refresh/workflow dispatch/state write occurred. Closed5.2 evidence and all three quarantines are unchanged.

## 6. VERIFICATION

Fresh commands/results:

```text
python3 -B /tmp/run-kesher-full-python-20261008.py
1321 tests; 0 failures/errors/skips; PASS (102.329s)

python3 -B -m unittest tests.test_image_catalog_replenishment tests.test_voice_attempt_durability tests.test_jules_dual_identity tests.test_authority_policy_sync tests.test_master_supervisor_learning tests.test_workflow_recovery_governance tests.test_v6_production_shadow tests.test_kesher_v6_intervention_isolation -v
57 tests; OK

python3 -B -m unittest tests.test_v6_production_shadow -v
17 tests; OK

python3 -B scripts/kesher_runtime/sync_authority_policy.py --check
matching; zero stale pins

python3 -B scripts/kesher_runtime/workflow_governance.py
failure_class=null; paths=[]

/Users/ninja/.codex/tmp/kesher-tools/actionlint-1.7.12/actionlint -shellcheck= -pyflakes=
PASS

git diff --check origin/main...HEAD
PASS
```

The full runner reuses the repository compatibility suite's eight explicitly retired mirror contracts; all exclusions are listed in `validation.json`, with canonical replacements included. No additional exclusions/skips/assertion weakening. Reproduction runner: `verification-runner.py.txt`.

Previous `npm run check` certification remains recorded, including content/lint/typecheck/build/prerender/distribution/frontend152/browser140. It was not rerun this continuation: exact main, content/frontend/build inputs remain unchanged; the three changed Python/policy inputs were recertified by the full Python suite. New683-input manifest SHA256: `854882a6ca44b0764018ee694d5275baeb41bcb7262b96802c948f49d161b04d`; implementation-commit mismatches0. No independent-agent review or final-head remote CI certification claimed.

## 7. PR #1083 CURRENT STATE

Read-only: CLOSED, non-draft, unmerged, head `ce749b46629b6c5674f3309c4b4d28a42f9e115e`, base current main. Owner closed it at2026-10-07T16:38:23Z and explicitly replaced it with PR1085. The old CI37633442328/Stability37633442326 runs now show failure, each with zero jobs; current rollup contains skipped merge/cleanup checks. Approval/rerun/merge of1083 is not the next action. The API still does not independently establish the exact historical security-trigger cause.

Replacement1085 is OPEN/non-draft/unmerged, head `fbf2c13f3d2426e6c4afab1fb8773d5928bc44b1`. Stability validation/render-proof pass; CI37653677701 fails during Schema-6 cutover safety:229 tests,1failure/4errors (`AUTHORITY_DISPATCH_BINDING_INVALID`, `AUTHORITY_UNCLASSIFIED_DEFINITION`). Exact main Git objects show the unclassified Short-metadata workflow and six stale child-definition hash leaves; see `main-authority-readback.json`. The stabilization policy already handles these conservatively and its full suite passes. No1083/1085 PR mutation or bypass was performed.

## 8. GIT RESULT

Correction commit `930d41a4aa8428320a98bf64c9e7fc73275a1b1b`; refreshed evidence/WORK_LOG checkpoint follows. Publication uses a normal fast-forward push to the same stabilization branch. Exact remote head and clean local status are independently verified after push and returned in the operator report. No force push, new branch/PR or main/GitHub PR merge.

## 9. REMAINING RISKS

The stabilization changes remain unmerged/inactive; final-head remote CI has not been certified. PR1085 is blocked by current-main authority errors. Real exclusion/drain of active retained/legacy mutation authorities is still required before any future cutover; this observation grants no live admission. Exact public media producer identities remain unproven; all existing5.2 quarantines persist. Image replenishment still depends on a healthy supported provider and acceptable pixels, failing closed otherwise. The broader production-cutover Goal is not complete.

## 10. NEXT RECOMMENDED ACTION

Review the pushed stabilization branch's authority correction for integration into main before revisiting PR1085's failed CI. Do not reopen/approve PR1083 or merge any candidate on local evidence alone.
