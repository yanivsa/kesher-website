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
  await page.goto('http://localhost:4173/');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot-home.png', fullPage: true });

  // Test "/services/couples"
  await page.goto('http://localhost:4173/services/couples');
  await page.waitForLoadState('networkidle');
  await page.screenshot({ path: 'screenshot-couples.png', fullPage: true });

  await browser.close();
})();
