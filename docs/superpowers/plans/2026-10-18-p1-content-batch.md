# KESHER P1 Content Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add or safely refresh five high-priority parent-guidance articles: הכנה לכיתה א׳, מוכנות לכיתה א׳, גמילה מחיתולים בגיל 3, גמילה מחיתולים בלילה, רגרסיה בגמילה מחיתולים.

**Architecture:** Reuse the repository's existing article/content data model, metadata conventions, routes, structured data and internal-link patterns. Before adding any article, inspect the current content inventory and prefer updating an existing matching URL over creating a competing page.

**Tech Stack:** Existing KESHER static site stack and content pipeline.

**Spec:** Approved keyword/content map in Google Sheet tab `40 מאמרים - סופי`.

## Global Constraints

- Hebrew, RTL-compatible content.
- Voice: first-person feminine, warm, professional, practical, non-judgmental.
- 800–1200 words per article where consistent with repository conventions.
- H1 includes primary keyword; use H2/H3, direct opening, practical guidance, FAQ, soft CTA to `/services/parenting`.
- 2–4 relevant internal links per article.
- No fabricated research, medical diagnosis, medication advice, or guaranteed outcomes.
- Avoid keyword cannibalization; refresh an existing page if it already covers the target intent.
- Do not merge to `main` or deploy production in this batch.

## Review Focus

- Existing URL already targets the same intent.
- Article metadata fields differ from assumptions.
- Internal links point to non-existent slugs.
- Medical-adjacent potty-training copy needs referral boundaries.
- Sitemap/prerender/index generation may require derived-file updates.

---

### Task 1: Audit content model and duplicates

**Files:** inspect current content source, route config, sitemap/prerender inputs, and article tests.

- [ ] Locate the canonical article source and required metadata fields.
- [ ] Search all five primary keywords and close variants in existing content.
- [ ] Identify which targets are new versus refreshes.
- [ ] Identify the project's content validation/build commands.

### Task 2: Add content validation tests/checks first

- [ ] Add or extend the smallest available content test/check so the five intended targets fail before content is added.
- [ ] Verify the check fails for the expected missing/insufficient content reason.

### Task 3: Implement the five articles

- [ ] Add/refresh `הכנה לכיתה א׳`.
- [ ] Add/refresh `מוכנות לכיתה א׳`.
- [ ] Add/refresh `גמילה מחיתולים בגיל 3`.
- [ ] Add/refresh `גמילה מחיתולים בלילה`.
- [ ] Add/refresh `רגרסיה בגמילה מחיתולים`.
- [ ] Preserve existing metadata/schema conventions and add internal links/CTA.

### Task 4: Regenerate derived assets if required

- [ ] Update sitemap/prerender/search indexes only if the repository's existing workflow requires checked-in derived files.

### Task 5: Verification

- [ ] Run targeted content validation.
- [ ] Run the repository's full relevant test/build/lint suite.
- [ ] Check all five routes/slugs, canonical metadata, internal links and duplicate-intent risk.
- [ ] Report any pre-existing failures separately.
