import { test, expect } from '@playwright/test';

test.describe('Article contact CTA', () => {
  test('is the final article conversion block and uses contextual parenting copy', async ({ page }) => {
    await page.goto('/blog/child-after-school-restraint-collapse');

    const cta = page.getByRole('region', { name: 'פנייה לשירה סהרוני' });
    await expect(cta).toBeVisible();
    await expect(cta.getByRole('heading', { name: 'זה פוגש משהו שקורה אצלכם?' })).toBeVisible();
    await expect(cta).toContainText('לילד ולמשפחה');
    await expect(cta.getByRole('link', { name: 'לקביעת פגישה עם שירה' })).toBeVisible();
    await expect(cta.getByRole('link', { name: 'לכתיבה לשירה בוואטסאפ' })).toBeVisible();

    const mainText = await page.locator('article').innerText();
    const contextualIndex = mainText.lastIndexOf('זה פוגש משהו שקורה אצלכם?');
    expect(contextualIndex).toBeGreaterThan(mainText.lastIndexOf('המאמר מספק מידע כללי'));
    expect(contextualIndex).toBeGreaterThan(mainText.lastIndexOf('צריכים עזרה עם הנושא הזה?'));
  });

  test('uses relocation-specific copy when the article is about relocation', async ({ page }) => {
    await page.goto('/blog/relocation-couple-conversations-before-moving');
    const cta = page.getByRole('region', { name: 'פנייה לשירה סהרוני' });
    await expect(cta).toContainText('המעבר');
    await expect(cta).toContainText('הקשר');
  });
});
