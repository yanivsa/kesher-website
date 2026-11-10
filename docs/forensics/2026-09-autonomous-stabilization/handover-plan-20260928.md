# Bounded 5.1 handover implementation ledger

Base: `693bb4c8ad38e6351bff5aa76b4424ae1b7f2665`. Same stabilization branch/worktree. The user's 2026-09-28 attachment is the controlling specification. No live activation, integration, PR or other blocker is in scope.

1. Implement the restartable handover journal in the existing controller-state document, exact migration/quarantine preservation and synthetic trusted sealing. Add phase/crash/CAS regressions first.
2. Implement explicit workflow/code authority policy, retirement operations, canonical live admission and legacy refusal. Review actual mutators separately from diagnostic and unrelated infrastructure paths.
3. Exercise captured production-shaped inputs offline, run affected/full Python and workflow gates, obtain an independent boundary review, resolve important findings, document and commit.

Ruling: `PREPARED` itself fences legacy admission; phase evidence lives in the existing state document, not a second production state store. Import CAS uses the currently observed journal revision and retains the originally observed legacy blob/content identity. Journal writes never rebind a changed legacy body.

Ruling: the 5.2 unsealed-capability quarantine is not removed by encryption. Sealed capabilities stay in the handover evidence with exact target/item/origin binding; existing 32 baselines, duplicate groups and all quarantines survive. Sealing alone grants no upload authority.

Ruling: GitHub can atomically compare main and state Git refs, but workflow activation, credentials and external writers are separate services. A trusted exclusive authority fence and complete external-writer inventory are mandatory preconditions; multiple GETs are not described as a cross-service transaction. Offline tests must exercise missing/failing fence refusal. Live service/actor acceptance remains unactivated and must be explicit in the final report.

Ruling: legacy definitions, registered workflow activation and old-revision in-flight executions are different facts. A retired definition cannot substitute for registered-disable/drain proof. Missing or unclassified registered paths fail closed. Read-only diagnostics and separately scoped infrastructure are not all treated as Kesher content writers.

## 2026-09-30 bounded hardening continuation

The September 30 user attachment supersedes the earlier implementation scope. Preserve the nine phases and the existing CAS/restart design; complete only the four verified evidence/topology/exclusion/digest gaps, reconcile the eight prior test failures, validate, obtain one independent bounded review, commit and stop. No current-main integration or live activation is authorized.

Ruling: refreshed inputs must carry the independently approved closed 5.2 evidence floor. The floor retains exact historical receipt bytes, identities, budgets and origins; missing rollover fields do not remove claims. A caller cannot substitute a floor and approve its own replacement. Conflicting fresh evidence remains separately retained and quarantined.

Ruling: the real retained capability obligation cannot disappear when a refreshed artifact list omits it. The actual closed-floor offline replay stops at `IMPORT_READY` with `HANDOVER_RETAINED_CAPABILITY_UNAVAILABLE_FOR_SEALING`, zero imports and all three quarantines preserved. Synthetic phase completion is reported separately from this actual evidence replay.

Ruling: exclusion is a persistent resource-side contract with inspect/CAS-protect/readback adapters for GitHub, Jules, NotebookLM, YouTube, Cloudflare and image-provider authority. A boolean, empty Actions inventory, or workflow disable is insufficient. Legacy grants, in-flight requests and bearer capabilities must be revoked or proven expired; unknown callers are denied. JSON receipts are structural evidence, not service authentication. Concrete live service adapters and acceptance remain pending.

Ruling: all executable and unknown paths remain pinned. Only outputs listed by the shared article publication contract may change, with byte/type/mode checks. Three exact historical `.venv-dub/bin/python*` Git symlinks are pinned as inert storage by mode and link bytes, never followed. A reachability review found no references from workflows, scripts, frontend, tests or package entrypoints; they cannot be accepted as active call-chain files. Unknown or publication symlinks still refuse admission.

Ruling: missing registered definitions remain unresolved authority and block admission; infrastructure sharing protected resources is retired unless exact service-enforced resource separation is proven. The two newly observed current writers are retained as inert local definitions, not disabled live.

Progress, validation and independent-review results are recorded in `handover-hardening-report-20260930.md`. No production mutation.
