import { test, expect } from '@playwright/test';

test.describe('Google Preferred Source Integration', () => {
  test('renders the Google Preferred Source widget and fallback on article pages', async ({ page }) => {
    // Navigate to a known article page
    await page.goto('/blog/child-after-school-restraint-collapse');

    // Verify custom element is in DOM
    const widget = page.locator('div[google-add-preferred-source-btn]');
    await expect(widget).toBeAttached();
    await expect(widget).toHaveAttribute('data-lang', 'he');

    // Verify fallback link is present and correct
    const fallbackLink = page.locator('a[href="https://www.google.com/preferences/source?q=kesher.saharoni.com"]');
    await expect(fallbackLink.first()).toBeVisible();

    // Verify script is injected exactly once and in head
    const scriptLocator = page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]');
    await expect(scriptLocator).toHaveCount(1);
    await expect(scriptLocator).toHaveAttribute('async', '');
    await expect(scriptLocator).not.toHaveAttribute('preferred-sources-control', 'manual');

    // Verify it doesn't duplicate script on SPA navigation
    await page.locator('text="← חזרה לבלוג"').click();
    await page.waitForURL('**/blog');

    // Check script count is still exactly 1 or 0 (if it was removed, though it usually stays attached to document body)
    const scriptCountAfterNav = await page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scriptCountAfterNav).toBeLessThanOrEqual(1);

    // Go to another article, check again
    await page.goto('/blog/relocation-couple-conversations-before-moving');
    await page.waitForSelector('div[google-add-preferred-source-btn]', { state: 'attached' });

    const scriptCountAfterSecondNav = await page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scriptCountAfterSecondNav).toBe(1); // Still only 1 injected globally
  });

  test('does not inject script on non-article pages on direct load', async ({ page }) => {
    await page.goto('/');
    const scripts = await page.locator('head script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scripts).toBe(0);

    const widget = page.locator('div[google-add-preferred-source-btn]');
    await expect(widget).toHaveCount(0);
  });
});
