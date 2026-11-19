import { expect, test } from '@playwright/test';
import summaries from '../../src/data/postSummaries.json';

const cohort = [
  'what-is-parenting-coordination',
  'parenting-coordination-vs-mediation',
  'divorced-parents-communication',
  'parenting-time-holidays-after-divorce',
  'can-one-parent-start-parenting-coordination',
];
const cards = 'main article';
const mixedLabel = 'תצוגה מגוונת לפי נושאים. תאריכי הפרסום המקוריים נשמרים.';
const visibleSlugs = (page: import('@playwright/test').Page) =>
  page.locator('main article h2 a').evaluateAll((links) =>
    links.map((element) => element.getAttribute('href')?.split('/').pop() ?? ''),
  );

test('blog homepage staggers coordination articles while retaining true dates and financial archive slots', async ({ page }) => {
  await page.goto('/blog');
  await expect(page.getByRole('heading', { name: 'מאמרים וקריאה מעשירה', level: 1 })).toBeVisible();
  await expect(page.getByText(mixedLabel)).toBeVisible();
  const slugs = await visibleSlugs(page);
  expect(new Set(slugs).size).toBe(slugs.length);
  // Every newly published article must appear once in the actual rendered blog.
  expect([...slugs].sort()).toEqual(summaries.map((post) => post.id).sort());

  const positions = cohort.map((slug) => slugs.indexOf(slug));
  expect(positions.every((position) => position >= 0)).toBe(true);
  for (let index = 1; index < positions.length; index += 1) {
    expect(positions[index] - positions[index - 1]).toBeGreaterThanOrEqual(4);
  }
  const allTopicIds = summaries.filter((post) => post.category === 'תיאום הורי').map((post) => post.id);
  const allTopicPositions = slugs.flatMap((slug, index) => allTopicIds.includes(slug) ? [index] : []);
  expect(allTopicPositions).toHaveLength(allTopicIds.length);
  for (let index = 1; index < allTopicPositions.length; index += 1) {
    expect(allTopicPositions[index] - allTopicPositions[index - 1]).toBeGreaterThanOrEqual(4);
  }
  for (const slug of cohort) {
    const card = page.locator(cards).filter({ has: page.locator(`h2 a[href="/blog/${slug}"]`) });
    await expect(card.locator('time')).toHaveAttribute('datetime', '2026-11-12');
  }

  const finance = page.locator(cards).filter({ has: page.locator('h2 a[href="/blog/financial-secrecy-couples"]') });
  await expect(finance.locator('time')).toHaveAttribute('datetime', '2026-11-17');
  await expect(finance.locator('[data-editorial-archive-slot]')).toHaveAttribute('data-editorial-archive-slot', '2026-11-07');
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', 'https://kesher.saharoni.com/blog');
});

test('topic filters and search are not editorially shuffled; mobile has no overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/blog');
  await expect(page.getByText(mixedLabel)).toBeVisible();

  const dims = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    viewport: document.documentElement.clientWidth,
  }));
  expect(dims.scroll).toBeLessThanOrEqual(dims.viewport);

  await page.getByRole('tab', { name: 'תיאום הורי', exact: true }).click();
  const topicSlugs = await visibleSlugs(page);
  expect(topicSlugs.length).toBeGreaterThanOrEqual(cohort.length);
  // New topic guides may be added, but the original five and their relative order remain.
  const originalOrder = topicSlugs.filter((slug) => cohort.includes(slug));
  expect(originalOrder).toEqual(cohort);
  await expect(page.getByText(mixedLabel)).toHaveCount(0);

  await page.getByRole('tab', { name: 'כלכלת המשפחה', exact: true }).click();
  expect((await visibleSlugs(page)).length).toBeGreaterThanOrEqual(17);
  expect(await page.locator('[data-editorial-archive-slot]').count()).toBeGreaterThanOrEqual(17);
  await expect(page.getByText(mixedLabel)).toHaveCount(0);

  await page.getByRole('button', { name: 'איפוס סינונים' }).click();
  await page.getByRole('textbox', { name: 'חיפוש מאמרים' }).fill('תיאום הורי');
  await expect(page.locator(cards).first()).toBeVisible();
  await expect(page.getByText(mixedLabel)).toHaveCount(0);
  const searchSlugs = await visibleSlugs(page);
  expect(searchSlugs.length).toBeGreaterThanOrEqual(2);
  expect(searchSlugs).toContain(cohort[0]);
  expect(new Set(searchSlugs).size).toBe(searchSlugs.length);
});
