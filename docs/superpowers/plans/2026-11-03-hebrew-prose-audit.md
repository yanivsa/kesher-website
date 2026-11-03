# Hebrew Prose Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Hebrew-first, report-only prose quality audit for recent KESHER articles and calibrate it on 30 published articles before any blocking enforcement.

**Architecture:** A dependency-free CommonJS audit script reuses the repository's canonical post loader and publishability policy. It scores observable Hebrew prose patterns only, emits a human-readable report, and runs through the existing governed `test:content` gate. It stays non-blocking until calibration supports stricter enforcement.

**Tech Stack:** Node.js 22, CommonJS, Node built-in test runner, existing repository CI.

**Spec:** `.github/prompts/kesher-article-authoring-contract.md`

## Global Constraints

- Hebrew-first checks; do not reuse SlopMonster's English score.
- Report-only by default; no deploy or merge blocking based on prose risk.
- No external package dependency.
- Reuse `scripts/load-posts.cjs` and `scripts/content-policy.cjs` as the source of truth.
- Do not rewrite article content automatically.
- A heuristic finding is an editorial signal, not proof of AI authorship.
- Do not add a standalone workflow when the existing governed content gate can run the audit.

## Review Focus

- Natural repeated wording must not create noisy false positives.
- HTML tags and entities must not distort prose counts.
- The sample must contain the 30 most recent publishable articles, not stubs.
- Existing validators remain authoritative for claims, schema and publication safety.
- A future strict mode must be opt-in and must not be enabled before calibration.

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

**Files:**
- Modify: `package.json`

**Interfaces:**
- Consumes: canonical repository post catalogs through `loadPosts()`.
- Produces: a report in the existing `test:content` CI logs for the 30 newest publishable articles.

- [x] Run unit tests through the existing content gate.
- [x] Run `node scripts/hebrew-prose-audit.cjs --sample=30 --format=markdown` through `test:content`.
- [x] Review the first real 30-article result.
- [x] Move `question-cadence` to advisory-only after it flagged 13/30 articles and proved too noisy for KESHER's question-led editorial style.
- [ ] Review the remaining punctuation/formulaic findings before considering any strict enforcement.
