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

## Public metadata and interrupted-upload boundaries

- A reproduced M-GAP-01 counterexample passed the old verifier with the wrong article URL because it only searched for the site-domain substring. New cases also reproduced an ignored response video ID, changed remote description, matching-but-invalid local/remote metadata, missing standalone site URL and unverified language.
- Source-derived metadata is now shared by Overview and Short: distinct Hebrew Short title, complete article and standalone site URLs, and a UTF-8 byte-limited description that reserves the entire URL suffix. Full remote title, description, tags, resource ID, channel and language must match. The receipt includes the source hash, kind, fetched metadata, verifier version and verification time; public visibility and successful processing remain required.
- Existing upload IDs are reverified without another insertion or requiring pruned local MP4s. A completed resumable-session status query now adopts its returned video ID rather than calling the byte uploader again. Both lost-response recovery cases failed against the prior implementation and pass with the fix. Expired sessions still reject a second insert.
- API behavior/limits were checked against the primary [video resource documentation](https://developers.google.com/youtube/v3/docs/videos#snippet) and [resumable protocol](https://developers.google.com/youtube/v3/guides/using_resumable_upload_protocol). No actual uploads or metadata writes were used for testing.
- Remaining integration includes canonical provenance/public delivery derivation, automatic metadata-only correction of existing uploads, exact worker projection, canonical dispatch and migration. These checks alone do not prove duplicate-free production publication or complete A+B+C.

## Exact dispatch and Actions admission

- Expanded run evidence collection completed: all 3,501 selected runs have records; 3,317 logs were available and 184 unavailable. Failed artifact/job reads are explicitly counted. Collection coverage does not establish adjudicated root causes.
- The canonical outbox now commits each exact command dispatch intent before POST. It adopts only the full command ID in the workflow run name, uses a bounded redelivery budget, and distinguishes HTTP acknowledgment, claim, execution and product completion. A queued workflow without a claim has a finite acceptance deadline. Dispatch history and known receipts cannot be erased or rewritten.
- The Actions admission entry point derives target and operation from the canonical command, validates the actual checkout and workflow definition against trusted main, and binds ownership to the precise GitHub run/attempt. Wrong workflow, fork/PR event, stale checkout and rerun do not acquire another claim. Later steps can attach only to the existing exact owner.
- Verification: 45 focused state/worker/outbox/admission tests passed. New-entry missing-module red evidence establishes API scaffolding only; the outbox stalled-run/history cases are reproduced behavioral failures. These tests are wired into the controller and stability gates.
- Production workflows and real media state I/O have not yet switched to this entry point. This remains incomplete until worker adapters, one controller, migration and retirement are connected and verified.

## Exact media execution and uncertain-effect reconciliation — 2026-09-20

- The real Overview/Short processing functions now accept a canonical single-item state adapter. Every provider source/task and upload-session creation persists its exact intent first and its returned identifier before subsequent processing. Reconciliation cannot select FIFO, newest global artifacts, another type or another source hash. The canonical worker invokes the full render-to-upload path directly without installing legacy module globals.
- Upload capabilities are AES-GCM encrypted with the existing state key and bound to repository, immutable target and purpose. Raw session URIs never enter public state. Missing keys stop before generation; existing uploaded IDs can still undergo metadata-only recovery. Pending upload bytes cannot be silently changed or regenerated.
- Metadata repair reads the exact remote video/channel, changes only its snippet, and reads it back. A lost PUT response is recovered by observing the matching remote metadata, not repeating the mutation. The controller must still perform its own public verification.
- Lost NotebookLM creation responses are reconciled by unique source title plus complete normalized content, or the complete saved generation prompt with its exact identity marker. SDK inspection confirmed that these creation methods disable mutation retries; read-only recovery uses source/artifact list APIs. Ambiguous duplicates fail closed. This has been tested with fakes; no real provider generation or upload was performed.
- Short render/signature caches now bind to actual bytes and complete provenance. Historical fixtures that assumed an appended outro or accepted a cached signature after deleting its final MP4 were migrated to the later approved in-content contract, preserving the old failures as negative tests.
- Verification: 173 focused provider/worker/state/dispatch/metadata/media tests passed (8.590s). An integration audit then reproduced GitHub string inputs being rejected as generation attempt numbers; three worker cases failed before the fix and all four passed afterward. Full Python discovery currently has 9 failures and 1 error among 611 tests, primarily legacy incomplete-proof fixtures/projectors; these are pending contract migration or retirement, not waived. Full CI has not yet passed.
- Remaining: immutable output-artifact handoff, controller/recovery, public article/deployment proof, attempt rotation, state migration, legacy retirement, trusted Jules repair, full gates and real production reconciliation. None of the local media work proves the final autonomy criteria.

## Single-controller decisions and exact article proofs — 2026-09-21

This is concrete local implementation and new forensic evidence, not a production cutover. The active goal still includes every original implementation, migration, retirement, repair, CI, merge and public-verification requirement.

- The controller decision core now adopts immutable sources from observed main, records independent A+B+C receipts, revokes completion on failing current evidence, plans at most one exact action per tick, and alternates current/backlog eligible work. State writes happen before dispatch; a CAS conflict prevents dispatch. Duplicate daily sources/PRs fail closed. Already adopted source identities and receipts remain auditable when content changes.
- Recovery uses identity-bound action budgets and semantic progress. Provider waits do not consume generation attempts. Unknown observation, unchanged PR head/status, missing worker acceptance and active worker stalls have finite deadlines and persistent incident identities. Software exhaustion requests repair; only confirmed provider-specific external reauthentication/permission evidence enters the external-action state. Jules execution of those repair incidents is still pending integration.
- Three behavioral counterexamples initially exposed missing circuit breakers: unknown observations and timestamp-only PR activity waited forever, and ambiguous sources still returned an earlier unclaimed command. Regressions now cover those cases. A fourth reproduced repeated delivery of an exhausted unclaimed command; it now leaves a persistent acceptance incident and no further delivery. The focused controller/state/worker gate passed 55 cases; route/admission integration passed 33 after the last route change.
- Ruling: pre-merge normalization/image/merge commands belong to the publication slot and exact PR head, not a final source hash that normalization or image attachment can change. The immutable media source is adopted from main after merge. Dispatch routing now supports those slot-bound worker commands; production workflow conversion is still outstanding.
- All article image proof consumers now share full decode, article/image digest and current-head checks. PNG structure plus complete Pillow decoding rejects header-only, truncated, corrupt and appended-byte files. Test dependencies are pinned in `requirements-article.txt` and installed in CI/deploy/image jobs. Existing header-only fixtures were replaced with real image bytes rather than loosening the guard.
- The independent public article verifier checks exact main/deploy SHA, canonical route (including Hebrew percent transport and permitted trailing slash), visible full body/title/date, structured and social metadata, decoded hero bytes, build HTML digest and source-bound markers. A matching manifest alone cannot certify wrong visible content. The build proof generator validates the actual rendered output before issuing its manifest. The site publication selector supplies eligible posts; unsupported legacy rows are listed explicitly and cannot satisfy canonical delivery.
- Real repository validation discovered G10/#836: the published image file equals another article's full PNG plus one NUL. The stronger gate and a valid-PNG recompression counterexample prove SHA-only uniqueness was insufficient. Decoded-pixel uniqueness is now checked by the producer and both merge/repository gates. The trusted deterministic LocalEditorial renderer produced the replacement without an external provider call; `image-repair-receipt.json` preserves provenance. All 87 repository images pass the strict gate.
- The formerly missing guard probe now exists and ran: all 123 cited sources were resolved (40 PRs, 53 commits, 22 pinned blobs, 6 comments and 2 incident force-push events); G06/G08/G10 counterexamples were reproduced offline and the pinned G09 CAS regression passed. These counts describe cited sources, distinct from the larger 276-PR scan and 170 timeline events.
- Verification so far: 100 focused article/controller/boundary tests passed; the real frontend build passed; the Node automation gate passed after behavioral fixture migration. Full Python discovery ran 650 tests and retains the same 9 legacy media-proof fixture/projector failures plus 1 upload-guard error. They are not waived. The next integration must finish media provenance/artifact persistence, canonical workers/controller observation/Jules repair, migration and retirement before full green CI can prove the intended architecture.
- Final precommit audit reproduced two additional defects: unresolved slots could route to deployment, and generic transient article retries counted `reconcile` while dispatching `deploy_article`, making the retry count remain zero. Both behavioral regressions failed before correction. Deployment now requires an adopted source, and recovery counts the actual dispatched operation. All 57 focused article/proof/controller/outbox tests pass; `git diff --check` is clean.

## Immutable media handoff and one media worker — 2026-09-22

- The committed-source article proof was rerun against `24aabb76883e58bec8880c85550f24cc5c0baa94`: 66 rendered articles passed exact Git source/image/HTML validation; 21 legacy exclusions remain explicit and cannot satisfy canonical delivery. This was a local built-artifact check, not a public deployment verification.
- A new behavioral regression reproduced upload beginning immediately after rendering, before the output existed anywhere durable. Canonical media execution now has explicit prepare and publish boundaries. Publish requires both the saved immutable artifact receipt and matching local file bytes; it never re-enters provider generation. Metadata recovery for an existing YouTube ID remains independent of retained local MP4s.
- Output bundles contain only declared raw/final media, manifests, render plans, props, signature and review files. No state, cookies or credentials are copied. The controller state stores the artifact intent and exact receipt; archives do not become competing state stores. Receipt validation reads GitHub artifact/run metadata and the complete archive, checks producer command/run/code/source/kind and every file checksum, rejects extra/duplicate/path-traversal/symlink entries, and streams bounded downloads without forwarding GitHub credentials to the archive host.
- Lost artifact responses are adopted only from their exact producer run/name. Recovery commands reuse that receipt and restore the original bytes, including after deleting the worker directory. Missing/expired artifacts or conflicting local files fail closed rather than rebuilding the bytes of an existing upload. An intent interrupted before artifact creation still needs the bounded controller repair/reconciliation path; no public product completion is inferred.
- The canonical outbox now routes both kinds to one `kesher-media-worker.yml`. The workflow claims exact ownership before provider credentials, restores exact output, prepares, archives, reads back, publishes and records execution separately. Its Actions definition passed actionlint 1.7.12 after correcting an invalid job-level runner context. The downloaded validator was checked against its release checksum. Existing legacy workflows remain live until the forthcoming atomic migration/retirement; this local routing change alone is not cutover.
- GitHub artifact semantics were checked against the official [artifact API](https://docs.github.com/en/rest/actions/artifacts) and the pinned upload action's [file selection implementation](https://github.com/actions/upload-artifact/blob/043fb46d1a93c77aae656e7c1c64a875d1fc6a0a/src/shared/search.ts). The latter filters directory entries, matching the archive validator's file-only contract.
- Validation: 62 focused controller/admission/outbox/worker/artifact tests passed before the last two additional cases; all 12 artifact cases subsequently passed, including a different recovery command and authenticated-download isolation. The render-before-archive regression failed first and passes after the boundary fix. This does not replace full CI, real media provenance validation, controller observation/recovery, migration, trusted repair, merge or public A+B+C proof.
