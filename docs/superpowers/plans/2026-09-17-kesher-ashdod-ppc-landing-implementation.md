# Kesher Ashdod PPC Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the approved `לצאת מהלופ` PPC control/challenger copy, brand-consistent Calendly styling, and conversion-value handling for `/couples-counseling-ashdod` without publishing or enabling paid media.

**Architecture:** Keep the existing React/Vite landing-page architecture and query-param A/B/C variant mechanism. Make only targeted copy/brand/measurement changes in the existing landing page, Calendly embed, and analytics helper; expand the existing Vitest/Playwright coverage so every approved behavior is regression-tested before the full repository quality gate runs.

**Tech Stack:** React 19, TypeScript 6, Vite 8, Vitest 4, Playwright 1.61, Calendly inline widget, GA4/GTM/Google Ads conversion forwarding.

**Spec:** `docs/superpowers/specs/2026-09-17-kesher-ashdod-ppc-campaign-design.md`

## Global Constraints

- Primary URL remains `/couples-counseling-ashdod`.
- Brand remains Shira Saharoni / Kesher.
- Big Idea remains `לצאת מהלופ`.
- Default Variant A is the control; B and C remain explicit challengers selected by `?variant=B` / `?variant=C`.
- Primary CTA remains `קביעת פגישה`; secondary CTA remains `יש לי שאלה לפני שקובעים`.
- Offer facts remain: 50 minutes, clinic in Ashdod or Zoom, 500 ILS including VAT, no advance commitment to a fixed number of sessions.
- Brand colors remain sage `#4A6854`, terracotta `#945035`, cream `#FAF7F4`, deep brown `#2D2926`, white `#FFFFFF`.
- Do not add outcome guarantees, success-rate claims, invented testimonials, unsupported credentials, fake urgency, or relationship-status inference.
- Canonical URL must remain the clean `/couples-counseling-ashdod` URL for every copy variant.
- Do not launch/enable Google Ads, change budgets, publish social posts, or merge a production-deploying PR without explicit human approval.

---

## File Structure

Files modified by this implementation:

- `src/pages/Landing/CouplesCounselingAshdod/CouplesCounselingAshdodPage.tsx` — approved control/challenger copy, offer microcopy, unsupported credential repair.
- `src/components/Booking/CalendlyBookingEmbed.tsx` — Calendly brand accent color only.
- `src/lib/analytics.ts` — preserve supplied conversion value/currency in direct GA4-to-Google-Ads forwarding while retaining safe defaults.
- `tests/e2e/couples-ashdod-cro.spec.ts` — landing copy, canonical, variant, responsive and aggregate analytics regression coverage.
- `tests/analytics-google-ads.test.ts` — conversion-value/currency regression coverage.
- `tests/calendly-branding.test.ts` — small source-level brand-lock regression test for the Calendly primary color.

No routing, schema architecture, booking provider, pricing, or CSS-system refactor is required.

---

### Task 1: Lock the approved A/B/C landing-page messages and remove unsupported credential wording

**Files:**
- Modify: `tests/e2e/couples-ashdod-cro.spec.ts`
- Modify: `src/pages/Landing/CouplesCounselingAshdod/CouplesCounselingAshdodPage.tsx`

**Interfaces:**
- Consumes: existing `VariantId = 'A' | 'B' | 'C'` and `copyVariants` lookup.
- Produces: stable variant-specific H1/subtitle content and a verified non-credentialed About heading.

- [ ] **Step 1: Replace the old default-H1 assertions with the approved control and add B/C challenger assertions**

Update `tests/e2e/couples-ashdod-cro.spec.ts` so the mobile/desktop default assertions use:

```ts
name: 'ייעוץ זוגי באשדוד – כשכל שיחה חוזרת לאותו מקום, אפשר להתחיל לדבר אחרת'
```

Add this test:

```ts
test('approved PPC copy variants remain explicit and canonical', async ({ page }) => {
  const cases = [
    {
      variant: 'A',
      heading: 'ייעוץ זוגי באשדוד – כשכל שיחה חוזרת לאותו מקום, אפשר להתחיל לדבר אחרת',
      subtitle: 'מזהים מה קורה ביניכם כשהשיחה מסתבכת, נותנים מקום לשתי נקודות המבט ומתחילים לתרגל דרך מעשית אחרת לנהל את השיחה.',
    },
    {
      variant: 'B',
      heading: 'ייעוץ זוגי באשדוד – לא צריך להסכים מי צודק כדי להתחיל לדבר אחרת',
      subtitle: 'הפגישה אינה מקום לבחור צד. עושים סדר במה שקורה כשהשיחה מסתבכת, נותנים מקום לשתי נקודות המבט ובודקים דרך אחרת להתמודד עם אותם רגעים.',
    },
    {
      variant: 'C',
      heading: 'ייעוץ זוגי באשדוד – אפשר להתחיל מפגישה אחת מסודרת',
      subtitle: '50 דקות שבהן עושים סדר במה שקורה ביניכם, מזהים את הדפוס שחוזר ובוחרים נקודה מעשית ראשונה לעבודה.',
    },
  ] as const;

  for (const item of cases) {
    await page.goto(`/couples-counseling-ashdod?variant=${item.variant}`);
    await expect(page.getByRole('heading', { level: 1, name: item.heading })).toBeVisible();
    await expect(page.getByText(item.subtitle, { exact: true })).toBeVisible();
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
      'href',
      'https://kesher.saharoni.com/couples-counseling-ashdod',
    );
  }
});
```

Add this accuracy assertion:

```ts
test('landing page does not present an unsupported counseling credential', async ({ page }) => {
  await page.goto('/couples-counseling-ashdod');

  await expect(page.getByText('יועצת נישואין מוסמכת באשדוד', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('heading', {
    level: 2,
    name: 'יועצת זוגית באשדוד – מרחב מכבד לשני הצדדים',
  })).toBeVisible();
});
```

- [ ] **Step 2: Run the focused Playwright spec and verify it fails on the old copy**

Run:

```bash
npx playwright test tests/e2e/couples-ashdod-cro.spec.ts
```

Expected: FAIL on the old Variant A heading and/or missing approved B/C copy/credential heading.

- [ ] **Step 3: Apply the approved copy to `copyVariants` and About heading**

In `CouplesCounselingAshdodPage.tsx`, set:

```ts
const copyVariants: Record<VariantId, { eyebrow: string; h1: string; subtitle: string }> = {
  A: {
    eyebrow: 'קליניקה באשדוד ובאונליין | שירה סהרוני',
    h1: 'ייעוץ זוגי באשדוד – כשכל שיחה חוזרת לאותו מקום, אפשר להתחיל לדבר אחרת',
    subtitle: 'מזהים מה קורה ביניכם כשהשיחה מסתבכת, נותנים מקום לשתי נקודות המבט ומתחילים לתרגל דרך מעשית אחרת לנהל את השיחה.',
  },
  B: {
    eyebrow: 'תהליך ממוקד ומעשי בקליניקה באשדוד ובאונליין',
    h1: 'ייעוץ זוגי באשדוד – לא צריך להסכים מי צודק כדי להתחיל לדבר אחרת',
    subtitle: 'הפגישה אינה מקום לבחור צד. עושים סדר במה שקורה כשהשיחה מסתבכת, נותנים מקום לשתי נקודות המבט ובודקים דרך אחרת להתמודד עם אותם רגעים.',
  },
  C: {
    eyebrow: 'ייעוץ זוגי באשדוד ובאונליין',
    h1: 'ייעוץ זוגי באשדוד – אפשר להתחיל מפגישה אחת מסודרת',
    subtitle: '50 דקות שבהן עושים סדר במה שקורה ביניכם, מזהים את הדפוס שחוזר ובוחרים נקודה מעשית ראשונה לעבודה.',
  },
};
```

Change the hero microcopy to exactly:

```tsx
<div className={styles.heroMicrocopy}>
  50 דקות · אשדוד או Zoom · 500 ₪ · ללא התחייבות מראש לתהליך ארוך
</div>
```

Replace:

```tsx
<h2>יועצת נישואין מוסמכת באשדוד – מרחב בטוח לשני הצדדים</h2>
```

with:

```tsx
<h2>יועצת זוגית באשדוד – מרחב מכבד לשני הצדדים</h2>
```

Do not change Shira's verified role line `שירה סהרוני | יועצת זוגית ומנחת הורים`.

- [ ] **Step 4: Run the focused Playwright spec again**

Run:

```bash
npx playwright test tests/e2e/couples-ashdod-cro.spec.ts
```

Expected: PASS at 320/375/390/430 mobile widths, 1366/1440/1920 desktop widths, copy variants, canonical, credential accuracy, and FAQ aggregate analytics.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/pages/Landing/CouplesCounselingAshdod/CouplesCounselingAshdodPage.tsx tests/e2e/couples-ashdod-cro.spec.ts
git commit -m "feat: align Ashdod landing copy with PPC campaign"
```

---

### Task 2: Bring the Calendly inline widget back into the approved brand palette

**Files:**
- Create: `tests/calendly-branding.test.ts`
- Modify: `src/components/Booking/CalendlyBookingEmbed.tsx`

**Interfaces:**
- Consumes: Calendly query parameters `background_color`, `text_color`, `primary_color`.
- Produces: the same booking widget behavior with `primary_color=945035` instead of cyan.

- [ ] **Step 1: Add a failing brand-lock regression test**

Create `tests/calendly-branding.test.ts`:

```ts
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const source = readFileSync(
  new URL('../src/components/Booking/CalendlyBookingEmbed.tsx', import.meta.url),
  'utf8',
);

describe('Calendly brand lock', () => {
  it('uses the approved Kesher terracotta accent and not the legacy cyan', () => {
    expect(source).toContain("calendlyUrl.searchParams.set('primary_color', '945035')");
    expect(source).not.toContain("calendlyUrl.searchParams.set('primary_color', '0ca5c9')");
  });
});
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
npx vitest run tests/calendly-branding.test.ts
```

Expected: FAIL because the source still contains `0ca5c9`.

- [ ] **Step 3: Change only the Calendly primary color**

In `CalendlyBookingEmbed.tsx`, replace:

```ts
calendlyUrl.searchParams.set('primary_color', '0ca5c9');
```

with:

```ts
calendlyUrl.searchParams.set('primary_color', '945035');
```

Keep `background_color=ffffff`, `text_color=111111`, all attribution parameters, booking event listeners, and redirect behavior unchanged.

- [ ] **Step 4: Run the brand-lock test**

Run:

```bash
npx vitest run tests/calendly-branding.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/components/Booking/CalendlyBookingEmbed.tsx tests/calendly-branding.test.ts
git commit -m "fix: align Calendly with Kesher brand palette"
```

---

### Task 3: Preserve real booking value in direct Google Ads conversion forwarding

**Files:**
- Modify: `tests/analytics-google-ads.test.ts`
- Modify: `src/lib/analytics.ts`

**Interfaces:**
- Consumes: `pushAnalyticsEvent(eventName, params)` with optional numeric `params.value` and string `params.currency`.
- Produces: in `ga4` mode only, direct Google Ads conversion call uses supplied value/currency; otherwise defaults remain `value: 1`, `currency: 'ILS'`. GTM mode continues to emit no direct Google Ads conversion call.

- [ ] **Step 1: Add a failing test for booking value and a regression test for default-value events**

In `tests/analytics-google-ads.test.ts`, add:

```ts
it('forwards the supplied booking value and currency to Google Ads in direct GA4 mode', () => {
  pushAnalyticsEvent('booking_complete', { value: 500, currency: 'ILS' });

  expect(window.gtag).toHaveBeenCalledWith(
    'event',
    'conversion',
    expect.objectContaining({
      send_to: ADS_DESTINATIONS.booking_complete,
      value: 500,
      currency: 'ILS',
    }),
  );
});

it('keeps the default value for conversion events that do not supply one', () => {
  pushAnalyticsEvent('phone_click');

  expect(window.gtag).toHaveBeenCalledWith(
    'event',
    'conversion',
    expect.objectContaining({
      send_to: ADS_DESTINATIONS.phone_click,
      value: 1,
      currency: 'ILS',
    }),
  );
});
```

Keep the existing GTM-mode test unchanged.

- [ ] **Step 2: Run the focused analytics test and verify the booking-value test fails**

Run:

```bash
npx vitest run tests/analytics-google-ads.test.ts
```

Expected: FAIL because direct forwarding currently hard-codes `value: 1`.

- [ ] **Step 3: Pass conversion parameters into `reportGoogleAdsConversion`**

Change the helper signature in `src/lib/analytics.ts` from:

```ts
const reportGoogleAdsConversion = (eventName: string) => {
```

to:

```ts
const reportGoogleAdsConversion = (eventName: string, params: AnalyticsParams) => {
```

Replace the conversion payload with:

```ts
const value = typeof params.value === 'number' && Number.isFinite(params.value)
  ? params.value
  : 1;
const currency = typeof params.currency === 'string' && params.currency.trim()
  ? params.currency
  : 'ILS';

window.gtag('event', 'conversion', {
  send_to: destination,
  value,
  currency,
});
```

Then replace:

```ts
reportGoogleAdsConversion(eventName);
```

with:

```ts
reportGoogleAdsConversion(eventName, params);
```

Do not change the existing measurement-mode guard:

```ts
if (window.__kesherMeasurementMode !== 'ga4' || typeof window.gtag !== 'function') return;
```

This preserves the no-direct-forwarding behavior when production uses GTM and avoids introducing a second conversion path.

- [ ] **Step 4: Run analytics tests**

Run:

```bash
npx vitest run tests/analytics-google-ads.test.ts
```

Expected: PASS, including supplied booking value, default value, GTM exclusion, and dedupe behavior.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/lib/analytics.ts tests/analytics-google-ads.test.ts
git commit -m "fix: preserve booking value in direct Ads conversion"
```

---

### Task 4: Verify variant attribution and booking analytics remain intact after copy changes

**Files:**
- Modify only if a regression is found: `tests/e2e/booking-attribution.spec.ts`
- Modify only if required by a failing test: `src/components/Booking/CalendlyBookingEmbed.tsx`, `src/hooks/useLandingPageAnalytics.ts`, `src/lib/attribution.ts`

**Interfaces:**
- Consumes: `variant_id`, UTM fields, GCLID-presence metadata, `booking_start`, `booking_complete`.
- Produces: unchanged attribution behavior across A/B/C landing variants.

- [ ] **Step 1: Run existing booking-attribution E2E coverage before changing any attribution code**

Run:

```bash
npx playwright test tests/e2e/booking-attribution.spec.ts
```

Expected: PASS. If it already passes, do not modify attribution implementation.

- [ ] **Step 2: Run landing-page aggregate analytics coverage for challenger B**

Run:

```bash
npx playwright test tests/e2e/couples-ashdod-cro.spec.ts --grep "FAQ interaction tracking stays aggregate and variant-aware"
```

Expected: PASS with `variant_id: 'B'` and no sensitive fields such as `relationship_status` or `audience`.

- [ ] **Step 3: Confirm production bootstrap remains single-path by mode**

Run:

```bash
npx vitest run tests/analytics-google-ads.test.ts
```

Expected: PASS for both direct `ga4` and `gtm` mode tests. Do not add a second reporting mechanism.

- [ ] **Step 4: Commit only if a real regression required a code/test repair**

If no changes were necessary, record `Task 4: verification only; no commit` in the implementation notes.

---

### Task 5: Run repository quality gates and inspect the rendered landing page

**Files:**
- No planned source changes; fix only failures caused by Tasks 1–3.

**Interfaces:**
- Produces: implementation proven against repository lint, type, content, build, prerender, accessibility/layout and E2E gates.

- [ ] **Step 1: Run focused Vitest suite**

```bash
npx vitest run tests/analytics-google-ads.test.ts tests/calendly-branding.test.ts
```

Expected: PASS.

- [ ] **Step 2: Run focused landing/booking Playwright suite**

```bash
npx playwright test tests/e2e/couples-ashdod-cro.spec.ts tests/e2e/booking-attribution.spec.ts
```

Expected: PASS.

- [ ] **Step 3: Run the full repository gate**

```bash
npm run check
```

Expected: PASS for generation, lint, content policy, Python policy/controller tests, Vitest, TypeScript/build/prerender, `verify:dist`, and Playwright E2E.

- [ ] **Step 4: Start preview and inspect the default plus challengers at mobile/desktop widths**

Run:

```bash
npm run preview -- --host 127.0.0.1
```

Inspect:

```text
/couples-counseling-ashdod
/couples-counseling-ashdod?variant=B
/couples-counseling-ashdod?variant=C
```

At minimum inspect 390x844 and 1440x900. Verify:

- no horizontal overflow;
- H1/subtitle match the selected variant;
- booking CTA remains visible and functional;
- WhatsApp CTA remains secondary;
- 500 ILS / 50 minutes / Ashdod or Zoom microcopy is readable;
- no unsupported `מוסמכת` wording appears in the landing-page About heading;
- Calendly uses the terracotta accent;
- no broken image or layout regression.

- [ ] **Step 5: Commit any gate-only repair, then rerun the failing command**

Use a scoped commit message such as:

```bash
git commit -m "test: repair Ashdod landing regression"
```

Do not weaken tests to make a failure disappear.

---

### Task 6: Prepare the implementation PR for human review without deploying or launching ads

**Files:**
- PR metadata only.

**Interfaces:**
- Produces: a reviewable implementation PR whose merge can be explicitly approved later.

- [ ] **Step 1: Summarize the exact implementation delta in the PR body**

Include:

```markdown
## Implementation
- approved `לצאת מהלופ` control copy and B/C challengers
- removed unsupported `יועצת נישואין מוסמכת` wording from the PPC landing page
- aligned Calendly accent with Kesher terracotta
- preserved 500 ILS booking value in direct GA4-to-Google-Ads conversion forwarding
- expanded landing-page, canonical, brand-lock and analytics tests

## Verification
- focused Vitest: PASS
- focused Playwright: PASS
- `npm run check`: PASS

## Not included
- no Google Ads campaign launch or enablement
- no budget/bid changes
- no social publishing
- no production merge/deploy without explicit approval
```

- [ ] **Step 2: Confirm CI status for the implementation head commit**

Use the GitHub Actions checks for the PR head SHA. Every required repository check must be green or explicitly understood before requesting merge approval.

- [ ] **Step 3: Stop at the human merge/launch gate**

Do not merge the implementation PR and do not enable any paid campaign. Present the PR, test results, and any remaining account-side measurement uncertainty to the user for explicit approval.

---

## Deferred Separate Plans

The approved campaign spec covers three independently reviewable systems. This plan deliberately implements only the website/measurement slice so it remains testable and reversible.

Create separate plans after this one is implemented:

1. **Google Ads account build plan** — campaign/ad-group creation, exact/phrase keywords, negatives, location setting, RSA assets, conversion-goal audit, draft-only build, and explicit budget/launch approval.
2. **Creative production plan** — Shira photography/video assets, three short-form videos, static concepts, asset QA and human image approval.
3. **Organic social plan** — seven-post production, channel adaptation, scheduling/publishing approval.

None of these deferred plans should block the landing-page implementation.