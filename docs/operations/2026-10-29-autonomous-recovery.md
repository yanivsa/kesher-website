# Controller-owned recovery: implementation and evidence

## Production architecture observed

The production state read on 2026-10-29 is Schema 5, cycle 2026-10-29, status complete. The article is `first-grade-adjustment`; all three deliverable links are recorded. This is state evidence, not a new audiovisual review or proof of three clean cycles after this change.

The canonical pre-cutover controller runs `kesher_content_controller_stabilized.py`. The old master supervisor workflow is deliberately retired. Three-strike handling can emit `direct_takeover_required`; an unknown exhausted stage can emit `blocked`. Neither event previously reached a live code-repair executor through the admitted controller workflow.

## Implemented behavior

- The admitted controller invokes bounded code-repair coordination after its normal tick, including a failed tick. No separate producer or retired workflow is activated.
- Terminal failure class + stage identifies the root incident; affected content identities are retained in a separate CAS ledger across midnight.
- Existing fast operational recovery remains in charge until a stage is blocked or the durable-progress threshold requires takeover.
- The coordinator persists uncertain creation intent before calling the existing Jules adapter. Lost replies/acknowledgements are reconciled by exact task identity. No blind second create occurs.
- The repair task receives only allowlisted identifiers/failure codes. Raw error strings, credentials and arbitrary provider text are excluded.
- Jules is asked for one generic code correction and regression test, without mutating the content PR, budgets, providers, credentials or authority topology.
- A returned PR must match the incident marker, target this repository/main, contain automation code + regression tests, and differ from the affected content PR. Existing authority hash recertification may preserve reviewed capabilities, paths and dispatch bindings; topology expansion is rejected.
- A merged PR is still not recovery proof. The current checkout must contain its merge commit, and the exact affected content must satisfy the real three-deliverable contract.
- Unresolved old blockers remain visible, and the summary selects the most severe unresolved status across incidents.
- Missing executor credentials can resume after restoration. Running-task timeout begins at task acquisition, not at the original incident creation time.
- Added explicit 00:35 Israel winter/summer wake-ups; existing local-time/idempotency guards keep one daily content slot.

## Proven stale-state failure and correction

Before the change, `tests.test_kesher_recovery_e2e.KesherRecoveryE2ETests.test_two_snapshots_only_one_upload_eligible` failed: supplying `state=` skipped the authoritative disk-state supersession prechecks in `upload_only`. It could silently report no upload rather than explicitly reject a superseded target. This observation alone did not prove a public duplicate upload, because later guards also exist.

All callers now reload the authoritative existing media item before progression, including callers supplying a snapshot. This test passes after the change. Existing external-effect crash-consistency tests also pass in the focused run.

## Recovery proof matrix

| Failure | Evidence suite |
|---|---|
| Unknown exhausted stage before an article exists | `tests.test_controller_repair` |
| Three-strike takeover reaches repair task | `tests.test_controller_repair`, `tests.test_kesher_three_strike_runtime` |
| Lost task-create response / lost ledger acknowledgement | `tests.test_controller_repair` |
| CAS conflict before task creation | `tests.test_controller_repair` |
| Stale media snapshot after supersession | `tests.test_kesher_recovery_e2e` |
| External upload effect survives crash | `tests.test_media_external_effect_crash_consistency` |
| Failed child resumes without exhausted budget | `tests.test_controller_child_failure_recovery` |
| Schema handover blocks legacy repair | `tests.test_controller_repair`, existing authority/cutover suites |
| Wrong/content PR cannot masquerade as correction | `tests.test_controller_repair` |
| Correct merged code not yet running | `tests.test_controller_repair` |
| Owner idea matures into verified exact deliverables | `tests.test_controller_repair`, real `delivery_contract` |
| Historical unresolved blocker after rollover | `tests.test_controller_repair` |

The new suites are included in CI, the stability workflow and `npm run test:controller`. Tests use isolated fake external boundaries and the actual coordinator/delivery contract. They do not create intentional production failures.

## Explicit operational limits

This change does **not** restore the old supervisor's denied automatic merge authority. Repair code PRs wait for existing review/merge policy; the coordinator reports `awaiting_review` and never labels that stage a successful recovery. Thus operational recovery and code-repair preparation are automated, while unrestricted end-to-end automatic code deployment is not claimed.

A source without a stable slug, content PR, owner idea, article run or Jules session cannot be identified safely from a date alone. Such a repair can be proposed, but its delivery cannot be auto-verified until an exact binding exists. Identity is never guessed from another same-day publication.

Future work must preserve these distinctions: live production validation, three consecutive clean post-change content cycles, and a separately reviewed policy for any additional automated code-merge authority.
