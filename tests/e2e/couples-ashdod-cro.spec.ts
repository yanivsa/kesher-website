import { expect, test } from '@playwright/test';

const mobileWidths = [320, 375, 390, 430];
const desktopWidths = [1366, 1440, 1920];

for (const width of mobileWidths) {
  test(`couples Ashdod CRO landing is usable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto('/couples-counseling-ashdod');

    await expect(page.getByRole('heading', {
      name: 'כשהשיחות חוזרות שוב ושוב לאותו ריב — אפשר ללמוד לדבר אחרת',
      level: 1,
    })).toBeVisible();
    await expect(page.getByRole('button', { name: 'קביעת פגישה' }).first()).toBeInViewport();
    await expect(page.getByRole('link', { name: 'יש לי שאלה לפני שקובעים' }).first()).toBeVisible();

    const widthState = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(widthState.scrollWidth).toBe(widthState.clientWidth);
  });
}

for (const width of desktopWidths) {
  test(`couples Ashdod CRO landing has no horizontal overflow at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/couples-counseling-ashdod');

    await expect(page.getByRole('heading', {
      name: 'כשהשיחות חוזרות שוב ושוב לאותו ריב — אפשר ללמוד לדבר אחרת',
      level: 1,
    })).toBeVisible();

    const widthState = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(widthState.scrollWidth).toBe(widthState.clientWidth);
  });
}

test('FAQ interaction tracking stays aggregate and variant-aware', async ({ page }) => {
  await page.goto('/couples-counseling-ashdod?variant=B');

  const firstFaq = page.locator('details').first();
  await firstFaq.locator('summary').click();

  const faqEvent = await page.evaluate(() => {
    const events = Array.isArray(window.dataLayer) ? window.dataLayer : [];
    return events.find((event) => event.event === 'faq_interaction');
  });

  expect(faqEvent).toMatchObject({
    event: 'faq_interaction',
    faq_index: 0,
    variant_id: 'B',
    landing_page_path: '/couples-counseling-ashdod',
    landing_page_type: 'ashdod',
    service_type: 'couples_counseling',
  });
  expect(faqEvent).not.toHaveProperty('faq_question');
  expect(faqEvent).not.toHaveProperty('relationship_status');
  expect(faqEvent).not.toHaveProperty('audience');
});
