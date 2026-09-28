const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true
  });

  const page = await context.newPage();

  // Test "/"
  await page.goto('http://127.0.0.1:4173/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot-home.png', fullPage: true });

  // Test "/services/couples"
  await page.goto('http://127.0.0.1:4173/services/couples');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot-couples.png', fullPage: true });

  // Test "/services/parenting"
  await page.goto('http://127.0.0.1:4173/services/parenting');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot-parenting.png', fullPage: true });

  // Test "/faq"
  await page.goto('http://127.0.0.1:4173/faq');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot-faq.png', fullPage: true });

  // Test "/contact"
  await page.goto('http://127.0.0.1:4173/contact');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot-contact.png', fullPage: true });

  await browser.close();
})();
