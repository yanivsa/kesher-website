const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  await page.setViewportSize({ width: 430, height: 800 });
  await page.goto('http://localhost:4173/', { waitUntil: 'networkidle' });

  // Inject some CSS to test a fix
  await page.addStyleTag({ content: `
    @media (max-width: 768px) {
      .Home_hero__0O4qX {
        padding-top: 5rem !important;
      }
    }
  `});

  const heroBoxes = await page.locator('[class*="heroWhatsapp"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));
  const dockBoxes = await page.locator('aside[class*="quickDock"]').evaluateAll(els => els.map(el => el.getBoundingClientRect()));

  const heroBox = heroBoxes[0];
  const dockBox = dockBoxes[0];

  console.log('HeroWhatsapp box:', heroBox);
  console.log('QuickDock box:', dockBox);

  const overlapX = heroBox.x < dockBox.x + dockBox.width && heroBox.x + heroBox.width > dockBox.x;
  const overlapY = heroBox.y < dockBox.y + dockBox.height && heroBox.y + heroBox.height > dockBox.y;

  console.log(`Overlap after fix: ${overlapX && overlapY}`);

  await browser.close();
})();
