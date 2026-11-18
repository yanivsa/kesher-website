import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';

const financialPosts = JSON.parse(
  readFileSync(new URL('../../src/data/financialGuidancePosts.json', import.meta.url), 'utf8'),
) as { id: string; image: string }[];

const archiveSlots = JSON.parse(
  readFileSync(new URL('../../src/data/financialGuidanceArchiveSlots.json', import.meta.url), 'utf8'),
) as Record<string, string>;

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

  test('editorial archive uses 17 vacant dates and retains genuine publication metadata', async ({ page, request }) => {
    const ids = financialPosts.map(post => post.id);
    expect(Object.keys(archiveSlots).sort()).toEqual([...ids].sort());
    expect(new Set(Object.values(archiveSlots)).size).toBe(17);
    const readPosts = (file: string) => JSON.parse(
      readFileSync(new URL('../../src/data/' + file, import.meta.url), 'utf8'),
    ) as { id: string; date: string; updatedAt?: string }[];
    const original = readPosts('financialGuidancePosts.json');
    const occupied = new Set([
      ...readPosts('posts.json'), ...readPosts('postsRecent.json'),
      ...readPosts('parentingCoordinationPosts.json'), ...readPosts('giftedParentPosts.json'),
      ...readPosts('giftedParentPostsWave2.json'),
    ].map(post => post.date));
    occupied.add('2026-10-24'); // manualPostsOct2026.ts
    for (const post of original) {
      const slot = archiveSlots[post.id];
      expect(slot, post.id).toMatch(/^2026-\d{2}-\d{2}$/);
      expect(slot < post.date, post.id).toBeTruthy();
      expect(occupied.has(slot), 'occupied: ' + slot).toBeFalsy();
      expect(post.date).toBe('2026-11-17');
      expect(post.updatedAt).toBe('2026-11-17');
    }
    await page.goto('/blog', { waitUntil: 'domcontentloaded' });
    await page.getByRole('tab', { name: 'כלכלת המשפחה', exact: true }).click();
    const cards = page.locator('article');
    await expect(cards).toHaveCount(17);
    const links = await cards.locator('h2 a').evaluateAll(items =>
      items.map(node => node.getAttribute('href')?.split('/').pop()),
    );
    expect(links).toEqual([...ids].sort((a, b) => archiveSlots[b].localeCompare(archiveSlots[a])));
    for (const post of original) {
      const card = cards.filter({ has: page.locator('h2 a[href="/blog/' + post.id + '"]') });
      await expect(card.locator('time')).toHaveAttribute('datetime', '2026-11-17');
      await expect(card.locator('[data-editorial-archive-slot]'))
        .toHaveAttribute('data-editorial-archive-slot', archiveSlots[post.id]);
      await expect(card).toContainText('מיקום בארכיון');
      await expect(card).toContainText('פורסם:');
    }
    const response = await request.get('/blog/' + ids[0]);
    expect(response.status()).toBe(200);
    const articleHtml = await response.text();
    expect(articleHtml).toMatch(/"datePublished":"2026-11-17"/);
    expect(articleHtml).toContain('data-kesher-article-date="2026-11-17"');
    expect(articleHtml).not.toContain('data-editorial-archive-slot');
  });


  test('the organic hub organizes all 20 articles into four accessible topic sections', async ({ page }) => {
    await page.goto(hub, { waitUntil: 'domcontentloaded' });
    const topics = [
      ['finance-couples', 'כסף וזוגיות', 8],
      ['finance-budget', 'תקציב משפחתי', 6],
      ['finance-children', 'ילדים וכסף', 4],
      ['finance-transitions', 'מעברים משפחתיים', 2],
    ] as const;
    for (const [id, title, expectedCount] of topics) {
      await expect(page.locator('nav[aria-label="קפיצה לנושאים"] a[href="#' + id + '"]')).toBeVisible();
      await expect(page.locator('#' + id + ' h2')).toHaveText(title);
      await expect(page.locator('#' + id + ' article')).toHaveCount(expectedCount);
    }
    const uniqueLinks = await page.locator('section[id^="finance-"] article h3 a').evaluateAll(
      anchors => anchors.map(anchor => anchor.getAttribute('href')),
    );
    expect(uniqueLinks).toHaveLength(20);
    expect(new Set(uniqueLinks).size).toBe(20);
    await expect(page.locator('a[href="/downloads/financial/money-conversation-worksheet.html"]')).toBeVisible();
    await expect(page.locator('a[href="/downloads/financial/family-budget-template.csv"]')).toBeVisible();
    await page.locator('nav[aria-label="קפיצה לנושאים"] a[href="#finance-budget"]').click();
    await expect(page).toHaveURL(/#finance-budget$/);
  });

  test('the standalone homepage visibly features financial guidance and the article hub', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    const serviceLink = page.locator('a[href="/services/family-financial-guidance"]').first();
    await expect(serviceLink).toBeVisible();
    await expect(serviceLink).toContainText('ליווי כלכלי לזוגות ומשפחות');
    await expect(page.locator('a[href="/blog/category/family-finances"]').first()).toBeVisible();
    const businessSchema = await page.locator('script[type="application/ld+json"]').allTextContents();
    expect(businessSchema.join(' ')).toContain('חינוך פיננסי');
    expect(businessSchema.join(' ')).toContain('/services/family-financial-guidance');
  });

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
