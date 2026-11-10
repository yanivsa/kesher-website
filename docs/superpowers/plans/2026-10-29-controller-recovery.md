# Controller recovery implementation plan

> **For agentic workers:** Use superpowers:executing-plans. Continue inline under the user's “do it” authorization.

**Goal:** Connect persistent failure diagnosis to a bounded repair executor from the admitted controller, and prove recovery does not duplicate media.

**Architecture:** Keep Schema-5 as the sole current production writer. Reuse the existing Jules recovery client and GitHub CAS transport. A repair ledger is separate from canonical content state; it never resets generation budgets or revives retired workflows. Preserve Schema-6 fencing.

**Tech Stack:** Python unittest, GitHub Actions, existing Jules API adapter.

**Spec:** KESHER_reliability_plan_2026-10-29.md, revised section 5 approved by “do it” in the thread.

## Global constraints

- Do not reactivate retired supervisors or bypass merge authority.
- No new generation, upload or content identity during repair coordination.
- Persist intent before external effects; reconcile uncertain outcomes by exact task identity.
- Never treat a repair PR or healthy unrelated cycle as verified recovery.
- Keep account credentials out of incident packets and reports.

## Review focus

- Repeated ticks, lost create response, failed ledger acknowledgement.
- Unknown failure before an article exists.
- Schema handover between observation and mutation.
- Completed Jules task with an unmerged PR.
- A previous cycle must remain unresolved when today's unrelated cycle completes.

## Tasks

- [x] Add tests for exhausted stages/direct-takeover classification, durable deduplicated repair creation, uncertain-create reconciliation, bounded running time, merged PR versus actual delivery, and admission fencing.
- [x] Implement scripts/kesher_controller_repair.py using existing client/transport; integrate after controller step with explicit outcome and structured summary.
- [x] Reproduce existing stale upload-state failure and enforce authoritative snapshot for all callers; run media crash-consistency tests.
- [x] Add all new recovery tests to CI and test:controller. Recertify only reviewed hash leaves after inspecting capability changes.
- [ ] Run required Python contract suites, review the entire change, publish a reviewable PR, and inspect CI.

## Execution ledger

- Baseline: 26/27 targeted recovery tests pass. test_two_snapshots_only_one_upload_eligible fails because upload_only skips authoritative-state prechecks when state= is supplied. Other production guards may still prevent upload; test expects explicit stale-target rejection.
- Ruling: execute inline without another plan-approval round; the user explicitly instructed execution of the revised plan.
- Ruling: do not revive the retired supervisor or its denied merge endpoint. Automated code repair must record an awaiting_review state when repository policy does not permit autonomous merge; it cannot claim deployment or repair success.

- Review: fresh reviewer found content-PR false proof, hidden historical blockers, prepublication binding gaps, summary severity and task acquisition timeout. Each was addressed with regression coverage.
- Verification: targeted production/recovery tests pass, including lost-create/acknowledgement and real delivery-contract checks. Controller, authority and CI contract suites were run; release verification and remote CI are recorded with the PR.
- Ruling: content cannot be bound by date alone. Owner idea, content PR, article run/session or exact slug/hash must match. If all are missing, successful delivery is not guessed.
