import { expect, test } from '@playwright/test';
import financialPosts from '../../src/data/financialGuidancePosts.json';

const origin = 'https://kesher.saharoni.com';
const service = '/services/family-financial-guidance';
const hub = '/blog/category/family-finances';
const ppc = ['/financial-guidance-couples', '/family-budget-guidance'];
const editorialRoutes = [
  service, hub,
  ...financialPosts.map(({ id }) => '/blog/' + id),
  '/blog/money-fights-communication',
  '/blog/marriage-preparation-money-fights',
  '/blog/marriage-prep-financial-expectations-2026-08-24',
];

test.describe('Financial guidance release acceptance', () => {
  test('all 22 indexable routes are statically rendered with exactly one H1 and canonical', async ({ request }) => {
    test.setTimeout(120_000);
    expect(editorialRoutes).toHaveLength(22);
    for (const route of editorialRoutes) {
      const response = await request.get(route);
      expect(response.status(), route).toBe(200);
      const html = await response.text();
      expect((html.match(/<h1(?:\s|>)/gi) || []).length, route).toBe(1);
      expect((html.match(/<meta name="description"/g) || []).length, route).toBe(1);
      expect((html.match(/rel="canonical"/g) || []).length, route).toBe(1);
      expect(html, route).toContain('href="' + origin + route + '"');
      expect(html, route).toContain('application/ld+json');
      expect(html, route).not.toMatch(/<meta name="robots" content="noindex/i);
      expect(html, route).toContain('dir="rtl"');
    }
  });

  test('PPC landings are reachable, uniquely named and excluded from indexing', async ({ request }) => {
    for (const route of ppc) {
      const response = await request.get(route);
      expect(response.status(), route).toBe(200);
      const html = await response.text();
      expect(html, route).toContain('content="noindex, follow"');
      expect(html, route).toContain('href="' + origin + route + '"');
      expect(html, route).toContain('/appointment?service=family-financial-guidance');
      expect(html, route).toContain('application/ld+json');
    }
  });

  test('service, hub and financial conversion links render in the SPA', async ({ page }) => {
    await page.goto(service, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1 })).toContainText('ליווי כלכלי');
    await expect(page.getByRole('link', { name: 'לקריאת מאמרים וכלים' })).toHaveAttribute('href', hub);
    await expect(page.locator('a[href="/appointment?service=family-financial-guidance"]').first()).toBeVisible();
    await page.goto(hub, { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1 })).toContainText('כלכלת המשפחה');
    await expect(page.locator('a[href="/blog/financial-secrecy-couples"]').first()).toBeVisible();
  });

  test('appointment and contact preserve financial service selection without submitting', async ({ page }) => {
    await page.goto('/appointment?service=family-financial-guidance', { waitUntil: 'domcontentloaded' });
    await expect(page.getByRole('heading', { level: 1 })).toContainText('ליווי כלכלי');
    await page.goto('/contact?service=family-financial-guidance', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('select[name="service"]')).toHaveValue('family-financial-guidance');
    await expect(page.locator('textarea[name="message"]')).toHaveAttribute('placeholder', /ללא מספרים או נתונים פיננסיים רגישים/);
  });

  test('both free worksheets and every finance image are served as files, not SPA fallbacks', async ({ request }) => {
    const worksheet = await request.get('/downloads/financial/money-conversation-worksheet.html');
    expect(worksheet.status()).toBe(200);
    const html = await worksheet.text();
    expect(html).toContain('שיחת הכסף הזוגית');
    expect(html).not.toContain('onclick=');
    const csvResponse = await request.get('/downloads/financial/family-budget-template.csv');
    expect(csvResponse.status()).toBe(200);
    const csv = (await csvResponse.text()).replace(/^\uFEFF/, '');
    expect(csv).toContain('sep=;');
    expect(csv).toContain('=SUM(C2:C4)');
    expect(csv).toContain('=SUM(C5:C13)');
    expect(csv).toContain('=C14-C15');
    for (const post of financialPosts) {
      const image = await request.get(post.image);
      expect(image.status(), post.image).toBe(200);
      const svg = await image.text();
      expect(svg, post.image).toContain('<svg');
    }
  });

  test('sitemap lists finance content, excludes PPC; robots allow search crawlers', async ({ request }) => {
    const sitemapResponse = await request.get('/sitemap.xml');
    expect(sitemapResponse.status()).toBe(200);
    const sitemap = await sitemapResponse.text();
    expect(sitemap).toContain(origin + service);
    expect(sitemap).toContain(origin + hub);
    expect(sitemap).toContain(origin + '/blog/financial-secrecy-couples');
    for (const route of ppc) expect(sitemap).not.toContain(origin + route);
    const robots = await request.get('/robots.txt');
    expect(robots.status()).toBe(200);
    expect(await robots.text()).toContain('OAI-SearchBot');
  });

  test('narrow viewports have no page-level horizontal overflow', async ({ page, isMobile }) => {
    test.skip(!isMobile, 'Mobile-only overflow assertion; desktop project covers navigation and content.');
    test.setTimeout(120_000);
    for (const route of [service, hub, ...ppc, '/blog/financial-secrecy-couples']) {
      await page.goto(route, { waitUntil: 'domcontentloaded' });
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      const widths = await page.evaluate(() => ({
        viewport: window.innerWidth, root: document.documentElement.scrollWidth,
      }));
      expect(widths.root - widths.viewport, route + ' should not cause horizontal scrolling').toBeLessThanOrEqual(3);
    }
  });
});
