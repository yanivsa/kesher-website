# Final-v9 attempt: blocked publication handoff and safe cutover runbook

Final verdict: **BLOCKED**. No final-v9 branch, push or Draft PR was created. The same `candidate/stabilization-final-v8` branch preserves all tested reconciliation and article-startup fixes in the same worktree. Latest tested main content is `7ae5b097e9be2dbe8e6287b1be9dfa2cdc9f6ac7`; last observed main advanced to `e79cccab32c046cc80a560ca43d0185b3b124f0b` with two commits and18 paths outside the permitted content/request/generated-only reconciliation. Existing v8 reports are historical; this report supersedes their remaining delta.

## Safe local readback

~~~sh
set -e
cd /Users/ninja/.codex/worktrees/stabilization-transplant-v6/Kesher
test -z "$(git status --porcelain)"
git rev-parse candidate/stabilization-final-v8
git log -1 --format='%H' -- docs/forensics/2026-09-autonomous-stabilization/final-v9-checkpoint-20261004.json
test "$(git merge-base HEAD e79cccab32c046cc80a560ca43d0185b3b124f0b)" = 1651fffd4bddba30b383b4c6f58636318699f2c9
git diff --check 1651fffd4bddba30b383b4c6f58636318699f2c9...HEAD
git diff --exit-code e79cccab32c046cc80a560ca43d0185b3b124f0b HEAD -- src/data/posts.json public/llms-full.txt .github/kesher-media-recovery-request.json .github/kesher-goal-request.json scripts/generate-llms-full.cjs remotion-kesher
gzip -dc docs/forensics/2026-09-autonomous-stabilization/final-v9-unreconciled-main-20261004.patch.gz | shasum -a 256
shasum -a 256 docs/forensics/2026-09-autonomous-stabilization/final-v9-validation-logs-20261004.tar.gz
~~~

Expected exact decompressed late patch digest: `e9fc136829e55b39618ac169084d19fd95477dc471fc01bfd30d2b8c6e71dba4`. Final checkpoint commit is the containing commit resolved above. The saved implementation commit is `6e48fbb7d01c7c4941558e67e90d0bccc0306990`. Neither this merge base nor validated implementation is exact latest-main rooted.

## Exact remaining local implementation slice — separately authorized future work

Coordinate a stable main window. Reconcile only the two recorded commits/18paths: preserve all public plugin files, its build/validator scripts and audit, current legal pages, main's prior-day PR immutable-blob inspection and regression. Semantically merge root package execution settings: add main's real plugin validator and packaging scripts while preserving the reviewed expanded safety suites and real unshimmed content evaluator. **Do not restore `tests/automation-gates-controller-shim.cjs` or its preload.** Main still carries that inherited shim; it must not replace the reviewed candidate evaluator. New executable bytes affect23 package callchain bindings,4 Jules-runner bindings and1 Jules-runner-test binding; review exact final roles/capabilities before refreshing only affected hashes. The new code was NOT reviewed or integrated by this continuation.

Recommended model for this one remaining local slice: GPT-6.1 Sol, xhigh. This run does not begin it.

The following preparation is for the recorded e79 case only and belongs to the separately authorized future slice. It preserves this complete checkpoint before trying the ONE net candidate transplant. A changed main or merge conflict stops for explicit classification and semantic review; never choose ours/theirs wholesale.

~~~sh
set -e
cd /Users/ninja/.codex/worktrees/stabilization-transplant-v6/Kesher
test -z "$(git status --porcelain)"
saved_checkpoint=$(git rev-parse candidate/stabilization-final-v8)
git fetch origin main
approved_main=$(git rev-parse origin/main)
test "$approved_main" = e79cccab32c046cc80a560ca43d0185b3b124f0b
handoff_dir=$(mktemp -d /tmp/kesher-final-v9-handoff.XXXXXX)
git diff --binary --full-index 7ae5b097e9be2dbe8e6287b1be9dfa2cdc9f6ac7 "$saved_checkpoint" > "$handoff_dir/reviewed-net-candidate.patch"
git switch -c candidate/stabilization-final-v9 "$approved_main"
git apply --3way --index "$handoff_dir/reviewed-net-candidate.patch"
git diff --cached --check
git status --short
~~~

This preparation has NOT run. The package overlap may require manual semantic reconciliation. After reviewing the actual resolved package and code, the additional local checks include:

~~~sh
npm run plugin:validate
npm run plugin:package
pytest tests/test_jules_article_runner.py
~~~

These commands belong only to the future reconciled branch; the saved current candidate does not include the new plugin scripts. The packaging output is a local artifact, not a plugin submission or publication. Complete the exact remaining delta, independently review it, run plugin validation/packaging and its relevant unit tests, updated prior-day Jules regression, authority/topology/admission/history, real content evaluator, fresh website/build/legal-browser checks. Retained unaffected media inputs remain proved; rerun them only for changed execution inputs or new failures. Require clean exact-current-main merge base, reviewed pins,0Critical/0Important, all affected gates green and final unchanged main readback before any conditional push/Draft PR. If these conditions fail, save a clean checkpoint again rather than publish ambiguity. No production action is authorized by local readiness.

## Reproduce affected checks without production effects

Use the declared dependencies. These local runtime locations were used for this finalization; provision equivalent versions if unavailable. A later source change invalidates only the affected proof and requires proportional validation plus renewed main reconciliation before publication.

~~~sh
export PATH="/Users/ninja/.codex/tmp/kesher-final-v8-20261003/venv/bin:/Users/ninja/.nvm/versions/node/v24.21.0/bin:/Users/ninja/.codex/tmp/kesher-tools/actionlint-1.7.12:$PATH"
export PYTHONPATH="$PWD"
python3 -m py_compile scripts/kesher_runtime/*.py scripts/*.py tests/*.py .github/scripts/article-image-worker.py .github/scripts/article-image-worker-v3.py .github/scripts/article-image-worker-v4.py
actionlint -shellcheck= -pyflakes=
python3 - <<'CHECK'
from pathlib import Path
from scripts.kesher_runtime.authority_topology import policy, inventory
from scripts.kesher_runtime.identity import digest
root=Path.cwd(); rules=policy(root); rows=inventory(root,rules)
assert len(rows)==len(rules['workflows'])==72
print('72/72; stale definitions/callchains/unknown0; dispatch validated; policy',digest(rules))
CHECK
pytest tests/test_article_image_worker.py tests/test_article_image_contract.py tests/test_article_image_fallback_exhaustion.py tests/test_article_image_validator_policy.py tests/test_kesher_article_image_worker.py tests/test_kesher_article_contract.py tests/test_kesher_article_public.py tests/test_kesher_provider_recovery.py tests/test_kesher_authority_digest.py tests/test_kesher_authority_topology.py tests/test_kesher_historical_evidence.py tests/test_kesher_worker_entry.py tests/test_kesher_worker_commands.py tests/test_kesher_state_write_safety.py tests/test_v5_backlog_media_recovery.py tests/test_v5_shared_video_controller.py
npm run test:content
npm test
npm run build
npm run verify:dist
npm run lint
npm run test:e2e
git diff --check
~~~

The full video/controller suites and both real synthetic renders already passed in v8. Their unchanged inputs are hashed in the v9 manifest; main's one changed image helper is covered by the 201-test affected set. Website startup changed, so the full website and owned-server browser suites were rerun. Failed browser diagnoses and stale generated-content failures remain in the evidence archive; none was waived. Do not use modified diagnostic JavaScript as validation evidence.

## Future live prerequisites — do not execute here

Draft review/merge and live cutover require separate human authorization. Merging a code candidate alone is not an authority certificate. Do not schedule the canonical controller or dispatch any provider/upload/deployment command merely because local tests passed.

Before handover, supply trusted authenticated observers and persistent service gateways for github,jules,notebooklm,youtube,cloudflare,image_provider. The current fail-closed library refuses missing/nonattesting observers; offline receipts are not service enforcement. Bind exact runtime code/policy/executable digest, Git ref/state CAS, resource/epoch/owner, complete credential classes and default deny. Fresh live inventory must include queued/waiting/requested/in-progress/pending runs, missing-YAML registrations, every indirect dispatcher, bearer/PAT/App/deploy-key/service token and surviving Jules session. Drain or revoke/expire only exact reviewed grants with immutable intents and trusted readbacks. A dated inventory is not an API lock; drift or uncertainty stops admission.

Keep one canonical state/store and append-only nine-phase handover journal:

1. PREPARED: pin exact closed floor/main/topology/approval/exclusion intent and independent trusted approval.
2. LEGACY_QUIESCING: acquire reviewed persistent six-resource fencing; record exact retirement/drain intents before effects.
3. LEGACY_QUIESCED: trusted service readback proves old grants, sessions and in-flight requests cannot mutate; separate infrastructure needs complete independent service/credential/resource proof.
4. IMPORT_READY: exact retained historical receipts and budget floors verified; contradictory claims stay quarantined. Missing trusted retained capability evidence stops here.
5. CAPABILITY_SEALED: trusted coordinator seals only the exact historical upload capability with the approved identity/key/receipt. Do not print or copy capability material; no public completion inference.
6. STATE_IMPORTED: single approved canonical import via exact Git-ref CAS. No alternate file authority or Schema5 write path.
7. CANONICAL_AUTHORITY_ESTABLISHED: bind canonical controller and exactly five command-only workers; attach service protection and live observer proofs. No worker may obtain provider authority before persisted command admission.
8. LEGACY_RETIRED: verify exact legacy actor retirement and continuing service fences; surviving sessions or stale credentials refuse.
9. VERIFIED: independently verify live code/state/policy/topology/exclusion and readbacks. Only separately approved production commands may follow. Controller scheduling remains a separate authorized decision.

On failed CAS, new main/topology/actor/credential, unknown provider receipt or lost acknowledgement, preserve immutable intent and inspect exact remote identity; do not repeat uncertain POST/upload or replace historical claims with a newer/nearest artifact. Recovery remains bounded at generation attempts1..3; no in-place attempt bump/fourth generation. Once canonical import begins, rollback may not downgrade to Schema5 or reopen retired producers; require canonical fail-closed recovery with persistent resource fencing.

Overview OPwpR3ReV0k and Short TKAwQMzvP6U stay quarantined; historical capability5QW2YCqMG6Q stays quarantined until trusted sealing during coordinated5.1. Evidence5.2 is already CLOSED; do not reopen forensic claims. Public delivery always needs exact independent proof. This checkpoint attests no live drain, key sealing, state import, activation, deployment, provider job, upload or public completion.
