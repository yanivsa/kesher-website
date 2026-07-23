import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const routes = [
  '/',
  '/about',
  '/services/couples',
  '/services/parenting',
  '/services/mediation',
  '/services/gifted-parenting',
  '/services/aliyah-families',
  '/blog',
  '/faq',
  '/contact',
];

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

test('AI chat is desktop-only and consent gated', async ({ page }, testInfo) => {
  await page.goto('/');
  await expect(page.locator('script[data-kesher-ai-chat]')).toHaveCount(0);
  const consentButton = page.getByRole('button', { name: 'הפעלת צ\'אט עם עוזרת AI חיצונית' });

  if (testInfo.project.name === 'mobile') {
    await expect(consentButton).toBeHidden();
  } else {
    await expect(consentButton).toBeVisible();
  }
});

test('gifted framework links reach the dedicated section', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'הכנה לכניסה למסגרת מחוננים' }).click();
  await expect(page).toHaveURL(/\/services\/gifted-parenting#gifted-framework$/);
  await expect(page.locator('#gifted-framework')).toBeInViewport();
});
