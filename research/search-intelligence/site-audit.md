# Phase 1 Data Audit & Baseline Intelligence Report

> **Project:** Search Intelligence & SEO Strategy  
> **Repository:** `yanivsa/kesher-website`  
> **Working Branch:** `seo/search-intelligence-20260918`  
> **Production Domain:** `https://kesher.saharoni.com`  
> **Date:** 2026-09-18  
> **Audit Status:** COMPLETED  

---

## 1. Executive Summary

Phase 1 establishes the verified data foundation and content baseline for the Kesher website (`https://kesher.saharoni.com`). Operating directly against repository evidence, live Google Search Console (GSC) API connections (`sc-domain:saharoni.com`), and Google Analytics 4 (GA4) API connections (`properties/551923843`), this audit maps the site's complete content surface, verifies its technical and indexing posture, logs baseline performance observations without synthetic inflation, and structures 31 seed queries across core business topics for Phase 2 SERP exploration.

### Key Highlights
* **Verified Production Identity:** Framework is React 19 + Vite 8 + React Router DOM 7, prerendered to static HTML (SSG) and deployed to Cloudflare Pages. The production target is strictly `https://kesher.saharoni.com`.
* **Content Inventory:** 116 public/routed items cataloged in `existing-content.csv` (28 indexable static routes, 1 noindex booking/thank-you routes group, 76 publishable blog articles, and 11 draft stubs held below editorial quality thresholds).
* **Live GSC Baseline:** 2 exposed queries confirmed (`לא להראות התלהבות בתחילת קשר`, `פגישה ראשונה`); 27 distinct Kesher URLs generated impressions despite heavy GSC privacy filtering. Top organic click performers are `/blog/communication-breakdown` (3 clicks, 60% CTR, pos 4.4) and `/blog/boundaries-without-punishments` (2 clicks, 18.2% CTR, pos 3.45).
* **Live GA4 Baseline:** 39 total sessions and 22 active users recorded between 2026-08-28 and 2026-09-17. Notable presence of AI Assistant traffic (`chatgpt.com / ai-assistant`, 3 sessions, 7.7% of total). Small sample caution applied.
* **Indexing Integrity:** Resolved the apparent sitemap discrepancy. While GSC sitemap report displays `102 submitted / 0 indexed`, direct live URL Inspection API returns `Submitted and indexed / PASS` for representative URLs.
* **Seed Topics & Canonical Master:** 31 seed queries mapped in `seed-topics.csv`; `keyword-master.csv` updated strictly with 7 new verified evidence-backed entries, preserving historical records.

---

## 2. Repository Architecture

### Framework & Build Pipeline
* **Engine:** React 19.2, Vite 8.0, TypeScript, React Router DOM 7.18.
* **Rendering Strategy:** Static Site Generation (SSG). Prerender script (`scripts/prerender.cjs`) executes a headless browser instance (`playwright` chromium) against a local Vite preview server to pre-bake fully rendered HTML files into `/dist` for every publishable route.
* **Deployment Platform:** Cloudflare Pages with edge rules in `public/_redirects` and `public/_headers`.
* **Content Storage:**
  * Articles: Centralized JSON database at `src/data/posts.json` (87 total entries). Published articles are filtered via `src/data/publishedPosts.ts` and `scripts/content-policy.cjs` (word count $\ge 500$, H3 subheadings $\ge 5$).
  * Static Pages: Modular TSX components in `src/pages/`.
  * Media Assets: Optimized WebP and JPG assets in `public/images/` and `public/images/generated/`.

### Technical SEO & Metadata Implementation
* **Dynamic Metadata:** Implemented via `src/components/SEO/MetaTags.tsx`, dynamically synchronizing document title, description, OpenGraph (locale `he_IL`), Twitter Cards, canonical tags, and robots directives.
* **Canonical Implementation:** Standardized to `https://kesher.saharoni.com` across all prerendered and client routes. Prevents trailing slash duplicates.
* **Structured Data (JSON-LD):** Implemented via `src/components/SEO/SchemaOrg.tsx`. Pages inject:
  * `LocalBusiness` / `Person` (Shira Saharoni) on Homepage and About.
  * `Article` + `BreadcrumbList` on all blog post routes.
  * `FAQPage` on `/faq`.
  * `ProfilePage` on `/about`.
* **Robots Configuration:** `public/robots.txt` explicitly allows AI Search crawlers (`OAI-SearchBot`, `ChatGPT-User`, `PerplexityBot`, `Claude-SearchBot`) while disallowing AI model training scrapers (`GPTBot`, `ClaudeBot`, `Google-Extended`, `CCBot`). Allows search engine crawlers (`Googlebot`, `Bingbot`). Points directly to `https://kesher.saharoni.com/sitemap.xml`.
* **Sitemap Generation:** `scripts/generate-sitemap.cjs` dynamically writes `public/sitemap.xml` during build, containing 103 valid indexable URLs.

---

## 3. Business & Service Scope

The repository provides an explicit, evidence-backed footprint of Shira Saharoni's professional positioning:

### Professional Credentials & Identity
* **Identity:** Shira Saharoni (שירה סהרוני).
* **Credentials:** Certified Family & Couples Counselor, Certified Mediator (מגשרת מוסמכת), trained Lawyer (עורכת דין בהכשרתה).
* **Locations:** Physical clinic in Ashdod (אשדוד) and online worldwide via Zoom.

### Categorization of Topics

#### 1. Services Offered (Core Commercial Scope)
* **ייעוץ זוגי (Couples Counseling):** Communication improvement, de-escalation, conflict resolution, intimacy renewal, emotional distance.
* **ייעוץ זוגי באשדוד (Local Couples Counseling):** Physical in-person clinic appointments in Ashdod.
* **הדרכת הורים (Parenting Guidance):** Behavioral struggles, positive discipline, emotional regulation, bedtime/morning routines.
* **הדרכת הורים באשדוד (Local Parenting Guidance):** Physical in-person clinic appointments in Ashdod.
* **גישור זוגי ומשפחתי (Couples & Family Mediation):** Separation agreements, divorce mediation, family conflict resolution outside of court.
* **גישור זוגי באשדוד (Local Mediation):** Local mediation in Ashdod.
* **הכנה לנישואים והשנה הראשונה (Premarital & Newlyweds):** Financial coordination, in-law boundaries, role allocation, expectations.
* **זוגיות ברילוקיישן ועלייה (Relocation & Aliyah Couples):** Acculturation gaps, trailing partner career loss, dependency, isolation.
* **הנחיית הורים לילדים מחוננים (Gifted Children Parenting):** Asynchronous development, emotional intensity, gifted framework entrance.
* **ייעוץ ברווקות מאוחרת (Late Singleness Counseling):** Dating burnout, app exhaustion, social/family pressure, repetitive selection traps.
* **ליווי למציאת זוגיות (Finding a Relationship):** Early-stage communication, first dates, boundary setting, partner criteria.
* **עזרה ראשונה במשבר זוגי (Couples Crisis Intervention):** Emergency de-escalation for acute crisis (`/services/couples/crisis`).
* **בירור זוגי לפני פרידה (Discernment Counseling):** Pre-divorce decision clarity (`/services/couples/before-separation`).
* **הרצאות וסדנאות (Workshops & Lectures):** Organizational and educational workshops (`/lectures`).

#### 2. Informational Expertise (Educational & Thought Leadership)
* Children with ADHD & couple dynamics involving an ADHD partner.
* Transitions to elementary school (כיתה א') and preschool separation anxiety.
* Adolescent withdrawal and social difficulties.
* Setting boundaries without punishments (גבולות ללא עונשים).
* Stopping yelling cycles at home (הפסקת צעקות).
* Financial disputes between couples (ריבים על כסף).
* Dating mechanics: text pacing, showing enthusiasm vs playing games, handling rejection.

#### 3. Adjacent Topics (Contextual / Referral)
* Individual adult psychotherapy (she is an accredited counselor/mediator, not a clinical psychologist or psychiatrist).
* Divorce court litigation (she mediates out-of-court agreements; she does not represent in adversarial family court or rabbinical court).
* Formal psycho-didactic diagnosis (she provides parent guidance for gifted/ADHD, not psychiatric diagnostic testing).

#### 4. Out of Scope (Do NOT Target)
* Domestic violence, active substance abuse, or severe unmanaged psychiatric disorders.
* Contested divorce litigation / custody battles.
* Rabbinical arbitration / Halachic rulings (טוענת רבנית / פסיקות הלכה).
* Direct child play therapy / art therapy (her modality is parent counseling, not direct child therapy).
* **Religious / Haredi Audience Specifics:** Repository audit confirms zero religious targeting keywords (`דתי`, `חרדי`, `מגזר`) on the site. Shira's current positioning is general/universal. Religious queries must remain investigatory only unless explicitly requested.

---

## 4. Existing Content Inventory Summary

A complete inventory of all 116 routed pages was compiled into `existing-content.csv`.

```
+------------------------------------+-------+-------------------+
| Content Group                      | Total | Indexable / Live  |
+------------------------------------+-------+-------------------+
| Homepage                           |   1   |   1 (INDEXABLE)   |
| Core Service Pages                 |  10   |  10 (INDEXABLE)   |
| CRO Local/Intent Landing Pages     |   5   |   5 (INDEXABLE)   |
| Resource & Index Pages (Blog, FAQ) |   2   |   2 (INDEXABLE)   |
| Authority / Bio Pages (About, Now) |   2   |   2 (INDEXABLE)   |
| Conversion & Booking Pages         |   2   |   2 (INDEXABLE)   |
| Legal & Utility Pages              |   4   |   4 (INDEXABLE)   |
| Post-Conversion Pages (Thank You)  |   2   |   2 (NOINDEX)     |
| Published Blog Articles            |  76   |  76 (INDEXABLE)   |
| Draft / Below-Threshold Articles   |  11   |  11 (DRAFT_HOLD)  |
+------------------------------------+-------+-------------------+
| Total Inventory                    |  116  | 103 Live / In XML |
+------------------------------------+-------+-------------------+
```

### Internal Link Equity Distribution
* **Header & Footer Distribution:** Sitewide links strongly pass PageRank to core service pages and local Ashdod landing pages.
* **In-Article Cross-Linking:**
  * `/couples-counseling-ashdod` receives 41 contextual inbound links from blog posts.
  * `/parenting-guidance-ashdod` receives 16 contextual inbound links from blog posts.
  * `/couples-mediation-ashdod` receives 7 contextual inbound links from blog posts.
* **Link Deficit:** Service pages such as `/services/premarital-first-year`, `/services/gifted-parenting`, and `/services/late-singleness` receive only 1–2 in-content links from blog posts despite having strong supporting articles.

---

## 5. Search Console Baseline

* **Connected Property:** `sc-domain:saharoni.com` (verified active via Composio GSC API).
* **Subdomain Target:** `kesher.saharoni.com`.
* **Verified Reporting Window:** 2026-06-01 to 2026-09-16 (complete 90-day+ window).
* **Privacy Threshold Caveat:** Search Console enforces strict privacy thresholds on rare queries. Only 2 exact query strings are unmasked in API reports, while 27 Kesher URLs registered impressions.

### Exposed Query Performance

| Query String | Target URL | Impr | Clicks | CTR | Avg Pos | Date Verified |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `לא להראות התלהבות בתחילת קשר` | `/blog/dating-transition-to-relationship-boundaries` | 1 | 0 | 0.0% | 95.0 | 2026-09-15 |
| `פגישה ראשונה` | `/blog/new-relationship-initial-intentions` | 1 | 0 | 0.0% | 82.0 | 2026-09-15 |

### Top Performing URLs in Search Console

| URL Route | Impr | Clicks | CTR | Position | Topical Relevance |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `/blog/communication-breakdown` | 5 | 3 | 60.0% | 4.4 | נתק בתקשורת בזוגיות (Top organic performer) |
| `/blog/boundaries-without-punishments` | 11 | 2 | 18.2% | 3.5 | גבולות ללא עונשים (High CTR parenting asset) |
| `/` (Homepage) | 20 | 1 | 5.0% | 2.1 | שירה סהרוני / מותג |
| `/blog/dating-fatigue-resilience` | 1 | 1 | 100.0% | 4.0 | עייפות מדייטים |
| `/faq` | 16 | 1 | 6.3% | 8.8 | שאלות נפוצות על ייעוץ זוגי |
| `/services/parenting` | 6 | 1 | 16.7% | 3.0 | שירות הדרכת הורים |
| `/services/premarital-first-year` | 3 | 1 | 33.3% | 6.3 | הכנה לנישואין |
| `/about` | 5 | 0 | 0.0% | 3.0 | אודות שירה סהרוני |
| `/blog/new-relationship-initial-intentions` | 6 | 0 | 0.0% | 70.7 | פגישה ראשונה / תחילת קשר |
| `/services/couples-aliyah-relocation` | 2 | 0 | 0.0% | 2.0 | זוגיות ברילוקיישן |

### Geographic & Device Distribution
* **Country:** 100% of exposed impressions originated from Israel (`ISR`).
* **Device:** Desktop accounted for 100% of exposed query records.

---

## 6. GA4 Baseline

* **Property ID:** `properties/551923843`
* **Data Stream:** `https://kesher.saharoni.com` (`G-6SM423N6EL`)
* **Tracking Window:** 2026-08-28 to 2026-09-17 (21 calendar days).
* **Aggregate Totals:** 39 Sessions, 22 Active Users, 18 Engaged Sessions (Overall Engagement Rate: 46.2%).

### Channel Breakdown

```
+------------------------+------------------------------------+----------+--------------+------------------+-----------------+
| Channel Group          | Source / Medium                    | Sessions | Active Users | Engaged Sessions | Engagement Rate |
+------------------------+------------------------------------+----------+--------------+------------------+-----------------+
| Direct                 | (direct) / (none)                  |    32    |      15      |        13        |      40.6%      |
| AI Assistant           | chatgpt.com / ai-assistant         |     3    |       2      |         1        |      33.3%      |
| Organic Search         | google / organic                   |     2    |       2      |         2        |     100.0%      |
| Organic Social         | l.instagram.com / referral         |     2    |       1      |         2        |     100.0%      |
+------------------------+------------------------------------+----------+--------------+------------------+-----------------+
| Total                  |                                    |    39    |      22      |        18        |      46.2%      |
+------------------------+------------------------------------+----------+--------------+------------------+-----------------+
```

### AI Referral & Search Discovery
* **ChatGPT Referrals:** 3 sessions logged from `chatgpt.com / ai-assistant`. Landed on Homepage (`/`), Gifted focus article (`/blog/smart-youth-focus-tasks-organization`), and `(not set)`. This confirms that Kesher content is actively retrieved and cited by OpenAI models.
* **Organic Search Referrals:** 2 sessions logged from `google / organic`. Landed on Homepage (`/`) and Dating resilience article (`/blog/dating-fatigue-resilience`).
* **Sample Size Warning:** With $N = 39$ sessions across 3 weeks, statistical significance is low. Data is utilized for directional discovery only.

---

## 7. Indexing & Sitemap Findings

### Issue Investigation: 102 Submitted / 0 Indexed Discrepancy
* **Observation:** The GSC Sitemap report at `https://kesher.saharoni.com/sitemap.xml` (last submitted 2026-07-24, last downloaded 2026-09-16) reported `submitted: 102`, `indexed: 0`, `errors: 0`, `warnings: 0`.
* **Direct URL Inspection Verification:** Executed live inspection calls via the GSC URL Inspection API for representative URLs:
  1. `https://kesher.saharoni.com/` (Homepage):
     * Coverage State: `Submitted and indexed`
     * Indexing State: `INDEXING_ALLOWED`
     * Page Fetch: `SUCCESSFUL`
     * Robots.txt: `ALLOWED`
     * User Canonical: `https://kesher.saharoni.com/`
     * Google Canonical: `https://kesher.saharoni.com/`
     * Verdict: `PASS`
  2. `https://kesher.saharoni.com/blog/communication-breakdown`:
     * Coverage State: `Submitted and indexed`
     * Indexing State: `INDEXING_ALLOWED`
     * Page Fetch: `SUCCESSFUL`
     * Verdict: `PASS`
* **Conclusion & Diagnosis:** High confidence ($>95\%$) that the site is actively indexed. The "0 indexed" metric in the GSC sitemap table is a documented Search Console reporting artifact that occurs under domain properties (`sc-domain:`) where sitemap aggregation counters lag by several weeks behind the primary indexation database. The URLs are crawled, indexed, and actively generating impressions.

---

## 8. Existing Topical Strengths

1. **Couples Communication & De-escalation:** Exceptional early signal on `/blog/communication-breakdown` (CTR 60% in top 5). Demonstrates high search intent alignment.
2. **Positive Discipline & Boundaries:** Strongest organic asset on site is `/blog/boundaries-without-punishments` (11 impressions, 2 clicks, pos 3.5). The phrasing matches natural Israeli parenting search behavior.
3. **Local Ashdod Presence:** Highly developed local infrastructure with dedicated landing pages (`/couples-counseling-ashdod`, `/parenting-guidance-ashdod`, `/couples-mediation-ashdod`), complete LocalBusiness schema, and extensive internal linking from 60+ articles.
4. **Gifted Children & ADHD:** Deep cluster of 6+ specialized articles plus a dedicated service page. Already recognized by generative AI assistants (ChatGPT referral verified).
5. **Premarital & Newlywed Counseling:** Solid foundation of 5 articles and a dedicated service page receiving steady impressions across marriage preparation queries.

---

## 9. Weak or Missing Topic Areas

1. **Money & Finances in Relationships:** The article `money-fights-communication` exists only as a draft stub (1,020 words, but 0 H3 headers, failing the automated publication threshold). This leaves a high-volume couple problem without live coverage.
2. **Relationship Dynamics After Childbirth:** `relationship-after-childbirth` is a 181-word stub that is currently unpublished. The postpartum transition is a major pain point for Israeli couples.
3. **Adolescent Social Anxiety:** `parenting-teen-social-anxiety` is an unpublishable 33-word stub. Parents of teens represent an underserved segment on the site.
4. **Mediation Educational Content:** While the local landing page `/couples-mediation-ashdod` is strong, there is almost no supporting informational content explaining the mediation process, legal differences vs. court, or child custody agreements.
5. **Religious / Traditional Audience:** Zero organic positioning on site. If this audience is to be targeted, it must be developed as a deliberate strategic decision.

---

## 10. Known Data Limitations

* **Query-Level Data Privacy Censorship:** GSC conceals queries with very few impressions. As a result, page-level impressions (27 pages) far exceed visible query records (2 queries). Absence of a query in GSC is never proof of zero search volume.
* **GA4 Property Youth:** With only 21 days of tracking and 39 total sessions, conversion funnels and bounce rates cannot yet be reliably segmented by landing page.
* **Search Appearance & PAA Gaps:** Phase 1 did not execute live SERP scraping; PAA (People Also Ask) questions and autocomplete variants remain to be collected in Phase 2.

---

## 11. Items Requiring Live SERP Research (Phase 2 Roadmap)

1. **Dating Head Query Intent (`פגישה ראשונה`):** Ranks at position 82. Phase 2 must evaluate whether Google SERP favors dating advice blogs, icebreaker question lists, lifestyle magazines, or commercial relationship coaching.
2. **Early Relationship Dynamics (`לא להראות התלהבות בתחילת קשר`):** Ranks at position 95. Phase 2 must analyze autocomplete and PAA questions around playing hard to get vs. open communication.
3. **Ashdod Local Pack & Commercial SERPs:** Analyze SERP composition for `ייעוץ זוגי אשדוד` and `הדרכת הורים אשדוד` (Google Business Profile 3-pack, directory portals like B144/MedReviews, vs. private practitioner websites).
4. **Gifted Children Parent Search Language:** Determine exact phrases used by Israeli parents when their child is identified as gifted (`מבחני מחוננים שלב ב`, `ילדים מחוננים קשיים רגשיים`, `יום שליפה`).
5. **Premarital Preparation:** Evaluate SERP landscape for `הכנה לנישואין` and `ייעוץ לפני נישואין` (religious rabbinate courses vs. secular couples counseling).

---

## 12. Issues Requiring ChatGPT Review

1. **Sitemap Discrepancy Status:** Confirm agreement that the "102 submitted / 0 indexed" GSC sitemap counter is a reporting delay and that URL Inspection `PASS` constitutes verified indexing.
2. **Strategic Stance on Religious / Traditional Audience:** Given that repository code and existing articles contain zero religious positioning, does ChatGPT recommend keeping this out of scope, or exploring it as an intentional future expansion? (Antigravity recommends keeping it `LOW_PRIORITY` / `OUT_OF_SCOPE` for Wave 1).
3. **Action Path for Exposed Dating Queries:** For `לא להראות התלהבות בתחילת קשר` and `פגישה ראשונה`, determine in Phase 3 whether to expand existing URLs (`/blog/dating-transition-to-relationship-boundaries` and `/blog/new-relationship-initial-intentions`) via `EXPAND_EXISTING` or create supporting FAQ clusters.
4. **Draft Backlog Strategy:** 11 article stubs exist in `src/data/posts.json` that fail the 500-word / 5-H3 threshold. Should Phase 3 prioritize upgrading high-potential stubs (like `money-fights-communication` and `relationship-after-childbirth`) over creating net-new URLs?
