import { expect, test } from '@playwright/test';

test('closing the cookie notice does not grant measurement consent', async ({ page }) => {
  await page.goto('/');

  const closeButton = page.getByRole('button', {
    name: 'סגירה והשארת cookies לא-חיוניים חסומים',
  });
  await expect(closeButton).toBeVisible();
  await closeButton.click();

  await expect(page.getByRole('button', { name: 'פתיחת הגדרות פרטיות ומדידה' })).toBeVisible();

  const privacyState = await page.evaluate(() => ({
    consent: localStorage.getItem('kesher_consent_v2'),
    dismissed: sessionStorage.getItem('kesher_consent_dismissed_v1'),
  }));

  expect(privacyState).toEqual({
    consent: null,
    dismissed: 'true',
  });

  await page.reload();
  await expect(page.getByRole('button', {
    name: 'סגירה והשארת cookies לא-חיוניים חסומים',
  })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'פתיחת הגדרות פרטיות ומדידה' })).toBeVisible();
});
