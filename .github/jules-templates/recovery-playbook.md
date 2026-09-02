# Kesher Jules Recovery Playbook

This playbook is mandatory when the Kesher Task Supervisor marks a request with `KESHER_RECOVERY_STAGE`.

## Core rule

Never repeat a failed approach unchanged. Preserve the existing Issue, Jules session, branch, and PR whenever they already exist. Do not create parallel work merely because a repair attempt failed.

## Five-stage ladder

### Stage 1 — Focused repair
- Diagnose the exact blocker.
- Make the smallest safe fix.
- Prove the blocker is gone with a deterministic check.
- Run relevant focused tests and repository checks.

### Stage 2 — Re-diagnose
- Re-read current `origin/main`, the complete PR diff, relevant logs, and the source of truth.
- Identify why the previous attempt failed.
- Do not reuse the same edit/command sequence.
- Fix the upstream cause, not only the visible symptom.
- Add a pre/post invariant that demonstrates the defect is gone.

### Stage 3 — Change strategy
Apply the matching recovery pattern below. A wording variation of the previous attempt does not count as a strategy change.

### Stage 4 — Controller coaching
- Review the previous Jules responses and attempted fixes.
- State in working notes what was tried and why it did not satisfy the Definition of Done.
- Choose a materially different repair mechanism.
- Inspect the complete final diff and machine-checkable evidence before claiming completion.

### Stage 5 — Deep recovery
- Treat the previous implementation approach as invalid.
- Reconstruct from a clean source of truth or reimplement only the minimum accepted intent.
- Preserve the SAME branch/PR when one exists.
- Prove every acceptance criterion with machine-checkable evidence.
- Report `HUMAN_BLOCKER: <minimal exact action>` only for a genuine external human-only dependency such as a new secret, 2FA, admin permission, or product decision.
- Otherwise continue autonomously and do not ask the user.

## Recovery patterns

### Dirty / overly broad / non-mergeable PR
Use when the PR contains unrelated files, recurring merge conflicts, `mergeable=false`, or scope contamination.

1. Fetch current `origin/main`.
2. Derive an explicit allowlist of files required by the Issue/PR intent.
3. Reconstruct the SAME branch from clean `main`.
4. Re-apply only intended changes.
5. Before push, verify `git diff --name-only origin/main...HEAD` matches the allowlist.
6. Never open a replacement PR.

### Persistent generated text or Hebrew corruption
Use when a corrected phrase returns after regeneration or the same bad string survives repeated fixes.

1. Search all occurrences.
2. Trace the text upstream to its source/template/generator.
3. Fix the source of truth.
4. Regenerate the affected artifact exactly once.
5. Assert zero bad occurrences before commit.
6. Do not hand-edit only generated output if the generator would restore the defect.

### CI / validator failure
1. Open the exact failing job and step logs.
2. Reproduce the narrow failing command when possible.
3. Isolate the first causal failure; ignore downstream noise.
4. Never weaken required checks, validators, security, or CSP.
5. Fix the cause and rerun the focused check, then the repository validation suite.

### Accidental generated artifacts
Examples: `.pyc`, cache files, generated maps, unrelated generated output.

1. Remove accidental artifacts from the PR.
2. Identify why they became tracked.
3. Preserve only intended source files.
4. Update ignore/build behavior if needed to prevent recurrence.
5. Verify the final diff has no unrelated generated churn.

### Evidence / overclaim failures
Use for competitor research, Google Ads state, deployment claims, or other assertions that require external/account-side proof.

1. Switch to evidence-first output.
2. Require a verifiable URL, identifier, or dated account-side evidence for each material claim.
3. Downgrade or remove unsupported claims.
4. Never state `launched`, `live`, `verified`, or equivalent without the required evidence.

### Article image backfill
1. Build a deterministic inventory.
2. Identify missing, broken, reused, or duplicate images/metadata.
3. Repair from the inventory.
4. Run the validator.
5. Require machine-checkable totals such as `missing=0`, `broken=0`, and `duplicate SHA=0` before completion.

### Deploy / live verification
1. Tie verification to the exact merged `main` SHA.
2. Identify the exact deploy workflow run.
3. Inspect logs when it fails.
4. Fix only the causal repository/config defect.
5. Verify the required production URL(s) and acceptance behavior after deployment.

## Global invariants

- No duplicate Issues, PRs, Jules sessions, article generations, video generations, or uploads.
- Scheduled Kesher content remains owned by the Kesher Content Controller and its heartbeat/backoff logic.
- Never bypass CI, validators, security gates, CSP, or safeguards.
- One article per slot and one video per article.
- A green workflow is not by itself Definition of Done when deploy/live/account-side evidence is required.
- Prefer deterministic proof: zero-occurrence checks, exact file allowlists, validator totals, exact SHAs, workflow IDs, URLs, and account-side evidence.
