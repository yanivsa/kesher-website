import { expect, test } from '@playwright/test';
import postSummaries from '../../src/data/postSummaries.json';

const selector = 'main article[data-blog-post-id]';
const originalIds = postSummaries.map((post) => post.id);
const orderForCategory = (category: string) =>
  postSummaries.filter((post) => post.category === category).map((post) => post.id);

const cardIds = (page: import('@playwright/test').Page) =>
  page.locator(selector).evaluateAll((cards) => cards.map((card) => card.getAttribute('data-blog-post-id')));

test('default overview disperses batch-created topics and retains authentic publication dates', async ({ page }) => {
  await page.goto('/blog');
  await expect(page.getByRole('heading', { level: 1, name: 'מאמרים וקריאה מעשירה' })).toBeVisible();
  await expect(page.getByText('המאמרים משולבים לפי נושאים. תאריכי הפרסום המקוריים נשמרים.')).toBeVisible();
  await expect(page.locator(selector).first()).toBeVisible();

  const ids = await cardIds(page);
  expect(ids).toHaveLength(originalIds.length);
  expect(new Set(ids).size).toBe(ids.length);
  expect([...ids].sort()).toEqual([...originalIds].sort());

  const financialPositions = ids.flatMap((slug, index) =>
    orderForCategory('כלכלת המשפחה').includes(slug || '') ? [index] : []);
  const coordinationPositions = ids.flatMap((slug, index) =>
    orderForCategory('תיאום הורי').includes(slug || '') ? [index] : []);

  expect(financialPositions).toHaveLength(17);
  expect(coordinationPositions).toHaveLength(5);
  expect(coordinationPositions[4] - coordinationPositions[0]).toBeGreaterThanOrEqual(8);

  const firstArticle = page.locator(selector).first();
  const firstSlug = await firstArticle.getAttribute('data-blog-post-id');
  const source = postSummaries.find((post) => post.id === firstSlug);
  expect(source).toBeDefined();
  await expect(firstArticle.locator('time')).toHaveAttribute('datetime', source!.date);
});

test('topic tabs and search remain in normal chronological order, including mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/blog');
  await expect(page.locator(selector).first()).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);

  const dims = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(dims.scrollWidth).toBeLessThanOrEqual(dims.clientWidth);

  await page.getByRole('tab', { name: 'תיאום הורי', exact: true }).click();
  await expect(page.locator(selector)).toHaveCount(5);
  expect(await cardIds(page)).toEqual(orderForCategory('תיאום הורי'));
  await expect(page.getByText('המאמרים משולבים לפי נושאים. תאריכי הפרסום המקוריים נשמרים.')).toHaveCount(0);

  await page.getByRole('tab', { name: 'כלכלת המשפחה', exact: true }).click();
  await expect(page.locator(selector)).toHaveCount(17);
  expect(await cardIds(page)).toEqual(orderForCategory('כלכלת המשפחה'));

  await page.getByRole('button', { name: 'איפוס סינונים' }).click();
  await page.getByRole('textbox', { name: 'חיפוש מאמרים' }).fill('תיאום הורי');
  await expect(page.locator(selector).first()).toBeVisible();
  await expect(page.getByText('המאמרים משולבים לפי נושאים. תאריכי הפרסום המקוריים נשמרים.')).toHaveCount(0);
  const expectedSearchIds = postSummaries
    .filter((post) => post.title.includes('תיאום הורי') || post.excerpt.includes('תיאום הורי'))
    .map((post) => post.id);
  expect(await cardIds(page)).toEqual(expectedSearchIds);

  await page.getByRole('button', { name: 'איפוס סינונים' }).click();
  await expect(page.locator(selector)).toHaveCount(originalIds.length);
  await expect(page.getByText('המאמרים משולבים לפי נושאים. תאריכי הפרסום המקוריים נשמרים.')).toBeVisible();
});
