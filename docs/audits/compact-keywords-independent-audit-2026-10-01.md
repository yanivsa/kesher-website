# Independent Defect Audit: Compact Keywords Landing Page System

**Auditor:** Independent Senior SEO, CRO, Local SEO & Quality Assurance Specialist  
**Repository:** `yanivsa/kesher-website` (`kesher.saharoni.com`)  
**Audit Scope:** Verification of code baseline, search intent validity, cannibalization, doorway risks, Edward Sturm method fidelity, CRO/UX, technical SEO, and ethical/regulatory compliance.  
**Mode:** READ-ONLY Defect Audit (Zero modifications applied).  
**Date:** 2026-10-01  

---

## 1. Executive Findings

1. **Severe Internal Keyword Cannibalization (`/couples-crisis-ashdod` vs. `/services/couples/crisis` & `/couples-counseling-ashdod`):** The newly deployed `/couples-crisis-ashdod` targets the exact same search intent, user pain points, pricing (500 ₪ / 50 min), therapist, and location as the pre-existing, indexed `/services/couples/crisis` and `/couples-counseling-ashdod` pages. Both crisis pages feature near-identical headlines, FAQ items, and booking embeds, splitting topical equity and risking ranking oscillation.
2. **Textbook Google Doorway Page Risk (`/couples-counseling-gan-yavne`):** Shira Saharoni operates a physical clinic in Ashdod, not Gan Yavne. The Gan Yavne page is a clone of the Ashdod template where city names were swapped. Live SERPs for `ייעוץ זוגי גן יבנה` strongly favor local physical practitioners (e.g., in Gan Yavne streets HaTal, HaGolan, HaSayfan). Creating a city-specific page without physical premises violates Google’s Doorway Guidelines.
3. **Orphan Architecture for Gan Yavne (`/couples-counseling-gan-yavne`):** The Gan Yavne route has **zero internal crawlable links** across the entire website. The automated blog callout classifier (`getLandingTargetForPost`) never routes to `couples_gan_yavne`, leaving the URL as an unlinked island present only in `sitemap.xml`.
4. **Indiscriminate Mass Blog Injection (Internal-Link Stuffing):** In `src/pages/Blog/BlogPost.tsx`, `<LandingCalloutBanner />` is injected into all 94 published posts via broad regex. Any post containing ubiquitous Hebrew roots like `"ילד"` (child), `"הור"` (parent), or `"השכבה"` (toddler bedtime) forcefully injects an ADHD landing page callout, causing severe topical mismatch and internal CTA fatigue.
5. **Loss of Location Specificity in Analytics Events:** In `src/hooks/useLandingPageAnalytics.ts`, `trackPhoneClick` and `trackWhatsappClick` dispatch events hardcoded to `cta_location: 'landing_page'`. Marketers cannot determine whether calls/clicks originated from the Header, Hero, or Mobile Sticky Bar.
6. **Accordion-Hidden FAQs Contradicting Compact Keywords Methodology:** Edward Sturm’s documented methodology requires objection-handling content to be visibly readable on the page to resolve pre-purchase friction. Placing all FAQs inside collapsed `<details>` accordions forces user interaction to read answers and relies on deprecated Google `FAQPage` rich snippets (discontinued globally by Google in May 2026).
7. **Above-the-Fold Human Trust Deficit:** The hero section is 100% typography and vector icons, with zero authentic photography of Shira Saharoni or her clinic above the fold. The only practitioner image is buried in Section 5 (a 140×140px avatar), undermining the immediate human trust required in personal counseling niches.
8. **Vague, Rhetorical H1 on Crisis Page:** The H1 on `/couples-crisis-ashdod` (*"זוגיות במשבר חריף? אפשר לעצור את ההסלמה ולהחזיר את השקט"*) is an emotional question that omits both the core service term (*"ייעוץ זוגי"*) and location (*"באשדוד"*), failing the 5-second clarity test.
9. **Legal Validity Ambiguity on Mediation Page (`/couples-mediation-ashdod`):** The page presents *שלום בית ולחילופין גירושין* without explaining that mediation agreements require formal judicial validation in Family Court or Rabbinical Court under the Financial Relations Law to possess legal enforceability, risking misinterpretation of mediation scope.
10. **Orphaned Dead CSS Artifact:** The pre-existing file `src/pages/Landing/CouplesMediationAshdod/CouplesMediationAshdodPage.module.css` (17.4 KB) was completely disconnected when the page was rewritten to use `LandingPageTemplate`, leaving dead code in the repository.

---

## 2. Keyword / Intent Evidence Matrix

*Note on Search Volume:* No third-party API (Ahrefs/SEMrush/Google Keyword Planner) is active in this sandbox. In strict accordance with auditor instructions: **Search-volume evidence not verified.**

| URL | Intended Primary Keyword | User Problem & Funnel Stage | Live Israeli SERP Observations | Competing Existing Kesher URLs | Compact Keyword Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`/couples-crisis-ashdod`** | ייעוץ זוגי במשבר באשדוד | Severe escalation, loss of trust, couples at a crossroads. BOFU / High Intent. | SERP features Ashdod Municipal Family Station (subsidized welfare clinic), Betipulnet/B144 directories, and local private couples therapists. | 1. `/services/couples/crisis`<br>2. `/couples-counseling-ashdod` | **SHOULD MERGE WITH EXISTING PAGE** (Severe intent collision with `/services/couples/crisis`). |
| **`/parenting-adhd-ashdod`** | הדרכת הורים ל-ADHD באשדוד | Exhausting morning routines, homework meltdowns, power struggles. BOFU. | SERP features Ashdod Center for Meaningful Parenting, Nitzan Ashdod, Telem, private CBT/parenting clinics. Distinct specific intent from general parenting. | 1. `/parenting-guidance-ashdod`<br>2. `/services/parenting` | **VALID COMPACT KEYWORD** (Distinct acute pain point from general parenting guidance). |
| **`/couples-counseling-gan-yavne`** | ייעוץ זוגי גן יבנה | Couples in Gan Yavne seeking local therapy. BOFU. | SERP strongly favors physical practitioners in Gan Yavne (clinics on HaTal, HaGolan, HaSayfan streets) and local directory listings. | 1. `/couples-counseling-ashdod`<br>2. `/services/couples` | **WRONG / MIXED INTENT** (Shira's clinic is in Ashdod. Classic doorway risk). |
| **`/couples-mediation-ashdod`** | גישור זוגי ושלום בית באשדוד | Couples seeking structured out-of-court dispute resolution or separation. BOFU. | SERP split between family law attorneys drafting formal divorce/financial agreements, Municipal Consensual Divorce Center, and private mediators. | 1. `/services/mediation` | **PLAUSIBLE BUT UNPROVEN** (Viable if clearly positioned as mediation rather than legal representation). |

---

## 3. Defect Register

| ID | Severity | URL / File | Defect | Evidence | Why It Matters | Recommended Fix |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DEF-01** | **P1** | `src/pages/Landing/CouplesCrisisAshdod/`<br>`src/pages/Landing/CouplesCrisis/` | Direct Keyword Cannibalization between `/couples-crisis-ashdod` and `/services/couples/crisis`. | `/services/couples/crisis` already targets *"ייעוץ זוגי במשבר | שירה סהרוני"* with H1 *"זוגיות במשבר? אפשר להתחיל משיחה אחת רגועה"*. Both pages are in `sitemap.xml`. | Competes with itself in Google index, diluting backlink signals and causing ranking instability. | Consolidate: Redirect `/services/couples/crisis` (301) to `/couples-crisis-ashdod` or canonicalize one to the other. |
| **DEF-02** | **P1** | `src/pages/Landing/CouplesCounselingGanYavne/` | Google Doorway Page Risk. | Shira's clinic is in Ashdod. Copy duplicates Ashdod counseling pain points and approach, merely stating *"דקות נסיעה ספורות מגן יבנה"*. | Violates Google Spam Policies on doorway pages (creating pages targeting locations where business has no physical presence). | Remove standalone page. Add Gan Yavne/Shfela to `areaServed` on `/couples-counseling-ashdod` and mention proximity in local copy. |
| **DEF-03** | **P1** | `src/App.tsx`<br>`src/pages/Blog/BlogPost.tsx` | Complete Orphan Page (`/couples-counseling-gan-yavne`). | `grep -rn "couples-counseling-gan-yavne" src/` reveals zero internal links in visible navigation, footer, or blog posts. `getLandingTargetForPost` never outputs `couples_gan_yavne`. | Orphan pages receive no PageRank flow and signal programmatic manipulation to search engine crawlers. | If kept, integrate into service menus or blog routing; otherwise remove. |
| **DEF-04** | **P1** | `src/pages/Blog/BlogPost.tsx` (lines 21–36) | Indiscriminate Blog-to-Landing Callout Injection (Over-Triggering). | Regex `/קשב\|ADHD\|הפרעת קשב\|הור\|ילד\|זעם.../` matches generic parenting posts (e.g. toddlers, gifted children, siblings) and injects ADHD Ashdod landing banner. | Causes extreme topical mismatch, poor reader UX, and CTA blindness. | Tighten classifier to match only specific ADHD/executive function tags, or use manual frontmatter `landingTarget`. |
| **DEF-05** | **P2** | `src/hooks/useLandingPageAnalytics.ts` (lines 123–129) | Analytics CTA Location Context Lost. | `trackPhoneClick` and `trackWhatsappClick` pass hardcoded `cta_location: 'landing_page'` regardless of whether clicked in Header, Hero, or Sticky Bar. | Inability to evaluate CRO performance across distinct page placements (e.g. Hero vs Mobile Sticky). | Update `trackPhoneClick(location)` and `trackWhatsappClick(location)` to pass the actual calling location. |
| **DEF-06** | **P2** | `src/pages/Landing/LandingPageTemplate.tsx` (lines 538–606) | Collapsed FAQ Accordion Violating Compact Keywords Methodology. | All objection-handling FAQs are enclosed in collapsed `<details>` elements. | Edward Sturm explicitly recommends open, readable FAQs on conversion landing pages to reduce cognitive friction for hesitant buyers. | Render FAQs as open questions with visible answers instead of collapsed accordions. |
| **DEF-07** | **P2** | `src/pages/Landing/LandingPageTemplate.tsx` (line 163) | Deprecated `FAQPage` Schema Markup. | Injects `@type: 'FAQPage'` into JSON-LD `@graph`. | Google deprecated `FAQPage` rich results for commercial websites in May 2026. Markup generates no SERP enhancement. | Remove `FAQPage` from JSON-LD to streamline payload, or retain only if secondary engines require it. |
| **DEF-08** | **P2** | `src/data/landingPagesConfig.ts` (lines 20–25) | Vague, Rhetorical Hero Headline on Crisis Page. | H1 is *"זוגיות במשבר חריף? אפשר לעצור את ההסלמה ולהחזיר את השקט"*. Omits *"ייעוץ זוגי"* and *"באשדוד"*. | Fails the 5-second clarity test. Searchers arriving from transactional queries must infer the exact professional service offered. | Change H1 to: *"ייעוץ זוגי במשבר חריף באשדוד — עצירת הסלמה וחידוש התקשורת"*. |
| **DEF-09** | **P2** | `src/pages/Landing/LandingPageTemplate.tsx` (lines 242–260) | Zero Human Practitioner Imagery Above the Fold. | Hero section consists purely of text, badges, and icon buttons. First photo of Shira appears in Section 5. | Personal counseling is a high-vulnerability service where facial recognition and human presence drive trust. | Integrate a clean, authentic portrait of Shira Saharoni alongside the hero copy. |
| **DEF-10** | **P2** | `src/data/landingPagesConfig.ts` (lines 645–672) | Omission of Judicial Approval Requirement for Mediation Agreements. | Does not mention that an *הסכם שלום בית ולחילופין גירושין* requires approval by the Family/Rabbinical Court for binding legal validity. | Potential client misunderstanding regarding the legal enforceability of mediation summaries vs. court-approved agreements. | Add clear note in FAQ explaining that the agreement is submitted to the Family Court or Rabbinical Court for formal validation. |
| **DEF-11** | **P3** | `src/pages/Landing/CouplesMediationAshdod/` | Abandoned Dead CSS File (`CouplesMediationAshdodPage.module.css`). | 17.4 KB file remains on disk in `src/pages/Landing/CouplesMediationAshdod/` but is never imported after template refactor. | Repository clutter and technical debt. | Delete the unused `.module.css` file. |

---

## 4. Per-Page Verdict

### 1. `/couples-crisis-ashdod`
- **What Works:** Clear pain points (escalation, stonewalling, trust crisis); transparent pricing (500 ₪ / 50 min); prefilled WhatsApp CTA; mobile sticky bar; clean distraction-free layout.
- **What Does Not:** H1 lacks the service name and location; hero lacks human photo; direct cannibalization with `/services/couples/crisis`.
- **Cannibalization:** **Severe.** Exact duplicate intent with `/services/couples/crisis` (which already ranks and has incoming links).
- **Doorway Assessment:** Clean (clinic is in Ashdod).
- **CRO Assessment:** Strong CTA group, but H1 is emotional rather than clear.
- **Recommendation:** **MERGE.** Redirect `/services/couples/crisis` to `/couples-crisis-ashdod`, upgrade H1 to directly state *"ייעוץ זוגי במשבר באשדוד"*, and add Shira's portrait to the hero.

### 2. `/parenting-adhd-ashdod`
- **What Works:** Highly differentiated from general parenting guidance; speaks directly to acute ADHD friction points (morning routine, screen battles, homework paralysis); explicit ethical disclaimer that Shira does not prescribe medication or replace medical doctors; realistic 50-minute consultation structure.
- **What Does Not:** Over-triggered across unrelated blog posts via loose regex; hero lacks imagery; FAQs hidden behind accordions.
- **Cannibalization:** **Low.** Distinct intent from `/parenting-guidance-ashdod`.
- **Doorway Assessment:** Clean (Ashdod clinic).
- **CRO Assessment:** High intent, empathetic copy, clear WhatsApp CTA.
- **Recommendation:** **KEEP WITH FIXES.** Restrict blog callout injection to specific ADHD articles, open FAQ accordion by default, and add a hero image.

### 3. `/couples-counseling-gan-yavne`
- **What Works:** Transparently admits clinic is in Ashdod; clear driving distance note.
- **What Does Not:** Identical copy to Ashdod couples counseling; complete orphan page with zero internal links; attempts to rank in a local market where competitors maintain physical clinics.
- **Cannibalization:** Competes directly with `/couples-counseling-ashdod`.
- **Doorway Assessment:** **High Risk.** Classic doorway page pattern (creating a location-targeted page for a neighboring town without physical presence).
- **CRO Assessment:** Poor trust signal when a searcher seeking a Gan Yavne clinic realizes they must travel to Ashdod.
- **Recommendation:** **REMOVE / DO NOT INDEX YET.** Delete route, remove from sitemap, and incorporate Gan Yavne into the `areaServed` and copy of `/couples-counseling-ashdod`.

### 4. `/couples-mediation-ashdod`
- **What Works:** Addresses genuine demand for consensual, out-of-court dispute resolution; highlights Shira’s legal background (`עורכת דין בהכשרתה`) without overstepping into partisan representation; outlines 3 structured mediation phases.
- **What Does Not:** Disconnected legacy CSS file left on disk; does not explain the necessity of court submission for formal agreement validity.
- **Cannibalization:** Minimal (distinct from `/services/mediation` overview).
- **Doorway Assessment:** Clean (Ashdod clinic).
- **CRO Assessment:** Strong reassurance copy for couples hesitant about adversarial litigation.
- **Recommendation:** **KEEP WITH FIXES.** Add clarification regarding judicial court approval of the agreement, clean up unused CSS, and open FAQ accordion.

---

## 5. Method-Fidelity Findings (Edward Sturm Methodology)

| Principle | Expected Sturm Standard | Implemented State | Fidelity Verdict |
| :--- | :--- | :--- | :--- |
| **Keyword Selection** | Specific BOFU scenario with commercial purchase intent | 3 acute scenarios (Crisis, ADHD, Mediation) + 1 artificial geo-variant (Gan Yavne). | **PARTIAL** (Gan Yavne is an artificial geo-split). |
| **Page Concision** | ~400–600 focused words, zero fluff | Pages range between 484 and 564 words. Crisp, punchy copywriting. | **PASS** |
| **Above-the-Fold Clarity** | Immediate service identification within 5 seconds | Clear on ADHD, Mediation, Gan Yavne. Vague/rhetorical on Crisis. | **PARTIAL** (Crisis H1 needs revision). |
| **Buyer-Intent FAQ** | Open, visible objection-handling content | Hidden behind collapsed `<details>` accordions on all pages. | **FAIL** (Sturm advises avoiding collapsed accordions). |
| **Contact Prominence** | Dual phone/messaging CTAs visible at all times | Header phone, Hero dual CTAs, and Mobile Sticky Bar. | **PASS** |
| **Trust & Proof** | Authentic imagery, clear credentials, physical reality | Real credentials and pricing, but zero hero photography. | **PARTIAL** (No authentic face/clinic in hero). |
| **Site Architecture** | Natural internal links from relevant contextual hubs | Injected indiscriminately into all 94 blog posts; Gan Yavne orphaned. | **FAIL** (Link stuffing on blogs, orphan on Gan Yavne). |

---

## 6. Google Compliance Findings

1. **People-First Content (Helpful Content System):** The content for Crisis, ADHD, and Mediation provides genuine, empathetic, and practical value for visitors seeking counseling. However, the Gan Yavne page provides no distinct value over the Ashdod page for a real human user.
2. **Doorway Abuse Risk (Google Spam Policies):** `/couples-counseling-gan-yavne` presents a direct violation of Google's doorway policies. Creating separate pages for neighboring suburbs (Gan Yavne, Bitzaron, Gedera) targeting the same centralized service without local physical operations risks algorithmic devaluation across the local entity cluster.
3. **Structured Data Truthfulness:** JSON-LD correctly sets `addressLocality: "אשדוד"` on all pages (including Gan Yavne), truthfully avoiding false location claims in schema. However, `FAQPage` schema is obsolete following Google’s 2026 deprecation.
4. **Crawlability & Indexability:** All prerendered static HTML files in `dist/` include valid self-referencing canonicals, single `<h1>` tags, and unique meta descriptions. All routes return HTTP 200.

---

## 7. Verification Results

| Command | Status | Result / Details |
| :--- | :--- | :--- |
| `npm run lint` | **PASS** | 0 errors (19 known ignore warnings across auxiliary scripts). |
| `npm run typecheck` | **PASS** | TypeScript compiler (`tsc && tsc -p tsconfig.functions.json`) passed with 0 errors. |
| `npm run test:content` | **PASS** | 94 published blog posts validated; content automation gates passed. |
| `npm test` | **PASS** | 21 test files, 134 tests passed in 47.3s. |
| `npm run build` | **PASS** | Vite production bundles built; Playwright Chromium prerendered all 126 static routes. |
| `npm run verify:dist` | **PASS** | 126 prerendered HTML routes verified with valid self-canonicals and `404.html`. |
| Mobile Viewport Suite (375/390/412px) | **PASS** | Verified via Playwright HTTP: `scrollWidth <= clientWidth`, zero horizontal overflow, sticky bar positioned with 72px padding clearance. |

---

## 8. Final Blockers

```text
DEPLOYMENT BLOCKERS:
1. [P1] DEF-01: Cannibalization between /couples-crisis-ashdod and /services/couples/crisis.
   Must establish 301 redirect from /services/couples/crisis to /couples-crisis-ashdod to prevent self-competition.
2. [P1] DEF-02: Google Doorway Page Risk on /couples-counseling-gan-yavne.
   Must remove standalone Gan Yavne URL and consolidate geographic coverage into /couples-counseling-ashdod.
3. [P1] DEF-03: Orphan Page architecture for /couples-counseling-gan-yavne (zero internal links).
4. [P1] DEF-04: Indiscriminate Blog-to-Landing Callout Injection across all 94 blog posts.
   Must restrict getLandingTargetForPost to semantically relevant articles only.
```

---

## Auditor Notes / Evidence Limitations

- **Search Volume:** As noted in Section 2, search volume for Israeli queries was not verifiable through third-party volume APIs in this local environment; qualitative SERP competition and practitioner landscape analysis was used instead.
- **Live GTM/GA4 Network Egress:** Real GA4 server hit receipt was not verified over live external networks because tracking is configured through GTM container injection in production, but client-side `window.dataLayer` pushes and custom events (`primary_cta_click`, `secondary_cta_click`, `phone_click`, `whatsapp_click`, `scroll_50`, `scroll_90`) were verified in the DOM runtime.
