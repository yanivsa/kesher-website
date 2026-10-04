# Final-v8 blocked-publication handoff and safe live cutover runbook

This is an operator handoff, not permission to execute live cutover. No live step was executed. Publication is BLOCKED: validated candidate base 1651fffd4bddba30b383b4c6f58636318699f2c9, final observed main 013494dbc031d093be8a3afaa721d40be3dd2246; one bounded reconciliation already consumed. Current next slice is solely bounded latest-main content reconciliation and affected validation in a stable coordinated main window (GPT-6.1 Sol/xhigh).

## Local checkpoint readback (safe, readonly)

~~~sh
cd /Users/ninja/.codex/worktrees/stabilization-transplant-v6/Kesher
git status --porcelain
git rev-parse candidate/stabilization-final-v8
git merge-base candidate/stabilization-final-v8 013494dbc031d093be8a3afaa721d40be3dd2246
git diff --check 1651fffd4bddba30b383b4c6f58636318699f2c9...candidate/stabilization-final-v8
git diff --check 013494dbc031d093be8a3afaa721d40be3dd2246...candidate/stabilization-final-v8
git log --format='%H %s' 1651fffd4bddba30b383b4c6f58636318699f2c9..013494dbc031d093be8a3afaa721d40be3dd2246
git diff --name-status 1651fffd4bddba30b383b4c6f58636318699f2c9..013494dbc031d093be8a3afaa721d40be3dd2246
shasum -a 256 docs/forensics/2026-09-autonomous-stabilization/final-v8-unreconciled-main-20261004.patch
shasum -a 256 docs/forensics/2026-09-autonomous-stabilization/final-v8-validation-logs-20261004.tar.gz
~~~

Expected merge base1651, one extra main commit013494, only posts.json,8+/8-. Unapplied patch SHA256 5877fba76de8e42c67b31bd57501a0df390893f181cc6f91e23f0f32f61235d7; archive SHA256 1c4a5d03fa9323a1fc92005fccde84ec0fa09cc79ba837795d044e87a8ecf256. Patch is public article text; never execute source from historical archives. Checkpoint hash resolves to the containing commit printed above.

## Separately authorized future local reconciliation

Coordinate a stable main window first. If main is newer than013494, classify every additional path/commit before any mutation. A new authority/CAS/security delta requires renewed review; never blindly repin or repeat main chasing. Capture the source checkpoint first. Use a fresh reviewed branch and transplant its ONE net diff from1651, not old stabilization history. The saved remaining patch is evidence; main itself supplies the exact authoritative content. The following script prepares the known013494 case only and refuses a different main:

~~~sh
set -e
cd /Users/ninja/.codex/worktrees/stabilization-transplant-v6/Kesher
test -z "$(git status --porcelain)"
checkpoint_sha=$(git rev-parse candidate/stabilization-final-v8)
git fetch origin main
approved_main=$(git rev-parse origin/main)
test "$approved_main" = "013494dbc031d093be8a3afaa721d40be3dd2246"
handoff_dir=$(mktemp -d /tmp/kesher-final-v8-handoff.XXXXXX)
git diff --binary 1651fffd4bddba30b383b4c6f58636318699f2c9 "$checkpoint_sha" > "$handoff_dir/validated-net-candidate.patch"
git switch -c candidate/stabilization-final-v9 "$approved_main"
git apply --3way --index "$handoff_dir/validated-net-candidate.patch"
git diff --cached --check
git diff --exit-code "$approved_main" -- src/data/posts.json .github/kesher-goal-request.json .github/kesher-media-recovery-request.json
~~~

A conflict stops for semantic review; do not use theirs/ours wholesale. This preparation has NOT run. Candidate net diff has no posts.json change, so exact main's sleep rewrite must survive. Regenerate derived public artifacts and inspect metadata, canonicals, summaries, sitemap/RSS/llms. Regeneration may update intended derived content; preserve exact published source and image bytes.

Use the reviewed Python/Node environments or provision the exact declared versions/dependencies without accessing provider credentials. Existing local runtimes:

~~~sh
export PATH="/Users/ninja/.codex/tmp/kesher-final-v8-20261003/venv/bin:/Users/ninja/.nvm/versions/node/v24.21.0/bin:/Users/ninja/.codex/tmp/kesher-tools/actionlint-1.7.12:$PATH"
export PYTHONPATH="$PWD"
python3 -m py_compile scripts/kesher_runtime/*.py scripts/*.py tests/*.py
actionlint -shellcheck= -pyflakes=
python3 - <<'CHECK'
from pathlib import Path
from scripts.kesher_runtime.authority_topology import policy, inventory
from scripts.kesher_runtime.identity import digest
root=Path.cwd(); rules=policy(root)
rows=inventory(root,rules)
assert len(rows)==len(rules['workflows'])==72
print('Reviewed definitions72; stale/unknown0; dispatch bindings valid; policy',digest(rules))
CHECK
npm run test:content
npm run test:controller
npm test
npm run build && npm run verify:dist
npm run lint
npm run test:e2e
git diff --check
git diff --cached --check
~~~

These website/controller gates are required for the known content delta. Full pytest, video-policy, focused authority/topology/CAS/exclusion/worker/statewrite/V5/history and synthetic render results are preserved for the old exact execution inputs; rerun them if those inputs change or a new concern appears. For a complete new final certificate, the exact full matrix is in the report. Keep Playwright reuseExistingServer=false; stale external preview is refusal. Record every failure and run only justified corrections; no skipped safety assertions.

Commit only after inspecting all intended changes and renewed independent review if implementation changes. Read main again; require clean worktree, merge-base exact final main, no published content/runtime reversion, unchanged closed5.2, reviewed actual pins,0Critical/0Important and all affected gates green. If main moves beyond the newly agreed bound, preserve a clean local checkpoint instead of publishing ambiguity. Only then may separately authorized future work push its branch and create a Draft PR with exact identities and explicit no-activation statement. This run created none.

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
