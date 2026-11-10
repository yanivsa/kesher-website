# KESHER Master Owner Foundation Implementation Plan

## Goal
Move KESHER orchestration decisions to Master Active Supervisor without introducing a second state authority or allowing split-brain execution.

## Safety boundary
This foundation remains shadow-only. It does not change the production runtime owner, does not write canonical state from Master, does not dispatch workers from Master, and does not change the Master Active Supervisor scheduled prompt.

## Tasks
1. Separate fresh fact reconciliation from controller action eligibility/selection. Preserve the existing controller decision wrapper for compatibility.
2. Make Master intent fail closed on stale main/state and forbid caller-provided worker inputs.
3. Derive exact worker inputs from fresh observation/canonical state: PR number/head/body/base, deploy SHA, and bounded media generation/recovery data.
4. Make the Master shadow entry perform a fresh revision-bound RepositoryObserver read, reconcile facts, then plan a non-persisted command.
5. Preserve Master-origin article quiescence without requiring Jules; retain lazy Jules compatibility only for legacy PRs.
6. Register new workflows in governance using the repository's canonical authority-policy sync tool, then run focused and full CI.

## Acceptance
- Fact-only reconciliation cannot invoke `_eligible` or create a command.
- Existing controller reconciliation still creates the same command decisions.
- Master payload cannot inject `pr_number`, head/body SHA, deploy SHA, provider IDs, generation attempt, recovery class, or other worker inputs.
- Shadow output is based on the exact loaded state revision and a fresh observation; it writes and dispatches nothing.
- All focused tests and repository governance/full quality gates pass.
- Production cutover is explicitly out of scope until shadow QA is green.
