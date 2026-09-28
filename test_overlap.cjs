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

    // Evaluate if .heroWhatsapp exists
    const hasHeroWhatsapp = await page.locator('.heroWhatsapp').count() > 0;

    // Note: the mobile dock uses MobileStickyBar instead of .quickDock inside Home.module.css sometimes
    const hasMobileStickyBar = await page.locator('[class*="stickyBar"]').count() > 0;

    console.log(`hasHeroWhatsapp: ${hasHeroWhatsapp}`);
    console.log(`hasMobileStickyBar: ${hasMobileStickyBar}`);

    if (hasHeroWhatsapp && hasMobileStickyBar) {
      const heroBox = await page.locator('.heroWhatsapp').boundingBox();
      const stickyBox = await page.locator('[class*="stickyBar"]').first().boundingBox();

      console.log('HeroWhatsapp box:', heroBox);
      console.log('MobileStickyBar box:', stickyBox);

      if (heroBox && stickyBox) {
        const overlapX = heroBox.x < stickyBox.x + stickyBox.width && heroBox.x + heroBox.width > stickyBox.x;
        const overlapY = heroBox.y < stickyBox.y + stickyBox.height && heroBox.y + heroBox.height > stickyBox.y;

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
