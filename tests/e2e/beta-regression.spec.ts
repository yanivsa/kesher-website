import { expect, test } from '@playwright/test';

test.describe('Beta 4 Regression Tests', () => {
  test('Beta 4 page loads correctly on /b and contains branding', async ({ page }) => {
    // Navigate to the beta route
    await page.goto('/b');

    // Wait for the main heading or specific text to confirm it's loaded
    await expect(page.locator('h1')).toBeVisible();

    // Verify branding text exists
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.getByText('שירה סהרוני').first()).toBeVisible();
  });
});
