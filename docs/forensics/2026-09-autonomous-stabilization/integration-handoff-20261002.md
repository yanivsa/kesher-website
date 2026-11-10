# Local integration recovery and finalization — 2026-10-02

This is an executable operator handoff for a **BLOCKED integration**, not a release, PR, activation, or authority approval. There is no further Codex continuation scheduled. The checkpoint branch contains exact final main plus non-ready evidence/recovery files. All unvalidated executable reconstruction edits are inside the checksum-verified archive, outside operational paths. The historical stabilization branch remains untouched.

## Verify the preserved checkpoint

From the candidate checkout:

```sh
cd /Users/ninja/.codex/worktrees/stabilization-transplant-v6/Kesher
python3 docs/forensics/2026-09-autonomous-stabilization/recover-integration-checkpoint.py
git status --porcelain
git diff --check
git log -1 --format='%H %s'
```

Verification checks every archived member, its byte length, SHA-256 and file mode. It performs no remote call, restored-code execution, provider action, deployment, production-state write or push. The archive SHA-256 is `c4dace067343700c448f1812d0d1027946115af2818558959d0fd9541fa3c7c6` and contains 253 pending files captured at the stop, including all 45 canonical runtime Python modules, the five canonical workers, combined tests, all source evidence, and the four subsequently generated article outputs. `unvalidated-tracked.diff.gz` records the raw tracked delta. The manifest is the authoritative member inventory.

To inspect the old draft in a separate fresh **local detached** checkout, explicitly choose a directory that does not exist:

```sh
python3 docs/forensics/2026-09-autonomous-stabilization/recover-integration-checkpoint.py \
  --restore-dir /Users/ninja/Documents/Kesher-worktrees/stabilization-transplant-unvalidated-recovery-20261002
```

This deliberately restores the raw draft at its historical base `833b8cea42f4344371b823bae4d9c1060a348b22`, not a publishable candidate. It disables checkout hooks and network protocols, rejects linked/outside paths, verifies restored bytes, and never runs the restored pipelines. The checkpoint branch and remote refs remain unchanged. Do not execute its workflows or provider entrypoints.

## One bounded implementation task

Finish controlled reconstruction against a newly fetched, exact final main, using the preserved raw draft only as comparison material. GPT-6.1 Sol / xhigh is the requested implementation/review model if an operator later has an authorized coding agent available. Do not rebase/cherry-pick/merge the 25 historical source commits. Preserve current-main-only content, assets, dependencies and runtime fixes; retain complete source modules and historical evidence; reconcile both sides of all 41 recorded overlaps. Do not blindly apply the old patch over current main.

### Exact newly arrived main delta

Start main was `833b8cea42f4344371b823bae4d9c1060a348b22`; preceding readback was `d2f92a93ef3e3f7966b35594e336e9707d5eba49`, commit “Use lightweight media state for KESHER Controller (#1009)”. It changes only:

- `.github/workflows/kesher-daily-video.yml`: upload a lightweight controller-state companion artifact and retain the newest three.
- `.github/workflows/kesher-short-v4.yml`: corresponding Short controller-state upload/retention.
- `scripts/kesher_content_controller_v5.py`: prefer the lightweight state, with durable full-state fallback on absent/broken/listing-failed companions.
- `tests/test_v5_shared_video_controller.py`: six new preference/fallback regression cases.

The exact patch is losslessly stored as `main-movement.diff.gz`; inspect it with `gzip -dc docs/forensics/2026-09-autonomous-stabilization/main-movement.diff.gz`. The tracked raw draft patch is also losslessly compressed so patch context blank-line prefixes retain their exact bytes. No whitespace rule is disabled. Refresh before reconstruction:

```sh
git fetch origin main
git rev-parse origin/main
git diff --name-status 833b8cea42f4344371b823bae4d9c1060a348b22 origin/main
git diff 833b8cea42f4344371b823bae4d9c1060a348b22 origin/main -- \
  .github/workflows/kesher-daily-video.yml .github/workflows/kesher-short-v4.yml \
  scripts/kesher_content_controller_v5.py tests/test_v5_shared_video_controller.py
```

The final readback advanced again to `839c9a8c15ede02956d02931cc55ac6bfd4b16a0` through four more commits: two Jules audit commits, the evidence-backed Compact Keywords landing system, and a Short V4 portrait-composition fix. The exact cumulative start-to-final patch is `final-main-movement-20261002.diff.gz`; all exact additional paths and commit SHAs are in `integration-checkpoint-20261002.json`. It includes scripts/content-policy.cjs, generate-sitemap.cjs, validate-content.cjs, kesher_short_pipeline_v4.py, src/App.tsx, BlogPost.tsx, SEO/layout/landing components and configuration, tests/vitest, posts/summaries and public feeds. Preserve these current-main changes. The recovery bundle intentionally remains captured at the earlier d2f92a93 readback.

The original four-file advance and this additional delta can be compared and reconstructed explicitly; neither was absorbed into the unfinished implementation. The raw draft also has the unfinished work below. Its reconciliation has not been performed or validated. Any additional advance must receive the same exact-byte review.

### Confirmed remaining reconstruction defects

1. Rebuild and independently review authority-policy and execution-input pins against the actual integrated byte graph. The archived policy has 15 definition mismatches and 54 distinct call-chain mismatches, union 67 paths. The full exact path list is in `integration-checkpoint-20261002.json`. Its canonical digest `0835c31e5f679c3159c561fe00c2a2e60a2349109dd6aef342409929a77377c2` is historical/unapproved for the raw reconstruction. Do not fix this by unexplained blind rehashing.
2. Add the missing `data-kesher-article-body` selector at the current-main body render expression without losing its sanitization/layout/CTA/direct-answer/image-credit behavior. The draft added hero/date selectors and signatureImageSrc provisionally; browser proof remains required.
3. Align the canonical article workflow's credentials and exact reviewed provider graph with current main: three distinct Gemini compositions, verified Pexels, verified Pixabay, concrete managed/seed fallback, no abstract placeholder, main's bounded local reuse and credit metadata. The raw canonical workflow still exposes retired Unsplash configuration and omits `PIXABAY_API_KEY`. Preserve one durable intent per external composition and never repeat an uncertain exact provider mutation.
4. Complete and validate the provisional metadata reconciliation: custom Overview/Short titles/tags/hooks, exact article/site/appointment URLs, actual-use stock attribution, and source-derived independent remote matching. Preserve all existing Hebrew, provenance, upload-capability and identity gates.
5. Integrate all source and current-main tests. Preserve the six #1009 cases and every newer main regression. Reconcile intentional main provider/reuse/metadata contracts explicitly. Remove or justify evaluator shims; do not synthesize successful old workflow text, skip tests, weaken refusals or hide newer regressions. The raw draft has no successful full integrated test result.
6. Preserve the existing main-ref/CAS/topology/epoch authority model and six-resource exclusion contracts. Any definition/registration/dispatch/execution-input/topology change after snapshot approval must block until readjudicated. Do not create a second authority store. The 100-active-registration read-only shape observation is dated evidence; its run listing was incomplete and proves no quiescence.

### Required final validation and review

After coherent reconstruction and actual policy review, run all required gates, retaining complete results:

```sh
pytest tests/
/Users/ninja/.codex/tmp/kesher-tools/actionlint-1.7.12/actionlint -shellcheck= -pyflakes=
npm ci --no-audit --no-fund
npm run check
git diff --check
```

`npm run check` must retain full browser/E2E results. Ensure the browser server serves the exact candidate build; do not reuse another checkout's server merely because its port responds. The Python test executable can come from an existing operator-managed environment; the run that established start-main baseline used `/Users/ninja/.codex/tmp/kesher-integration-20261002/venv/bin/python -m pytest tests/`.

Also run real policy/topology integrity plus the existing focused handover/exclusion/CAS, canonical worker admission/fail-closed, legacy schema-downgrade and closed-floor regressions. The archive carries all relevant source tests. Verify the five canonical workflows have only workflow_dispatch, required persisted command_id, claim before provider credentials/effects, and missing/invalid-command refusal. Keep deploy/controller/supervisor and the four reviewed one-offs inert in the reconstructed implementation; do not live-disable them.

Obtain the required bounded adversarial review of the completed executable integration, fix all confirmed Critical/Important issues, then perform a final main fetch/readback. This checkpoint's review approves the isolation/recovery boundary only, not the unfinished implementation. Preserve the closed 5.2 floor digest `5f2bb8d19b6ca3e9004d1e34997c9a55b05dea944f7ea901c1c33ff62a71df1c` and all three quarantines. No sealing, replacement artifact or inferred public completion is authorized.

Push and Draft PR remain conditional on all required integrated gates passing, a clean committed worktree, stable exact final main, explicit reconciliation with that SHA, and no reverted current-main-only change. Otherwise retain a correct documented local checkpoint. Do not merge, activate Schema 6, deploy, write production state, start provider jobs or perform live handover.
