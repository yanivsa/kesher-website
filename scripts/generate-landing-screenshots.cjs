const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

async function captureLandingScreenshots() {
  const browser = await chromium.launch();
  const outputDir = path.resolve(__dirname, '../public/images/landing-previews');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Base URL (assume local vite preview or live dev server if available, or file/dist)
  const baseUrl = process.env.TEST_URL || 'https://kesher.saharoni.com';

  const targets = [
    { name: 'variant_a_desktop', url: `${baseUrl}/couples-counseling-ashdod`, viewport: { width: 1440, height: 900 } },
    { name: 'variant_a_mobile', url: `${baseUrl}/couples-counseling-ashdod`, viewport: { width: 390, height: 844 } },
    { name: 'variant_b_desktop', url: `${baseUrl}/couples-counseling-ashdod?variant=B`, viewport: { width: 1440, height: 900 } },
    { name: 'variant_b_mobile', url: `${baseUrl}/couples-counseling-ashdod?variant=B`, viewport: { width: 390, height: 844 } },
    { name: 'variant_c_desktop', url: `${baseUrl}/couples-counseling-ashdod?variant=C`, viewport: { width: 1440, height: 900 } },
    { name: 'variant_c_mobile', url: `${baseUrl}/couples-counseling-ashdod?variant=C`, viewport: { width: 390, height: 844 } },
    { name: 'thank_you_booked_desktop', url: `${baseUrl}/thank-you-booked`, viewport: { width: 1440, height: 900 } },
    { name: 'thank_you_booked_mobile', url: `${baseUrl}/thank-you-booked`, viewport: { width: 390, height: 844 } },
    { name: 'thank_you_contact_desktop', url: `${baseUrl}/thank-you-contact`, viewport: { width: 1440, height: 900 } },
    { name: 'thank_you_contact_mobile', url: `${baseUrl}/thank-you-contact`, viewport: { width: 390, height: 844 } },
  ];

  for (const t of targets) {
    const page = await browser.newPage({ viewport: t.viewport });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(t.url, { waitUntil: 'networkidle' });
    const filePath = path.join(outputDir, `${t.name}.png`);
    await page.screenshot({ path: filePath, fullPage: true });
    console.log(`Captured: ${t.name}.png (${t.viewport.width}x${t.viewport.height})`);
    await page.close();
  }

  await browser.close();
}

captureLandingScreenshots().catch(console.error);
