const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto('http://localhost:4173/', { waitUntil: 'networkidle' });
  const heroBoxes = await page.locator('[class*="heroWhatsapp"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));
  const dockBoxes = await page.locator('aside[class*="quickDock"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));
  if (heroBoxes.length > 0 && dockBoxes.length > 0) {
    const heroBox = heroBoxes[0];
    const dockBox = dockBoxes[0];
    const overlapY = heroBox.y < dockBox.y + dockBox.height && heroBox.y + heroBox.height > dockBox.y;
    console.log(`Height 667px - Overlap Y: ${overlapY}`);
  }
  await browser.close();
})();
