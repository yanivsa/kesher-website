const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const routes = [
    '/',
    '/services/couples',
    '/services/parenting',
    '/services/mediation',
    '/blog',
    '/faq',
    '/contact'
  ];

  const widths = [360, 390, 430];
  let hasIssues = false;

  for (const route of routes) {
    for (const width of widths) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto(`http://localhost:5173${route}`);
      // Wait for network idle or a short timeout
      await page.waitForTimeout(500);

      const dims = await page.evaluate(() => {
        return {
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          bodyScrollWidth: document.body.scrollWidth,
          windowInnerWidth: window.innerWidth
        };
      });

      if (dims.scrollWidth > dims.windowInnerWidth) {
        console.log(`[OVERFLOW] Route: ${route} at width ${width}px -> scrollWidth: ${dims.scrollWidth}, innerWidth: ${dims.windowInnerWidth}`);
        hasIssues = true;
      }
    }
  }

  if (!hasIssues) {
    console.log("No horizontal overflow detected.");
  }

  await browser.close();
})();
