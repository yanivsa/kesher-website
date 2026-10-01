# Compact Keywords Evidence Manifest

**Audit Baseline Date:** 2026-10-01  
**Repository:** `yanivsa/kesher-website`  
**Target Environment:** `https://kesher.saharoni.com`  

---

## 1. Git Provenance

- **Base SHA (immediately preceding Compact Keywords work):** `0bf9271edace85627a3d38541cd88480784261d5`
- **Main Branch Current SHA:** `0bf9271edace85627a3d38541cd88480784261d5`
- **Freeze Branch Name:** `audit/compact-keywords-freeze-20261001`
- **Commit Date:** 2026-10-01

To inspect the exact diff against the pre-implementation baseline:
```bash
git diff 0bf9271edace85627a3d38541cd88480784261d5...HEAD
```

---

## 2. Designated Landing Routes

| Route | Designated Purpose | Canonical URL |
| :--- | :--- | :--- |
| `/couples-crisis-ashdod` | ייעוץ זוגי במשבר חריף באשדוד | `https://kesher.saharoni.com/couples-crisis-ashdod` |
| `/parenting-adhd-ashdod` | הדרכת הורים ל-ADHD והפרעות קשב באשדוד | `https://kesher.saharoni.com/parenting-adhd-ashdod` |
| `/couples-counseling-gan-yavne` | ייעוץ זוגי בגן יבנה והסביבה | `https://kesher.saharoni.com/couples-counseling-gan-yavne` |
| `/couples-mediation-ashdod` | גישור והסכם שלום בית ולחילופין גירושין באשדוד | `https://kesher.saharoni.com/couples-mediation-ashdod` |

---

## 3. Implementation Files Manifest

### Core Architecture & Configuration
- `src/data/landingPagesConfig.ts`: Central typed dictionary defining metadata, keywords, hero, pain points, 3-step approach, bio, pricing, Calendly embeds, FAQs, and Schema.org for all landing routes.
- `src/pages/Landing/LandingPageTemplate.tsx`: Reusable layout component with minimal header, hero, pain-point cards, 3-step timeline, bio card, pricing card, Calendly embed, FAQ accordion, closing CTA, minimal footer, and sticky mobile bar.
- `src/pages/Landing/LandingPageTemplate.module.css`: CSS Module defining mobile-first responsive layout, CSS variables, sticky bottom bar (z-index 1000), and mobile padding clearance (72px).

### Dedicated Page Entries
- `src/pages/Landing/CouplesCrisisAshdod/CouplesCrisisAshdodPage.tsx`: Route entry for `/couples-crisis-ashdod`.
- `src/pages/Landing/ParentingAdhdAshdod/ParentingAdhdAshdodPage.tsx`: Route entry for `/parenting-adhd-ashdod`.
- `src/pages/Landing/CouplesCounselingGanYavne/CouplesCounselingGanYavnePage.tsx`: Route entry for `/couples-counseling-gan-yavne`.
- `src/pages/Landing/CouplesMediationAshdod/CouplesMediationAshdodPage.tsx`: Refactored route entry for `/couples-mediation-ashdod`.
- *Note:* `src/pages/Landing/CouplesMediationAshdod/CouplesMediationAshdodPage.module.css` (17.4 KB) was left unreferenced following the template refactor (Audit finding DEF-11).

### Application Routing & Layout Isolation
- `src/App.tsx`: Registered `loadable` imports, `routeLoaders` with memoized preloading, and `<Route>` declarations for all 4 landing routes.
- `src/components/Layout/Layout.tsx`: Configured `usesStandaloneHomepage` to render distraction-free layouts (suppressing global header, global footer, floating WhatsApp, and chatbot).

### Internal Funneling
- `src/components/LandingCalloutBanner/LandingCalloutBanner.tsx`: Reusable callout widget with presets for crisis, ADHD, Gan Yavne, and mediation.
- `src/components/LandingCalloutBanner/LandingCalloutBanner.module.css`: Visual styling for callout widget.
- `src/pages/Blog/BlogPost.tsx`: Injected `getLandingTargetForPost()` and `<LandingCalloutBanner />` dynamically before `<SignatureMark />`.
- `src/data/posts.json`: Added contextual bridge links in `relationship-crisis-flydubai-lessons` and `adhd-morning-conflict-dopamine-myth`.

### Build & Sitemap Integration
- `.gitignore`: Updated root `/data/` and `/reports/` ignore patterns to prevent accidental exclusion of `src/data/landingPagesConfig.ts`.
- `scripts/content-policy.cjs`: Added routes to `STATIC_ROUTES`.
- `scripts/generate-sitemap.cjs`: Registered routes in sitemap generator with priority 0.95.
- `public/sitemap.xml`, `public/llms-full.txt`, `public/rss.xml`, `src/data/postSummaries.json`: Regenerated artifacts.

### Test Suites
- `tests/landing-pages-config.test.ts`: 29 tests verifying data structure, titles (< 60 chars), descriptions (< 155 chars), canonicals, phone numbers, and FAQ answers.
- `tests/landing-page-component.test.tsx`: 7 tests verifying component rendering and CTA presence.
- `tests/app-routing.test.ts`: Route loader preloading tests.
- `vitest.config.ts`: Configured `tests/**/*.test.tsx` inclusion and `testTimeout: 15000`.

---

## 4. Verification Commands Snapshot

All commands executed locally against the working tree and documented in the audit:

| Command | Status | Output / Details |
| :--- | :--- | :--- |
| `npm run generate` | **PASS** | Generated 94 lightweight post summaries, sitemap, llms-full.txt, and rss.xml. Exit code 0. |
| `npm run lint` | **PASS** | 0 errors (19 known warning notices for script ignores). Exit code 0. |
| `npm run typecheck` | **PASS** | `tsc && tsc -p tsconfig.functions.json` passed with 0 errors. Exit code 0. |
| `npm run test:content` | **PASS** | Validated 94 published posts; all automation gates passed. Exit code 0. |
| `npm test` | **PASS** | 21 test files passed (134 of 134 tests passed) in 47.3s. Exit code 0. |
| `npm run build` | **PASS** | Vite production bundle built; Playwright Chromium prerendered 126 routes. Exit code 0. |
| `npm run verify:dist` | **PASS** | Verified 126 prerendered routes with self-canonicals and 404.html. Exit code 0. |

---

## 5. Browser & Viewport Verification

All checks performed using Playwright against prerendered static distribution files served over local HTTP:

| Target Page | Viewports Tested | Observations | Status |
| :--- | :--- | :--- | :--- |
| `/couples-crisis-ashdod` | 375×667, 390×844, 412×915, 1280×800 | `scrollWidth <= clientWidth` (zero overflow). Fixed bottom sticky bar active with 72px padding clearance. Zero footer overlap. | **PASS** |
| `/parenting-adhd-ashdod` | 375×667, 390×844, 412×915, 1280×800 | Zero horizontal overflow. CTAs accessible. | **PASS** |
| `/couples-counseling-gan-yavne` | 375×667, 390×844, 412×915, 1280×800 | Zero horizontal overflow. Sticky bar visible. | **PASS** |
| `/couples-mediation-ashdod` | 375×667, 390×844, 412×915, 1280×800 | Zero horizontal overflow. Sticky bar visible. | **PASS** |
| Core Pre-existing Pages (`/`, `/services/couples`, `/services/parenting`, `/blog`, `/contact`) | 375×667 | All return HTTP 200. Main header present. Landing sticky bar correctly absent (no CSS bleed). | **PASS** |

---

## 6. Search & SERP Evidence Log

Directly observed SERP observations from live search executed on 2026-10-01 (Israel / Hebrew):

1. **`ייעוץ זוגי במשבר אשדוד`:**
   - *Observed SERP:* Prominent municipal subsidized clinic (התחנה לטיפול זוגי ומשפחתי של עיריית אשדוד ברחוב יצחק שדה 8), directory listings (בטיפולנט, B144, איזי), and private therapists specializing in crisis/infidelity.
   - *Interpretation:* Commercial/transactional local intent exists in Ashdod. However, Kesher already has an established, indexed page (`/services/couples/crisis`) targeting this exact query, creating direct internal cannibalization.
2. **`הדרכת הורים ל-ADHD באשדוד`:**
   - *Observed SERP:* Municipal parenting centers (המרכז להורות משמעותית אשדוד, מרכז הורים וילדים י"ב), private diagnostic/treatment institutes (מכון ממדים, ת.ל.מ אשדוד, ניצן הורים), and CBT/parenting practitioners on Betipulnet.
   - *Interpretation:* Clear, distinct transactional query cluster separating ADHD parenting from general parenting. Standing page is justified.
3. **`ייעוץ זוגי גן יבנה`:**
   - *Observed SERP:* Multiple practitioners maintaining physical clinics inside Gan Yavne (e.g., Eran Rozen on HaTal 17, Ilona Shani on HaGolan 6, Anat Rothschild on HaSayfan 4) alongside local directory packs.
   - *Interpretation:* Google local search for Gan Yavne strongly rewards local physical presence. Shira Saharoni operates solely in Ashdod. Creating a Gan Yavne URL with an Ashdod clinic constitutes a doorway risk.
4. **`גישור זוגי אשדוד` / `הסכם שלום בית ולחילופין גירושין אשדוד`:**
   - *Observed SERP:* Municipal Consensual Divorce Center (המרכז לגירושין בהסכמה - עיריית אשדוד), family law attorneys drafting enforceable court agreements, and private mediators.
   - *Interpretation:* Legally sensitive intent. An *הסכם שלום בית ולחילופין גירושין* in Israel is predominantly understood as a formal agreement requiring judicial confirmation by the Family Court or Rabbinical Court under the Financial Relations Law.
