import { expect, test } from '@playwright/test';

test('trusted Calendly scheduled event carries the real service context into thank-you analytics', async ({ page }) => {
  await page.goto('/appointment?utm_source=google&utm_medium=cpc&utm_campaign=general_booking', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[aria-label="לוח זמנים לקביעת פגישת ייעוץ עם שירה סהרוני"]')).toBeVisible({ timeout: 15_000 });

  await page.evaluate(() => {
    window.dispatchEvent(new MessageEvent('message', {
      origin: 'https://calendly.com',
      data: {
        event: 'calendly.event_scheduled',
        payload: {
          event: { uri: 'https://api.calendly.com/scheduled_events/e2e-general-booking' },
          invitee: { uri: 'https://api.calendly.com/scheduled_events/e2e-general-booking/invitees/1' },
        },
      },
    }));
  });

  await expect(page).toHaveURL(/\/thank-you-booked$/i, { timeout: 15_000 });

  await page.waitForFunction(() => Array.isArray(window.dataLayer)
    && window.dataLayer.some((event) => event.event === 'thank_you_view'), null, { timeout: 15_000 });

  const thankYouEvent = await page.evaluate(() => window.dataLayer.find(
    (event) => event.event === 'thank_you_view',
  ));
  expect(thankYouEvent).toMatchObject({
    page_type: 'thank_you_booked',
    service_type: 'general_consultation',
    booking_page_path: '/appointment',
    entry_page_path: '/appointment',
  });
  expect(thankYouEvent).not.toMatchObject({
    service_type: 'couples_counseling',
    service_region: 'ashdod',
  });
});

test('untrusted Calendly-shaped message cannot produce a booking conversion', async ({ page }) => {
  await page.goto('/appointment', { waitUntil: 'domcontentloaded' });
  await expect(page.locator('[aria-label="לוח זמנים לקביעת פגישת ייעוץ עם שירה סהרוני"]')).toBeVisible({ timeout: 15_000 });

  await page.evaluate(() => {
    window.dispatchEvent(new MessageEvent('message', {
      origin: 'https://attacker.example',
      data: {
        event: 'calendly.event_scheduled',
        payload: {
          event: { uri: 'https://api.calendly.com/scheduled_events/attacker-event' },
        },
      },
    }));
  });

  const bookingCount = await page.evaluate(() => window.dataLayer.filter(
    (event) => event.event === 'booking_confirmed',
  ).length);
  expect(bookingCount).toBe(0);
  await expect(page).toHaveURL(/\/appointment$/);
});
