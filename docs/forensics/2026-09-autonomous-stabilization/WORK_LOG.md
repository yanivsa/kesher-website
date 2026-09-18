# Stabilization work log

Goal remains active. This is a progress ledger, not an autonomy/completion claim.

## Scope and baseline

- Repository: `yanivsa/kesher-website`.
- Branch: `codex/kesher-autonomous-stabilization-20260917`.
- Baseline main: `55563f42e16618af5d93c39c26a8dd921d3ce019` (#865).
- Full requested scope: forensic history, canonical identity/state, deterministic controller and recovery, Jules incident repair with guard integrity, public Article + Overview + native Short verification, obsolete-path retirement, regression/chaos tests, one PR, complete CI, safe merge and production reconciliation.
- Production mutations during inventory: none. No generation/upload/canary sessions created.

## Completed evidence collection

1. Paginated all 781 PRs, all 84 Issues, all issue/review comments, changed paths and final PR commit lists. The initial index contains 566 scope candidates and 299 reviewable exclusions. Candidates/claims are explicitly UNKNOWN pending adjudication.
2. Fetched every PR head, including closed/unmerged PRs. Local history grew from 4,472 to 5,925 reachable commits. Force-pushed historical heads/review bodies are a separate ongoing pass.
3. Captured all 21,442 retained Actions runs through 2026-09-17T20:06:06Z across 105 historical workflow paths. Creation-time partitions avoid GitHub's 1,000-result filtered-search limit; every partition's unique row count was checked.
4. Inventoried all 61 workflow files on baseline main. An API workflow's `active` flag is not treated as evidence its file/trigger still exists.
5. Read-only snapshots of production controller, supervisor and five media artifact state files were captured. One archive download was unavailable; this is recorded, not silently treated as empty state.
6. Baseline `python3 -m unittest discover -s tests -p 'test_*.py'`: 501 tests passed.
7. Baseline `npm ci` and `npm run check`: completed with exit 0, including content/video/controller gates, Vitest, build/dist validation, and 116 Playwright checks. Existing dependency advisories and lint warnings are baseline observations, not repaired by this inventory.

Raw snapshots/logs are in an external private cache. Committed indexes identify capture times, hashes, gaps and confidence. They are evidence inputs, not mutable production truth.

## Active investigation

- Article/image/normalization/deployment history: independent forensic pass, no runtime edits.
- Media/auth/signature/voice/duration/cache/metadata history: independent forensic pass, no runtime edits.
- Intermediate agent guard changes and Jules repair contract: independent forensic pass, no runtime edits.
- Controller/state/ownership/escalation history, Actions/job/log evidence and architecture: primary investigation.

## Findings awaiting regression/implementation

- The legacy Task Supervisor and V6 workflow are currently validation-only. Their existence alone does not establish competing production mutation.
- Production dispatch still traverses V3/V4/V5/stabilized layers, several with mutable module-level installation hooks.
- Controller state saves reread the newest blob SHA and can overwrite newer state with an old in-memory snapshot; this is not a compare-and-swap against the revision originally observed.
- General controller HTTP retries include POST workflow dispatch, allowing an uncertain accepted request to be repeated.
- Backlog resume dispatch can select an exact item, then omit that identity from worker inputs.
- Supervisor run adoption uses creation time rather than a command-bound receipt; its active-worker exception is global rather than source-bound.
- Jules article progress fingerprint includes `updateTime`, contrary to semantic-progress intent.
- Persisted baseline state simultaneously marks an Overview verified and exhausted; one supervisor incident has strike 55 and `human_blocker`, showing repeated bookkeeping beyond the advertised three-stage ladder.

These findings are based on inspected baseline code/state. Historical causality and final recovery design remain under review.

## Remaining required work

Complete incident adjudication and source-linked root-cause graph; inspect relevant Actions logs/jobs/artifacts and missing historical evidence; write final design/invariants/migration; add failing reproductions; implement canonical runtime and state migration; eliminate obsolete mutation entrypoints; enforce Jules repair integrity; run full and chaos suites; adversarial review; one stabilization PR, exact-head CI, safe merge and shadow/public reconciliation. Do not equate this inventory or passing baseline tests with completion.

## Canonical boundary implementation — 2026-09-18

This is local implementation on the single stabilization branch; canonical runtime is not yet wired to production. No provider creation, upload, production state mutation, or workflow dispatch was used for these checks.

- The target architecture and eight-part implementation plan are persisted alongside this log. The full original scope remains required, including migration, removal of old mutators, public verification, one PR, complete CI and post-merge proof.
- The first Actions evidence pass inspected 917 selected runs: 829 logs available, 88 unavailable. A scope audit then found historical one-off mutators and shared CI/deploy runs missing from that selection. Expanded selection now includes 3,501 runs from 10,915 pipeline-associated runs, including all cancelled/skipped outcomes. Collection is proceeding in bounded, restartable API batches. Read `workflow-run-evidence-coverage.json` for actual collected and pending counts; selected does not mean adjudicated.
- `GitHubClient` no longer retries uncertain POST/PUT requests or rebinds stale state to a newer SHA after a 409. Four original behavioral regressions failed before this fix; all six boundary tests passed after it. The old 409-retry expectation came from direct commit `581300481f32285b80ce13e028630386e3c079ce`; replacing it with a one-write/reconcile requirement strengthens the invariant rather than weakening a guard.
- `scripts/kesher_runtime` now has explicit source/media/slot identities, immutable loaded snapshots, revision-bound CAS, one pending action per target, deterministic command IDs, exact worker claims, append-only external intent/receipt records, and semantic progress without heartbeat-only rewrites. New code does not inherit or install any legacy controller globals.
- Workers can preserve an already-created provider receipt when a source is superseded, but cannot start a new external effect for that source. An independent verifier, not the worker's success result, must establish public product completion.
- Additional adversarial cases reproduced two gaps in the first local implementation: different operations racing one media resource, and recovery commands creating the same external work again. Failing tests were preserved before implementing shared resource exclusion and exact cross-command effect adoption. A pending uncertain external effect blocks a changed request.
- A real localhost HTTP server accepted requests and dropped the response, and injected 401/403/429/500/CAS failures. Mutations were never transport-retried; reads backed off within four attempts; long rate limits returned to the scheduler. No actual provider/API write was involved.
- Verification: 542 Python discovery tests passed after the initial canonical boundary implementation; after the cross-command recovery correction, 43 focused canonical/HTTP/worker/legacy boundary tests passed. New cases are included in the existing local controller gate and Actions stability gate. Full end-state CI is still outstanding.

Private red/green evidence: `state-safety-red.log`, `state-safety-green.log`, `state-safety-integration.log`, `canonical-conflict-red.log`, `canonical-conflict-green.log`, `cross-command-effect-red.log`, `canonical-worker-green.log`, `canonical-state-http-green.log`, and `canonical-boundary-discovery.log` in the external forensic cache. The initial missing-module run for the new API is only interface scaffolding evidence, not a reproduced historical bug.

Next implementation boundary: wire the durable command/effect protocol into existing real workers, implement the single controller and independent verifier, then migrate/retire existing writers. The new library alone does not demonstrate autonomous production operation.
