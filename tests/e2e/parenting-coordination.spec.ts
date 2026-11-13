import { expect, test } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const articleIds = [
  'what-is-parenting-coordination',
  'parenting-coordination-vs-mediation',
  'divorced-parents-communication',
  'parenting-time-holidays-after-divorce',
  'can-one-parent-start-parenting-coordination',
];
const origin = 'https://kesher.saharoni.com';
const inquiry = '/contact?service=parenting_coordination';

const showStickyAfterScroll = async (page: import('@playwright/test').Page) => {
  // The page is prerendered, so its H1 can be present before client-side effects attach.
  await expect.poll(async () => {
    await page.evaluate(() => {
      window.scrollTo(0, 650);
      window.dispatchEvent(new Event('scroll'));
    });
    return page.locator('div[class*="stickyBar"]').isVisible();
  }, { timeout: 15_000 }).toBe(true);
};

test('service page and editorial hub are indexable, linked and responsive', async ({ page }) => {
  for (const route of ['/services/parenting-coordination', '/blog/category/parenting-coordination']) {
    const response = await page.goto(route);
    expect(response?.status()).toBe(200);
    await expect(page.locator('h1')).toHaveCount(1);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', origin + route);
    await expect(page.locator('meta[name="description"]')).toHaveCount(1);
    await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
    const sizes = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      available: document.documentElement.clientWidth,
    }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.available);
  }
  await expect(page.locator('section[aria-label="מאמרים בנושא תיאום הורי"] article')).toHaveCount(5);
  // JSON-LD can mount after visible cards during client hydration on slower mobile CI.
  // Poll for the same required CollectionPage schema rather than racing its insertion.
  await expect.poll(async () => (
    await page.locator('script[type="application/ld+json"]').allTextContents()
  ).join('\n'), { timeout: 15_000 }).toContain('CollectionPage');
  for (const slug of articleIds) {
    await expect(page.locator('section[aria-label="מאמרים בנושא תיאום הורי"] a[href="/blog/' + slug + '"]').first()).toBeVisible();
  }
});

test('all five articles render with an accessible intake CTA, not a direct booking CTA', async ({ page }) => {
  for (const slug of articleIds) {
    const route = '/blog/' + slug;
    const response = await page.goto(route);
    expect(response?.status()).toBe(200);
    await expect(page.locator('h1')).toHaveCount(1);
    await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', origin + route);
    await expect(page.locator('meta[name="description"]')).toHaveCount(1);
    const jsonLd = await page.locator('script[type="application/ld+json"]').allTextContents();
    const schemas = jsonLd.flatMap((raw) => {
      const data = JSON.parse(raw);
      return Array.isArray(data['@graph']) ? data['@graph'] : [data];
    });
    const articleSchema = schemas.find((item) => item['@type'] === 'Article');
    const breadcrumbSchema = schemas.find((item) => item['@type'] === 'BreadcrumbList');
    expect(articleSchema?.isPartOf?.['@id']).toBe(origin + '/blog/category/parenting-coordination#webpage');
    expect(articleSchema?.about?.name).toBe('תיאום הורי');
    expect(breadcrumbSchema?.itemListElement?.map((item: { position: number }) => item.position)).toEqual([1, 2, 3, 4]);
    expect(breadcrumbSchema?.itemListElement?.[2]?.item).toBe(origin + '/blog/category/parenting-coordination');
    await expect(page.locator('a[href="/blog/category/parenting-coordination"]').first()).toBeVisible();
    const heroImage = page.locator('img[data-kesher-article-hero]');
    await expect(heroImage).toBeVisible();
    await expect.poll(() => heroImage.evaluate((image) => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    const cta = page.getByRole('region', { name: 'פנייה לשירה סהרוני' });
    await expect(cta).toBeVisible();
    await expect(cta.getByRole('link', { name: 'לבירור התאמה ראשוני עם שירה' })).toHaveAttribute('href', inquiry);
    await expect(page.locator('aside a[href="' + inquiry + '"]').first()).toBeVisible();
    await expect(cta.locator('a[href="/appointment"]')).toHaveCount(0);
    await expect(page.locator('header a[href="' + inquiry + '"]').first()).toHaveAttribute('href', inquiry);
    await expect(page.locator('footer a[href="' + inquiry + '"]').first()).toHaveAttribute('href', inquiry);
    const width = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      available: document.documentElement.clientWidth,
    }));
    expect(width.scroll).toBeLessThanOrEqual(width.available);
  }
});

test('contact inquiry is preselected and hides direct appointment booking', async ({ page }) => {
  await page.goto(inquiry);
  const form = page.locator('section#contact');
  await expect(form.locator('select[name="service"]')).toHaveValue('parenting_coordination');
  await expect(form).toContainText('נא לא למסור כאן פרטים רגישים');
  await expect(form.locator('textarea[name="message"]')).toHaveAttribute('placeholder', /ללא פרטי ילדים/);
  await expect(form.locator('a[href="/privacy"]')).toBeVisible();
  await expect(form).not.toContainText('דיסקרטיות מלאה');
  await expect(form.locator('a[href="/appointment"]')).toHaveCount(0);
  await expect(page.locator('header a[href="/appointment"]')).toHaveCount(0);
  await expect(page.locator('footer a[href="/appointment"]')).toHaveCount(0);
  await expect(page.locator('header a[href="' + inquiry + '"]')).toHaveCount(1);
  await expect(page.locator('footer a[href="' + inquiry + '"]')).toHaveCount(1);
  await expect(page.locator('a[aria-label="יצירת קשר בוואטסאפ"]')).toHaveAttribute('href', /%D7/);

  await page.goto('/contact');
  await expect(page.locator('header a[href="/appointment"]')).toHaveCount(1);
  await expect(page.locator('footer a[href="/appointment"]')).toHaveCount(1);
  await form.locator('select[name="service"]').selectOption('parenting_coordination');
  await expect(form).toContainText('נא לא למסור כאן פרטים רגישים');
  await expect(form.locator('a[href="/appointment"]')).toHaveCount(0);
});

test('mobile sticky conversion sends specialty readers to safe intake', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/blog/what-is-parenting-coordination');
  await expect(page.getByRole('heading', { level: 1, name: 'מה זה תיאום הורי ולמי הוא מתאים?' })).toBeVisible();
  await showStickyAfterScroll(page);
  const sticky = page.locator('div[class*="stickyBar"]');
  await expect(sticky).toBeVisible();
  await expect(sticky.getByRole('link', { name: 'בירור התאמה לתיאום הורי' })).toHaveAttribute('href', inquiry);

  await page.goto('/services/parenting');
  await expect(page.locator('h1')).toHaveCount(1);
  await showStickyAfterScroll(page);
  await expect(page.locator('div[class*="stickyBar"] a[href="/appointment"]')).toBeVisible();
  await expect(page.locator('footer a[href="/appointment"]')).toHaveCount(1);
});

test('new specialty pages have no serious accessibility violations', async ({ page }) => {
  for (const route of [
    '/services/parenting-coordination',
    '/blog/category/parenting-coordination',
    '/blog/what-is-parenting-coordination',
  ]) {
    await page.goto(route);
    await expect(page.locator('h1')).toHaveCount(1);
    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter((issue) => issue.impact === 'serious' || issue.impact === 'critical'),
      route,
    ).toEqual([]);
  }
});

test('topic cluster appears in the blog, the sitemap, RSS and AI-readable catalog', async ({ page, request }) => {
  const sources = ['/sitemap.xml', '/rss.xml', '/llms-full.txt'];
  for (const source of sources) {
    const response = await request.get(source);
    expect(response.status(), source).toBe(200);
    const text = await response.text();
    for (const slug of articleIds) {
      expect(text, source + ': ' + slug).toContain('/blog/' + slug);
    }
  }
  await page.goto('/blog');
  await expect(page.getByRole('link', { name: 'מדריכים בנושא תיאום הורי והורות לאחר פרידה' })).toHaveAttribute('href', '/blog/category/parenting-coordination');
  await expect(page.getByRole('tab', { name: 'תיאום הורי' })).toBeVisible();

  await page.goto('/parenting-guidance-divorce');
  await expect(page.locator('a[href="/services/parenting-coordination"]').first()).toBeVisible();
  await page.goto('/services/parenting');
  await expect(page.locator('a[href="/services/parenting-coordination"]').first()).toBeVisible();
});
