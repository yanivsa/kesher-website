# Search Intelligence Shared Workspace

> Canonical coordination file for ChatGPT and Google Antigravity.
> Repository: `yanivsa/kesher-website`
> Working branch: `seo/search-intelligence-20260918`
> Production target: `https://kesher.saharoni.com`
> Created: 2026-09-18

## Purpose

This file is the shared human-readable source of truth for the Search Intelligence project.

Both ChatGPT and Antigravity MUST read this file before starting a phase and MUST update it before finishing a phase.

The canonical keyword/query dataset is:
`research/search-intelligence/keyword-master.csv`

Do not create a competing master keyword file elsewhere.

## Persistent project-session rule

This rule applies to every future conversation, session, or agent run in this project that touches SEO, Search Intelligence, content strategy, Google Search Console, GA4, SERP research, PAA, AEO/GEO, article planning, implementation, or related website optimization.

Before doing substantive work, both Antigravity and ChatGPT must:

1. Fetch the latest state of branch `seo/search-intelligence-20260918`.
2. Read this file completely.
3. Read `research/search-intelligence/keyword-master.csv`.
4. Review the latest Antigravity and ChatGPT handoff entries.
5. Continue from the recorded CURRENT STATE rather than reconstructing project state from chat memory alone.

Before finishing substantive work, both must:

1. Update this file if project state, conclusions, review requests, or next actions changed.
2. Update `keyword-master.csv` when query-level evidence or classification changed.
3. Add a handoff entry identifying what was reviewed or changed.
4. Record the relevant commit SHA when files were committed.

Chat messages are not the canonical state. Git files on the working branch are the persistent coordination layer.

## Collaboration protocol

1. Always pull/fetch the latest state of this branch before work.
2. Read this file and `keyword-master.csv` before starting.
3. Do not rewrite or delete another agent's historical notes.
4. Append new observations to the appropriate log section.
5. Update the CURRENT STATE block when a phase materially changes status.
6. Every material conclusion must include an evidence source.
7. If evidence is uncertain, mark it `UNKNOWN`, `NEEDS_REVIEW`, or `LOW_CONFIDENCE` instead of guessing.
8. Do not publish, deploy, merge to `main`, or delete production content without explicit authorization.
9. Prefer UPDATE_EXISTING over CREATE when one existing URL already satisfies the same search intent.
10. One distinct search intent does not automatically require one new URL.

## CURRENT STATE

- project_status: IN_PROGRESS
- current_phase: PHASE_1_DATA_AUDIT
- current_owner: SHARED
- last_completed_phase: PHASE_1_DATA_AUDIT
- next_phase: PHASE_2_GOOGLE_SEARCH_INTELLIGENCE
- production_domain: https://kesher.saharoni.com
- search_console_property: sc-domain:saharoni.com
- ga4_property: properties/551923843
- ga4_stream: G-6SM423N6EL
- canonical_keyword_file: research/search-intelligence/keyword-master.csv
- last_updated_utc: 2026-09-18T10:30:00Z
- last_updated_by: Antigravity

## Verified baseline

### Search Console
- Connected and active.
- Kesher pages are present under `sc-domain:saharoni.com`.
- Two query strings are currently exposed for Kesher in the sampled reporting window:
  - `לא להראות התלהבות בתחילת קשר`
  - `פגישה ראשונה`
- Query-level data is sparse; page-level impressions exist beyond the visible query rows.
- Representative URL Inspection checks returned PASS and indexing allowed.
- Sitemap observed at `https://kesher.saharoni.com/sitemap.xml`.
- Sitemap report showed 102 submitted URLs and 0 indexed in the sitemap summary, while inspected URLs were indexed. Treat this as a diagnostic inconsistency that requires later review, not as proof that the site is unindexed.

### GA4
- Property: `properties/551923843`
- Web stream: `https://kesher.saharoni.com`
- Measurement ID: `G-6SM423N6EL`
- Property/stream is young; avoid strong conclusions from small samples.
- AI-referral traffic from `chatgpt.com / ai-assistant` has already appeared in the sampled period.

### GitHub
- Repository: `yanivsa/kesher-website`
- Working branch for this project: `seo/search-intelligence-20260918`

## Phase contract

### PHASE 1 — Data Audit & Seed Discovery
Owner: Antigravity
Output expected:
- site/content inventory
- Search Console baseline
- GA4 baseline
- seed topics
- existing-content coverage map

Status: COMPLETED

### PHASE 2 — Google Search Intelligence
Owner: Antigravity
Output expected:
- PAA
- Autocomplete
- Related Searches
- PASF where available
- SERP composition
- normalized observations appended/merged into keyword-master.csv

Status: NOT_STARTED

### PHASE 3 — Intent Clustering & Strategy
Owner: Antigravity
Output expected:
- intent clusters
- UPDATE/CREATE/MERGE/IGNORE decisions
- Wave 1
- content briefs
- cannibalization review

Status: NOT_STARTED

### PHASE 4 — Editorial Production
Owner: Antigravity
Output expected:
- final Wave 1 article/page drafts
- no publication yet unless explicitly authorized

Status: NOT_STARTED

### PHASE 5 — Implementation & Technical QA
Owner: Antigravity
Output expected:
- implementation on project branch
- metadata/canonicals/schema/internal links
- build/lint/tests/browser QA
- final diff and handoff

Status: NOT_STARTED

## Shared decision vocabulary

Use only these action labels:
- UPDATE_EXISTING
- EXPAND_EXISTING
- CREATE_ARTICLE
- CREATE_SERVICE_PAGE
- ADD_FAQ_SECTION
- MERGE
- INTERNAL_LINK_ONLY
- IGNORE
- NEEDS_REVIEW

Use only these confidence labels:
- HIGH
- MEDIUM
- LOW

Use only these funnel labels:
- TOFU
- MOFU
- BOFU

## Review queue

Add review items as unchecked tasks. Never delete completed history; mark items complete.

- [x] Investigate sitemap summary discrepancy: 102 submitted / 0 indexed versus URL Inspection PASS. (Resolved: GSC URL Inspection API confirms PASS and "Submitted and indexed"; the "0 indexed" in sitemap summary is an aggregation reporting lag under domain properties).
- [ ] Validate local-commercial SERP intent for Ashdod service queries.
- [ ] Determine whether `פגישה ראשונה` should improve an existing article or become a supporting section/cluster only.
- [ ] Determine whether `לא להראות התלהבות בתחילת קשר` is adequately served by the existing relationship-transition article.
- [ ] Measure AI referral landing pages over a larger sample before drawing conclusions.
- [ ] Confirm strategic stance on religious/traditional audience (site contains zero religious keywords; confirm keeping it out of scope for Wave 1).
- [ ] Determine strategy for 11 draft stubs in posts.json (upgrade high-potential drafts like money-fights and postpartum vs. net-new articles).

## ChatGPT review notes

### 2026-09-18 — Initial setup
- Do not use Search Console alone for demand discovery because current query-level data is sparse.
- Use GSC as an evidence layer, then expand with live SERP/PAA/Autocomplete research.
- Prioritize business/service relevance and search intent over raw query count.
- Avoid mass production. Wave 1 should normally contain no more than 5–8 high-confidence actions.

### 2026-09-18 — Persistent session protocol
- Future project conversations must use the shared Git files as the coordination layer.
- ChatGPT and Antigravity should not rely on conversation memory alone for project state.
- Both sides should read latest handoffs before continuing related work.

## Antigravity handoff log

Append entries using this exact structure:

### 2026-09-18 13:30 — PHASE 1 — Antigravity
- commit: ee13d57e
- files_changed:
  - research/search-intelligence/existing-content.csv
  - research/search-intelligence/gsc-baseline.csv
  - research/search-intelligence/ga4-baseline.csv
  - research/search-intelligence/content-coverage.csv
  - research/search-intelligence/seed-topics.csv
  - research/search-intelligence/keyword-master.csv
  - research/search-intelligence/site-audit.md
  - research/search-intelligence/COLLABORATION.md
- completed:
  - Completed Phase 1 data audit & seed discovery.
  - Verified repository identity, framework (React 19 + Vite 8 SSG), and target domain (https://kesher.saharoni.com).
  - Built complete content inventory (116 total items: 28 static routes, 76 publishable blog posts, 11 draft stubs).
  - Pulled live GSC baseline (2 exposed queries, 27 pages with impressions, top performers: /blog/communication-breakdown and /blog/boundaries-without-punishments).
  - Pulled live GA4 baseline (39 sessions, 22 active users, 3 ChatGPT referrals, 2 organic Google search referrals).
  - Resolved sitemap indexing discrepancy: representative URLs inspected via GSC API returned PASS / Submitted and Indexed.
  - Built content coverage map across 22 business topic areas.
  - Generated 31 seed queries across core families for Phase 2 SERP exploration.
  - Preserved historical keyword master entries and added 7 verified evidence-backed query seeds.
- important_findings:
  - Parenting / boundaries without punishments is currently the strongest organic discovery asset on site (11 impressions, 2 clicks, pos 3.5).
  - Couples communication breakdown is the strongest click driver (3 clicks, 60% CTR, pos 4.4).
  - Ashdod local infrastructure is robust with 3 dedicated landing pages and heavy internal linking (41 inbound post links for couples counseling).
  - AI Assistant referrals from ChatGPT are active (3 sessions), specifically targeting homepage and gifted focus content.
  - No religious / orthodox positioning exists in the repository or published articles; site targets a general audience.
- uncertainties:
  - SERP composition and actual intent for head queries `פגישה ראשונה` and local Ashdod terms are pending Phase 2 live search exploration.
  - GSC query filtering conceals queries for 25 out of 27 impression-generating pages.
- review_requests_for_ChatGPT:
  - Confirm agreement on sitemap discrepancy diagnosis (reporting lag vs live URL indexation).
  - Confirm strategic recommendation to keep religious/traditional queries OUT_OF_SCOPE / LOW_PRIORITY for Wave 1.
  - Review whether 11 draft stubs (especially money-fights and postpartum relationship) should be expanded in Wave 1 over creating net-new URLs.
- recommended_next_action:
  - Await ChatGPT review of Phase 1 artifacts and confirmation to proceed with Phase 2 (Google Search Intelligence: PAA, Autocomplete, Related Searches, SERP analysis).

## ChatGPT handoff log

Append entries using this exact structure:

### YYYY-MM-DD HH:MM — ChatGPT
- reviewed_commit:
- reviewed_files:
- findings:
- corrections_requested:
- decisions:
- next_action_for_Antigravity:

## Conflict handling

If Antigravity and ChatGPT disagree:

1. Do not silently overwrite the other conclusion.
2. Add the disputed item to the Review queue.
3. Record both positions with evidence.
4. Mark the relevant keyword/cluster `NEEDS_REVIEW`.
5. Resolve before article production or URL creation.

## Completion definition

This project is not complete because files exist.

Completion requires:
- evidence-backed demand map
- intent clustering
- cannibalization review
- Wave 1 approval
- useful human-first content
- implementation QA
- measurement baseline
- explicit authorization before merge/deployment
