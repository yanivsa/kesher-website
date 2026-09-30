# GitHub resource-exclusion adapter: bounded offline checkpoint

Date: 2026-09-30. Same worktree `/Users/ninja/Documents/Kesher-worktrees/autonomous-stabilization-20260917`, branch `codex/kesher-autonomous-stabilization-20260917`, starting commit `0f2c8cd87fbfa6c29b3262831ae4e092725536d8`. Scope is the latest September 30 user attachment: four GitHub safety problems, validation, one independent review, local commit, then stop. The original goal is incomplete. Nine handover phases and the existing state branch/path are preserved.

## 1. Resource-exclusion adapter status

**COMPLETE for this bounded offline implementation, validation and review slice.** This checkpoint implements exact retained-registration classification, restartable Actions drain, real Git-ref epoch acquisition and legacy schema rollback refusal. It composes them in `GitHubResourceExclusion`; there is no live CLI or default production credential gateway. Completion of this offline implementation cannot establish live resource enforcement.

## 2. Retained registrations

The bounded read-only observation ran at **16:29:28–16:29:41 UTC**, pinned main `7152264b5713fbc42b36a809f7b5df2d6ae99eea`, verified commit tree `724f90beb09ff4365cc0854f9f156272fc98cd6f`. It found **64 current-main YAML definitions, 97 registered workflows**, including **33 exact policy-retained historical ID/path pairs with missing YAML**. All 33 remained **active** and were explicitly adjudicated **`refused_active_registration`**. All five status inventories were complete and empty. Thus **0** actual registrations were certified `retired_missing_yaml`; zero runs does not cure active workflow authority.

One unknown active registration remains: **370535154**, `.github/workflows/kesher-owner-exact-975.yml`. Five candidate canonical worker paths are absent from the remote registry. The complete exact 33-row adjudication and unknown/missing-path details are in `github-retained-registration-adjudication-20260930.json`. This is a dated read-only observation, not live retirement, integrated-code approval or a later-state claim.

The local reviewed candidate still contains **68 definitions: 35 retired, 19 infrastructure requiring separation or retirement, 8 diagnostics, 5 workers, 1 controller**. These counts differ from remote main and registry counts. The final reviewed execution-input set contains **217 unique paths**, including the two new runtime modules and three new regression modules. Only intended reviewed source/test bindings were repinned; the unknown remote workflow was not added or exempted.

`classify_registered` admits a known missing-YAML row only with exact ID/path, **`disabled_manually`**, complete explicit run evidence and no queued/in-progress/waiting/pending/requested run. Its classification/configured role is `retired_missing_yaml`; effective `role=retired` preserves the existing retirement phases. Unknown, duplicate, rebound, incomplete or newly appearing registrations fail closed. The observer checks three workflow inventories around two complete five-status run inventories. Provisional candidate inventory is only a retirement target admission, never a quiescence proof.

## 3. Run drain

`GithubDrain` follows inspect → durably record disable intent → disable when required → enumerate all five statuses → record cancel intent → cancel where permitted → poll exact run ID/attempt/path/workflow/code identity → require terminal conclusion → fresh workflow and complete run readbacks → save drain proof. Each step issues at most one Actions mutation. Terminal attempts, effect intent/outcomes and proof bytes are monotonic in the same state document's `github_exclusion.drains` ledger.

A disable response does not certify drain. A lost disable response is reconciled from fresh workflow state, with bounded idempotent reconciliation only for an unresolved intent. A previously acknowledged disable followed by active state is a re-enable refusal. An acknowledged, denied or ambiguous cancellation remains nonterminal until exact attempt readback proves completion; an ambiguous cancel intent is never replayed. A crash after effect but before acknowledgment persistence resumes from durable intent. Natural completion is accepted from exact terminal evidence. Newly queued runs, attempts, concurrent re-enables and unknown registrations prevent certification. After PREPARED freezes the ledger, `observe_drained` recertifies read-only, including every stored exact terminal attempt.

The mandatory resource gateway installs default-deny and intent guards before Actions reconciliation. `require_exclusion_actions` authenticates independently approved code, owner/epoch, exact durable target and latest exact attempt at the endpoint. This is necessary because GitHub cancellation is run-ID scoped. Gateway installation and actual credential revocation remain unperformed live.

GitHub documents workflow disable as PUT/204 with no revision comparison; run cancel is POST/202 (or 409), which is acceptance rather than terminal proof; exact attempts have their own GET. The five filtered run inventories enforce pagination totals and the documented 1,000-result search limit. [Workflow API](https://docs.github.com/en/rest/actions/workflows), [run and attempt API](https://docs.github.com/en/rest/actions/workflow-runs).

## 4. Exclusion epoch / CAS

`GitExclusionEpoch` acquires authority by creating a **same-tree commit on the existing `automation-state` ref**, containing a canonical epoch/owner/repository-node-ID/resource-policy/main/before-ref record in its commit message. State bytes are unchanged by acquisition. The existing GraphQL `updateRefs` primitive atomically compares unchanged main and the exact prior state ref, with `force=false`. Only the successful ref advancement owns the epoch; a losing dangling commit grants no authority.

Fresh runners read the exact persisted anchor from the existing state document, validate its acquisition commit, original parent and unchanged tree, then prove ancestry with an immutable-ID GitHub comparison. Exact base and merge-base must equal the anchor, status must be ahead/identical, behind count must be zero, and fresh main/state refs must still match. Recovery does not depend on the paginated commits list or any fixed lifetime descendant count. Before a ledger exists, bootstrap discovery remains bounded and refuses incomplete/malformed/merge ancestry rather than guessing. Another epoch/owner/policy refuses. An uncertain CAS response ends the invocation; the next runner reads the exact ref and adopts the reachable anchor without repeating the CAS. Stale observed refs and main/resource changes refuse. The proof revision is the **40-character acquisition commit SHA**, explicitly `revision_kind=git_ref_cas`; no integer workflow revision is accepted as GitHub exclusion authority. Later drain and handover commits advance the same ref while preserving the anchor.

The journal is initialized and persisted at `.kesher-controller/state.json`, not a second state store. Drain CAS may change only that ledger before PREPARED; import carries its exact bytes into schema 6, and canonical workers cannot erase or rewrite it. A Git anchor proves coordinator ownership, not external credential revocation or an API lock on Actions. The gateway must prohibit unauthorized ref rewrites/descendants and authenticate narrow operations.

The official contract says multi-ref updates are atomic and `beforeOid` requires the reference to have the exact expected value. This is the actual API primitive used and tested; workflow disable has no such contract. [GitHub GraphQL Git reference](https://docs.github.com/en/graphql/reference/git#updaterefs).

The [commit comparison API](https://docs.github.com/en/rest/commits/commits#compare-two-commits) supplies base/merge-base, status and ahead/behind counts separately from its paginated commit list. One additional bounded GET compared the pinned production main SHA with itself: exact full base/merge-base SHA, identical status and zero counts were confirmed. Its permalink abbreviates IDs, so the implementation deliberately does not use permalink text as authority. No mutation or provider/credential read occurred.

## 5. Legacy V5 rollback protection

V5 now checks protected state **before** falling through to blank schema-5 reconstruction. Schema ≥6, any `handover` key and any `github_exclusion` key refuse, including empty/malformed authority-key values. The shared legacy load/save boundary keeps the original document and blob SHA; it neither rereads nor rebinds a stale snapshot to force a write.

The trusted resource hook `validate_legacy_write` independently reads current state, requires a full exact Git identity and refuses downgrade or journal erasure even when an old caller supplies the newest SHA. New code cannot retroactively modify an old process; the actual endpoint must apply this guard and revoke/bypass-proof its old credentials.

`record_denied_legacy_write` persists a stable hash-only incident and additive audit through exact existing main/state Git CAS. It preserves schema, journal, evidence, commands and quarantine. Lost acknowledgment is reconciled by stable incident identity; no attempted payload/credential is saved. Open `legacy_authority_violation` incidents block drain/handover, canonical state transitions and resource/control effects, including attempts to clear the incident in the same write. The regression set includes a stale V5 waking after schema 6, latest-SHA old-worker downgrade, stale CAS, every handover phase, empty/null authority keys, malformed attempted identities and incident recovery.

## 6. External authority still unsolved

No real workflow/app/PAT/deploy-key grants were revoked. An independently installed authenticated GitHub gateway, complete actual credential-class revocation/readback and protection against direct bypass remain activation prerequisites. `GitHubResourceExclusion` refuses a missing, partial, changed or wrong-resource guard; drained Actions never synthesize a credential receipt.

Unresolved Jules sessions/continuation/repository access, stale credentialed processes, direct Cloudflare deployment/configuration credentials, NotebookLM/image-provider sessions or credentials, YouTube OAuth/metadata credentials and resumable-upload capabilities still need service-enforced revocation, expiry or exact gated authority. A completed GitHub run does not settle these actors. The existing six-resource fail-closed boundary is preserved. General Jules repair, Cloudflare credential redesign, attempt transitions and activation are outside this slice.

Closed 5.2 evidence is unchanged: **32 baselines, 64 IDs, 14 duplicate groups, 1 ambiguous group, 2 unresolved stages, 1 unsealed capability, 0 new proven bindings**. Overview `OPwpR3ReV0k` remains quarantined for exact contradictory source/kind evidence; Short `TKAwQMzvP6U` remains quarantined for missing exact producer lineage; capability `5QW2YCqMG6Q` remains quarantined until trusted identity-bound sealing during coordinated handover. No newer/nearest artifact substitution. The actual floor still deliberately refuses missing capability evidence at IMPORT_READY, with zero actual imports.

## 7. Validation

| Gate | Result |
| --- | --- |
| Initial new epoch regressions | Six expected missing-module failures before implementation; then green. |
| New retained/observer/drain focused regressions | 29 passed in 0.662s; missing-YAML, all five statuses, natural completion, lost effects, fresh runner, new runs/registrations, re-enable and monotonic journal. |
| Root composed Git/Actions port | 11 passed in 0.415s; independent implementation check 11 in 0.451s. |
| Legacy/core/V5/state/handover affected gate | 147 passed in 7.026s; includes 19 new legacy regressions and reproduced pre-fix rollback failures. |
| Combined authority/digest/handover/controller/state/migration gate | **214 passed in 17.787s**, exit 0. Initial three pin refusals were corrected by explicit intended call-chain review/repinning. |
| Full Python discovery before review fix | **1,026 passed in 138.589s**, exit 0; no failure/error. |
| Review recovery regression | Old implementation failed after 512 valid descendants (21.042s); 13 Git tests pass after fix (24.997s), including 520 individually validated journal CAS descendants, false ancestry/base and ref-change refusal. |
| Final combined affected gate after review fix | **216 passed in 72.168s**, exit 0; no failure/error. |
| Final full Python discovery after review fix | **1,028 passed in 182.110s**, exit 0; no failure/error. |
| Repository-wide actionlint 1.7.12 | Exit 0, no diagnostics; existing shellcheck/pyflakes integrations disabled. No workflow YAML changed. |
| Closed evidence preservation | Floor validates at original digest `5f2bb8d19b6ca3e9004d1e34997c9a55b05dea944f7ea901c1c33ff62a71df1c`; five closed evidence/report artifacts byte-identical to starting HEAD. |
| Staged/unstaged diff integrity | Passed before independent review; final commit/clean checks required below. |

The deliberately interrupted developer-only full run is not counted; the final complete post-review discovery above validates the final runtime code. No assertion was weakened. Logs are outside Git under `/Users/ninja/.codex/tmp/kesher-forensics-20260917`, including `github-adapter-affected-post-review-20260930.log`, `github-adapter-full-python-post-review-20260930.log`, the pre-review logs and `github-adapter-actionlint-20260930.log`. No frontend/browser inputs changed; earlier browser/CI/integration requirements remain documented and unwaived.

## 8. Independent review

One bounded independent GPT-6.1 Sol/xhigh review found **0 Critical and 1 Important** issue: fixed 512-commit epoch lookup would eventually refuse a fresh runner after ordinary valid checkpoint growth. The independent reproduction used actual epoch/journal methods and 510 monotonic run discoveries. Root reproduced the old-code failure and replaced lifetime traversal with direct persisted-anchor validation plus immutable-ID comparison and fresh exact ref readbacks. The 520-descendant positive regression and wrong base/merge-base/status/behind/ref-race negatives pass. The **same review seat independently confirmed the fix**, with **6 targeted tests passing in 46.352s**, including coordinator races, lost receipts, ledger preservation and composed Actions recovery. Its initial independent focused gate passed **149 tests in 16.592s**. It found **no remaining confirmed Critical/Important finding** and returned ready for the offline checkpoint after final validation/commit; this is not live-gateway acceptance. No second review or next slice was started.

## 9. Commit / worktree

All **22 intended implementation/test/policy/evidence/report files** are included in the containing checkpoint commit on the same stabilization branch. The closing response records its exact SHA and post-commit clean/diff checks; this report cannot embed its own commit SHA. No push, main integration, history rewrite, PR, merge or activation occurred.

## 10. 5.1 live readiness

**STILL BLOCKED.** This bounded offline adapter does not resolve the live unknown registration, active retained registrations, missing canonical registration/definition alignment, direct credential bypass, six-resource enforcement/acceptance, integrated exact-head approval or trusted capability sealing/import. The original goal and blockers 5.3–5.6 remain open.

**production_state_written=false; public_completion_inferred=false; production_activated=false.** Only bounded GET metadata was fetched. No provider/YouTube/Cloudflare state mutation, actual capability/key access, workflow disable/cancel/dispatch, push, PR or merge occurred.

## 11. Next smallest slice

Exactly one recommendation: **offline exact-source authority review/adjudication of newly registered workflow 370535154 (`kesher-owner-exact-975.yml`)**, pinning its actual current-main definition, indirect call chain and credential/resource scope, with unknown/rebound identity regressions. Keep it refused unless exact evidence supports a reviewed disposition. Do not integrate or activate in that slice.

## 12. Model / effort

**GPT-6.1 Sol, xhigh / Extra High** for that bounded unknown-authority review. STOP after this checkpoint; no next slice is begun.
