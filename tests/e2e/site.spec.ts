import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const routes = ['/', '/about', '/services/couples', '/services/parenting', '/blog', '/faq', '/contact'];

for (const route of routes) {
  test(`${route} renders route metadata and accessible content`, async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error') errors.push(message.text());
    });
    await page.goto(route);
    await expect(page.locator('h1')).toHaveCount(1);
    await expect(page.locator('meta[name="description"]')).toHaveCount(1);
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
    const width = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(width.scrollWidth).toBe(width.clientWidth);
    const results = await new AxeBuilder({ page }).analyze();
    expect(results.violations.filter((violation) => ['critical', 'serious'].includes(violation.impact || ''))).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test('unknown routes render the noindex 404 page', async ({ page }) => {
  await page.goto('/definitely-not-a-real-page');
  await expect(page.getByRole('heading', { name: 'העמוד לא נמצא' })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow');
});

test('AI chat is consent gated', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('script[data-kesher-ai-chat]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'הפעלת צ\'אט עם עוזרת AI חיצונית' })).toBeVisible();
});
