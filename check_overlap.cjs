const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Test multiple viewports
  const viewports = [360, 390, 430];

  for (const width of viewports) {
    console.log(`\n--- Viewport: ${width}px ---`);
    await page.setViewportSize({ width, height: 800 });
    await page.goto('http://localhost:4173/', { waitUntil: 'networkidle' });

    const hasHeroWhatsapp = await page.locator('.heroWhatsapp').count() > 0;
    const hasQuickDock = await page.locator('.quickDock').count() > 0;

    console.log(`hasHeroWhatsapp: ${hasHeroWhatsapp}`);
    console.log(`hasQuickDock: ${hasQuickDock}`);

    if (hasHeroWhatsapp && hasQuickDock) {
      const heroBox = await page.locator('.heroWhatsapp').boundingBox();
      const dockBox = await page.locator('.quickDock').boundingBox();

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

  await browser.close();
})();
