# Kesher Supervision Stability V2 — Design

## Goal

Make the existing Kesher Article → Video Overview → Short pipeline converge reliably without duplicate work, with a deterministic hourly escalation contract: **S1 Controller → S2 Jules → S3 Direct supervisor takeover**.

## Existing foundation we preserve

The production V5 controller already owns durable state on `automation-state`, exact article/media source identity, provider/artifact/source IDs, retry budgets, public YouTube verification, backlog recovery, and strict A+B+C delivery checks. V6 already has an isolated read-only shadow namespace. This change extends those mechanisms instead of creating a second state system.

## Durable incident identity

Each incident is identified by:

`pipeline_id + slug + content_sha256 + stage + failure_signature`

The persisted intervention record also carries a deterministic idempotency key, owner (`controller`, `jules`, `direct`), strike, last durable progress fingerprint, last action time, and any Jules repair session identity. A changed failure signature is a new incident. Durable progress resets the old incident sequence.

## Escalation contract

- **S1 Controller:** first hourly observation of a persistent failure. Production V5 remains the owner; its fast 5-minute watchdog/recovery cadence may continue, but the supervisor does not create a second identity.
- **S2 Jules:** if the exact same incident is still incomplete on the next hourly observation, hand that exact incident to Jules. Reuse an existing exact incident repair session if present; otherwise create at most one deterministic repair session. The Jules prompt is identity-bound and forbids creating a new article/provider/media identity or a duplicate upload.
- **S3 Direct:** if the same incident is still incomplete on the third hourly observation, persist `direct_takeover_required` for the supervisor to repair code/config/workflow/PR/deploy directly after normal QA gates.

An external NotebookLM generation or YouTube processing job may remain active up to the configured hard timeout, but ordinary Controller/Jules/CI coordination does not suppress the next hourly escalation.

## Supervision policy / SLAs

Extend `config/kesher-production-contract.json` with a validated `supervision` section containing:

- `incident_fingerprint_version: 2`
- `strike_interval_minutes: 60`
- `external_running_hard_timeout_minutes: 90`
- escalation sequence `controller`, `jules`, `direct`
- stage SLA table: article 60 minutes, long video 90 minutes, short 90 minutes
- prompt versions for controller recovery and Jules incident repair

The root production contract remains backward-compatible; the new section is additive but mandatory for current code.

## Idempotency

Keep existing provider/upload idempotency and add an explicit deterministic supervisor idempotency key derived from the exact incident identity. Jules repair sessions use this key in their title and state, so an uncertain API response can be reconciled by listing sessions instead of blindly retrying creation.

## Jules incident repair

Add a focused repair adapter separate from the daily article generator. Its prompt must require:

- operate only on the exact existing incident identity;
- inspect current repo/workflow evidence first;
- preserve source/provider/task/artifact identities;
- never create another article, NotebookLM provider generation, video or YouTube upload;
- create at most one code/config/workflow repair PR if a repository fix is actually required;
- otherwise report the evidence/fix path in the same session.

Unsafe Jules session creation is never blindly retried.

## V5 state enhancements

Persist `pipeline_id: v5`, the current exact `source` identity when an authoritative article exists, and the supervision contract version. The existing `interventions` map remains the single durable incident ledger.

## V6 shadow learning

V6 remains non-production and read-only. Add an incident retrospective/parity report that reads V5 durable state and emits what V6 would recommend for the current incident, while continuing to assert all dispatch/upload flags are false. Schedule the V6 shadow analyzer hourly on a staggered minute so it can accumulate evidence without colliding with V5.

## Testing and rollout

Use TDD. First update/add tests so they fail against the current `Controller → Controller recovery → Direct` behavior. Then implement the smallest changes to pass. CI must cover intervention identity, S1/S2/S3 behavior, idempotent Jules repair, V5 state source persistence, supervision contract validation, and V6 isolation. V6 is not promoted by this change; promotion remains a later decision after enough shadow incidents.