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
  '/services/late-singleness',
  '/services/finding-relationship',
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
  const consentButton = page.locator('button.ai-chat-consent');

  if (testInfo.project.name === 'mobile') {
    await expect(consentButton).toHaveCount(0);
  } else {
    await expect(consentButton).toHaveCount(1);
    await expect(consentButton).toBeVisible();
  }
});

test('mobile menu has an obvious close action and supports Escape', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');

  await page.getByRole('button', { name: 'פתיחת תפריט' }).click();
  await expect(page.getByRole('button', { name: 'סגירת תפריט', exact: true })).toBeVisible();
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');

  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'פתיחת תפריט' })).toBeFocused();
  await expect(page.getByRole('button', { name: 'סגירת תפריט', exact: true })).toHaveCount(0);

  await page.getByRole('button', { name: 'פתיחת תפריט' }).click();
  await page.getByRole('button', { name: 'סגירת התפריט בלחיצה מחוץ לתפריט' })
    .click({ position: { x: 10, y: 400 } });
  await expect(page.getByRole('button', { name: 'פתיחת תפריט' })).toBeVisible();
});

test('appointment page embeds Shira Calendly and keeps a direct fallback', async ({ page }) => {
  await page.goto('/appointment');
  await expect(page.getByRole('heading', { name: 'קביעת פגישת ייעוץ עם שירה' })).toBeVisible();
  await expect(page.locator('meta[name="description"]')).toHaveCount(1);
  await expect(page.locator('link[rel="canonical"]')).toHaveCount(1);
  const width = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(width.scrollWidth).toBe(width.clientWidth);
  const results = await new AxeBuilder({ page }).exclude('iframe').analyze();
  expect(results.violations.filter((violation) => ['critical', 'serious'].includes(violation.impact || ''))).toEqual([]);
  await expect(page.locator('iframe[title="לוח זמנים לקביעת פגישת ייעוץ עם שירה סהרוני"]'))
    .toHaveAttribute('src', 'https://calendly.com/shira-saharoni/50');
  await expect(page.getByRole('link', { name: 'פתחו את Calendly בחלון חדש' }))
    .toHaveAttribute('href', 'https://calendly.com/shira-saharoni/50');
});

test('gifted framework links reach the dedicated section', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'הכנה לכניסה למסגרת מחוננים' }).click();
  await expect(page).toHaveURL(/\/services\/gifted-parenting#gifted-framework$/);
  await expect(page.locator('#gifted-framework')).toBeInViewport();
});

test('legacy singles guidance route redirects to the late singleness page', async ({ page }) => {
  await page.goto('/services/singles-guidance');
  await expect(page).toHaveURL(/\/services\/late-singleness$/);
  await expect(page.getByRole('heading', { name: 'ייעוץ במצבי רווקות מאוחרת' })).toBeVisible();
});

test('the two singles guidance pages link to each other', async ({ page }) => {
  await page.goto('/services/late-singleness');
  await page.getByRole('link', { name: 'ליווי מעשי למציאת זוגיות' }).click();
  await expect(page).toHaveURL(/\/services\/finding-relationship$/);
  await expect(page.getByRole('heading', { name: 'ליווי למציאת זוגיות' })).toBeVisible();
});
