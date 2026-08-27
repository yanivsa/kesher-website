import { test, expect } from '@playwright/test';

test.describe('Google Preferred Source Integration', () => {
  test('renders the Google Preferred Source widget and fallback on article pages', async ({ page }) => {
    // Navigate to a known article page
    await page.goto('/blog/child-after-school-restraint-collapse');

    // Verify custom element is in DOM
    const widget = page.locator('google-add-preferred-source-btn');
    await expect(widget).toBeAttached();
    await expect(widget).toHaveAttribute('data-lang', 'he');

    // Verify fallback link is present and correct
    const fallbackLink = page.locator('a[href="https://www.google.com/preferences/source?q=kesher.saharoni.com"]');
    await expect(fallbackLink).toHaveCount(1); // One in .jsFallback (noscript is not parsed by playwright locator usually)

    // Verify script is injected once
    const scripts = await page.locator('script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scripts).toBe(1);

    // Verify it doesn't duplicate script on SPA navigation
    await page.locator('text="← חזרה לבלוג"').click();
    await page.waitForURL('**/blog');

    // Check script count is still exactly 1 or 0 (if it was removed, though it usually stays attached to document body)
    const scriptCountAfterNav = await page.locator('script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scriptCountAfterNav).toBeLessThanOrEqual(1);

    // Go to another article, check again
    await page.goto('/blog/relocation-couple-conversations-before-moving');
    await page.waitForSelector('google-add-preferred-source-btn', { state: 'attached' });

    const scriptCountAfterSecondNav = await page.locator('script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scriptCountAfterSecondNav).toBe(1); // Still only 1 injected globally
  });

  test('does not inject script on non-article pages on direct load', async ({ page }) => {
    await page.goto('/');
    const scripts = await page.locator('script[src="https://news.google.com/swg/js/v1/publisher.js"]').count();
    expect(scripts).toBe(0);

    const widget = page.locator('google-add-preferred-source-btn');
    await expect(widget).toHaveCount(0);
  });
});
