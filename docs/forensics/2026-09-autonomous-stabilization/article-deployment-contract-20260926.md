# Canonical exact Pages deployment

Status: implementation and local verification in progress. This is not a production
activation or public A+B+C claim. Legacy deployment and controller retirement remain
part of the coordinated migration.

## Evidence that changed the implementation

- **PROVEN (pinned source):** Wrangler 4.100.0 retries the deployment-creation POST
  for its `UNKNOWN_ERROR` response. The canonical executor therefore uses Wrangler
  only to compile Functions and upload content-addressed assets. Creation is a
  separate single HTTP request with no automatic retry or redirect.
  [Pinned deployment implementation](https://github.com/cloudflare/workers-sdk/blob/wrangler%404.100.0/packages/wrangler/src/api/pages/deploy.ts),
  [asset-only command](https://github.com/cloudflare/workers-sdk/blob/wrangler%404.100.0/packages/wrangler/src/pages/upload.ts).
- **PROVEN (authenticated read-only API):** The existing project is
  `kesher-website`, ID `41773648-4870-407a-b868-5f05f2a2da57`, production branch
  `main`, Functions compatibility date `2026-05-15`, flags `[]`. Creation refuses
  changed project identity, production branch or compiler compatibility. No
  project configuration, domains or environment values were changed or copied.
- **PROVEN (authenticated read-only API):** A production listing with
  `per_page=100` returned API error `8000024`; `per_page=25` succeeded and reported
  757 deployments across 31 pages. The adapter uses the accepted size and checks
  page/count/total consistency, uniqueness and complete bounded pagination.
  The first 25 rows had the expected project, boolean skip status, string commit
  metadata and immutable Pages URL structure. This is schema evidence, not a
  current public delivery assertion.
- **PROVEN (local compiler):** The pinned `pages functions build` command creates
  the actual multipart `_worker.bundle` plus routing metadata. Output parent
  directories must exist before asking it to write generated routes. The local
  probe first exposed that requirement and passed after creating the directory.
  [Compiler implementation](https://github.com/cloudflare/workers-sdk/blob/wrangler%404.100.0/packages/wrangler/src/pages/build.ts).

## Connected execution

`deploy_article` routes exclusively to `kesher-article-deploy.yml`, with exact
command admission, immutable main checkout and one global deployment concurrency
group. A new build runs the complete existing production quality gate. Measurement
placeholder handling remains explicit, and the trusted publication-manifest
generator binds the committed article and hero bytes to rendered HTML.

The archive includes every static file, `_headers`, `_redirects` when present,
`_routes.json`, the hidden publication manifest, compiled Functions multipart
bundle and Functions routing metadata. Its descriptor contains all file lengths
and SHA-256 hashes. Only compact source/code/build/manifest digests and original
producer identity enter canonical state. The service artifact ID, original Actions
run/attempt/workflow, archive digest and every downloaded byte are checked before
the worker may publish. Static or Functions changes after archival are rejected.

Replacement commands adopt the original request and producer before recovery.
Restoration validates a temporary sibling tree and atomically renames it; an
already completed restore is verified before reuse. When an exact producer has
stopped and the complete artifact inventory has no matching archive, recovery may
retire only that non-public archive attempt and allow a bounded rebuild. A late
archive cannot publish and is not silently selected. This permission never
applies to an uncertain Cloudflare creation request.

After uploading assets, the worker rechecks all local bytes, current main, current
source ownership and project compatibility. It persists the complete deployment
intent, including an exact commit marker, archive receipt and asset-manifest
digest, before a single Pages creation POST. A response body never proves delivery:
the worker always observes the exact marker, deployment ID, SHA, production branch,
project and latest stage through separate GETs. A known ID survives missing local
build files and stopped workers. Another canonical deployment makes the old one
superseded. Duplicate markers are an incident, never resolved by selecting newest.

Confirmed terminal failures or definitive rejected requests permit a second
creation, with a durable two-attempt budget per main revision. Uncertain acceptance
permits only observation. Any preceding unresolved creation prevents a newer
revision from creating another deployment. Polls are finite under the controller's
deadline/incident policy and do not count as semantic progress.

A replacement runner observes the existing intent before choosing its path. A
permitted retry restores the original archive and prepares the pinned asset tool;
waiting or already settled deployments need no local build. Deployment recovery
budgets and stall clocks bind the exact main revision, independently of unchanged
article content. Settled prior deployment observations are retained so earlier
history does not require a full re-read for every new creation; the current
canonical deployment is still fetched freshly for public verification. No endpoint
that retries an existing deployment is used by this runtime.

## Independent public boundary

The observer reads Pages canonical routing and the original immutable Actions
artifact metadata independently, including when the worker died before recording
a receipt. A green `deploy.yml` run is no longer a deployment reader or accepted
proof. Article verifier version 2 requires that actual deployment identity and the
exact archived publication-manifest digest, then checks actual public HTTP,
canonical route, source-derived title/body/metadata, HTML digest and full hero
bytes. The source-level controller rejects older article-verifier versions.
Overview/Short proof remains independently required.

## Limits to retain in the final audit

Cloudflare's documented creation API offers neither an idempotency key nor an
atomic condition on GitHub main. A fresh main read narrows that cross-service race;
it is not a transactional fence. Durable one-shot intents and serialization prevent
an ambiguous request from being blindly replayed, but an intent persisted just
before a process dies can remain uncertain without any creation. Such an unresolved
creation must not become permission to overwrite newer production; its finite
incident resolution still needs scrutiny in the whole-system chaos/escalation audit.
[Creation API](https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/deployments/methods/create/).

The compiler and asset uploader are version-pinned, but the new path has not yet
performed a real Pages creation. Service metadata is not a remote Functions-byte
download. Public article verification proves the served article/hero/manifest;
Functions provenance rests on the exact archived bundle sent by trusted code.
The archive retention is 90 days. Expiry handling, historical state adoption,
live cutover, legacy retirement and final exact public delivery remain explicit
whole-goal work. Existing production schedules continued advancing main during
this investigation; dated observations must never be treated as current main.

## Local review and proof

The initial independent archive review reproduced two Important defects: a
replacement request failed to adopt its original producer and a killed restore
left a partial destination. Both were corrected with red/green regressions. A
subsequent independent review reproduced the missing fresh-runner archive/tool
restoration before a permitted Pages retry; that path also has a new regression
and correction. The reviewer then stopped with an account usage-limit error.
Final independent review of the full connected slice remains outstanding.

`deployment-local-proof-20260926.json` records the exact runtime module hashes for
a real local 342-file site/Functions archive, full ZIP-byte readback and atomic
restore. The artifact-service metadata in that probe is synthetic. It did not
upload an artifact to GitHub, create a Cloudflare deployment or verify production.
