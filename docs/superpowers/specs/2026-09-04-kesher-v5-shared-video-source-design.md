# Kesher V5 Shared Video Source Pipeline — Design

Date: 2026-09-04
Status: Design for review

## Problem

The current production V4 controller intentionally replaced the legacy long-form `video` stage with the dedicated Short V4 stage. As a result, a cycle can finish with a live article and public Short while never dispatching `kesher-daily-video.yml`, so no regular YouTube video is produced.

A naive fix would dispatch both the long-form and Short workflows independently. That is unsafe and wasteful because both pipelines wrap the same NotebookLM provider engine but keep separate durable state. With independent `full` generation they can each create a distinct NotebookLM Video Overview for the same article, producing duplicate provider work and two media identities for one content item.

## Goal

For each authoritative article, produce exactly one provider source identity and publish all intended outputs:

1. article is public and verified;
2. one regular long-form YouTube video is public and processing succeeded;
3. one YouTube Short is public and processing succeeded;
4. long-form and Short are both traceable to the same article identity (`slug` + `content_sha256`) and the same NotebookLM provider identity (`task_id` + `artifact_id`);
5. retries resume existing work and never create a second provider generation for the same article unless the stored provider identity is proven unusable and an explicit bounded recovery policy permits replacement.

## Recommended Architecture

Use a V5 controller with three explicit downstream stages: `article`, `long_video`, and `short`. The long-form pipeline owns provider generation. Short becomes a derivative publisher that reuses the long-form provider artifact instead of creating its own NotebookLM generation.

The source-of-truth flow is:

`article -> long_video provider source -> long_video publish -> short derive/publish -> complete`

This is deliberately sequential at the provider-identity boundary. The controller may reconcile stages on every event/heartbeat, but it must not dispatch Short fresh generation independently.

### Why V5

V4 has an explicit runtime contract that maps the generic controller `video` stage to `kesher-short-v4.yml` and archives the old Video Overview as a different product. Existing V4 tests enforce that the Short workflow is the single controller-owned video worker. Reintroducing long-form semantics without a schema/version boundary would overload one state slot with two products and make migrations ambiguous. V5 therefore introduces distinct state fields rather than mutating the meaning of V4 `video` in place.

## Stage Contracts

### `article`

Keep the current article generation, normalization, trusted-image, deploy and public verification behavior. Article publication remains independent and must never be rolled back because video generation fails.

The canonical content identity is captured when the article is verified live:

- `slug`
- `content_sha256`
- public URL
- title/date as needed for metadata

Both video stages must match that exact identity.

### `long_video`

Use the existing `kesher-daily-video.yml` and `kesher_daily_pipeline.py` as the provider-generation and long-form publication engine.

Responsibilities:

- reconcile the exact authoritative article or matching unresolved durable item;
- create at most one NotebookLM Video Overview provider task for the article;
- persist `source_id`, `task_id`, `artifact_id`, article identity and media evidence in `kesher-video-state`;
- render/validate the long-form 16:9 output;
- upload exactly once and verify the public YouTube video;
- retain provider identity after local MP4 pruning so the NotebookLM artifact can be redownloaded for downstream derivation/recovery.

The controller considers `long_video` complete only when the matching durable item has public YouTube verification and exact article identity.

### `short`

Keep `kesher-short-v4.yml` and `kesher_short_pipeline_v4.py` for the creative contract, portrait Remotion render, validation and YouTube upload, but change controller-owned production behavior so it does not create a new NotebookLM generation.

Add a derivation/adoption operation that:

1. reads/imports the matching `long_video` durable provider identity for the current article;
2. seeds/reconciles a Short state item using the same `source_id`, `task_id`, `artifact_id`, `slug` and `content_sha256`;
3. redownloads the existing NotebookLM artifact if local media is absent;
4. renders the Short from that exact source using the current V4 Short adapter (`overview-segment` when the source is longer than the Short limit);
5. validates portrait media, uploads exactly once, and verifies public YouTube processing;
6. persists to the separate `kesher-short-v4-state` artifact.

Existing manual `full/generate` behavior may remain temporarily for backward compatibility and diagnostics, but V5 controller production must never use it for a normal article. Controller-owned Short dispatches must use the adopt/derive path only.

## Shared Identity Contract

A Short may be derived only when all of the following from long-form state match the current authoritative article:

- non-empty `source.slug` equals article `slug`;
- `source.content_sha256` equals the current article hash;
- non-empty `source_id`;
- non-empty `task_id`;
- non-empty `artifact_id`;
- the long-form item is not a tombstone/released item and its provider generation has reached a state from which the artifact can be retrieved.

If any identity field is missing or mismatched, fail closed. Do not start an independent Short generation as an automatic fallback.

## Controller V5 State

Bump controller schema to V5 and represent the two products separately:

```text
article:      existing article stage
image:        existing trusted-image stage
long_video:   long-form attempts/run/provider/publication state
short:        derivative Short attempts/run/provider/publication state
```

Do not reuse one `video` field for both products.

The final cycle status is `complete` only when:

- article is verified public;
- matching long-form YouTube video is verified public;
- matching Short is verified public.

Intermediate product failures do not invalidate the live article. They keep the cycle incomplete/blocked or retryable according to the bounded retry policy.

## Migration and Current Article

Migration must be evidence-based and idempotent.

### Existing V4 Short

If V4 durable Short state already contains a verified public Short matching the current article `slug` + `content_sha256`, migrate/adopt it as V5 `short=complete`. Do not upload another Short merely to satisfy the new architecture.

### Existing legacy long-form state

Inspect `kesher-video-state`. Adopt a long-form item only if it matches the current article identity and has authoritative public YouTube verification. Otherwise initialize `long_video` as incomplete and dispatch/resume the existing long-form pipeline for the current article.

For the current article `smart-youth-focus-tasks-organization`, the existing public Short should therefore remain the active Short if its identity matches, and V5 should generate/publish only the missing long-form video. Future articles follow the shared-source derivation flow.

## Event Wiring

Update `kesher-content-controller.yml` so controller reconciliation wakes on completion of both child workflows:

- `Kesher Daily NotebookLM Video Overview`
- `Kesher Daily Article Short V4`

Keep the heartbeat for recovery.

The controller must correlate child runs by workflow name, dispatch time/run id and exact stage, so a completed long-form run cannot be adopted as Short completion or vice versa.

## Retry and Duplicate Prevention

- Before any dispatch, reload the newest durable state for the target stage.
- If an active production run exists for that stage, wait rather than dispatch another.
- If a matching provider identity exists, resume/recover it rather than generate fresh work.
- Revalidate stale rebuild/derive inputs against newest durable state immediately before dispatch, preserving the stale-input race fix already added in V4.
- Short derivation must never silently fall back to fresh provider generation.
- A successful workflow conclusion alone is not completion; durable item/public YouTube evidence is required.
- Keep independent concurrency groups for long-form and Short, but do not allow Short derivation until a reusable long-form provider artifact identity exists.

## Error Handling

### Long-form generation pending

Wait/resume the same provider task. Do not start Short generation.

### Long-form upload failure with reusable artifact

The controller may continue retrying long-form upload. Short derivation can be enabled once the provider artifact is proven retrievable and exact identity is stable; however, the first implementation should prefer the simpler conservative gate of deriving Short after long-form public verification unless tests prove earlier derivation materially improves recovery without weakening identity guarantees.

### Provider artifact unavailable

Fail closed with a specific blocker. A replacement provider generation is allowed only under the existing bounded recovery rules and must create a new identity that both downstream products subsequently share.

### Short render/upload failure

Retry/rebuild the exact Short item derived from the shared artifact. Never regenerate NotebookLM solely because Short rendering failed.

### One product succeeds and the other fails

Persist the successful product. Retry only the missing product. Never duplicate the successful upload.

## Testing Strategy

Use TDD. Add failing tests before production changes.

Required coverage:

1. V5 migration preserves a matching verified V4 Short and does not dispatch another Short.
2. V5 migration adopts a matching verified long-form item but rejects stale/mismatched long-form state.
3. A live article with neither output dispatches long-form first, not Short generation.
4. A reusable matching long-form provider identity causes Short derive/adopt dispatch with the same `task_id`/`artifact_id` and no NotebookLM generation call.
5. Short derivation fails closed on slug/hash mismatch or missing provider identity.
6. Long-form public + Short missing dispatches only Short derivation.
7. Short public + long-form missing dispatches only long-form and preserves the Short.
8. Both public yields controller `complete`.
9. Active child runs are not duplicated.
10. Fast child completion is correlated to the correct stage.
11. Stale derive/rebuild input is revalidated against newest durable state before dispatch.
12. Workflow contract test verifies the controller listens to both child workflows.
13. Short production path test proves controller-owned execution cannot call NotebookLM `generate video` when a shared provider identity is required.
14. Current article regression proves the existing public Short is not duplicated while the missing long-form video is created.

Run the existing controller, V4 runtime, Short V4, video reconcile, stability and CI suites in addition to new V5 tests.

## Rollout

1. Introduce V5 code and tests behind the controller entrypoint without deleting V4 rollback code.
2. Migrate state on first V5 tick using evidence-only adoption.
3. Dispatch the missing long-form video for the current article.
4. Verify the regular YouTube video is public and processing succeeded.
5. Verify the existing Short remains the same public item and no duplicate Short/provider generation occurred.
6. On the next fresh article, verify one NotebookLM provider task feeds both long-form and Short outputs.
7. Keep V4 runtime available for rollback until at least one fresh V5 cycle completes end-to-end.

## Definition of Done

The change is done only when a fresh article completes end-to-end with:

- one verified live article;
- one provider generation identity;
- one public verified long-form video;
- one public verified Short derived from that same provider identity;
- no duplicate provider task or YouTube upload;
- durable state that can resume each product independently after interruption;
- all relevant CI/tests green.
