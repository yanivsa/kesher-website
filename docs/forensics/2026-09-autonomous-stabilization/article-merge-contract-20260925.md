# Exact article publication and stopped-worker reconciliation

## Scope and authority

This implements the planned slot-bound `merge_article` worker. It replaces that command's legacy article-generation route with `kesher-article-merge.yml`. It is local implementation evidence, not an activated production path, safe-cutover claim or proof of public A+B+C completion.

The worker accepts only an owned canonical command for an exact PR number, head, validated body digest and trusted main revision. It reopens the candidate as immutable Git data, compares the exact tree/article/image digests with independently inspected canonical CI, and freshly checks Jules quiescence. The publication tree contains the trusted base plus the checked article data/image; candidate executables, dependencies, tests and workflows are never run.

## Transaction and policy

[GitHub's `updateRefs` contract](https://docs.github.com/en/graphql/reference/git#updaterefs) describes an atomic transaction with a `beforeOid` condition for each ref. The request conditionally advances `main` from the validated base to the already tested candidate, while comparing the PR branch with its same validated head. Both updates use `force: false`. A changed main or PR branch therefore rejects the transaction; the worker does not compute or publish a different merge tree.

The route refuses a protected main, any applicable branch rule, and unavailable or incomplete policy reads. Its workflow uses the repository installation token, with no administrator/controller PAT fallback. This does not modify protections or grant a bypass. A read-only September 25 observation returned main `a1fc391f95556ad64719435796cf432691185a4e`, `protected: false`, and an empty applicable branch-rules list. The worker must repeat those checks at execution; this dated observation is not an evergreen authorization.

This policy boundary is deliberate: GitHub documents that [indirect PR merges can occur without satisfying PR protection requirements](https://docs.github.com/en/pull-requests/reference/pull-request-merges#indirect-merges). Neither successful ref advancement nor `merged: true` certifies review policy. Repositories requiring those protections need GitHub's native merge/queue path and validation of its actual merge result, rather than bypass through this worker.

Git refs are the atomic preconditions. PR body/open/draft/base metadata and repository-policy edits are not in that transaction. The worker checks fresh metadata before sending, but cannot claim to lock it. The persisted CI result binds the reviewed body digest as an immutable snapshot and the exact tested tree. A later metadata edit cannot introduce new tree bytes; it may require independent PR reconciliation. This limitation must remain visible in operational acceptance, including the installation actor's actual configured bypass eligibility.

## Durable recovery

Every full validated request has a distinct immutable effect identity. Its send budget is separately bound to repository/base/head/branch, so changing CI evidence or body text cannot reset the three-send budget for that same ref transaction. Different heads remain separated. Delayed requests remain fenced by both exact refs. Old pre-send intents do not trap fresh validated inputs behind an unrelated uncertain-creation fence.

The worker records its intent before sending one request. Missing, malformed and disconnected responses all lead to readback. A successful ref change followed by a lost response is adopted; a descendant main is preserved. Historical inclusion is not proof that a later main still contains the article: the independent source/public verifier checks that separately.

Readback requires the exact PR/repository/base/head identity, its merge commit, and main inclusion. Comparison responses must bind the actual requested commit pair and have coherent status/counts/merge-base evidence. Malformed or unrelated responses remain unknown and cannot create a terminal merged or superseded receipt.

If a worker stops after the ref transaction but before PR recognition or receipt persistence, `RepositoryObserver.read` continues read-only reconciliation of its outstanding intent, even after the slot adopts the merged source. The controller appends the later external receipt while preserving the worker's actual failed outcome. It never republishes to repair missing bookkeeping. Pending/unknown observation receives a persistent incident after twelve hours; timestamps do not restart that deadline. Superseded intents require independently confirmed non-inclusion before they receive a terminal receipt.

## Evidence and limits

- Behavioral tests first reproduced the legacy dispatch route, lost responses, concurrent refs, final-quiescence draft changes, missing controller body/base binding, stale-intent poisoning, malformed POST responses and unreachable reconciliation after source adoption.
- Four readback corruption cases failed before correction: empty comparison, wrong PR number, wrong repository and wrong base ref.
- The merge entrypoint is executed with Python site packages disabled. This exposed and removed an accidental dependency on the legacy media module; the shared quiescence gate is now a lightweight module with unchanged behavior.
- Disposable real Git tests inspect a real article candidate and apply the emitted transaction through local Git's atomic ref mechanism. They prove local lost-response recovery and rejection of a stale no-op head comparison without advancing main. They do not prove GitHub's deployed no-op implementation or live installation-token permissions.
- The preceding full project gate passed at the media-migration boundary. This change's focused article/controller/observer gate passed 82 tests in 20.995 seconds. Full Python discovery subsequently passed 812 tests in 126.198 seconds, and the separate daily suite passed 46 tests in 5.529 seconds. Independent final review passed 64 focused tests and reported no remaining Critical or Important finding in this bounded slice. Actionlint and whitespace checks passed. These are local results; the live GitHub transaction/actor contract remains unproven.

Before live cutover, validate the actual GitHub transaction/actor contract in a bounded non-publication probe, complete merge/deploy integration, and reconcile against current production state. No remote ref, PR, policy, provider, upload or production-state mutation was performed for this local implementation. Deployment, incident-bound code repair, actual migration/retirement and final public delivery remain parts of the original goal.
