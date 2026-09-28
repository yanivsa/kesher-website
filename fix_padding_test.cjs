const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const viewports = [360, 390, 430];

  for (const width of viewports) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto('http://localhost:4173/', { waitUntil: 'networkidle' });

    const heroBoxes = await page.locator('[class*="heroWhatsapp"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));
    const dockBoxes = await page.locator('aside[class*="quickDock"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));

    if(heroBoxes.length && dockBoxes.length) {
      const heroBox = heroBoxes[0];
      const dockBox = dockBoxes[0];
      const overlapY = heroBox.y < dockBox.y + dockBox.height && heroBox.y + heroBox.height > dockBox.y;
      console.log(`[${width}px] Overlap with fix: ${overlapY}`);
    }
  }

  await browser.close();
})();
