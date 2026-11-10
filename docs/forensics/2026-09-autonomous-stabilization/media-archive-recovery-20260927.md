# Media archive crash recovery

Status: connected local implementation with regression and full Python verification;
bounded independent review clean. This does not activate the canonical production path.

## Failure and invariant

**PROVEN (local reproductions):** A media worker could save its immutable archive
intent and stop before Actions created the archive. Subsequent commands adopted
that intent indefinitely. They could also begin rendering again while the original
archive remained uncertain. Previous metadata checks bound the run ID but omitted
its original attempt and workflow path.

Archival is a non-public evidence operation. It must remain separate from provider
generation and a YouTube upload session. Retiring a missing archive can authorize
another archive request; it can never authorize a new provider job or video insert.

## Recovery decisions

| Observed evidence | Deterministic response |
| --- | --- |
| Exact archive exists | Check original service metadata, all ZIP bytes and full descriptor; restore and reuse it. |
| Inventory incomplete, malformed or unavailable | Preserve uncertainty; do not retire or replace. |
| No archive and original producer still active | Persist archive-pending result; skip provider, render and upload steps. |
| Complete inventory has no matching archive and exact original attempt is terminal | Record unavailable archive receipt; a later admitted command may reconstruct derived bytes from the existing provider identity. |
| Three distinct archive requests for one source/kind/generation attempt | Stop creating archives and record a persistent repair incident. |
| Existing upload capability lacks its archived bytes | Preserve the capability and fail closed; reconstruction cannot replace bytes already bound to an upload. |

The inventory is bounded and checked for stable totals, complete counts, unique
IDs and a unique exact name. The original attempt is read through the
[attempt-specific Actions endpoint](https://docs.github.com/en/rest/actions/workflow-runs#get-a-workflow-run-attempt).
The [artifact inventory and metadata APIs](https://docs.github.com/en/rest/actions/artifacts#list-workflow-run-artifacts)
provide producer-run and immutable archive identity. Local tests use a controlled
service fixture; no actual Actions archive was created for this regression.

Retired requests stay in canonical state. Replacement names bind the new producer
command/run, so a late artifact from the old request cannot become the replacement
archive. The independent lineage auditor rejects conflicting active archives and
ignores only request-bound unavailable receipts. All existing media, source,
native-Short, signature, audio, channel and public-metadata gates remain required.

## Proof and limits

`tests/test_kesher_output_artifacts.py` exercises real canonical claims, effects,
ZIP files and restored bytes, with only the external service replaced by a fixture.
It proves lost-response adoption, active-producer waiting, terminal missing-archive
recovery, wrong producer attempts/workflows, changed service identity, incomplete
inventory and archive-budget exhaustion even when render bytes change.

Controller and media-observer regressions prove that archive recovery does not
inherit earlier provider-poll counts and eventually creates one persistent incident.
The workflow consumes the restore result before loading media-provider credentials
into the preparation step.

The earlier full Python suite passed 859 tests (125.169 seconds). Subsequent review
reproduced a changed-render-hash exhaustion bypass, now blocked before rendering.
The reviewer independently passed 65 focused tests and reproduced terminal exhaustion
at three requests, plus adoption of an active third producer without a fourth request.
The combined deployment/media review-fix gate passed 102 tests (16.660 seconds).
The latest complete Python result is recorded in WORK_LOG. Archive expiry, independent technical-proof upgrades, generation-attempt
rotation, incident-bound Jules repair, migration and live public proof are separate
remaining parts of the full stabilization goal.
