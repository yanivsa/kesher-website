# Final-v9 local verification and separate coordinated5.1 handover

**NO SCHEMA-6 PRODUCTION ACTIVATION HAS OCCURRED.** This runbook's live steps are prerequisites for separately authorized human/admin work, not commands executed by this continuation. The recorded18-path local reconciliation is complete; the old blocked final-v9 attempt files remain historical evidence.

Verify the final evidence commit, exact base, clean tree and preserved main paths:

~~~sh
set -e
cd /Users/ninja/.codex/worktrees/stabilization-transplant-v6/Kesher
test "$(git branch --show-current)" = candidate/stabilization-final-v9
git rev-parse HEAD
git log -1 --format=%H -- docs/forensics/2026-09-autonomous-stabilization/final-v9-completion-report-20261004.md
test -z "$(git status --porcelain)"
test "$(git merge-base HEAD e79cccab32c046cc80a560ca43d0185b3b124f0b)" = e79cccab32c046cc80a560ca43d0185b3b124f0b
git diff --check e79cccab32c046cc80a560ca43d0185b3b124f0b...HEAD
git diff --exit-code e79cccab32c046cc80a560ca43d0185b3b124f0b HEAD -- chatgpt-plugin docs/audits/chatgpt-plugin-submission-2026-10-04.md scripts/build_chatgpt_plugin_zip.py scripts/validate-chatgpt-plugin.cjs scripts/jules_article_runner_v3.py tests/test_jules_article_runner.py src/pages/Legal/PrivacyPolicy.tsx src/pages/Legal/TermsOfUse.tsx src/data/posts.json public/llms-full.txt .github/kesher-media-recovery-request.json .github/kesher-goal-request.json scripts/generate-llms-full.cjs remotion-kesher
test ! -e tests/automation-gates-controller-shim.cjs
~~~

Reproduce proportional local checks with declared equivalent dependency versions. Exact private runtimes used here:

~~~sh
export PATH="/Users/ninja/.codex/tmp/kesher-final-v8-20261003/venv/bin:/Users/ninja/.nvm/versions/node/v24.21.0/bin:/Users/ninja/.codex/tmp/kesher-tools/actionlint-1.7.12:$PATH"
export PYTHONPATH="$PWD"
python3 -m py_compile scripts/kesher_runtime/*.py scripts/*.py tests/*.py .github/scripts/article-image-worker.py .github/scripts/article-image-worker-v3.py .github/scripts/article-image-worker-v4.py
actionlint -shellcheck= -pyflakes=
python3 - <<'CHECK'
from pathlib import Path
from scripts.kesher_runtime.authority_topology import inventory, policy
from scripts.kesher_runtime.identity import digest
rules=policy(Path.cwd()); rows=inventory(Path.cwd(),rules)
assert len(rows)==len(rules['workflows'])==72
assert digest(rules)=='a37490d980c4c5bbf3e8449b8e75ca31f7d6aa3e19222dbd8ca907a56704170a'
print('72/72; stale definitions/callchains/unknown0; dispatch reviewed')
CHECK
pytest tests/test_article_image_worker.py tests/test_article_image_contract.py tests/test_article_image_fallback_exhaustion.py tests/test_article_image_validator_policy.py tests/test_kesher_article_image_worker.py tests/test_kesher_article_contract.py tests/test_kesher_article_public.py tests/test_kesher_provider_recovery.py tests/test_kesher_authority_digest.py tests/test_kesher_authority_topology.py tests/test_kesher_historical_evidence.py tests/test_kesher_worker_entry.py tests/test_kesher_worker_commands.py tests/test_kesher_state_write_safety.py tests/test_v5_backlog_media_recovery.py tests/test_v5_shared_video_controller.py tests/test_kesher_article_stall.py tests/test_jules_article_runner.py tests/test_kesher_jules_sessions.py tests/test_kesher_command_dispatch.py tests/test_kesher_observe.py tests/test_kesher_article_worker.py
npm run test:controller
npm run plugin:validate
npm run plugin:package
npm run test:content
npm test
npm run build
npm run verify:dist
npm run lint
npm run test:e2e
~~~

Packaging creates an untracked local dist-artifacts ZIP; preserve it outside Git after verification before claiming a clean tree. It is not an external plugin submission. Playwright owns its server4173 with reuseExistingServer=false. Relevant changes invalidate affected proofs; retain unchanged media/render proof only when hashed execution bytes match. Never use an evaluator shim or suppress product/browser assertions to get green results.

The Oct4 capture is immutable, read-only and time bounded. Do not dispatch a live article or modify stale Schema5 merely to test recovery. Actual production recovery and scheduler/provider inventory need separate authorization; workflow diagnostics are not a current provider certificate.

Future live handover: use trusted authenticated observers/persistent service gateways for github,jules,notebooklm,youtube,cloudflare,image_provider, complete actor/credential/inflight/session inventory, and exact independently approved scope. A dated local manifest is not persistent service exclusion. No missing observer, unknown receipt or stale credential can be interpreted as permission. Follow the existing tested nine-phase journal without skipping steps:

1. PREPARED: bind exact main/code/policy/closed5.2 floor, approved scope and independent trusted approval.
2. LEGACY_QUIESCING: acquire persistent default-deny six-resource protection; persist exact drain/retirement intents before effects.
3. LEGACY_QUIESCED: trusted readbacks establish old grants, indirect dispatchers, queued/inflight requests and Jules sessions cannot mutate. Separate infrastructure needs complete credential/resource proof.
4. IMPORT_READY: verify retained exact historical receipts and immutable attempt/budget floors; preserve all contradictions/quarantines.
5. CAPABILITY_SEALED: trusted coordinator seals only the approved exact historical upload identity/key/receipt. Do not print/copy secrets or infer public completion.
6. STATE_IMPORTED: one approved canonical import through exact Git-ref/stateCAS; no alternate file authority/Schema5 write path.
7. CANONICAL_AUTHORITY_ESTABLISHED: exactly one controller/five command-only workers, persisted admission before provider authority, trusted live observer and continuing service enforcement.
8. LEGACY_RETIRED: exact live actor retirement and persistent service fences verified; surviving credentials/sessions refuse admission.
9. VERIFIED: independent live code/state/policy/topology/exclusion/public evidence readbacks. Scheduling and production jobs remain separate authorized decisions.

On drift, failedCAS, lost acknowledgement or unknown provider receipt, preserve immutable intent and reconcile exact identity; no repeat uncertainPOST/upload, timestamp-nearest substitution, Schema5downgrade, in-place attempt bump or fourth generation. OverviewOPwpR3ReV0k and ShortTKAwQMzvP6U remain quarantined; historical capability5QW2YCqMG6Q remains quarantined until trusted5.1 sealing. Evidence5.2 stays CLOSED. Draft PR review/merge and production cutover are distinct decisions.

**STOP after the requested final report.**
