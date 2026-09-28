const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const viewports = [360, 390, 430];

  for (const width of viewports) {
    console.log(`\n--- Viewport: ${width}px ---`);
    await page.setViewportSize({ width, height: 800 });
    await page.goto('http://localhost:4173/', { waitUntil: 'networkidle' });

    // Evaluate if .heroWhatsapp exists
    const hasHeroWhatsapp = await page.locator('[class*="heroWhatsapp"]').count() > 0;
    const hasQuickDock = await page.locator('[class*="quickDock"]').count() > 0;

    console.log(`hasHeroWhatsapp: ${hasHeroWhatsapp}`);
    console.log(`hasQuickDock: ${hasQuickDock}`);

    if (hasHeroWhatsapp && hasQuickDock) {
      // get the actual elements
      const heroBoxes = await page.locator('[class*="heroWhatsapp"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));
      const dockBoxes = await page.locator('aside[class*="quickDock"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));

      if (heroBoxes.length > 0 && dockBoxes.length > 0) {
        const heroBox = heroBoxes[0];
        const dockBox = dockBoxes[0];

        console.log('HeroWhatsapp box:', heroBox);
        console.log('QuickDock box:', dockBox);

        const overlapX = heroBox.x < dockBox.x + dockBox.width && heroBox.x + heroBox.width > dockBox.x;
        const overlapY = heroBox.y < dockBox.y + dockBox.height && heroBox.y + heroBox.height > dockBox.y;

        console.log(`Overlap X: ${overlapX}, Overlap Y: ${overlapY}`);
        if (overlapX && overlapY) {
          console.log('=> THEY INTERSECT!');
        } else {
          console.log('=> They do not intersect.');
        }
      }
    }
  }

  await browser.close();
})();
