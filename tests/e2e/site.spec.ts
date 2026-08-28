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
  '/services/couples-aliyah-relocation',
  '/services/premarital-first-year',
  '/services/late-singleness',
  '/services/finding-relationship',
  '/couples-counseling-ashdod',
  '/blog',
  '/blog/child-after-school-restraint-collapse',
  '/blog/relocation-couple-conversations-before-moving',
  '/blog/premarital-questions-before-wedding',
  '/faq',
  '/contact',
  '/accessibility',
  '/privacy',
  '/terms',
];

for (const route of routes) {
  test(`${route} renders route metadata and accessible content`, async ({ page }) => {
    await page.route('https://news.google.com/**', route => route.fulfill({ status: 200, body: '' }));
    const errors: string[] = [];
    page.on('console', (message) => {
      if (message.type() === 'error' && !message.text().includes('requestStorageAccess')) {
        errors.push(message.text());
      }
    });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(route, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toHaveCount(1, { timeout: 15_000 });
    await expect(page.locator('meta[name="description"]')).toHaveCount(1, { timeout: 15_000 });
    await expect(page.locator('link[rel="canonical"]')).toHaveCount(1, { timeout: 15_000 });
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
  await page.route('https://news.google.com/**', route => route.fulfill({ status: 200, body: '' }));
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('/definitely-not-a-real-page');
  await expect(page.getByRole('heading', { name: 'העמוד לא נמצא' })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow');
  expect(errors).toEqual([]);
});

test('the promoted homepage is indexable and uses the standalone design', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /אפשר לבחור לבנות/ })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveCount(0);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    'href',
    'https://kesher.saharoni.com',
  );
  const structuredData = page.locator('script[type="application/ld+json"]');
  await expect(structuredData).toHaveCount(1);
  const schemaText = await structuredData.textContent();
  expect(schemaText).toContain('LocalBusiness');
  expect(schemaText).toContain('יועצת זוגית');
});

test('homepage mounts cleanly with reduced motion enabled', async ({ page }) => {
  await page.route('https://news.google.com/**', route => route.fulfill({ status: 200, body: '' }));
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /אפשר לבחור לבנות/ })).toBeVisible();
  expect(errors).toEqual([]);
});

test('the former beta route resolves to the primary homepage', async ({ page }) => {
  await page.goto('/b/');
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { name: /אפשר לבחור לבנות/ })).toBeVisible();
});

test('the promoted beta2 route resolves to the primary homepage', async ({ page }) => {
  await page.goto('/beta2/');
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('heading', { name: /אפשר לבחור לבנות/ })).toBeVisible();
});

test('unknown blog posts render the noindex 404 page', async ({ page }) => {
  await page.route('https://news.google.com/**', route => route.fulfill({ status: 200, body: '' }));
  const errors: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(message.text());
  });
  await page.goto('/blog/definitely-not-a-real-post');
  await expect(page.getByRole('heading', { name: 'העמוד לא נמצא' })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', 'noindex, nofollow');
  expect(errors).toEqual([]);
});

test('AI chat is desktop-only and consent gated', async ({ page }, testInfo) => {
  await page.goto('/about');
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
  await page.goto('/about');

  await page.getByRole('button', { name: 'פתיחת תפריט' }).click();
  await expect(page.getByRole('button', { name: 'סגירת תפריט', exact: true })).toBeVisible();
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');

  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'פתיחת תפריט' })).toBeFocused();
  await expect(page.getByRole('button', { name: 'סגירת תפריט', exact: true })).toHaveCount(0);

  await page.getByRole('button', { name: 'פתיחת תפריט' }).click();
  const closeButton = page.getByRole('button', { name: 'סגירת תפריט', exact: true });
  const appointmentLink = page.getByRole('navigation', { name: 'ניווט ראשי' })
    .getByRole('link', { name: 'לתיאום פגישה' });
  await appointmentLink.focus();
  await page.keyboard.press('Tab');
  await expect(closeButton).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(appointmentLink).toBeFocused();

  await page.getByRole('button', { name: 'סגירת התפריט בלחיצה מחוץ לתפריט' })
    .click({ position: { x: 10, y: 400 } });
  await expect(page.getByRole('button', { name: 'פתיחת תפריט' })).toBeVisible();
});

test('global search opens its first result with Enter and restores focus', async ({ page }) => {
  await page.goto('/about');
  const searchButton = page.getByRole('button', { name: 'חיפוש באתר' });
  await searchButton.click();
  const searchInput = page.getByRole('textbox', { name: 'חיפוש באתר' });
  await searchInput.fill('קביעת פגישת ייעוץ עם שירה');
  await searchInput.press('Enter');
  await expect(page).toHaveURL(/\/appointment$/);
  await expect(searchButton).toBeFocused();
});

test('appointment page uses the auto-resizing Calendly embed and keeps a direct fallback', async ({ page }) => {
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
  await expect(page.locator('[aria-label="לוח זמנים לקביעת פגישת ייעוץ עם שירה סהרוני"]'))
    .toBeVisible();
  await expect(page.locator('script[src="https://assets.calendly.com/assets/external/widget.js"]'))
    .toHaveCount(1);
  await expect(page.getByRole('link', { name: 'פתחו את Calendly בחלון חדש' }))
    .toHaveAttribute('href', 'https://calendly.com/shira-saharoni/50');
});

test('gifted framework anchor reaches the dedicated section', async ({ page }) => {
  await page.goto('/services/gifted-parenting#gifted-framework');
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

test('relocation and premarital service pages expose their practical article hubs', async ({ page }) => {
  await page.goto('/services/couples-aliyah-relocation');
  await expect(page.getByRole('heading', { name: 'ייעוץ זוגי לעולים ולזוגות ברילוקיישן' })).toBeVisible();
  await page.getByRole('link', { name: /7 שיחות שחייבים לעשות לפני שאורזים/ }).click();
  await expect(page).toHaveURL(/\/blog\/relocation-couple-conversations-before-moving$/);
  await expect(page.getByRole('link', { name: 'ייעוץ זוגי בעלייה וברילוקיישן' }))
    .toHaveAttribute('href', '/services/couples-aliyah-relocation');

  await page.goto('/services/premarital-first-year');
  await expect(page.getByRole('heading', { name: 'הכנה לנישואים וליווי בשנה הראשונה' })).toBeVisible();
  await page.getByRole('link', { name: /12 שאלות שחייבים לשאול לפני החתונה/ }).click();
  await expect(page).toHaveURL(/\/blog\/premarital-questions-before-wedding$/);
  await expect(page.getByRole('link', { name: 'פגישות הכנה לנישואים' }))
    .toHaveAttribute('href', '/services/premarital-first-year');
});

test('couples counseling Ashdod landing page uses the trackable Calendly embed and captures campaign context', async ({ page }) => {
  await page.goto('/couples-counseling-ashdod?gclid=test_gclid&utm_source=google&utm_campaign=ashdod_search');

  await expect(page.getByRole('heading', {
    name: 'כשהשיחות חוזרות שוב ושוב לאותו ריב — אפשר ללמוד לדבר אחרת',
    level: 1,
  })).toBeVisible();
  await expect(page.getByText('500 ₪').first()).toBeVisible();
  await expect(page.locator('[aria-label="לוח זמנים לקביעת פגישת ייעוץ זוגי באשדוד עם שירה סהרוני"]'))
    .toBeVisible();
  await expect(page.locator('script[src="https://assets.calendly.com/assets/external/widget.js"]'))
    .toHaveCount(1);

  const trackingState = await page.evaluate(() => ({
    source: sessionStorage.getItem('kesher_attr_utm_source'),
    campaign: sessionStorage.getItem('kesher_attr_utm_campaign'),
    googleClickPresent: sessionStorage.getItem('kesher_attr_google_click_id_present'),
    rawGclid: sessionStorage.getItem('kesher_gclid'),
    dataLayerHasView: Array.isArray(window.dataLayer) && window.dataLayer.some(
      (evt) => evt.event === 'landing_page_view' && evt.variant_id === 'A'
    ),
  }));
  expect(trackingState).toEqual({
    source: 'google',
    campaign: 'ashdod_search',
    googleClickPresent: 'true',
    rawGclid: null,
    dataLayerHasView: true,
  });

  await expect(page.getByText('94%')).not.toBeVisible();
  await expect(page.getByText('אבחון מהיר')).not.toBeVisible();
  await expect(page.getByText('ז׳ ו-נ׳')).not.toBeVisible();
  await expect(page.getByText('PLACEHOLDER')).not.toBeVisible();
});

test('PPC attribution survives home to appointment navigation without persisting raw click ids', async ({ page }) => {
  await page.goto('/?utm_source=google&utm_medium=cpc&utm_campaign=home_search&gclid=raw-click-id-should-not-be-stored');
  await page.waitForFunction(() => sessionStorage.getItem('kesher_attr_utm_campaign') === 'home_search');

  await page.goto('/appointment');
  const attribution = await page.evaluate(() => ({
    entry: sessionStorage.getItem('kesher_attr_entry_page_path'),
    source: sessionStorage.getItem('kesher_attr_utm_source'),
    medium: sessionStorage.getItem('kesher_attr_utm_medium'),
    campaign: sessionStorage.getItem('kesher_attr_utm_campaign'),
    clickPresent: sessionStorage.getItem('kesher_attr_google_click_id_present'),
    containsRawClickId: Object.keys(sessionStorage).some((key) =>
      String(sessionStorage.getItem(key)).includes('raw-click-id-should-not-be-stored')
    ),
  }));

  expect(attribution).toEqual({
    entry: '/',
    source: 'google',
    medium: 'cpc',
    campaign: 'home_search',
    clickPresent: 'true',
    containsRawClickId: false,
  });
});

test('privacy choice persists and updates the measurement state', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'אישור מדידה' })).toBeVisible();
  await page.getByRole('button', { name: 'אישור מדידה' }).click();
  await expect(page.getByRole('button', { name: 'פתיחת הגדרות פרטיות ומדידה' })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('kesher_consent_v2'))).toBe('granted');

  await page.reload();
  await expect(page.getByRole('button', { name: 'פתיחת הגדרות פרטיות ומדידה' })).toBeVisible();
  await page.getByRole('button', { name: 'פתיחת הגדרות פרטיות ומדידה' }).click();
  await page.getByRole('button', { name: 'המשך ללא cookies' }).click();
  expect(await page.evaluate(() => localStorage.getItem('kesher_consent_v2'))).toBe('denied');
});

test('copy variants A, B, and C render their respective H1 titles', async ({ page }) => {
  await page.goto('/couples-counseling-ashdod');
  await expect(page.getByRole('heading', {
    name: 'כשהשיחות חוזרות שוב ושוב לאותו ריב — אפשר ללמוד לדבר אחרת',
    level: 1,
  })).toBeVisible();

  await page.goto('/couples-counseling-ashdod?variant=B');
  await expect(page.getByRole('heading', {
    name: 'לעצור את מעגל הריבים, להבין מה קורה ביניכם ולבנות דרך אחרת לדבר',
    level: 1,
  })).toBeVisible();

  await page.goto('/couples-counseling-ashdod?variant=C');
  await expect(page.getByRole('heading', {
    name: 'גם כשכבר קשה לדבר בלי להיפגע — אפשר ליצור שיחה אחרת ביניכם',
    level: 1,
  })).toBeVisible();
});

test('thank-you pages render with noindex and standalone layout', async ({ page }) => {
  await page.goto('/thank-you-booked');
  await expect(page.getByRole('heading', { name: 'הפגישה נקבעה', level: 1 })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/);

  const bookedDataLayer = await page.evaluate(() => {
    return Array.isArray(window.dataLayer) && window.dataLayer.some((evt) => evt.event === 'thank_you_view');
  });
  expect(bookedDataLayer).toBe(true);

  await page.goto('/thank-you-contact');
  await expect(page.getByRole('heading', { name: 'הפנייה התקבלה', level: 1 })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute('content', /noindex/);

  const contactDataLayer = await page.evaluate(() => {
    return Array.isArray(window.dataLayer) && window.dataLayer.some((evt) => evt.event === 'thank_you_view');
  });
  expect(contactDataLayer).toBe(true);
});

test('Calendly postMessage event scheduled triggers one booking_confirmed event and deduplicates', async ({ page }) => {
  await page.goto('/couples-counseling-ashdod');
  await expect(page.locator('[aria-label="לוח זמנים לקביעת פגישת ייעוץ זוגי באשדוד עם שירה סהרוני"]')).toBeVisible();

  await page.evaluate(() => {
    window.location.assign = () => {};
    window.postMessage(
      {
        event: 'calendly.event_scheduled',
        payload: { event: { uri: 'test_uri_123' } },
      },
      '*',
    );
  });

  await page.waitForFunction(() => {
    return Array.isArray(window.dataLayer) && window.dataLayer.some((evt) => evt.event === 'booking_confirmed');
  });

  const bookingCount = await page.evaluate(() => {
    return window.dataLayer.filter((evt) => evt.event === 'booking_confirmed').length;
  });
  expect(bookingCount).toBe(1);

  await page.evaluate(() => {
    window.postMessage(
      {
        event: 'calendly.event_scheduled',
        payload: { event: { uri: 'test_uri_123' } },
      },
      '*',
    );
  });

  const newBookingCount = await page.evaluate(() => {
    return window.dataLayer.filter((evt) => evt.event === 'booking_confirmed').length;
  });
  expect(newBookingCount).toBe(1);
});

test('booking listener rejects Calendly-shaped messages from an untrusted origin', async ({ page }) => {
  await page.goto('/couples-counseling-ashdod');
  await page.evaluate(() => {
    window.dispatchEvent(new MessageEvent('message', {
      origin: 'https://attacker.example',
      data: {
        event: 'calendly.event_scheduled',
        payload: {
          event: { uri: 'https://api.calendly.com/scheduled_events/fake-event' },
        },
      },
    }));
  });

  const bookingCount = await page.evaluate(() =>
    window.dataLayer.filter((evt) => evt.event === 'booking_confirmed').length
  );
  expect(bookingCount).toBe(0);
});

test('couples crisis landing page (/services/couples/crisis) captures crisis intent and trackable embed', async ({ page }) => {
  await page.goto('/services/couples/crisis?gclid=test_crisis_gclid&utm_source=google&utm_campaign=crisis_search');

  await expect(page.getByRole('heading', { name: 'זוגיות במשבר? אפשר להתחיל משיחה אחת רגועה', level: 1 })).toBeVisible();
  await expect(page.getByText('500 ₪').first()).toBeVisible();
  await expect(page.locator('[aria-label="לוח זמנים לקביעת פגישת ייעוץ זוגי עם שירה סהרוני"]')).toBeVisible();

  const trackingState = await page.evaluate(() => ({
    source: sessionStorage.getItem('kesher_attr_utm_source'),
    campaign: sessionStorage.getItem('kesher_attr_utm_campaign'),
    googleClickPresent: sessionStorage.getItem('kesher_attr_google_click_id_present'),
    dataLayerHasView: Array.isArray(window.dataLayer) && window.dataLayer.some(
      (evt) => evt.event === 'landing_page_view' && evt.landing_page_type === 'crisis'
    ),
  }));

  expect(trackingState).toEqual({
    source: 'google',
    campaign: 'crisis_search',
    googleClickPresent: 'true',
    dataLayerHasView: true,
  });

  const whatsappLink = page.getByRole('link', { name: /WhatsApp/i }).first();
  await expect(whatsappLink).toHaveAttribute('href', /wa\.me/);
  // Ensure standalone layout: no global header navigation
  await expect(page.getByRole('navigation', { name: 'ניווט ראשי' })).toHaveCount(0);
});

test('couples before-separation landing page (/services/couples/before-separation) renders non-legal framing and trackable embed', async ({ page }) => {
  await page.goto('/services/couples/before-separation?gclid=test_sep_gclid&utm_source=google&utm_campaign=before_sep_search');

  await expect(page.getByRole('heading', { name: 'לפני שמקבלים החלטה כבדה – בירור זוגי רגוע וממוקד', level: 1 })).toBeVisible();
  await expect(page.getByText('500 ₪').first()).toBeVisible();
  await expect(page.locator('[aria-label="לוח זמנים לקביעת פגישת בירור וייעוץ זוגי עם שירה סהרוני"]')).toBeVisible();

  const trackingState = await page.evaluate(() => ({
    source: sessionStorage.getItem('kesher_attr_utm_source'),
    campaign: sessionStorage.getItem('kesher_attr_utm_campaign'),
    googleClickPresent: sessionStorage.getItem('kesher_attr_google_click_id_present'),
    dataLayerHasView: Array.isArray(window.dataLayer) && window.dataLayer.some(
      (evt) => evt.event === 'landing_page_view' && evt.landing_page_type === 'before_separation'
    ),
  }));

  expect(trackingState).toEqual({
    source: 'google',
    campaign: 'before_sep_search',
    googleClickPresent: 'true',
    dataLayerHasView: true,
  });

  // Verify non-legal disclaimer exists
  await expect(page.getByText('אינו מהווה ייעוץ משפטי').first()).toBeVisible();
  // Ensure standalone layout: no global header navigation
  await expect(page.getByRole('navigation', { name: 'ניווט ראשי' })).toHaveCount(0);
});
