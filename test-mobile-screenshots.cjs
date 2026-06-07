const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  if (!fs.existsSync('screenshots')) fs.mkdirSync('screenshots');

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 } // iPhone 12/13/14
  });

  const page = await context.newPage();
  const routes = [
    '/',
    '/services/couples',
    '/services/parenting',
    '/services/mediation',
    '/blog',
    '/faq',
    '/contact'
  ];

  for (const route of routes) {
    const url = `http://localhost:4173${route}`;
    await page.goto(url);
    await page.waitForTimeout(1000); // wait for animations
    const safeName = route === '/' ? 'home' : route.replace(/\//g, '-');
    await page.screenshot({ path: `screenshots/${safeName}.png`, fullPage: true });
    console.log(`Saved screenshot for ${route}`);
  }

  await browser.close();
})();
