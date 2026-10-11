# Schema-6 activation preparation evidence — 2026-10-11

Status: **READY FOR REVIEW**. All local gates pass; production cutover remains **NO-GO** pending independent external prerequisites.
This is preparation for reviewed manual activation, not a production cutover approval.

## Exact revisions and unchanged production state

- Final integrated base: `a1c8eca483fa748134b00ca313df835984f4926f` (latest main includes PRs #1099/#1100).
- Independently reviewed implementation: `af0d0bb7d36f0f1c470edae8e9e4e70e5cd0d7e7`.
- State branch/ref: `automation-state`, `cb2b97ad3039d4423467c232ee01f0c56b217f8d`.
- Exact legacy state blob: `93b5004d7ca0505d0072cde33413d932b53a1f88`.
- Schema 5; cycle `2026-10-04`; status `article_image_running`.
- `production_state_written=false`, `production_activated=false`, `public_completion_inferred=false`.
- No production workflow dispatch, state migration, article creation, NotebookLM/YouTube publication, credential/provider mutation or cutover occurred.
- No canonical controller schedule was added. Retired legacy controllers remain retired.
- The final publication checkpoint adds only this evidence report after the reviewed implementation; executable inputs remain identical.

## Antigravity Blocker Reconciliation

| Blocker | Independently reproduced | Root cause and final correction | Proof | Status |
|---|---|---|---|---|
| Post-freeze adoption / multiple same-day posts | YES | Source availability did not bind slots; automatic date adoption refused actual Oct5/Oct8 duplicates. Require a complete, sorted, disjoint reviewed adopted/excluded source-key partition, at most one adopted daily owner, immutable candidate/evidence/quarantine records and exact source body/hash. No implicit date-based selection. | `tests.test_kesher_post_freeze_migration`, `tests.test_kesher_real_data_migration`, native `tests.test_kesher_cutover_host` material-completeness/path tests | FIXED |
| Incomplete freeze-day Oct4 article | YES | Exclusive lower bound omitted a publication finalized after the snapshot. Inclusive freeze≤date≤reviewed cutover permits only explicit independently verified Oct4 identity. Missing/inconsistent boundaries still refuse; no provider history is invented. | `test_incomplete_freeze_day_requires_explicit_exact_adoption` and real-data exact Oct4 binding/quarantine tests | FIXED |
| Permanent SOURCE_AMBIGUOUS head-of-line backlog starvation | YES | Selecting minimum unchanged observed_at repeatedly chose a blocked date. Durable round-robin observation turns advance even on ambiguity/absence, preserve incidents and blocked status, skip completed slots and ignore unrelated PR cursor resets. | `tests.test_kesher_backlog_rotation`, `test_real_observer_blocked_history_cannot_starve_oct9_or_current_work` | FIXED |

Real-data tests read the actual repository `src/data/posts.json`, including duplicate dates Oct1/Oct2/Oct5/Oct8, a representative explicitly labeled frozen Schema-5 fixture, Oct4, exact Oct9 and Oct10 current/cutover contexts. Fixture decisions are test review choices, not production approval. Oct9 key independently regenerated and confirmed:
`source:89b290e6750339224a9f978df77bace2e27828d0f3557ee44a2b8f1d249e6d26`.
They prove no duplicate Oct9 article, missing Overview/Short eligibility only after independent article verification, current-slot progress, no arbitrary ownership, explicit alternatives and ZERO inferred public media completion.

## Latest-main publication catalog correction

The site and maintained pipeline combine `posts.json` and `postsRecent.json`. Canonical observation, article duplicate protection and preflight previously read only the former, missing actual Oct6 and newly merged Oct10 publications. Shared pure catalog validation is reused; both exact Git catalogs are read, missing/transient/malformed/duplicate catalogs refuse, and native preflight independently verifies every reviewed source plus its fixed catalog path. `source_git_paths` cannot name arbitrary paths. Canonical PR normalization still uses only its maintained historical write contract; occupied dates refuse replacement. Recent catalog data is exempt from executable digest changes only after inert byte/mode/path validation; canonical article PR write paths are unchanged.

Actual recent posts tested: Oct6 `child-meltdown-after-school`, Oct10 `child-argues-every-request-boundaries`. Their existing missing hero evidence remains unverified and blocked, never fabricated. The initial preflight requires the trusted host's current Israel date, so stale review windows refuse. Later handover recovery retains original immutable material.

## Authority and installation contracts

Only manual controller dispatch on exact repository/main is executable. Schema5, incomplete migration, non-VERIFIED handover and forged completion flags refuse before observe/save/worker dispatch. Workers still accept only persisted command IDs and claim before credentials/provider work. Read-only OIDC admission goes to the independent credential-owning gateway. `/v1/cutover/step` is the only remote mutation route. Signed identity is checked before privileged observations; replay ledger is durable, protected and fail-closed; body/path/credential/evidence injection is refused.

The existing nine-phase `Coordinator`, CAS/exact-ref checks, original snapshot lineage, interruption/restart/import recovery, resource exclusion and closed 5.2 historical evidence floor remain. Historical Overview identity contradiction, unproven Short lineage and unsealed historical upload capability remain quarantined; no newer/timestamp-nearest replacement is inferred.

Installation/runbook: `docs/operations/kesher-cutover-host.md`; Linux systemd unit `deploy/kesher-cutover.service`; pinned `scripts/requirements-cutover.txt`. Runbook uses the existing runtime, exact merged-main revision and separately installed native ports. Tests use disposable fake services; no fake port is offered for production.

Canonical synchronizer generated all hashes. Inventory: 71 current definitions (1 controller, 5 workers, 32 retired, other explicitly reviewed roles), 43 historical registrations. 142 call-chain pins across 27 changed dependency paths were regenerated; roles/resources/capabilities and native registrations were not changed. Main's production-verifier pin and current content/prerender changes were preserved.

## Validation

Local Python 3.14.7; workflows retain Python 3.12.
- Complete maintained Python command: **1,353 tests OK** on the rebased implementation.
- Rebased exact CI Schema-6 safety command: **285 tests OK**.
- Rebased focused migration/real-data/rotation/controller/command/handover/cutover/observer/digest suites: **165 tests OK**.
- Independent review: no unresolved Critical/Important/Minor findings; latest **82 tests OK**, earlier focused **117 OK**.
- `npm run check`: generation, lint, content/plugin gates; video policy **247 OK**; controller **505 OK**; frontend **152 passed**. Build, typecheck, prerender and distribution passed; **140 browser E2E tests passed**.
- Final exact CI authority/governance **49 tests OK**, CI contracts **181 tests OK**, Stability **653 tests OK** on the rebased implementation.
- `python3 scripts/kesher_runtime/sync_authority_policy.py --check`: matching, zero stale pins.
- `python3 scripts/kesher_runtime/workflow_governance.py`: passed, failure_class=null.
- actionlint 1.7.12 and `git diff --check`: passed.
- Synthetic Overview/Short rendering proof: decoded audio identical, signature and cached bytes verified. Rendering implementation unchanged; no provider generation/upload.

The maintained broad Python command, equivalent to the workflow's module expansion, is:
```sh
read -r -a python_suites <<< "$(python3 -c 'from pathlib import Path; print(" ".join("tests." + path.stem for path in sorted(Path("tests").glob("test_*.py")) if path.stem != "test_kesher_daily_pipeline"))')"
python3 -B -m unittest "${python_suites[@]}" tests.kesher_daily_pipeline_suite -v
```
The unchanged compatibility suite excludes explicitly obsolete legacy reviewer assertions; current canonical policy/reconcile coverage remains. The exact CI/Stability commands are in their checked-in workflow steps. Synthetic render command: `python3 tests/real_media_render.py --output /tmp/kesher-activation-render-proof`.

## Remaining external prerequisites — cutover still NO-GO

- Independently installed persistent trusted host, TLS and protected ledger/config; complete independently reviewed native fence/observation adapters for GitHub, Jules, NotebookLM, YouTube, Cloudflare and the actual image provider/project. `production_ports.PREREQUISITES` remains authoritative; absent native ports fail closed.
- Isolated gateway GitHub credential outside Actions; native predecessor grant/session/resumable-capability retirement and enforcement; actual protected NOTEBOOKLM_STATE_KEY and bound metadata; approved immutable code/policy/evidence/material/resource digests.
- Repository `KESHER_CUTOVER_GATEWAY_URL` variable was absent at readback. Configure only after independent installation and verification.
- Native readback: **125 registrations**, **15 unknown active** and **4 missing reviewed**. They cannot be assumed safe by filename. Reconcile/classify/retire through a separate reviewed operator process; this PR changes no registrations. No active queued/in-progress/waiting/pending/requested runs at the recorded readback.
- Review the complete inclusive source-key adoption/exclusion boundary across both catalogs at the actual merged main and actual cutover day. Test selections do not approve production ownership. Preflight must pass again immediately before manual invocation.

After PR review/merge and trusted installation, the read-only next command is:
```sh
sudo -u kesher-cutover /opt/kesher-cutover/venv/bin/python -B -m scripts.kesher_runtime.cutover_host --config /etc/kesher-cutover/installation.json preflight
```
Run from the pinned `/opt/kesher-cutover/code` checkout. No workflow should be manually invoked until independently observed preflight and operational gates pass. First post-VERIFIED controller E2E remains manual.

## Exact changed files

- `.github/workflows/ci.yml`
- `.github/workflows/kesher-article-deploy.yml`
- `.github/workflows/kesher-article-merge.yml`
- `.github/workflows/kesher-article-validation.yml`
- `.github/workflows/kesher-article-worker.yml`
- `.github/workflows/kesher-content-controller.yml`
- `.github/workflows/kesher-media-worker.yml`
- `.github/workflows/kesher-stability-pr.yml`
- `deploy/kesher-cutover.service`
- `docs/forensics/2026-09-autonomous-stabilization/production-cutover-runbook-20261004.md`
- `docs/operations/kesher-cutover-host.md`
- `scripts/kesher_daily_pipeline.py`
- `scripts/kesher_runtime/article_verification.py`
- `scripts/kesher_runtime/article_worker.py`
- `scripts/kesher_runtime/authority.py`
- `scripts/kesher_runtime/authority_client.py`
- `scripts/kesher_runtime/authority_policy.json`
- `scripts/kesher_runtime/authority_topology.py`
- `scripts/kesher_runtime/controller.py`
- `scripts/kesher_runtime/cutover_auth.py`
- `scripts/kesher_runtime/cutover_host.py`
- `scripts/kesher_runtime/cutover_service.py`
- `scripts/kesher_runtime/migration.py`
- `scripts/kesher_runtime/observe.py`
- `scripts/requirements-cutover.txt`
- `tests/fixtures/kesher/schema5-freeze-20261004.json`
- `tests/test_kesher_authority_digest.py`
- `tests/test_kesher_authority_topology.py`
- `tests/test_kesher_autonomous_controller.py`
- `tests/test_kesher_backlog_rotation.py`
- `tests/test_kesher_controller_entry.py`
- `tests/test_kesher_cutover_host.py`
- `tests/test_kesher_historical_evidence.py`
- `tests/test_kesher_observe.py`
- `tests/test_kesher_post_freeze_migration.py`
- `tests/test_kesher_real_data_migration.py`
- `tests/test_kesher_runtime_migration.py`
- `tests/test_single_scheduler_policy.py`

- `docs/forensics/2026-09-autonomous-stabilization/schema6-activation-preparation-20261011.md` (evidence-only publication checkpoint)
