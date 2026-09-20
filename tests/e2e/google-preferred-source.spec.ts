import { test, expect } from '@playwright/test';

test.describe('Google Preferred Source Integration', () => {
  test('uses one resilient Hebrew custom trigger on article pages', async ({ page }) => {
    await page.goto('/blog/child-after-school-restraint-collapse');

    const trigger = page.getByRole('button', { name: 'הוסיפו את שירה למקורות המועדפים' });
    await expect(trigger).toBeVisible();
    await trigger.focus();
    await expect(trigger).toBeFocused();

    // The standard auto-render widget is intentionally not used. Google documents
    // manual control for custom UI, which avoids duplicate buttons and remote badge assets.
    await expect(page.locator('div[google-add-preferred-source-btn]')).toHaveCount(0);

    const width = await page.evaluate(() => ({
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
    }));
    expect(width.scrollWidth).toBe(width.clientWidth);

    const scriptLocator = page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]');
    await expect(scriptLocator).toHaveCount(1);
    await expect(scriptLocator).toHaveAttribute('async', '');
    await expect(scriptLocator).toHaveAttribute('preferred-sources-control', 'manual');

    await page.locator('text="← חזרה לבלוג"').click();
    await page.waitForURL('**/blog');
    const scriptCountAfterNav = await page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scriptCountAfterNav).toBeLessThanOrEqual(1);

    await page.goto('/blog/relocation-couple-conversations-before-moving');
    await expect(page.getByRole('button', { name: 'הוסיפו את שירה למקורות המועדפים' })).toBeVisible();
    const scriptCountAfterSecondNav = await page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scriptCountAfterSecondNav).toBe(1);
  });

  test('does not inject the library on non-article pages on direct load', async ({ page }) => {
    await page.goto('/');
    const scripts = await page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scripts).toBe(0);
    await expect(page.getByRole('button', { name: 'הוסיפו את שירה למקורות המועדפים' })).toHaveCount(0);
  });
});
