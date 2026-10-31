# KESHER Master Owner Foundation — Implementation Plan

Date: 2026-10-31
Scope: foundation only. No production authority cutover and no Master Active Supervisor prompt change in this phase.

## Goal

Move KESHER decision ownership toward Master Active Supervisor while preserving the existing Schema-6 state, CAS guarantees, deterministic workers, and fail-closed production authority controls.

Target control loop:

`OBSERVE -> RECONCILE FACTS -> MASTER DECIDE -> PLAN EXACT COMMAND -> WORKER EXECUTE -> VERIFY -> REPEAT`

The Content Controller and Jules must not remain future decision owners. Existing workers remain deterministic executors.

## Task 1 — Separate fact reconciliation from command selection

Files:
- `scripts/kesher_runtime/controller.py`
- controller unit/contract tests

Steps:
1. Add a pure fact-reconciliation result that updates canonical observations, settlements, receipts, incidents, and eligible actions without selecting/planning a command.
2. Keep `reconcile()` behavior compatible by delegating to fact reconciliation and then the legacy deterministic selector.
3. Add regression tests proving fact reconciliation creates no new command and legacy `reconcile()` still produces the same exact command.

## Task 2 — Provider-neutral Master intent

Files:
- `scripts/kesher_runtime/master_intent.py`
- `scripts/kesher_runtime/master_intent_entry.py`
- `tests/test_master_intent.py`

Requirements:
- fail closed on stale main/state revision;
- explicit operation/target allowlist;
- no `create_article` through the legacy controller/Jules intent path;
- no dispatch from shadow mode;
- before production, sensitive worker inputs must be derived from fresh reconciled observations rather than trusted from an external payload.

## Task 3 — Provider-neutral article authoring contract

Files:
- `.github/prompts/kesher-article-authoring-contract.md`

Requirements:
- Master owns topic/research/copy/metadata and initial article PR;
- exact provenance marker and branch convention;
- no validator weakening;
- same identity must ultimately bind article, long video, and Short.

## Task 4 — Master-origin article quiescence

Files:
- `scripts/kesher_runtime/article_quiescence.py`
- `scripts/kesher_runtime/article_worker.py`
- focused tests

Requirements:
- exact branch + exact PR-body provenance marker required;
- Master-origin PRs must not require Jules session evidence;
- Jules construction remains lazy for legacy PR compatibility;
- legacy behavior remains fail closed.

## Task 5 — Shadow workflow

Files:
- `.github/workflows/kesher-master-intent-shadow.yml`
- `.github/workflows/kesher-master-owner-foundation-ci.yml`

Requirements:
- read-only permissions;
- shadow only;
- no canonical state write;
- no worker dispatch;
- focused CI compiles changed runtime modules and runs Master Owner tests.

## Task 6 — Verification and cutover prerequisites

Before any production cutover:
1. baseline CI is green on main;
2. focused Master Owner CI is green;
3. generic CI and stability validation are green on the foundation PR;
4. fact reconciliation is independently callable and tested;
5. Master intent derives exact worker inputs from fresh observation;
6. authority topology is changed only through the existing coordinated cutover machinery;
7. first production cycle is a canary;
8. three consecutive clean Master-owned cycles are required before retiring legacy orchestration.

## Non-goals in this PR

- no change to the existing Master Active Supervisor automation prompt;
- no production authority transfer;
- no removal of the current controller workflow;
- no deletion of Jules compatibility paths;
- no alternate state store, lease, or competing scheduler.
