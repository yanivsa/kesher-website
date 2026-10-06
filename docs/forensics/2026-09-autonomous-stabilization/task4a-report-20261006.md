# Task 4A — native authority preflight and gateway readiness

**BLOCKED_BY_EXACT_EXTERNAL_CAPABILITIES. Task 4B executable now: NO.**

Started/resumed the same worktree and `codex/kesher-autonomous-stabilization-20260917` at local/remote `35d1b7290965d55b0c92560ce64a3ffedab6212a`. Existing uncommitted Task 4A changes were preserved and inspected after the continuation. No reset, rebase, checkout-over or cleanup occurred. Observed origin/main: `db31dfdbc6f5539bc0b743db88990b4d7186a60b`; initial divergence 40 candidate-only / 1 main-only commit. Main was observed, not integrated. The final containing commit and remote SHA are independently verified after the single normal push and returned in the completion response (not embedded self-referentially here).

## Completed repository-local work

- Exact expected external supervisor task `6aa71096e1788191ae791be184322d69` is enforced by gateway installation validation against the actual control-plane adapter. Its independently audited ACTIVE state remains production recovery; nothing was suspended or converted. The older operator readback remains unresolved and byte-identical. Fresh task/account/tool-authority observation is required.
- Python gateway now validates exact repository ID/node/main/epoch/owner, all six resource bindings, HTTPS OIDC audience, existing protected SQLite ledger and independent external hash-pinned factory. Added read-only `--check-only` and reused the runtime preflight before effects. Missing/corrupt/wrong-schema storage never initializes or repairs itself. SQLite connections now close explicitly. No static-key authentication alternative or fake provider observer was added.
- Live GitHub inventory: **124 active registrations = 74 current-main definitions + 50 retained missing-main-definition registrations**. All ten newly observed October 5–6 identities are pinned as unresolved retirement candidates, with exact source commit/blob/SHA-256 evidence. No authority is granted. Known GitHub default-branch workflow_dispatch requirements are preserved; no historical-ref execution claim or dispatch experiment was made.
- Existing GitExclusionEpoch exact-main/state CAS, complete identity-bound drain, double fresh zero-active checks, canonical gates, all 19 strict infrastructure receipts, restart/lost-response recovery and V5 downgrade refusal remain in place and pass regression coverage. The nine-phase handover and runtime exclusion guards are not redesigned.
- All existing role/capability/resource/credential/dispatch metadata and workflow definitions remain unchanged. Policy changes are ten retained registration entries and pins for the changed/new reviewed source/tests. Historical 111/112/114 fixtures now explicitly project their dated registration scope; the fresh 124-row regression rejects stale inventories and every new/rebound identity. All 50 still-active retained rows refuse authority.
- The exact live-action matrix has one row per outstanding prerequisite, including each of the 19 infrastructure workflows and OCI service proofs. Independent host installation and cutover choreography are executable specifications with unresolved trust roots explicitly marked; no service was installed/started.

## Verified observations and limits

GitHub GETs confirm repository `yanivsa/kesher-website`, numeric ID `1239881973`, node `R_kgDOSecY9Q`, personal owner, available repository admin permission, no repository rulesets, no deploy keys returned, absent `KESHER_CUTOVER_GATEWAY_URL`, and the existing protected environment. That environment uses protected-branches rather than an exact main-only policy, requiring future native correction/readback. Five active-run status inventories were empty at observation; this is **not** external exclusion proof.

Cloudflare GET confirms account `95ba6a62314a0682d0711050ba9c3445`, Pages `kesher-website`, project `41773648-4870-407a-b868-5f05f2a2da57`. Account-token inventory is HTTP403 using the available local credential and error9109 using the connected Cloudflare MCP credential. Shared `CLOUDFLARE_API_TOKEN` across Pages and OCI/OpenClaw remains unresolved. Pages permissions are account-scoped; the required boundary is an independent minimum Pages credential, separate infrastructure authority and exact project admission in the trusted gateway, with native readback. No per-project token policy is invented.

Fresh production state GET remains Schema5, blob `93b5004d7ca0505d0072cde33413d932b53a1f88`, without `handover` or `github_exclusion`. No state was written. Readbacks contain projected identities only, not tokens, secret contents, upload capabilities or private provider responses.

The user-supplied Antigravity audit independently corroborates 124/74/50/10, no ruleset, active exact supervisor, Cloudflare403/9109 and shared credential concerns. Its supplied corrections take precedence: retained registrations are not presumed directly dispatchable; the ruleset must contain exactly one reviewed canonical Integration bypass; Task4A retains V5/supervisor recovery; Jules session/API-key/App-installation/future-creation authority are separate; YouTube isolation is grant revocation plus canonical environment custody, not a Google environment-scoped token.

## Six production adapter classifications

| Resource | Status |
|---|---|
| github | EXTERNAL_ADMIN_CAPABILITY_REQUIRED |
| jules | EXTERNAL_ADMIN_CAPABILITY_REQUIRED |
| notebooklm | API_CAPABILITY_NOT_AVAILABLE |
| youtube | API_CAPABILITY_NOT_AVAILABLE |
| cloudflare | EXTERNAL_ADMIN_CAPABILITY_REQUIRED |
| image_provider | EXTERNAL_ADMIN_CAPABILITY_REQUIRED |

These classify the **complete production exclusion adapter**, not isolated working API clients. GitHub's ruleset/CAS/drain implementation is implemented and tested, but its native credential/direct-write boundary, canonical App and admin custody are not provisioned. No provider is falsely marked ready because its ordinary publishing client works. Detailed native methods, exact known identities, unknown identities, reversibility and before-activation sequencing are in [the complete live-action matrix](task4a-live-action-matrix-20261006.md) and its JSON companion.

## Five recurring stall classes checked against exact current main

| Class | Current-main conclusion | Owner layer / exact evidence |
|---|---|---|
| A — pending-review asset identity hijacking | **Unresolved on current main.** `load_pending` selects the sole pending item without a requested source/item identity. `tests/test_video_review_target_identity.py` is absent from main. Recovery branch/source evidence is not a merged repair. | Review worker / controller target handoff; `scripts/jules_video_reviewer.py:62`; no content repair imported in Task4A. |
| B — B-roll CDN/download stalls | **Mitigations present, permanent closure not proven.** Existing time-budget/read-timeout/drop-on-failure handling is best-effort; automatic B-roll remains enabled on main. Disable change `8ad717b6` exists only on `origin/fix/disable-auto-broll-20261006`. | Provider download adapter / worker; `scripts/kesher_free_stock_broll.py`, `tests/test_kesher_free_stock_broll.py`; no branch integration or provider call. |
| C — resumable upload restart/quota | **Restart/receipt loss protections implemented; quota recovery not certified.** Accepted upload status recovers exact video ID; encrypted durable capabilities survive local crash; expired sessions refuse a second insert. These do not prove live quota recovery or all historical capability retirement. | Provider adapter / media state machine; `scripts/kesher_daily_pipeline.py`, `scripts/kesher_runtime/media_state.py`, `tests/test_kesher_public_delivery.py`, `tests/test_kesher_media_state.py`. |
| D — Jules plan/user-feedback deadlocks | **Fail-closed detection implemented; automatic trusted repair unresolved.** Owned sessions in AWAITING_PLAN_APPROVAL/AWAITING_USER_FEEDBACK/PAUSED report JULES_STALLED. New regression covers all three with no duplicate creation or false completion. Existing PR sessions must quiesce. Incident-bound trusted repair executor remains unconnected. | Jules contract / controller incident handling; `article_worker.py`, `article_quiescence.py`, `tests/test_kesher_article_worker.py`, `tests/test_kesher_article_stall.py`. |
| E — merge/state desynchronization | **Canonical exact-head and uncertain-response recovery implemented/tested; live convergence not proved.** Exact main/PR ref CAS and durable receipt reconciliation prevent a second merge after lost acknowledgment. Current production remains V5. | Merge worker / canonical state machine; `article_merge.py`, `tests/test_kesher_article_merge.py`. |

The audited implementation/test files for C/D/E and the A/B worker paths are byte-identical between starting candidate and observed main (apart from the added D regression in this task). Candidate-only terminal circuit hardening from Task3.5 is not misreported as main functionality. No unrelated media/content implementation is added.

## Minimum actual external blocker set

1. **Independent gateway trust roots and host custody:** exact installed/reviewed main, canonical App ID/credential, ruleset-admin exclusivity and complete GitHub predecessor control-plane boundary; durable host/factory/TLS origin, native ports, exact six bindings and sealing custody. GitHub ruleset/environment/variable/disable APIs are available and automatable when these bindings exist; they are not intrinsically human-only operations.
2. **Fresh external supervisor and Jules authority observation/custody:** exact task account/state/tool readback, complete repo-capable sessions/API keys and Google Labs Jules App installation access, including surviving work. No dedicated task observer or complete Jules administrative adapter is installed.
3. **Consumer NotebookLM and YouTube complete capability exclusion:** consumer-native session/grant/capability readback is unavailable; YouTube lacks an available complete outstanding resumable-capability inventory/settlement observer. Ordinary revoke/list APIs alone cannot supply these proofs.
4. **Cloudflare/OCI complete credential separation:** account-token inventory403/9109, shared Pages/infrastructure credential, missing native effective-policy/credential IDs for all19 service separation proofs. Separate account-scoped Pages credentials must still use exact project admission.
5. **Image provider administrative identities/capability readback:** exact Google project/API-key authority and stock account custody, in-flight/bearer inventory and native canonical-only admission are unresolved.

Missing identity/readback is never filled by a static file. The local A/B recurring-stall repairs and trusted Jules repair integration above are separately recorded implementation work; Task4A does not silently certify them or claim end-to-end production readiness.

## Closed 5.2 preservation

Overview `OPwpR3ReV0k` remains quarantined because its exact archive contradicts claimed source/kind; Short `TKAwQMzvP6U` still lacks exact producer lineage; historical capability `5QW2YCqMG6Q` stays quarantined until trusted coordinated sealing. No replay, migration input, claim/provider identity or evidence file was replaced. No timestamp-nearest artifact substitution. `production_state_written=false`, `production_activated=false`, `public_completion_inferred=false`.

## Validation and review

Focused authority/exclusion/control-plane/drain/ruleset/handover/legacy suite: **232 OK**. Stall-path suites: **106 OK**. Installation tests: **9 OK**, included in232. New explicit cases: 11 total (9 installation, 1 full current inventory, 1 three-state Jules classification). Initial RED evidence covers absent installation contract and unclassified new registrations. The first broader run correctly exposed the stale40-retained assertion; it now verifies all50, without weakening classification.

Full Python discovery: **1250 OK**, zero skips. One bounded independent read-only review: **0 Critical / 0 Important / 0 substantive Minor**; reviewer independently passed17 installation/current-authority tests and verified74 definitions, zero stale pins,124/50/10 identities and all19 infrastructure rows. Nine of ten archived source triples were independently matched to local Git objects; one source was absent locally to the reviewer and relies on the parent native GET evidence (no mismatch observed). No second review or production certification is claimed. Authority verification currently reports74 definitions,124 registrations,50 retained, zero stale definitions/callchains. No frontend/browser/e2e certification is claimed. All new Task4A code is local and unactivated.

Final exact changed files, source/log hashes, validation results and review resolutions are saved in `task4a-checkpoint-20261006.json`. Its containing commit is the Task4A checkpoint. The normal remote readback and clean status are reported after commit/push.

NO PRODUCTION ACTIVATION. NO V5 RETIREMENT. NO MASTER SUPERVISOR MUTATION. NO LIVE RULESET MUTATION. NO JULES/PROVIDER/CREDENTIAL MUTATION. NO PR. NO MERGE.
