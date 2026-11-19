# KESHER — Parenting coordination: editorial expansion and protected release packet
**Prepared:** 2026-11-19  
**Scope:** kesher.saharoni.com only. No campaign activation or production deployment.  
**Status:** four full-length sourced editorial drafts; **not yet public**.

## Why expand beyond the five existing guides
The five published guides cover (1) what parenting coordination is, (2) comparison with mediation, (3) post-divorce parent communication, (4) parenting-time holidays, and (5) one-parent initiation. They make a useful introductory cluster but leave four independent intents unanswered. Four new, non-duplicative longform guides are now staged under `src/data/parentingCoordinationDrafts/` with no publication date, image or public import.

| Priority | Draft slug | Main intent | Existing pages to link |
| --- | --- | --- | --- |
| P1 | `parenting-coordination-first-meeting-process` | First appointment, preparation, boundaries and scope | service + what-is + consent |
| P1 | `parenting-coordination-cost-private-public` | Cost, fees and differences between public/private routes | service + compare mediation |
| P1 / safety | `parenting-coordination-domestic-violence-safety` | Safety suitability, violence, coercion and limitations | service + what-is + consent |
| P2 / supportive | `child-refuses-parenting-time-after-divorce` | Child-led distress/refusal, risk screening and transitions | parenting-time + communication; don't present coordination as a substitute for risk assessment |

These are **editorially chosen intent hypotheses**, not queries from connected Google Search Console or Google Ads Keyword Planner. Verify real impressions/search terms before making future SEO/PPC budget decisions.

## Sources and accuracy guardrails
- AFCC, Understanding the Parenting Coordination Process:
  https://www.afccnet.org/Resource-Center/Family-Resources/Understanding-the-Parenting-Coordination-Process
- AFCC, Making Your Parenting Plan Work:
  https://www.afccnet.org/Resource-Center/Family-Resources/Making-your-Parenting-Plan-Work
- AFCC/NCJFCJ joint statement on parent-child contact difficulties:
  https://www.afccnet.org/Resource-Center/Center-for-Excellence-in-Family-Court-Practice/afcc-and-ncjfcj-joint-statement-on-parent-child-contact-problems
- Myers-JDC-Brookdale, Israel parenting-coordination pilot evaluation:
  https://brookdale.jdc.org.il/publication/parenting_coordination/
- Israeli Ministry of Welfare official instructions/tariffs must be checked *at actual launch* before quoting any public eligibility or monetary figure. No universal rate is claimed in the cost guide.

All drafts must be fact-checked against current official/local rules at publication. No guaranteed outcomes, unverified professional qualifications, purported judicial authority, diagnostic use of 'parental alienation', or legal advice. Safety pre-screening supersedes sales CTAs. The first enquiry never requests children’s names, ID numbers, court documents or violence details in a public form.

## Publication gate: fail closed
1. **Do not import the four drafts into** `src/data/parentingCoordinationPosts.json`, `publishedPosts.ts`, `postSummaries.json`, sitemap, RSS, NotebookLM pipeline or any route while `publicationState=editorial_draft_unpublished`.
2. Assign each guide an **original, topic-specific, human-reviewed hero image** (not a generic or repeated SVG). Verify visually, add truthful Hebrew alt and image provenance. Existing drafts intentionally have `image=null`; they are not publication-ready without asset review.
3. Obtain review of legal/safety language, local eligibility, service qualifications and pricing from the appropriate qualified professional, including suitability where violence or child-safety concerns exist.
4. Finalize accurate internal links and related-post IDs in both directions, and distinct title/description/canonical. Preserve original five article dates, URLs and established rankings.
5. Only when the **genuine approved production workflow** is available, select true publish dates for each new guide at the time of actual release. Never predate them to fill empty archive slots. Add drafts to canonical catalog **in controlled small batches**; regenerate summaries, sitemap, RSS and the AI discovery feeds and validate structured Article datePublished/dateModified.
6. Recheck automated tests including `tests/parenting-coordination-growth-drafts.test.ts`, `tests/parenting-coordination.test.cjs`, blog topic spacing and E2E. Update the draft tests intentionally as each article transitions to the canonical catalog.
7. Require exact-HEAD CI, Stability PR Validation, no unresolved authority-policy pin changes and approved single-writer Schema-6 release. Do not rerun `deploy.yml` (legacy bridge exclusion) or publish directly through Cloudflare connector.
8. Independently confirm **Cloudflare canonical production SHA** equals deployed reviewed SHA; inspect HTML body, Article JSON-LD, canonicals, indexability, links, images, topic list, mobile layout, CTA pre-screening and forms. Collect deployment receipt and browser evidence.
9. Do not create or trigger Google Ads campaigns. For a future campaign, point commercial intent toward the service/landing route and use guides for helpful supporting content. Track lead-quality signals while respecting privacy and Google's current ad policies.

## Next topic candidates only after measurement
- Choosing a parenting coordinator and validating relevant qualifications;
- Education, healthcare and extracurricular decisions with two households;
- Parenting coordination when parents live far apart / online suitability.

Avoid publishing near-duplicate variations such as a second generic 'what is parenting coordination' page. Prioritize based on real Google Search Console impressions, intent and client enquiries, then judge performance after indexing.

## Current deployment blocker (independent from this editorial change)
Production Cloudflare Pages canonical was observed at `fce759ecabfc88879553cb93a4a2c9875c363e73` while reviewed GitHub main is newer. The Schema-6 gateway and native resource authorizations are not ready; see issue #1428. **Publishing code to GitHub is not the same as publishing it online.**
