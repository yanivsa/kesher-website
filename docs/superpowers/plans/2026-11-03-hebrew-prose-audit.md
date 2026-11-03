# Hebrew Prose Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Hebrew-first, report-only prose quality audit for recent KESHER articles and calibrate it on 30 published articles before any blocking enforcement.

**Architecture:** A dependency-free CommonJS audit script reuses the repository's canonical post loader and publishability policy. It scores observable Hebrew prose patterns only and emits a human-readable report. The pilot is intentionally not wired into production CI: the repository's authority policy pins workflow definitions and `package.json`, so production automation requires a separate reviewed recertification change.

**Tech Stack:** Node.js 22, CommonJS, Node built-in test runner.

**Spec:** `.github/prompts/kesher-article-authoring-contract.md`

## Global Constraints

- Hebrew-first checks; do not reuse SlopMonster's English score.
- Report-only by default; no deploy or merge blocking based on prose risk.
- No external package dependency.
- Reuse `scripts/load-posts.cjs` and `scripts/content-policy.cjs` as the source of truth.
- Do not rewrite article content automatically.
- A heuristic finding is an editorial signal, not proof of AI authorship.
- Do not change authority-pinned CI surfaces as part of this pilot.

## Review Focus

- Natural repeated wording must not create noisy false positives.
- HTML tags and entities must not distort prose counts.
- The sample must contain the 30 most recent publishable articles, not stubs.
- Existing validators remain authoritative for claims, schema and publication safety.
- A future strict mode must be opt-in and must not be enabled before calibration and authority review.

---

### Task 1: Hebrew prose heuristics

**Files:**
- Create: `scripts/hebrew-prose-audit.cjs`
- Test: `tests/hebrew-prose-audit.test.cjs`

**Interfaces:**
- Consumes: post title, excerpt and HTML content.
- Produces: `auditText(text)`, `auditPosts(posts, options)`, `formatMarkdownReport(report)`.

- [x] Write failing unit tests for natural prose and each heuristic category.
- [x] Verify tests fail before implementation.
- [x] Implement minimal dependency-free audit logic.
- [x] Verify the focused tests pass.

### Task 2: 30-article calibration run

**Interfaces:**
- Consumes: canonical repository post catalogs through `loadPosts()`.
- Produces: a report for the 30 newest publishable articles.

- [x] Run the focused Node test suite.
- [x] Run `node scripts/hebrew-prose-audit.cjs --sample=30 --format=markdown` against the repository corpus.
- [x] Review the first real 30-article result.
- [x] Move `question-cadence` to advisory-only after it flagged 13/30 articles and proved too noisy for KESHER's question-led editorial style.
- [x] Re-run calibration: 24 low, 6 watch, 0 medium, 0 high; five punctuation-cadence findings and one formulaic-phrases finding.
- [x] Manually review the six `watch` articles. The five punctuation findings remain useful as soft editorial signals. `first-grade-maturity` was a false positive because four different stock phrases appeared only once each in a long article.
- [x] Add a regression test for distinct single-use stock phrases and raise the diverse-phrase threshold from 4 to 6 while preserving detection when one stock phrase repeats.
- [x] Re-run the focused suite and 30-article calibration after the threshold change: 9/9 tests passed; 25 low, 5 watch, 0 medium, 0 high. `first-grade-maturity` moved to low and the five punctuation watches remained unchanged.
- [x] Remove the temporary calibration workflow after the run; do not leave an unreviewed workflow definition in the repository.

### Task 3: Production integration

- [ ] Prepare a separate authority-reviewed change that wires the audit into an existing governed Jules/article-validation path and recertifies only the affected hashes.
- [ ] Keep the integration report-only: surface the audit result to the article worker/review path, but do not block publication or rewrite prose automatically.
- [ ] Consider strict enforcement only after additional calibration; keep question cadence advisory unless later evidence supports a different threshold.
